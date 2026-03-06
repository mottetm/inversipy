"""Container implementation for dependency injection."""

import asyncio
import contextvars
import inspect
import types as types_mod
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional, Union, get_args, get_origin, get_type_hints

from .binding_strategies import (
    BindingStrategy,
    RequestStrategy,
    SingletonStrategy,
    TransientStrategy,
)
from .decorators import extract_inject_all_info, extract_inject_info
from .exceptions import (
    AmbiguousDependencyError,
    CircularDependencyError,
    DependencyNotFoundError,
    RegistrationError,
    ResolutionError,
    ValidationError,
)
from .scopes import Scopes
from .types import (
    DependencyKey,
    Factory,
    FactoryCallable,
    ModuleProtocol,
    get_type_from_key,
    make_key,
)


class _MissingType:
    """Sentinel class for parameters without type hints."""

    pass


def _format_dependency(dep_type: type, name: str | None = None) -> str:
    """Format a dependency type and optional name for error messages."""
    if name:
        return f"{dep_type.__name__}[name='{name}']"
    return dep_type.__name__


@dataclass(frozen=True)
class ParameterDependency:
    """Describes a parameter that needs dependency resolution."""

    name: str
    dep_type: type
    dep_name: str | None  # Named qualifier
    is_collection: bool  # True for InjectAll
    has_default: bool
    is_optional: bool = False  # True for T | None annotations
    wrapper_type: type | None = None  # Factory


def _extract_optional_type(annotation: Any) -> type | None:
    """Extract T from T | None or Optional[T] annotations.

    Returns the inner type T if the annotation is an optional type,
    or None if it's not an optional type.
    """
    origin = get_origin(annotation)
    if origin is Union or origin is types_mod.UnionType:
        args = get_args(annotation)
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1 and len(args) == 2:
            return non_none_args[0]  # type: ignore[no-any-return]
    return None


def _make_wrapper(
    wrapper_type: type, dep_type: type, dep_name: str | None, container: "Container"
) -> Factory:  # type: ignore[type-arg]
    """Create a Factory wrapper that resolves from the container."""

    def resolver(_t: type = dep_type, _n: str | None = dep_name) -> Any:
        return container.get(_t, name=_n)

    return Factory(resolver)


def _extract_wrapper_type(annotation: Any) -> tuple[type, type] | None:
    """Extract T and wrapper class from Factory[T] annotations.

    Returns (inner_type, wrapper_class) or None if not a wrapper type.
    """
    origin = get_origin(annotation)
    if origin is Factory:
        args = get_args(annotation)
        if args:
            return args[0], origin
    return None


@lru_cache(maxsize=256)
def analyze_parameters(
    callable_obj: Callable[..., Any],
    skip_self: bool = False,
) -> tuple[ParameterDependency, ...]:
    """Analyze function/method parameters to determine what needs resolution.

    This shared helper eliminates duplication between sync/async resolution paths.
    Results are cached for performance since the same callable is often analyzed
    multiple times during dependency resolution.

    Args:
        callable_obj: Function or method to analyze
        skip_self: Whether to skip 'self' parameter (for methods)

    Returns:
        Tuple of ParameterDependency describing each injectable parameter
    """
    try:
        type_hints = get_type_hints(callable_obj, include_extras=True)
    except Exception:
        type_hints = {}

    type_hints.pop("return", None)
    sig = inspect.signature(callable_obj)
    dependencies: list[ParameterDependency] = []

    for param_name, param in sig.parameters.items():
        if skip_self and param_name == "self":
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        param_type = type_hints.get(param_name)
        has_default = param.default is not inspect.Parameter.empty

        if param_type is None:
            if not has_default:
                # Parameter has no type hint and no default - can't resolve
                dependencies.append(
                    ParameterDependency(
                        name=param_name,
                        dep_type=_MissingType,
                        dep_name=None,
                        is_collection=False,
                        has_default=False,
                    )
                )
            continue

        # Check for InjectAll first
        inject_all_info = extract_inject_all_info(param_type)
        if inject_all_info is not None:
            item_type, coll_name = inject_all_info
            dependencies.append(
                ParameterDependency(
                    name=param_name,
                    dep_type=item_type,
                    dep_name=coll_name,
                    is_collection=True,
                    has_default=has_default,
                )
            )
            continue

        # Check for Inject with optional Named
        inject_info = extract_inject_info(param_type)
        if inject_info:
            actual_type, dep_name = inject_info
            # Check if the injected type is Factory[T]
            wrapper = _extract_wrapper_type(actual_type)
            if wrapper is not None:
                inner_type, wrapper_cls = wrapper
                dependencies.append(
                    ParameterDependency(
                        name=param_name,
                        dep_type=inner_type,
                        dep_name=dep_name,
                        is_collection=False,
                        has_default=has_default,
                        wrapper_type=wrapper_cls,
                    )
                )
            else:
                dependencies.append(
                    ParameterDependency(
                        name=param_name,
                        dep_type=actual_type,
                        dep_name=dep_name,
                        is_collection=False,
                        has_default=has_default,
                    )
                )
        else:
            # Check for Factory[T] (bare, without Inject)
            wrapper = _extract_wrapper_type(param_type)
            if wrapper is not None:
                inner_type, wrapper_cls = wrapper
                dependencies.append(
                    ParameterDependency(
                        name=param_name,
                        dep_type=inner_type,
                        dep_name=None,
                        is_collection=False,
                        has_default=has_default,
                        wrapper_type=wrapper_cls,
                    )
                )
            # Check for Optional[T] / T | None
            elif (optional_type := _extract_optional_type(param_type)) is not None:
                dependencies.append(
                    ParameterDependency(
                        name=param_name,
                        dep_type=optional_type,
                        dep_name=None,
                        is_collection=False,
                        has_default=has_default,
                        is_optional=True,
                    )
                )
            else:
                # Regular type hint
                dependencies.append(
                    ParameterDependency(
                        name=param_name,
                        dep_type=param_type,
                        dep_name=None,
                        is_collection=False,
                        has_default=has_default,
                    )
                )

    return tuple(dependencies)


