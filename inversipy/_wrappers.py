"""Factory / Lazy wrapper construction and dependency-formatting helpers.

These helpers are used by :class:`~inversipy.container.Container` during
dependency resolution. They live in their own module so resolution-time
wrapper creation is decoupled from container orchestration.
"""

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from .exceptions import AmbiguousDependencyError
from .types import Factory, Lazy, make_key

if TYPE_CHECKING:
    from .container import Container


def _format_dependency(dep_type: type, name: str | None = None) -> str:
    """Format a dependency type and optional name for error messages."""
    if name:
        return f"{dep_type.__name__}[name='{name}']"
    return dep_type.__name__


def _build_wrapper(
    wrapper_type: type,
    dep_type: type,
    dep_name: str | None,
    container: "Container",
    sync_resolver: Callable[..., Any],
    async_resolver: Callable[..., Coroutine[Any, Any, Any]] | None,
) -> Factory | Lazy:  # type: ignore[type-arg]
    """Construct a Factory or Lazy wrapper from prepared resolvers.

    Shared between the sync-only (_make_wrapper) and async-aware
    (_make_wrapper_async) entry points. The caller supplies the resolver
    closures; this helper handles the Factory/Lazy branching, the cached
    Lazy lookup via the binding's scope strategy, and the eager ambiguity
    check.
    """
    if wrapper_type is Factory:
        if async_resolver is not None:
            return Factory(sync_resolver, async_resolver)
        return Factory(sync_resolver)

    key = make_key(dep_type, dep_name)
    binding = container._find_binding(key)
    if binding is not None:
        if async_resolver is not None:
            return binding.create_lazy_wrapper_async(container, dep_type, dep_name)
        return binding.create_lazy_wrapper(container, dep_type, dep_name)

    # Raise eagerly if ambiguous, rather than deferring to Lazy call time
    bindings = container._bindings.get(key, [])
    if len(bindings) > 1:
        raise AmbiguousDependencyError(dep_type, len(bindings), container._name)

    if async_resolver is not None:
        return Lazy(sync_resolver, async_resolver)
    return Lazy(sync_resolver)


def _make_wrapper(
    wrapper_type: type, dep_type: type, dep_name: str | None, container: "Container"
) -> Factory | Lazy:  # type: ignore[type-arg]
    """Create a Factory or Lazy wrapper that resolves from the container."""

    def resolver(_t: type = dep_type, _n: str | None = dep_name) -> Any:
        return container.get(_t, name=_n)

    return _build_wrapper(wrapper_type, dep_type, dep_name, container, resolver, None)


def _make_wrapper_async(
    wrapper_type: type, dep_type: type, dep_name: str | None, container: "Container"
) -> Factory | Lazy:  # type: ignore[type-arg]
    """Create a Factory or Lazy wrapper with async resolution support."""

    def sync_resolver(_t: type = dep_type, _n: str | None = dep_name) -> Any:
        return container.get(_t, name=_n)

    async def async_resolver(_t: type = dep_type, _n: str | None = dep_name) -> Any:
        return await container.get_async(_t, name=_n)

    return _build_wrapper(
        wrapper_type, dep_type, dep_name, container, sync_resolver, async_resolver
    )
