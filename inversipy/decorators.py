"""Decorators for dependency injection."""

import inspect
from typing import Any, Callable, Optional, Type, get_type_hints, get_args, get_origin, Annotated

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


class Injectable:
    """Base class for services using property-based dependency injection.

    Services that inherit from Injectable can use Annotated[Type, Inject] to declare
    dependencies as class attributes. The Injectable base class automatically generates
    a constructor that accepts these dependencies as parameters.

    Example:
        ```python
        class UserService(Injectable):
            database: Annotated[Database, Inject]
            logger: Annotated[Logger, Inject]

            def get_users(self):
                return self.database.query("SELECT * FROM users")

        container.register(Database)
        container.register(Logger)
        container.register(UserService)

        # Container resolves dependencies and passes them to __init__
        service = container.get(UserService)

        # Can also instantiate manually
        service = UserService(database=my_db, logger=my_logger)
        ```
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Called when a class inherits from Injectable.

        Scans for Annotated[Type, Inject()] attributes and generates __init__.
        """
        super().__init_subclass__(**kwargs)

        # Scan class annotations for Inject() markers
        inject_fields: dict[str, Type[Any]] = {}

        # Get annotations from the class (not inherited)
        annotations = getattr(cls, '__annotations__', {})

        for attr_name, annotation in annotations.items():
            # Check if this is Annotated[Type, Inject()]
            origin = get_origin(annotation)
            if origin is Annotated:
                args = get_args(annotation)
                if len(args) >= 2:
                    # First arg is the actual type, rest are metadata
                    actual_type = args[0]
                    metadata = args[1:]

                    # Check if Inject is in metadata
                    for meta in metadata:
                        if isinstance(meta, Inject) or meta is Inject or (
                            inspect.isclass(meta) and issubclass(meta, Inject)
                        ):
                            inject_fields[attr_name] = actual_type
                            # Note: We don't create descriptors anymore
                            # Dependencies are passed as constructor parameters
                            break

        # Store inject fields metadata on the class
        cls._inject_fields = inject_fields

        # Generate __init__ method
        if inject_fields:
            # Check if class already has custom __init__
            has_custom_init = '__init__' in cls.__dict__
            original_init = cls.__init__ if has_custom_init else None

            # Create function that accepts dependency parameters
            # Build parameter list and annotations
            import types

            # Create the __init__ function dynamically
            param_names = list(inject_fields.keys())
            param_types = list(inject_fields.values())

            # Build the function code
            def make_init(field_names: list[str]) -> Callable[..., None]:
                def __init__(self: Any, **kwargs: Any) -> None:
                    """Auto-generated __init__ that accepts dependencies."""
                    # Assign each dependency to the instance
                    for field_name in field_names:
                        if field_name in kwargs:
                            setattr(self, field_name, kwargs[field_name])

                    # Call original __init__ if it exists and is not object.__init__
                    if original_init is not None and original_init is not object.__init__:
                        original_init(self)

                return __init__

            new_init = make_init(param_names)

            # Set proper annotations on the function
            annotations = {name: typ for name, typ in zip(param_names, param_types)}
            annotations['return'] = None
            new_init.__annotations__ = annotations

            # Create proper signature
            from inspect import Parameter, Signature
            params = [Parameter('self', Parameter.POSITIONAL_OR_KEYWORD)]
            for name, typ in zip(param_names, param_types):
                params.append(Parameter(name, Parameter.POSITIONAL_OR_KEYWORD, annotation=typ))
            new_init.__signature__ = Signature(params)  # type: ignore

            cls.__init__ = new_init