class Binding:
    """Represents a binding between a type and its implementation.

    Uses strategy pattern to handle different scope types. The appropriate
    strategy is automatically selected based on the scope.
    """

    def __init__(
        self,
        key: DependencyKey,
        factory: FactoryCallable[Any] | None = None,
        implementation: type[Any] | None = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: Any | None = None,
    ) -> None:
        """Initialize a binding."""
        self.key = key
        self.factory = factory
        self.implementation = implementation
        self.scope = scope
        self.instance = instance

        if factory is None and implementation is None and instance is None:
            raise RegistrationError(
                f"Must provide either factory, implementation, or instance for {key}"
            )

        self._is_async_factory = inspect.iscoroutinefunction(factory) if factory else False
        self._factory_has_params = False
        if factory is not None:
            sig = inspect.signature(factory)
            self._factory_has_params = len(sig.parameters) > 0

        self._strategy = self._create_strategy(scope)

    def _create_strategy(self, scope: Scopes) -> BindingStrategy:
        """Create the appropriate binding strategy for the scope."""
        match scope:
            case Scopes.SINGLETON:
                return SingletonStrategy()
            case Scopes.TRANSIENT:
                return TransientStrategy()
            case Scopes.REQUEST:
                return RequestStrategy()
            case _:
                raise RegistrationError(f"Unknown scope: {scope}")

    def create_instance(self, container: "Container") -> Any:
        """Create an instance of the dependency (sync context)."""
        if self.instance is not None:
            return self.instance

        if self.factory is not None:
            if self._factory_has_params:
                factory = self.factory

                def factory_func() -> Any:
                    return self._call_factory_with_deps(container, factory)

            else:
                factory_func = self.factory
        elif self.implementation is not None:
            implementation = self.implementation

            def factory_func() -> Any:
                return container._create_instance(implementation)

        else:
            raise ResolutionError(f"Cannot create instance for {self.key}")

        return self._strategy.get(factory_func, self._is_async_factory)

    def _call_factory_with_deps(self, container: "Container", factory: Callable[..., Any]) -> Any:
        """Call a factory function, resolving its dependencies from the container."""
        try:
            deps = analyze_parameters(factory)
            kwargs: dict[str, Any] = {}

            for dep in deps:
                if dep.dep_type is _MissingType:
                    raise ResolutionError(
                        f"Factory parameter '{dep.name}' has no type hint "
                        f"and no default value for {self.key}"
                    )

                if dep.wrapper_type is not None:
                    kwargs[dep.name] = _make_wrapper(
                        dep.wrapper_type, dep.dep_type, dep.dep_name, container
                    )
                    continue

                try:
                    if dep.is_collection:
                        kwargs[dep.name] = container.get_all(dep.dep_type, name=dep.dep_name)
                    else:
                        kwargs[dep.name] = container.get(dep.dep_type, name=dep.dep_name)
                except DependencyNotFoundError:
                    if dep.is_optional:
                        kwargs[dep.name] = None
                    elif not dep.has_default:
                        raise ResolutionError(
                            f"Cannot resolve factory parameter '{dep.name}' "
                            f"of type {_format_dependency(dep.dep_type, dep.dep_name)} "
                            f"for {self.key}"
                        )

            return factory(**kwargs)
        except Exception as e:
            if isinstance(e, (ResolutionError, DependencyNotFoundError, CircularDependencyError)):
                raise
            raise ResolutionError(f"Failed to call factory for {self.key}: {e}")

    async def create_instance_async(self, container: "Container") -> Any:
        """Create an instance of the dependency (async context)."""
        if self.instance is not None:
            return self.instance

        if self.factory is not None:
            if self._factory_has_params:
                factory = self.factory

                async def factory_func() -> Any:
                    return await self._call_factory_with_deps_async(container, factory)

            else:
                factory_func = self.factory
        elif self.implementation is not None:
            implementation = self.implementation

            async def factory_func() -> Any:
                return await container._create_instance_async(implementation)

        else:
            raise ResolutionError(f"Cannot create instance for {self.key}")

        return await self._strategy.get_async(factory_func)

    async def _call_factory_with_deps_async(
        self, container: "Container", factory: Callable[..., Any]
    ) -> Any:
        """Call a factory function asynchronously, resolving dependencies."""
        try:
            deps = analyze_parameters(factory)
            kwargs: dict[str, Any] = {}

            for dep in deps:
                if dep.dep_type is _MissingType:
                    raise ResolutionError(
                        f"Factory parameter '{dep.name}' has no type hint "
                        f"and no default value for {self.key}"
                    )

                if dep.wrapper_type is not None:
                    kwargs[dep.name] = _make_wrapper(
                        dep.wrapper_type, dep.dep_type, dep.dep_name, container
                    )
                    continue

                try:
                    if dep.is_collection:
                        kwargs[dep.name] = await container.get_all_async(
                            dep.dep_type, name=dep.dep_name
                        )
                    else:
                        kwargs[dep.name] = await container.get_async(
                            dep.dep_type, name=dep.dep_name
                        )
                except DependencyNotFoundError:
                    if dep.is_optional:
                        kwargs[dep.name] = None
                    elif not dep.has_default:
                        raise ResolutionError(
                            f"Cannot resolve factory parameter '{dep.name}' "
                            f"of type {_format_dependency(dep.dep_type, dep.dep_name)} "
                            f"for {self.key}"
                        )

            result = factory(**kwargs)
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as e:
            if isinstance(e, (ResolutionError, DependencyNotFoundError, CircularDependencyError)):
                raise
            raise ResolutionError(f"Failed to call factory for {self.key}: {e}")


