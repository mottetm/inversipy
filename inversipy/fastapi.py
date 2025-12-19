"""FastAPI integration for inversipy dependency injection."""

import inspect
from collections.abc import Callable
from typing import Annotated, Any, get_args, get_origin, get_type_hints

from .container import Container
from .decorators import Inject, _InjectMarker

try:
    from fastapi import Depends, Request  # type: ignore[import-not-found]
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

    Example:
        ```python
        from fastapi import FastAPI
        from inversipy import Container

        app = FastAPI()
        app.state.container = Container()

        # Container is automatically available via Depends
        ```
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
    1. Identifying parameters marked with Inject[Type]
    2. Resolving them from the container
    3. Passing them to the original function

    The container is injected via FastAPI's Depends() mechanism.

    Example:
        ```python
        @app.get("/users")
        @inject
        async def get_users(
            db: Inject[Database],
            logger: Inject[Logger],
            limit: int = 10
        ):
            logger.info(f"Fetching {limit} users")
            return db.query("SELECT * FROM users LIMIT ?", limit)
        ```

    The above is transformed to:
        ```python
        async def get_users(
            container: Container = Depends(get_container),
            limit: int = 10
        ):
            db = container.get(Database)
            logger = container.get(Logger)
            return original_get_users(db, logger, limit)
        ```
    """
    # Get function signature and type hints
    sig = inspect.signature(func)
    type_hints = get_type_hints(func, include_extras=True)

    # Identify which parameters need injection vs normal parameters
    inject_params: dict[str, type] = {}
    normal_params: list[tuple[str, inspect.Parameter]] = []

    for param_name, param in sig.parameters.items():
        if param_name in type_hints:
            hint = type_hints[param_name]
            origin = get_origin(hint)

            # Check if this uses the Inject[T] type alias
            if origin is Inject:
                # Inject[T] expands to the type parameter
                args = get_args(hint)
                if args:
                    inject_params[param_name] = args[0]
            # Also support raw Annotated[Type, _InjectMarker] for compatibility
            elif origin is Annotated:
                args = get_args(hint)
                if len(args) >= 2:
                    actual_type = args[0]
                    metadata = args[1:]

                    # Check if Inject marker is in metadata
                    needs_injection = False
                    for meta in metadata:
                        if isinstance(meta, _InjectMarker):
                            needs_injection = True
                            break

                    if needs_injection:
                        inject_params[param_name] = actual_type
                    else:
                        normal_params.append((param_name, param))
                else:
                    normal_params.append((param_name, param))
            else:
                normal_params.append((param_name, param))
        else:
            normal_params.append((param_name, param))

    # Create wrapper function that FastAPI will actually call
    if inspect.iscoroutinefunction(func):

        async def wrapper(container: Container = Depends(get_container), **kwargs: Any) -> T:
            """Auto-generated async wrapper with dependency injection."""
            # Resolve injected dependencies from container
            injected: dict[str, Any] = {}
            for param_name, param_type in inject_params.items():
                injected[param_name] = container.get(param_type)

            # Merge with normal parameters passed by FastAPI
            all_params = {**kwargs, **injected}

            # Call original function with all parameters
            return await func(**all_params)  # type: ignore[no-any-return]

    else:

        def wrapper(container: Container = Depends(get_container), **kwargs: Any) -> T:  # type: ignore[misc]
            """Auto-generated wrapper with dependency injection."""
            # Resolve injected dependencies from container
            injected: dict[str, Any] = {}
            for param_name, param_type in inject_params.items():
                injected[param_name] = container.get(param_type)

            # Merge with normal parameters passed by FastAPI
            all_params = {**kwargs, **injected}

            # Call original function with all parameters
            return func(**all_params)

    # Build new signature for the wrapper
    # FastAPI will see: (<normal_params>, container: Container = Depends(...))
    new_params = []

    # Add normal (non-injected) parameters first
    for param_name, param in normal_params:
        new_params.append(param)

    # Add container as last keyword-only parameter
    new_params.append(
        inspect.Parameter(
            "container",
            inspect.Parameter.KEYWORD_ONLY,
            default=Depends(get_container),
            annotation=Container,
        )
    )

    wrapper.__signature__ = inspect.Signature(new_params)  # type: ignore
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__

    return wrapper  # type: ignore
