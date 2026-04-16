"""Binding class, parameter analysis, and supporting helpers.

This module owns the "what is a dependency" and "how is a binding instantiated"
concerns that support the :class:`~inversipy.container.Container`. It is kept
separate so binding lifecycle management can be read and tested independently
from container orchestration.
"""

import inspect
import types as types_mod
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin, get_type_hints

from .binding_strategies import (
    BindingStrategy,
    RequestStrategy,
    SingletonStrategy,
    TransientStrategy,
)
from .decorators import extract_inject_all_info, extract_inject_info
from .exceptions import InvalidScopeError, RegistrationError
from .scopes import CustomScope, Scope, Scopes
from .types import DependencyKey, Factory, FactoryCallable, Lazy

if TYPE_CHECKING:
    from .container import Container


class _MissingType:
    """Sentinel class for parameters without type hints."""

    pass


@dataclass(frozen=True)
class ParameterDependency:
    """Describes a parameter that needs dependency resolution."""

    name: str
    dep_type: type
    dep_name: str | None  # Named qualifier
    is_collection: bool  # True for InjectAll
    has_default: bool
    is_optional: bool = False  # True for T | None annotations
    wrapper_type: type | None = None  # Factory or Lazy


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


def _extract_wrapper_type(annotation: Any) -> tuple[type, type] | None:
    """Extract T and wrapper class from Factory[T] or Lazy[T] annotations.

    Returns (inner_type, wrapper_class) or None if not a wrapper type.
    """
    origin = get_origin(annotation)
    if origin is Factory or origin is Lazy:
        args = get_args(annotation)
        if args:
            return args[0], origin
    return None


def _injectable_to_param_deps(cls: type[Any]) -> tuple[ParameterDependency, ...] | None:
    """Convert Injectable field metadata into ParameterDependency tuples.

    Returns None if the class has no Injectable fields.
    """
    inject_fields: dict[str, tuple[type, str | None]] | None = getattr(cls, "_inject_fields", None)
    inject_all_fields: dict[str, tuple[type, str | None]] | None = getattr(
        cls, "_inject_all_fields", None
    )

    if not inject_fields and not inject_all_fields:
        return None

    deps: list[ParameterDependency] = []

    if inject_fields:
        for field_name, (field_type, dep_name) in inject_fields.items():
            wrapper = _extract_wrapper_type(field_type)
            if wrapper is not None:
                inner_type, wrapper_cls = wrapper
                deps.append(
                    ParameterDependency(
                        name=field_name,
                        dep_type=inner_type,
                        dep_name=dep_name,
                        is_collection=False,
                        has_default=False,
                        wrapper_type=wrapper_cls,
                    )
                )
            else:
                deps.append(
                    ParameterDependency(
                        name=field_name,
                        dep_type=field_type,
                        dep_name=dep_name,
                        is_collection=False,
                        has_default=False,
                    )
                )

    if inject_all_fields:
        for field_name, (item_type, coll_name) in inject_all_fields.items():
            deps.append(
                ParameterDependency(
                    name=field_name,
                    dep_type=item_type,
                    dep_name=coll_name,
                    is_collection=True,
                    has_default=False,
                )
            )

    return tuple(deps)


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
        scope: Scope = Scopes.TRANSIENT,
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

        # Unified provider/invoke callables.
        # _provider: what to introspect for dependency types (via analyze_parameters).
        # _invoke: what to call with resolved kwargs to produce an instance.
        # They differ for classes: _provider = cls.__init__ (for correct get_type_hints),
        # _invoke = cls (calling cls(**kwargs) invokes __init__ via Python's protocol).
        self._provider: Callable[..., Any] | None = None
        self._invoke: Callable[..., Any] | None = None
        if factory is not None:
            self._provider = factory
            self._invoke = factory
        elif implementation is not None:
            self._provider = implementation.__init__
            self._invoke = implementation

        self._strategy = self._create_strategy(scope)
        self._lazy_strategy = self._create_strategy(scope)

    def _create_strategy(self, scope: Scope) -> BindingStrategy:
        """Create the appropriate binding strategy for the scope."""
        if isinstance(scope, CustomScope):
            return scope.strategy_class()
        match scope:
            case Scopes.SINGLETON:
                return SingletonStrategy()
            case Scopes.TRANSIENT:
                return TransientStrategy()
            case Scopes.REQUEST:
                return RequestStrategy()
            case _:
                raise InvalidScopeError(f"Unknown scope: '{scope}'", scope_name=str(scope))

    def _build_lazy_wrapper(
        self,
        container: "Container",
        dep_type: type,
        dep_name: str | None,
        *,
        with_async: bool,
    ) -> "Lazy[Any]":
        """Cache and return a Lazy wrapper, optionally with async resolution."""

        def wrapper_factory() -> Lazy[Any]:
            def resolver(_t: type = dep_type, _n: str | None = dep_name) -> Any:
                return container.get(_t, name=_n)

            if not with_async:
                return Lazy(resolver)

            async def async_resolver(_t: type = dep_type, _n: str | None = dep_name) -> Any:
                return await container.get_async(_t, name=_n)

            return Lazy(resolver, async_resolver)

        return self._lazy_strategy.get(wrapper_factory, is_async_factory=False)  # type: ignore[no-any-return]

    def create_lazy_wrapper(
        self, container: "Container", dep_type: type, dep_name: str | None
    ) -> "Lazy[Any]":
        """Create a Lazy wrapper cached through this binding's scope strategy."""
        return self._build_lazy_wrapper(container, dep_type, dep_name, with_async=False)

    def create_lazy_wrapper_async(
        self, container: "Container", dep_type: type, dep_name: str | None
    ) -> "Lazy[Any]":
        """Create a Lazy wrapper with async support, cached via scope strategy."""
        return self._build_lazy_wrapper(container, dep_type, dep_name, with_async=True)

    def create_instance(self, container: "Container") -> Any:
        """Create an instance of the dependency (sync context)."""
        if self.instance is not None:
            return self.instance

        if self.factory is not None and not self._factory_has_params:
            factory_func = self.factory  # Parameterless fast-path
        else:
            binding = self

            def factory_func() -> Any:
                return container._instantiate_binding(binding)

        return self._strategy.get(factory_func, self._is_async_factory)

    async def create_instance_async(self, container: "Container") -> Any:
        """Create an instance of the dependency (async context)."""
        if self.instance is not None:
            return self.instance

        if self.factory is not None and not self._factory_has_params:
            factory_func = self.factory  # Parameterless fast-path
        else:
            binding = self

            async def factory_func() -> Any:
                return await container._instantiate_binding_async(binding)

        return await self._strategy.get_async(factory_func)
