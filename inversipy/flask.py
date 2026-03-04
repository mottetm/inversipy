"""Flask integration for inversipy dependency injection."""

import functools
import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from .container import Container
from .decorators import extract_inject_all_info, extract_inject_info

try:
    from flask import Flask, current_app
except ImportError:
    raise ImportError(
        "Flask is required for inversipy.flask integration. " "Install it with: pip install flask"
    )


def bind(app: Flask, container: Container) -> None:
    """Bind a container to a Flask application.

    Args:
        app: Flask application instance
        container: Container to bind
    """
    app.extensions["inversipy"] = container


def get_container() -> Container:
    """Get the container bound to the current Flask application.

    Returns:
        Container instance bound to the current app

    Raises:
        RuntimeError: If container hasn't been configured
    """
    container: Container | None = current_app.extensions.get("inversipy")
    if container is None:
        raise RuntimeError("Container not configured. " "Call bind(app, container) during setup.")
    return container


def inject[T](func: Callable[..., T]) -> Callable[..., T]:
    """Decorator for Flask routes that auto-injects dependencies.

    Transforms route handlers by:
    1. Identifying parameters marked with Inject[Type] or InjectAll[Type]
    2. Resolving them from the container
    3. Passing non-injected parameters through from Flask
    """
    sig = inspect.signature(func)
    type_hints = get_type_hints(func, include_extras=True)

    inject_params: dict[str, tuple[type, str | None]] = {}
    inject_all_params: dict[str, tuple[type, str | None]] = {}

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

    # If nothing to inject, return original function
    if not inject_params and not inject_all_params:
        return func

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        container = get_container()
        for param_name, (param_type, dep_name) in inject_params.items():
            kwargs[param_name] = container.get(param_type, name=dep_name)
        for param_name, (item_type, coll_name) in inject_all_params.items():
            kwargs[param_name] = container.get_all(item_type, name=coll_name)
        return func(*args, **kwargs)

    return wrapper
