"""FastAPI integration for inversipy dependency injection."""

import functools
import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from .container import Container
from .decorators import extract_inject_all_info, extract_inject_info

try:
    from fastapi import Depends, Request
except ImportError:
    raise ImportError(
        "FastAPI is required for inversipy.fastapi integration. "
        "Install it with: pip install fastapi"
    )


def get_container(request: Request) -> Container:
    """FastAPI dependency that returns the container from app.state.

    Args:
        request: FastAPI request object

    Returns:
        Container instance stored in app.state

    Raises:
        RuntimeError: If container hasn't been configured in app.state
    """
    if not hasattr(request.app.state, "container"):
        raise RuntimeError(
            "Container not configured in app.state. "
            "Set it with: app.state.container = Container()"
        )
    container: Container = request.app.state.container
    return container


def inject[T](func: Callable[..., T]) -> Callable[..., T]:
    """Decorator for FastAPI routes that auto-injects dependencies.

    Transforms route handlers by:
    1. Identifying parameters marked with Inject[Type], Inject[Type, Named("x")],
       InjectAll[Type], or InjectAll[Type, Named("x")]
    2. Resolving them from the container
    3. Passing them to the original function

    The container is injected via FastAPI's Depends() mechanism.
    """
    sig = inspect.signature(func)
    type_hints = get_type_hints(func, include_extras=True)

    # Categorize parameters
    inject_params: dict[str, tuple[type, str | None]] = {}
    inject_all_params: dict[str, tuple[type, str | None]] = {}
    normal_params: list[tuple[str, inspect.Parameter]] = []

    for param_name, param in sig.parameters.items():
        if param_name in type_hints:
            hint = type_hints[param_name]
            inject_all_info = extract_inject_all_info(hint)
            if inject_all_info is not None:
                inject_all_params[param_name] = inject_all_info
            else:
                inject_info = extract_inject_info(hint)
                if inject_info is not None:
                    inject_params[param_name] = inject_info
                else:
                    normal_params.append((param_name, param))
        else:
            normal_params.append((param_name, param))

    is_async = inspect.iscoroutinefunction(func)

    def _resolve_dependencies(container: Container) -> dict[str, Any]:
        """Resolve all injectable dependencies from the container."""
        injected: dict[str, Any] = {}
        for param_name, (param_type, dep_name) in inject_params.items():
            injected[param_name] = container.get(param_type, name=dep_name)
        for param_name, (item_type, coll_name) in inject_all_params.items():
            injected[param_name] = container.get_all(item_type, name=coll_name)
        return injected

    if is_async:

        @functools.wraps(func)
        async def wrapper(container: Container = Depends(get_container), **kwargs: Any) -> T:
            injected = _resolve_dependencies(container)
            all_params = {**kwargs, **injected}
            return await func(**all_params)  # type: ignore[misc,no-any-return]

    else:

        @functools.wraps(func)
        def wrapper(container: Container = Depends(get_container), **kwargs: Any) -> T:
            injected = _resolve_dependencies(container)
            all_params = {**kwargs, **injected}
            return func(**all_params)

    # Build new signature for FastAPI
    new_params = [param for _, param in normal_params]
    new_params.append(
        inspect.Parameter(
            "container",
            inspect.Parameter.KEYWORD_ONLY,
            default=Depends(get_container),
            annotation=Container,
        )
    )

    wrapper.__signature__ = inspect.Signature(new_params)  # type: ignore

    # Update __annotations__ to remove injected params (FastAPI uses this for validation)
    new_annotations = {
        name: param.annotation
        for name, param in normal_params
        if param.annotation != inspect.Parameter.empty
    }
    new_annotations["container"] = Container
    if "return" in type_hints:
        new_annotations["return"] = type_hints["return"]
    wrapper.__annotations__ = new_annotations

    return wrapper  # type: ignore