class Container:
    """Dependency injection container.

    A Container manages dependency registration and resolution with support for:
    - Parent-child hierarchies for dependency inheritance
    - Module registration for composition
    - All dependencies are public by default
    """

    def __init__(self, parent: Optional["Container"] = None, name: str = "Container") -> None:
        """Initialize a container."""
        self._name = name
        self._bindings: dict[DependencyKey, list[Binding]] = {}
        self._modules: list[ModuleProtocol] = []
        self._parent = parent
        self._frozen = False
        self._resolution_stack_var: contextvars.ContextVar[list[DependencyKey]] = (
            contextvars.ContextVar(f"_resolution_stack_{id(self)}")
        )

    @property
    def _resolution_stack(self) -> list[DependencyKey]:
        """Get the resolution stack for the current thread/async context.

        Each thread and async task gets its own independent stack, preventing
        concurrent resolution calls from corrupting each other's cycle detection.
        """
        try:
            return self._resolution_stack_var.get()
        except LookupError:
            stack: list[DependencyKey] = []
            self._resolution_stack_var.set(stack)
            return stack

    @property
    def name(self) -> str:
        """Get the container name."""
        return self._name

    @property
    def parent(self) -> Optional["Container"]:
        """Get the parent container."""
        return self._parent

    @property
    def frozen(self) -> bool:
        """Whether the container is frozen (read-only)."""
        return self._frozen

    def freeze(self) -> "Container":
        """Freeze the container, preventing further registrations.

        After freezing, any call to register(), register_factory(),
        register_instance(), or register_module() will raise RegistrationError.

        Freezing cascades to all registered modules and to the parent
        container, ensuring that no mutation to any dependency provider
        can affect resolution from this container.

        Returns:
            Self for chaining
        """
        self._frozen = True
        for module in self._modules:
            module.freeze()
        if self._parent is not None:
            self._parent.freeze()
        return self

    def _check_not_frozen(self) -> None:
        """Raise RegistrationError if the container is frozen."""
        if self._frozen:
            raise RegistrationError(
                f"Cannot register dependencies: container '{self._name}' is frozen"
            )

    def register[T](
        self,
        interface: type[T],
        implementation: type[T] | None = None,
        factory: FactoryCallable[T] | None = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: T | None = None,
        name: str | None = None,
    ) -> "Container":
        """Register a dependency in the container."""
        self._check_not_frozen()
        if implementation is None and factory is None and instance is None:
            implementation = interface

        key = make_key(interface, name)
        binding = Binding(
            key=key,
            factory=factory,
            implementation=implementation,
            scope=scope,
            instance=instance,
        )

        if key not in self._bindings:
            self._bindings[key] = []
        self._bindings[key].append(binding)

        return self

    def register_factory[T](
        self,
        interface: type[T],
        factory: FactoryCallable[T],
        scope: Scopes = Scopes.TRANSIENT,
        name: str | None = None,
    ) -> "Container":
        """Register a factory function for a dependency."""
        return self.register(interface, factory=factory, scope=scope, name=name)

    def register_instance[T](
        self, interface: type[T], instance: T, name: str | None = None
    ) -> "Container":
        """Register a pre-created instance."""
        return self.register(interface, instance=instance, scope=Scopes.SINGLETON, name=name)

    def register_module(self, module: ModuleProtocol) -> "Container":
        """Register a module as a provider of dependencies."""
        self._check_not_frozen()
        self._modules.append(module)
        return self

    def get[T](self, interface: type[T], name: str | None = None) -> T:
        """Resolve a dependency from the container."""
        key = make_key(interface, name)

        if key in self._resolution_stack:
            self._resolution_stack.append(key)
            cycle_types = [get_type_from_key(k) for k in self._resolution_stack]
            raise CircularDependencyError(cycle_types)

        bindings = self._bindings.get(key, [])

        if len(bindings) > 1:
            raise AmbiguousDependencyError(interface, len(bindings), self._name)

        binding = bindings[0] if len(bindings) == 1 else None

        if binding is None:
            for module in self._modules:
                try:
                    instance = module.get(interface, name=name)
                    return instance
                except DependencyNotFoundError:
                    continue
                except AmbiguousDependencyError:
                    raise

        if binding is None and self._parent is not None:
            return self._parent.get(interface, name=name)

        if binding is None:
            raise DependencyNotFoundError(interface, self._name, name=name)

        self._resolution_stack.append(key)
        try:
            instance = binding.create_instance(self)
            return instance
        finally:
            self._resolution_stack.pop()

    def try_get[T](
        self,
        interface: type[T],
        name: str | None = None,
        *,
        suppress_ambiguity: bool = False,
    ) -> T | None:
        """Try to resolve a dependency, returning None if not found."""
        try:
            return self.get(interface, name=name)
        except DependencyNotFoundError:
            return None
        except AmbiguousDependencyError:
            if suppress_ambiguity:
                return None
            raise

    async def try_get_async[T](
        self,
        interface: type[T],
        name: str | None = None,
        *,
        suppress_ambiguity: bool = False,
    ) -> T | None:
        """Try to resolve a dependency asynchronously, returning None if not found."""
        try:
            return await self.get_async(interface, name=name)
        except DependencyNotFoundError:
            return None
        except AmbiguousDependencyError:
            if suppress_ambiguity:
                return None
            raise

    async def get_async[T](self, interface: type[T], name: str | None = None) -> T:
        """Resolve a dependency from the container asynchronously."""
        key = make_key(interface, name)

        if key in self._resolution_stack:
            self._resolution_stack.append(key)
            cycle_types = [get_type_from_key(k) for k in self._resolution_stack]
            raise CircularDependencyError(cycle_types)

        bindings = self._bindings.get(key, [])

        if len(bindings) > 1:
            raise AmbiguousDependencyError(interface, len(bindings), self._name)

        binding = bindings[0] if len(bindings) == 1 else None

        if binding is None:
            for module in self._modules:
                try:
                    instance = await module.get_async(interface, name=name)
                    return instance
                except DependencyNotFoundError:
                    continue
                except AmbiguousDependencyError:
                    raise

        if binding is None and self._parent is not None:
            return await self._parent.get_async(interface, name=name)

        if binding is None:
            raise DependencyNotFoundError(interface, self._name, name=name)

        self._resolution_stack.append(key)
        try:
            instance = await binding.create_instance_async(self)
            return instance
        finally:
            self._resolution_stack.pop()

    def has(self, interface: type[Any], name: str | None = None) -> bool:
        """Check if a dependency is registered."""
        key = make_key(interface, name)

        if key in self._bindings and self._bindings[key]:
            return True

        for module in self._modules:
            if module.has(interface, name=name):
                return True

        if self._parent is not None:
            return self._parent.has(interface, name=name)

        return False

    def count(self, interface: type[Any], name: str | None = None) -> int:
        """Count implementations registered for an interface."""
        key = make_key(interface, name)
        total = len(self._bindings.get(key, []))

        for module in self._modules:
            total += module.count(interface, name=name)

        if self._parent is not None:
            total += self._parent.count(interface, name=name)

        return total

    def get_all[T](self, interface: type[T], *, name: str | None = None) -> list[T]:
        """Resolve all implementations of an interface."""
        instances: list[T] = []
        key: DependencyKey = (interface, name) if name is not None else interface

        bindings = self._bindings.get(key, [])
        for binding in bindings:
            instance = binding.create_instance(self)
            instances.append(instance)

        for module in self._modules:
            try:
                module_instances = module.get_all(interface, name=name)
                instances.extend(module_instances)
            except DependencyNotFoundError:
                pass

        if self._parent is not None:
            parent_instances = self._parent.get_all(interface, name=name)
            instances.extend(parent_instances)

        return instances

    async def get_all_async[T](self, interface: type[T], *, name: str | None = None) -> list[T]:
        """Resolve all implementations asynchronously."""
        instances: list[T] = []
        key: DependencyKey = (interface, name) if name is not None else interface

        bindings = self._bindings.get(key, [])
        for binding in bindings:
            instance = await binding.create_instance_async(self)
            instances.append(instance)

        for module in self._modules:
            try:
                module_instances = await module.get_all_async(interface, name=name)
                instances.extend(module_instances)
            except DependencyNotFoundError:
                pass

        if self._parent is not None:
            parent_instances = await self._parent.get_all_async(interface, name=name)
            instances.extend(parent_instances)

        return instances

    def run[T](self, func: Callable[..., T], **provided_kwargs: Any) -> T:
        """Run a function with dependency injection using synchronous resolution."""
        try:
            deps = analyze_parameters(func)
            resolved_kwargs = provided_kwargs.copy()

            for dep in deps:
                if dep.name in provided_kwargs:
                    continue

                if dep.dep_type is _MissingType:
                    raise ResolutionError(
                        f"Parameter '{dep.name}' of function '{func.__name__}' "
                        f"has no type annotation and no default value"
                    )

                if dep.wrapper_type is not None:
                    resolved_kwargs[dep.name] = _make_wrapper(
                        dep.wrapper_type, dep.dep_type, dep.dep_name, self
                    )
                    continue

                try:
                    if dep.is_collection:
                        resolved_kwargs[dep.name] = self.get_all(dep.dep_type, name=dep.dep_name)
                    else:
                        resolved_kwargs[dep.name] = self.get(dep.dep_type, name=dep.dep_name)
                except DependencyNotFoundError:
                    if dep.is_optional:
                        resolved_kwargs[dep.name] = None
                    elif not dep.has_default:
                        raise ResolutionError(
                            f"Cannot resolve parameter '{dep.name}' of type "
                            f"{_format_dependency(dep.dep_type, dep.dep_name)} "
                            f"for function '{func.__name__}'"
                        )

            return func(**resolved_kwargs)

        except Exception as e:
            resolution_errors = (
                ResolutionError,
                DependencyNotFoundError,
                CircularDependencyError,
                AmbiguousDependencyError,
            )
            if isinstance(e, resolution_errors):
                raise
            raise ResolutionError(f"Failed to run function '{func.__name__}': {e}")

    async def run_async[T](self, func: Callable[..., T], **provided_kwargs: Any) -> T:
        """Run a function with dependency injection using asynchronous resolution."""
        try:
            deps = analyze_parameters(func)
            resolved_kwargs = provided_kwargs.copy()

            for dep in deps:
                if dep.name in provided_kwargs:
                    continue

                if dep.dep_type is _MissingType:
                    raise ResolutionError(
                        f"Parameter '{dep.name}' of function '{func.__name__}' "
                        f"has no type annotation and no default value"
                    )

                if dep.wrapper_type is not None:
                    resolved_kwargs[dep.name] = _make_wrapper(
                        dep.wrapper_type, dep.dep_type, dep.dep_name, self
                    )
                    continue

                try:
                    if dep.is_collection:
                        resolved_kwargs[dep.name] = await self.get_all_async(
                            dep.dep_type, name=dep.dep_name
                        )
                    else:
                        resolved_kwargs[dep.name] = await self.get_async(
                            dep.dep_type, name=dep.dep_name
                        )
                except DependencyNotFoundError:
                    if dep.is_optional:
                        resolved_kwargs[dep.name] = None
                    elif not dep.has_default:
                        raise ResolutionError(
                            f"Cannot resolve parameter '{dep.name}' of type "
                            f"{_format_dependency(dep.dep_type, dep.dep_name)} "
                            f"for function '{func.__name__}'"
                        )

            return func(**resolved_kwargs)

        except Exception as e:
            resolution_errors = (
                ResolutionError,
                DependencyNotFoundError,
                CircularDependencyError,
                AmbiguousDependencyError,
            )
            if isinstance(e, resolution_errors):
                raise
            raise ResolutionError(f"Failed to run function '{func.__name__}': {e}")

    def _resolve_injectable_deps(
        self, cls: type[Any]
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Resolve dependencies for Injectable classes.

        Returns (inject_kwargs, inject_all_kwargs) or None if not Injectable.
        """
        inject_fields: dict[str, tuple[type, str | None]] | None = getattr(
            cls, "_inject_fields", None
        )
        inject_all_fields: dict[str, tuple[type, str | None]] | None = getattr(
            cls, "_inject_all_fields", None
        )

        if not inject_fields and not inject_all_fields:
            return None

        kwargs: dict[str, Any] = {}

        if inject_fields:
            for field_name, (field_type, dep_name) in inject_fields.items():
                wrapper = _extract_wrapper_type(field_type)
                if wrapper is not None:
                    inner_type, wrapper_cls = wrapper
                    kwargs[field_name] = _make_wrapper(wrapper_cls, inner_type, dep_name, self)
                else:
                    try:
                        kwargs[field_name] = self.get(field_type, name=dep_name)
                    except DependencyNotFoundError:
                        raise ResolutionError(
                            f"Cannot resolve dependency '{field_name}' of type "
                            f"{_format_dependency(field_type, dep_name)} "
                            f"for class '{cls.__name__}'"
                        )

        if inject_all_fields:
            for field_name, (item_type, coll_name) in inject_all_fields.items():
                kwargs[field_name] = self.get_all(item_type, name=coll_name)

        return kwargs, {}

    async def _resolve_injectable_deps_async(
        self, cls: type[Any]
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Resolve dependencies for Injectable classes asynchronously."""
        inject_fields: dict[str, tuple[type, str | None]] | None = getattr(
            cls, "_inject_fields", None
        )
        inject_all_fields: dict[str, tuple[type, str | None]] | None = getattr(
            cls, "_inject_all_fields", None
        )

        if not inject_fields and not inject_all_fields:
            return None

        kwargs: dict[str, Any] = {}

        if inject_fields:
            for field_name, (field_type, dep_name) in inject_fields.items():
                wrapper = _extract_wrapper_type(field_type)
                if wrapper is not None:
                    inner_type, wrapper_cls = wrapper
                    kwargs[field_name] = _make_wrapper(wrapper_cls, inner_type, dep_name, self)
                else:
                    try:
                        kwargs[field_name] = await self.get_async(field_type, name=dep_name)
                    except DependencyNotFoundError:
                        raise ResolutionError(
                            f"Cannot resolve dependency '{field_name}' of type "
                            f"{_format_dependency(field_type, dep_name)} "
                            f"for class '{cls.__name__}'"
                        )

        if inject_all_fields:
            for field_name, (item_type, coll_name) in inject_all_fields.items():
                kwargs[field_name] = await self.get_all_async(item_type, name=coll_name)

        return kwargs, {}

    def _create_instance[T](self, cls: type[T]) -> T:
        """Create an instance of a class, resolving its dependencies."""
        try:
            # Check if this is an Injectable class
            injectable_result = self._resolve_injectable_deps(cls)
            if injectable_result is not None:
                injectable_kwargs, _ = injectable_result
                return cls(**injectable_kwargs)

            # Regular class - use constructor inspection
            deps = analyze_parameters(cls.__init__, skip_self=True)
            kwargs: dict[str, Any] = {}

            for dep in deps:
                if dep.dep_type is _MissingType:
                    raise ResolutionError(
                        f"Parameter '{dep.name}' of class '{cls.__name__}' "
                        f"has no type annotation and no default value"
                    )

                if dep.wrapper_type is not None:
                    kwargs[dep.name] = _make_wrapper(
                        dep.wrapper_type, dep.dep_type, dep.dep_name, self
                    )
                    continue

                try:
                    if dep.is_collection:
                        kwargs[dep.name] = self.get_all(dep.dep_type, name=dep.dep_name)
                    else:
                        kwargs[dep.name] = self.get(dep.dep_type, name=dep.dep_name)
                except DependencyNotFoundError:
                    if dep.is_optional:
                        kwargs[dep.name] = None
                    elif not dep.has_default:
                        raise ResolutionError(
                            f"Cannot resolve parameter '{dep.name}' of type "
                            f"{_format_dependency(dep.dep_type, dep.dep_name)} "
                            f"for class '{cls.__name__}'"
                        )

            return cls(**kwargs)

        except Exception as e:
            if isinstance(e, (ResolutionError, DependencyNotFoundError, CircularDependencyError)):
                raise
            raise ResolutionError(f"Failed to create instance of {cls.__name__}: {e}")

    async def _create_instance_async[T](self, cls: type[T]) -> T:
        """Create an instance of a class asynchronously, resolving its dependencies."""
        try:
            # Check if this is an Injectable class
            injectable_result = await self._resolve_injectable_deps_async(cls)
            if injectable_result is not None:
                injectable_kwargs, _ = injectable_result
                return cls(**injectable_kwargs)

            # Regular class - use constructor inspection
            deps = analyze_parameters(cls.__init__, skip_self=True)
            kwargs: dict[str, Any] = {}

            for dep in deps:
                if dep.dep_type is _MissingType:
                    raise ResolutionError(
                        f"Parameter '{dep.name}' of class '{cls.__name__}' "
                        f"has no type annotation and no default value"
                    )

                if dep.wrapper_type is not None:
                    kwargs[dep.name] = _make_wrapper(
                        dep.wrapper_type, dep.dep_type, dep.dep_name, self
                    )
                    continue

                try:
                    if dep.is_collection:
                        kwargs[dep.name] = await self.get_all_async(dep.dep_type, name=dep.dep_name)
                    else:
                        kwargs[dep.name] = await self.get_async(dep.dep_type, name=dep.dep_name)
                except DependencyNotFoundError:
                    if dep.is_optional:
                        kwargs[dep.name] = None
                    elif not dep.has_default:
                        raise ResolutionError(
                            f"Cannot resolve parameter '{dep.name}' of type "
                            f"{_format_dependency(dep.dep_type, dep.dep_name)} "
                            f"for class '{cls.__name__}'"
                        )

            return cls(**kwargs)

        except Exception as e:
            if isinstance(e, (ResolutionError, DependencyNotFoundError, CircularDependencyError)):
                raise
            raise ResolutionError(f"Failed to create instance of {cls.__name__}: {e}")

    def create_child(self, name: str | None = None) -> "Container":
        """Create a child container."""
        child_name = name if name else f"{self._name}.Child"
        return Container(parent=self, name=child_name)

    def _get_implementation_dependencies(self, cls: type[Any]) -> list[type[Any]]:
        """Get the dependency types required by a class implementation."""
        dependencies: list[type[Any]] = []
        try:
            deps = analyze_parameters(cls.__init__, skip_self=True)
            for dep in deps:
                if dep.dep_type is not _MissingType and not dep.has_default:
                    dependencies.append(dep.dep_type)
        except Exception:
            pass
        return dependencies

    def _detect_cycles(self) -> list[list[type[Any]]]:
        """Detect circular dependencies in the container.

        Note: This method accesses module._bindings via hasattr checks because
        cycle detection requires inspecting internal binding state. This is
        intentional duck-typing — only Container-based modules support validation.
        """
        graph: dict[type[Any], list[type[Any]]] = {}

        for key, bindings in self._bindings.items():
            for binding in bindings:
                if binding.instance is not None or binding.factory is not None:
                    continue
                if binding.implementation is not None:
                    node_type = get_type_from_key(key)
                    deps = self._get_implementation_dependencies(binding.implementation)
                    registered_deps = [
                        d
                        for d in deps
                        if d in self._bindings
                        or any(d in m._bindings for m in self._modules if hasattr(m, "_bindings"))
                    ]
                    graph[node_type] = registered_deps

        for module in self._modules:
            if hasattr(module, "_bindings"):
                for key, bindings in module._bindings.items():
                    for binding in bindings:
                        if binding.instance is not None or binding.factory is not None:
                            continue
                        if binding.implementation is not None:
                            node_type = get_type_from_key(key)
                            deps = self._get_implementation_dependencies(binding.implementation)
                            registered_deps = [
                                d
                                for d in deps
                                if d in self._bindings
                                or d in module._bindings
                                or any(
                                    d in m._bindings
                                    for m in self._modules
                                    if hasattr(m, "_bindings")
                                )
                            ]
                            graph[node_type] = registered_deps

        cycles: list[list[type[Any]]] = []
        visited: set[type[Any]] = set()
        rec_stack: set[type[Any]] = set()
        path: list[type[Any]] = []

        def dfs(node: type[Any]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.remove(node)

        for node in graph:
            if node not in visited:
                dfs(node)

        return cycles

    def _validate_dependency(
        self, dep: ParameterDependency, cls: type[Any], errors: list[str]
    ) -> None:
        """Validate a single dependency can be resolved."""
        if dep.dep_type is _MissingType:
            return  # Skip - will be caught at resolution time

        if dep.is_collection:
            return  # Collections are always valid (may be empty)

        # Check if this is an Injectable's inject_all field
        inject_all_fields = getattr(cls, "_inject_all_fields", None)
        if inject_all_fields and dep.name in inject_all_fields:
            return

        dep_key = make_key(dep.dep_type, dep.dep_name)
        has_dependency = (
            dep_key in self._bindings
            and self._bindings[dep_key]
            or any(
                dep_key in m._bindings and m._bindings[dep_key]
                for m in self._modules
                if hasattr(m, "_bindings")
            )
            or (self._parent is not None and self._parent.has(dep.dep_type, name=dep.dep_name))
        )

        if not has_dependency:
            if not dep.has_default:
                dep_fmt = _format_dependency(dep.dep_type, dep.dep_name)
                errors.append(
                    f"Dependency '{cls.__name__}' requires "
                    f"'{dep_fmt}' (parameter '{dep.name}') "
                    f"which is not registered"
                )
        elif not dep.has_default and dep.dep_name is None:
            # Check for ambiguity (only for non-named dependencies)
            dep_count = self.count(dep.dep_type)
            if dep_count > 1:
                type_name = getattr(dep.dep_type, "__name__", str(dep.dep_type))
                errors.append(
                    f"Dependency '{cls.__name__}' requires "
                    f"'{type_name}' (parameter '{dep.name}') "
                    f"but {dep_count} implementations are "
                    f"registered. Use Inject[{type_name}, "
                    f"Named('...')] to disambiguate or "
                    f"InjectAll[{type_name}] for collection."
                )

    def validate(self) -> None:
        """Validate that all registered dependencies can be resolved."""
        errors: list[str] = []

        # Check for circular dependencies
        cycles = self._detect_cycles()
        for cycle in cycles:
            chain_str = " -> ".join(t.__name__ for t in cycle)
            errors.append(f"Circular dependency detected: {chain_str}")

        for key, bindings in self._bindings.items():
            for binding in bindings:
                if binding.instance is not None or binding.factory is not None:
                    continue

                if binding.implementation is not None:
                    cls = binding.implementation
                    try:
                        deps = analyze_parameters(cls.__init__, skip_self=True)
                        for dep in deps:
                            self._validate_dependency(dep, cls, errors)
                    except Exception as e:
                        errors.append(f"Failed to validate dependency '{cls.__name__}': {e}")

        if errors:
            raise ValidationError(errors)

    def __repr__(self) -> str:
        """Get string representation of the container."""
        deps = ", ".join(getattr(k, "__name__", str(k)) for k in self._bindings.keys())
        return f"Container({self._name}, dependencies=[{deps}])"
