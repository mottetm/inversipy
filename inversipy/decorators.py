"""Dependency injection utilities.

This module provides utilities for dependency injection without coupling
implementations to the container.
"""

from collections.abc import Callable
from typing import Annotated, Any, get_args, get_origin, get_type_hints


class _InjectMarker:
    """Internal marker class for dependency injection."""

    pass


# Singleton marker instance
_inject_marker = _InjectMarker()


type Inject[T] = Annotated[T, _inject_marker]
"""Type alias for dependency injection.

Use Inject[T] to mark class attributes or function parameters for injection.

Example:
    ```python
    from inversipy import Injectable, Inject

    class UserService(Injectable):
        database: Inject[Database]
        logger: Inject[Logger]

        def get_users(self):
            return self.database.query("SELECT * FROM users")

    container.register(UserService)
    service = container.get(UserService)
    ```
"""


class Injectable:
    """Base class for services using property-based dependency injection.

    Services that inherit from Injectable can use Annotated[Type, Inject] to declare
    dependencies as class attributes. The Injectable base class automatically generates
    a constructor that accepts these dependencies as parameters.

    This pattern keeps your classes decoupled from the container - they remain pure
    and can be instantiated manually or via the container.

    Example:
        ```python
        class UserService(Injectable):
            database: Annotated[Database, Inject]
            logger: Annotated[Logger, Inject]

            def get_users(self):
                return self.database.query("SELECT * FROM users")

        # Container resolves dependencies and passes them to __init__
        container.register(Database)
        container.register(Logger)
        container.register(UserService)
        service = container.get(UserService)

        # Can also instantiate manually - class remains pure
        service = UserService(database=my_db, logger=my_logger)
        ```
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Called when a class inherits from Injectable.

        Scans for Annotated[Type, Inject] attributes and generates __init__.
        """
        super().__init_subclass__(**kwargs)

        # Scan class annotations for Inject markers
        inject_fields: dict[str, type[Any]] = {}

        # Get type hints from the class to resolve type aliases
        # Use include_extras=True to preserve Annotated metadata
        try:
            annotations = get_type_hints(cls, include_extras=True)
        except Exception:
            # Fallback to raw annotations if get_type_hints fails
            annotations = getattr(cls, "__annotations__", {})

        for attr_name, annotation in annotations.items():
            origin = get_origin(annotation)

            # Check if this uses the Inject[T] type alias
            if origin is Inject:
                # Inject[T] expands to the type parameter
                args = get_args(annotation)
                if args:
                    inject_fields[attr_name] = args[0]
            # Also support raw Annotated[Type, _InjectMarker] for compatibility
            elif origin is Annotated:
                args = get_args(annotation)
                if len(args) >= 2:
                    # First arg is the actual type, rest are metadata
                    actual_type = args[0]
                    metadata = args[1:]

                    # Check if Inject marker is in metadata
                    for meta in metadata:
                        if isinstance(meta, _InjectMarker):
                            inject_fields[attr_name] = actual_type
                            break

        # Store inject fields metadata on the class
        setattr(cls, "_inject_fields", inject_fields)

        # Generate __init__ method
        if inject_fields:
            # Check if class already has custom __init__
            has_custom_init = "__init__" in cls.__dict__
            original_init = cls.__init__ if has_custom_init else None

            # Create function that accepts dependency parameters
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
            annotations["return"] = None
            new_init.__annotations__ = annotations

            # Create proper signature
            from inspect import Parameter, Signature

            params = [Parameter("self", Parameter.POSITIONAL_OR_KEYWORD)]
            for name, typ in zip(param_names, param_types):
                params.append(Parameter(name, Parameter.POSITIONAL_OR_KEYWORD, annotation=typ))
            new_init.__signature__ = Signature(params)  # type: ignore

            setattr(cls, "__init__", new_init)
