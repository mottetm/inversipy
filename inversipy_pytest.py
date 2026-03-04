"""Pytest plugin for inversipy dependency injection.

This module is loaded by pytest via the ``pytest11`` entry point.
It lives outside the ``inversipy`` package so that loading the plugin
does not trigger an early import of the library (which would defeat
``pytest-cov`` coverage measurement).
"""

import functools
import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, get_type_hints

import pytest

if TYPE_CHECKING:
    from inversipy.container import Container


@pytest.fixture
def container() -> "Container":
    """Default container fixture. Override in your conftest.py."""
    from inversipy.container import Container

    return Container()


def inject[T](func: Callable[..., T]) -> Callable[..., T]:
    """Decorator for test functions that auto-injects dependencies.

    Resolves parameters marked with Inject[Type] or InjectAll[Type] from the
    ``container`` fixture. Non-injected parameters are passed through for
    normal pytest fixture resolution.

    Example::

        @inject
        def test_user_creation(service: Inject[UserService]):
            assert service.create("alice") is not None
    """
    from inversipy.decorators import extract_inject_all_info, extract_inject_info

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

    if not inject_params and not inject_all_params:
        return func

    @functools.wraps(func)
    def wrapper(*args: Any, container: Any, **kwargs: Any) -> T:
        for param_name, (param_type, dep_name) in inject_params.items():
            kwargs[param_name] = container.get(param_type, name=dep_name)
        for param_name, (item_type, coll_name) in inject_all_params.items():
            kwargs[param_name] = container.get_all(item_type, name=coll_name)
        return func(*args, **kwargs)

    # Rewrite signature so pytest sees `container` as a fixture request
    # and does NOT see the injected params
    old_params = sig.parameters
    new_params: list[inspect.Parameter] = []
    for name, param in old_params.items():
        if name not in inject_params and name not in inject_all_params:
            new_params.append(param)

    # Add container if not already present
    if "container" not in old_params:
        new_params.append(inspect.Parameter("container", inspect.Parameter.KEYWORD_ONLY))

    wrapper.__signature__ = inspect.Signature(new_params)  # type: ignore[attr-defined]

    return wrapper  # type: ignore[return-value,unused-ignore]
