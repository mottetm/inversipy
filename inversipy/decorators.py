"""Decorators for dependency injection."""

import inspect
from typing import Any, Callable, Optional, Type, get_type_hints

from .container import Container
from .scopes import Scopes


def injectable[T](
    container: Container,
    interface: Optional[Type[Any]] = None,
    scope: Scopes = Scopes.TRANSIENT,
) -> Callable[[Type[T]], Type[T]]:
    """Decorator to mark a class as injectable and register it in a container.

    Args:
        container: Container to register the class in
        interface: Optional interface type to bind to (defaults to the class itself)
        scope: Scope for the dependency lifecycle

    Returns:
        Decorator function

    Example:
        ```python
        @injectable(container, scope=Scopes.SINGLETON)
        class MyService:
            pass
        ```
    """

    def decorator(cls: Type[T]) -> Type[T]:
        target = interface if interface is not None else cls
        container.register(target, implementation=cls, scope=scope)
        return cls

    return decorator


def singleton[T](
    container: Container, interface: Optional[Type[Any]] = None
) -> Callable[[Type[T]], Type[T]]:
    """Decorator to register a class as a singleton.

    Args:
        container: Container to register the class in
        interface: Optional interface type to bind to

    Returns:
        Decorator function

    Example:
        ```python
        @singleton(container)
        class MyService:
            pass
        ```
    """
    return injectable(container, interface, Scopes.SINGLETON)


def transient[T](
    container: Container, interface: Optional[Type[Any]] = None
) -> Callable[[Type[T]], Type[T]]:
    """Decorator to register a class as transient (new instance each time).

    Args:
        container: Container to register the class in
        interface: Optional interface type to bind to

    Returns:
        Decorator function

    Example:
        ```python
        @transient(container)
        class MyService:
            pass
        ```
    """
    return injectable(container, interface, Scopes.TRANSIENT)


def inject[T](container: Container) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to inject dependencies into a function.

    Args:
        container: Container to resolve dependencies from

    Returns:
        Decorator function

    Example:
        ```python
        @inject(container)
        def my_function(service: MyService):
            return service.do_something()
        ```
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Get type hints for the function
            try:
                type_hints = get_type_hints(func)
            except Exception:
                type_hints = {}

            type_hints.pop("return", None)

            # Get function signature
            sig = inspect.signature(func)

            # Resolve dependencies for parameters not provided
            resolved_kwargs = kwargs.copy()

            for param_name, param in sig.parameters.items():
                # Skip if already provided
                if param_name in kwargs or param_name in [
                    "self",
                    "cls",
                ]:
                    continue

                # Get the type hint
                param_type = type_hints.get(param_name)

                if param_type is not None:
                    try:
                        resolved_kwargs[param_name] = container.get(param_type)
                    except Exception:
                        # If resolution fails and no default, let function handle it
                        if param.default is inspect.Parameter.empty:
                            pass

            return func(*args, **resolved_kwargs)

        return wrapper

    return decorator


class Inject[T]:
    """Descriptor for property-based dependency injection.

    Example:
        ```python
        class MyClass:
            service = Inject(MyService)

            def __init__(self, container: Container):
                self._container = container

            def do_something(self):
                return self.service.do_something()
        ```
    """

    def __init__(self, dependency_type: Type[T]) -> None:
        """Initialize the inject descriptor.

        Args:
            dependency_type: Type of dependency to inject
        """
        self.dependency_type = dependency_type
        self.attr_name = f"_injected_{id(self)}"

    def __get__(self, obj: Any, objtype: Optional[Type[Any]] = None) -> T:
        """Get the injected dependency.

        Args:
            obj: Instance to get the dependency for
            objtype: Type of the instance

        Returns:
            The injected dependency
        """
        if obj is None:
            return self  # type: ignore

        # Check if already cached
        if not hasattr(obj, self.attr_name):
            # Get container from object
            if not hasattr(obj, "_container"):
                raise AttributeError(
                    f"{obj.__class__.__name__} must have a '_container' attribute "
                    "to use Inject descriptor"
                )
            container = getattr(obj, "_container")
            # Resolve and cache
            value = container.get(self.dependency_type)
            setattr(obj, self.attr_name, value)

        return getattr(obj, self.attr_name)
