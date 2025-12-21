"""FastAPI integration for inversipy dependency injection."""

import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from .container import Container
from .decorators import extract_inject_all_info, extract_inject_info

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
    1. Identifying parameters marked with Inject[Type], Inject[Type, Named("x")],
       InjectAll[Type], or InjectAll[Type, Named("x")]
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
            primary_db: Inject[IDatabase, Named("primary")],
            plugins: InjectAll[IPlugin],
            core_plugins: InjectAll[IPlugin, Named("core")],
            limit: int = 10
        ):
            logger.info(f"Fetching {limit} users")
            for plugin in plugins:
                plugin.process()
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
            primary_db = container.get(IDatabase, name="primary")
            plugins = container.get_all(IPlugin)
            core_plugins = container.get_all(IPlugin, name="core")
            return original_get_users(db, logger, primary_db, plugins, core_plugins, limit)
        ```
    """
    # Get function signature and type hints
    sig = inspect.signature(func)
    type_hints = get_type_hints(func, include_extras=True)

    # Identify which parameters need injection vs normal parameters
    inject_params: dict[str, tuple[type, str | None]] = {}
    inject_all_params: dict[str, tuple[type, str | None]] = {}
    normal_params: list[tuple[str, inspect.Parameter]] = []

    for param_name, param in sig.parameters.items():
        if param_name in type_hints:
            hint = type_hints[param_name]
            # Check for InjectAll/InjectAllNamed first
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

    # Create wrapper function that FastAPI will actually call
    if inspect.iscoroutinefunction(func):

        async def wrapper(container: Container = Depends(get_container), **kwargs: Any) -> T:
            """Auto-generated async wrapper with dependency injection."""
            # Resolve injected dependencies from container
            injected: dict[str, Any] = {}
            for param_name, (param_type, dep_name) in inject_params.items():
                injected[param_name] = container.get(param_type, name=dep_name)
            for param_name, (item_type, coll_name) in inject_all_params.items():
                injected[param_name] = container.get_all(item_type, name=coll_name)

            # Merge with normal parameters passed by FastAPI
            all_params = {**kwargs, **injected}

            # Call original function with all parameters
            return await func(**all_params)  # type: ignore[no-any-return]

    else:

        def wrapper(container: Container = Depends(get_container), **kwargs: Any) -> T:  # type: ignore[misc]
            """Auto-generated wrapper with dependency injection."""
            # Resolve injected dependencies from container
            injected: dict[str, Any] = {}
            for param_name, (param_type, dep_name) in inject_params.items():
                injected[param_name] = container.get(param_type, name=dep_name)
            for param_name, (item_type, coll_name) in inject_all_params.items():
                injected[param_name] = container.get_all(item_type, name=coll_name)

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
