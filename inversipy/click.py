"""Click integration for inversipy dependency injection."""

import functools
import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from .container import Container
from .decorators import extract_inject_all_info, extract_inject_info
from .types import ModuleProtocol

try:
    import click
except ImportError:
    raise ImportError(
        "Click is required for inversipy.click integration. " "Install it with: pip install click"
    )

CONTAINER_KEY = "container"


def _get_container_from_context(key: str = CONTAINER_KEY) -> Container:
    """Retrieve the container from the current Click context."""
    ctx = click.get_current_context()
    if ctx.obj is None or not isinstance(ctx.obj, dict) or key not in ctx.obj:
        raise RuntimeError(
            f"Container not found in Click context. "
            f"Set it with @pass_container(container) on your group, "
            f"or store it manually: ctx.obj['{key}'] = container"
        )
    container: Container = ctx.obj[key]
    return container


def inject[T](func: Callable[..., T]) -> Callable[..., T]:
    """Decorator for Click commands that auto-injects dependencies.

    Transforms command callbacks by:
    1. Identifying parameters marked with Inject[Type], Inject[Type, Named("x")],
       InjectAll[Type], or InjectAll[Type, Named("x")]
    2. Resolving them from the container stored in Click's context
    3. Passing them to the original function

    The container must be stored in ctx.obj["container"] (see pass_container).
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

    @functools.wraps(func)
    def wrapper(**kwargs: Any) -> T:
        container = _get_container_from_context()

        # Resolve dependencies
        injected: dict[str, Any] = {}
        for param_name, (param_type, dep_name) in inject_params.items():
            injected[param_name] = container.get(param_type, name=dep_name)
        for param_name, (item_type, coll_name) in inject_all_params.items():
            injected[param_name] = container.get_all(item_type, name=coll_name)

        all_params = {**kwargs, **injected}
        return func(**all_params)

    # Rewrite signature to exclude injected params (Click inspects this)
    new_params = [param for _, param in normal_params]
    wrapper.__signature__ = inspect.Signature(new_params)  # type: ignore[attr-defined]

    # Preserve Click's decorator metadata
    wrapper.__click_params__ = getattr(func, "__click_params__", [])  # type: ignore[attr-defined]

    return wrapper


def pass_container(
    container: Container, key: str = CONTAINER_KEY
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that stores a container in Click's context object.

    Use this on a click.group() to make the container available to all subcommands:

        @click.group()
        @pass_container(container)
        def cli():
            pass
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @click.pass_context
        @functools.wraps(func)
        def wrapper(ctx: click.Context, *args: Any, **kwargs: Any) -> Any:
            ctx.ensure_object(dict)
            ctx.obj[key] = container
            return ctx.invoke(func, *args, **kwargs)

        return wrapper

    return decorator


def with_modules(
    *modules: ModuleProtocol, key: str = CONTAINER_KEY
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that registers modules on the container in Click's context.

    Use this on a click.group() to register domain-specific modules:

        @cli.group()
        @with_modules(AuthModule())
        def auth():
            pass

    Modules are registered directly on the shared container. Since Click only
    executes one command path per invocation, there is no cross-group leaking.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @click.pass_context
        @functools.wraps(func)
        def wrapper(ctx: click.Context, *args: Any, **kwargs: Any) -> Any:
            if ctx.obj is None or not isinstance(ctx.obj, dict) or key not in ctx.obj:
                raise RuntimeError(
                    "Container not found in Click context. "
                    "Ensure @pass_container(container) is applied to a parent group."
                )
            container: Container = ctx.obj[key]
            for module in modules:
                container.register_module(module)
            return ctx.invoke(func, *args, **kwargs)

        return wrapper

    return decorator
