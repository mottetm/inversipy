"""Container implementation for dependency injection."""

import asyncio
import contextvars
from collections import deque
from collections.abc import Callable
from typing import Any, Optional

from ._wrappers import _format_dependency, _make_wrapper, _make_wrapper_async
from .binding import (
    Binding,
    ParameterDependency,
    _injectable_to_param_deps,
    _MissingType,
    analyze_parameters,
)
from .exceptions import (
    AmbiguousDependencyError,
    CircularDependencyError,
    DependencyNotFoundError,
    RegistrationError,
    ResolutionError,
    ValidationError,
)
from .scopes import Scope, Scopes
from .types import (
    DependencyKey,
    Factory,
    FactoryCallable,
    Lazy,
    ModuleProtocol,
    get_type_from_key,
    make_key,
)

_RESOLUTION_ERRORS = (
    ResolutionError,
    DependencyNotFoundError,
    CircularDependencyError,
    AmbiguousDependencyError,
)


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
        scope: Scope = Scopes.TRANSIENT,
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
        scope: Scope = Scopes.TRANSIENT,
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
            cycle_types = [get_type_from_key(k) for k in self._resolution_stack] + [
                get_type_from_key(key)
            ]
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
            cycle_types = [get_type_from_key(k) for k in self._resolution_stack] + [
                get_type_from_key(key)
            ]
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

    def _find_binding(self, key: DependencyKey) -> Binding | None:
        """Find a single binding for a key, searching locally and in parent."""
        bindings = self._bindings.get(key, [])
        if len(bindings) == 1:
            return bindings[0]

        for module in self._modules:
            if isinstance(module, Container):
                binding = module._find_binding(key)
                if binding is not None:
                    return binding

        if self._parent is not None:
            return self._parent._find_binding(key)

        return None

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

    def _resolve_deps(
        self,
        deps: tuple[ParameterDependency, ...],
        target_name: str,
        provided: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve a list of parameter dependencies synchronously."""
        kwargs = dict(provided) if provided else {}
        for dep in deps:
            if dep.name in kwargs:
                continue
            if dep.dep_type is _MissingType:
                raise ResolutionError(
                    f"Parameter '{dep.name}' of {target_name} "
                    f"has no type hint and no default value"
                )
            if dep.wrapper_type is not None:
                kwargs[dep.name] = _make_wrapper(dep.wrapper_type, dep.dep_type, dep.dep_name, self)
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
                        f"for {target_name}"
                    )
        return kwargs

    async def _resolve_deps_async(
        self,
        deps: tuple[ParameterDependency, ...],
        target_name: str,
        provided: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve a list of parameter dependencies asynchronously."""
        kwargs = dict(provided) if provided else {}
        for dep in deps:
            if dep.name in kwargs:
                continue
            if dep.dep_type is _MissingType:
                raise ResolutionError(
                    f"Parameter '{dep.name}' of {target_name} "
                    f"has no type hint and no default value"
                )
            if dep.wrapper_type is not None:
                kwargs[dep.name] = _make_wrapper_async(
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
                        f"for {target_name}"
                    )
        return kwargs

    def run[T](self, func: Callable[..., T], **provided_kwargs: Any) -> T:
        """Run a function with dependency injection using synchronous resolution."""
        try:
            deps = analyze_parameters(func)
            target = f"function '{func.__name__}'"
            resolved_kwargs = self._resolve_deps(deps, target, provided=provided_kwargs)
            return func(**resolved_kwargs)
        except Exception as e:
            if isinstance(e, _RESOLUTION_ERRORS):
                raise
            raise ResolutionError(f"Failed to run function '{func.__name__}': {e}")

    async def run_async[T](self, func: Callable[..., T], **provided_kwargs: Any) -> T:
        """Run a function with dependency injection using asynchronous resolution."""
        try:
            deps = analyze_parameters(func)
            target = f"function '{func.__name__}'"
            resolved_kwargs = await self._resolve_deps_async(deps, target, provided=provided_kwargs)
            return func(**resolved_kwargs)
        except Exception as e:
            if isinstance(e, _RESOLUTION_ERRORS):
                raise
            raise ResolutionError(f"Failed to run function '{func.__name__}': {e}")

    def _resolve_injectable_deps(
        self, cls: type[Any]
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Resolve dependencies for Injectable classes.

        Returns (inject_kwargs, inject_all_kwargs) or None if not Injectable.
        """
        deps = _injectable_to_param_deps(cls)
        if deps is None:
            return None
        target = f"class '{cls.__name__}'"
        return self._resolve_deps(deps, target), {}

    async def _resolve_injectable_deps_async(
        self, cls: type[Any]
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Resolve dependencies for Injectable classes asynchronously."""
        deps = _injectable_to_param_deps(cls)
        if deps is None:
            return None
        target = f"class '{cls.__name__}'"
        return await self._resolve_deps_async(deps, target), {}

    def _instantiate_binding(self, binding: "Binding") -> Any:
        """Create an instance from a binding, resolving its dependencies.

        Handles both factory-based and implementation-based bindings uniformly
        via binding._provider (what to introspect) and binding._invoke (what to
        call with resolved kwargs).
        """
        try:
            # @Injectable fast-path (class-only decorator metadata)
            if binding.implementation is not None:
                injectable_result = self._resolve_injectable_deps(binding.implementation)
                if injectable_result is not None:
                    injectable_kwargs, _ = injectable_result
                    return binding.implementation(**injectable_kwargs)

            # Generic path: analyze _provider, resolve deps, invoke.
            # _provider and _invoke are guaranteed non-None for non-instance
            # bindings (set in Binding.__init__); instance bindings exit via
            # the early return in create_instance/create_instance_async.
            assert binding._provider is not None
            assert binding._invoke is not None
            deps = analyze_parameters(binding._provider, skip_self=True)
            target = (
                f"class '{binding.implementation.__name__}'"
                if binding.implementation is not None
                else f"factory for {binding.key}"
            )
            kwargs = self._resolve_deps(deps, target)
            return binding._invoke(**kwargs)
        except Exception as e:
            if isinstance(e, _RESOLUTION_ERRORS):
                raise
            if binding.factory is not None:
                raise ResolutionError(f"Failed to call factory for {binding.key}: {e}")
            assert binding.implementation is not None
            raise ResolutionError(
                f"Failed to create instance of {binding.implementation.__name__}: {e}"
            )

    async def _instantiate_binding_async(self, binding: "Binding") -> Any:
        """Create an instance from a binding asynchronously, resolving deps."""
        try:
            if binding.implementation is not None:
                injectable_result = await self._resolve_injectable_deps_async(
                    binding.implementation
                )
                if injectable_result is not None:
                    injectable_kwargs, _ = injectable_result
                    return binding.implementation(**injectable_kwargs)

            assert binding._provider is not None
            assert binding._invoke is not None
            deps = analyze_parameters(binding._provider, skip_self=True)
            target = (
                f"class '{binding.implementation.__name__}'"
                if binding.implementation is not None
                else f"factory for {binding.key}"
            )
            kwargs = await self._resolve_deps_async(deps, target)
            result = binding._invoke(**kwargs)
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as e:
            if isinstance(e, _RESOLUTION_ERRORS):
                raise
            if binding.factory is not None:
                raise ResolutionError(f"Failed to call factory for {binding.key}: {e}")
            assert binding.implementation is not None
            raise ResolutionError(
                f"Failed to create instance of {binding.implementation.__name__}: {e}"
            )

    def create_child(self, name: str | None = None) -> "Container":
        """Create a child container."""
        child_name = name if name else f"{self._name}.Child"
        return Container(parent=self, name=child_name)

    def _detect_cycles(self) -> list[list[type[Any]]]:
        """Detect circular dependencies in the container.

        Uses multi-root DFS over all registered bindings. Dependencies are
        extracted from each binding's ``_provider`` callable uniformly — no
        distinction between factories and class implementations.

        Lazy[T] and Factory[T] wrapper edges do not recurse in the current
        traversal (they defer resolution at runtime) but are enqueued as
        independent roots so that cycles *within* the deferred subgraph are
        still detected.

        Note: This method accesses module._bindings via hasattr checks because
        cycle detection requires inspecting internal binding state. This is
        intentional duck-typing — only Container-based modules support validation.
        """
        # Collect all binding sources into a unified lookup.
        all_bindings: dict[DependencyKey, list[Binding]] = dict(self._bindings)
        for module in self._modules:
            if hasattr(module, "_bindings"):
                for key, bindings in module._bindings.items():
                    all_bindings.setdefault(key, []).extend(bindings)

        def _is_registered(dep_key: DependencyKey) -> bool:
            return dep_key in all_bindings

        # Seed all registered keys as roots.
        roots: deque[DependencyKey] = deque(all_bindings.keys())
        global_visited: set[DependencyKey] = set()
        rec_stack: set[DependencyKey] = set()
        path: list[type[Any]] = []
        cycles: list[list[type[Any]]] = []

        def dfs(key: DependencyKey) -> None:
            if key in global_visited:
                return
            if key in rec_stack:
                node_type = get_type_from_key(key)
                cycle_start = path.index(node_type)
                cycles.append(path[cycle_start:] + [node_type])
                return

            rec_stack.add(key)
            path.append(get_type_from_key(key))

            bindings = all_bindings.get(key, [])
            for binding in bindings:
                if binding._provider is None:
                    continue  # Instance bindings have no deps

                try:
                    deps = analyze_parameters(binding._provider, skip_self=True)
                except Exception:
                    continue

                for dep in deps:
                    if dep.dep_type is _MissingType or dep.has_default:
                        continue

                    dep_key = make_key(dep.dep_type, dep.dep_name)

                    if dep.wrapper_type in (Lazy, Factory):
                        # Deferred resolution — don't recurse, schedule as new root
                        if dep_key not in global_visited:
                            roots.append(dep_key)
                        continue

                    if dep.is_optional and not _is_registered(dep_key):
                        continue

                    if dep.is_collection:
                        # Fan out to all bindings matching this type
                        for registered_key in all_bindings:
                            if get_type_from_key(registered_key) == dep.dep_type:
                                dfs(registered_key)
                        continue

                    if _is_registered(dep_key):
                        dfs(dep_key)

            rec_stack.remove(key)
            path.pop()
            global_visited.add(key)

        while roots:
            root = roots.popleft()
            if root not in global_visited:
                dfs(root)

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
