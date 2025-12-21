"""Dependency injection utilities.

This module provides utilities for dependency injection without coupling
implementations to the container.
"""

from collections.abc import Callable
from typing import Annotated, Any, get_args, get_origin, get_type_hints

from .types import Named


class _InjectMarker:
    """Internal marker class for dependency injection."""

    pass


class _InjectAllMarker:
    """Internal marker class for collection injection."""

    pass


# Singleton marker instances
_inject_marker = _InjectMarker()
_inject_all_marker = _InjectAllMarker()


type Inject[T, *Ts] = Annotated[T, _inject_marker, *Ts]

type InjectAll[T] = Annotated[list[T], _inject_all_marker]

# Store reference to the Inject TypeAliasType for runtime checks
_InjectAliasType = Inject  # type: ignore[type-arg]
_InjectAllAliasType = InjectAll  # type: ignore[type-arg]
"""Type alias for dependency injection with optional qualifiers.

Use Inject[T] to mark class attributes or function parameters for injection.
Use Inject[T, Named("qualifier")] for named dependencies.

Example:
    ```python
    from inversipy import Injectable, Inject, Named

    class UserService(Injectable):
        # Unnamed dependencies (most common case)
        database: Inject[Database]
        logger: Inject[Logger]

        # Named dependencies for multiple implementations
        primary_db: Inject[IDatabase, Named("primary")]
        replica_db: Inject[IDatabase, Named("replica")]

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
            database: Inject[Database]
            logger: Inject[Logger]

            # Named dependencies
            primary_db: Inject[IDatabase, Named("primary")]
            replica_db: Inject[IDatabase, Named("replica")]

            def get_users(self):
                return self.database.query("SELECT * FROM users")

        # Container resolves dependencies and passes them to __init__
        container.register(Database)
        container.register(Logger)
        container.register(IDatabase, PostgresDB, name="primary")
        container.register(IDatabase, MySQLDB, name="replica")
        container.register(UserService)
        service = container.get(UserService)

        # Can also instantiate manually - class remains pure
        service = UserService(database=my_db, logger=my_logger, ...)
        ```
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Called when a class inherits from Injectable.

        Scans for Inject[Type], Inject[Type, Named("x")], and InjectAll[Type] attributes
        and generates __init__.
        """
        super().__init_subclass__(**kwargs)

        # Scan class annotations for Inject and InjectAll markers
        # inject_fields stores (type, name | None) tuples for single dependencies
        inject_fields: dict[str, tuple[type[Any], str | None]] = {}
        # inject_all_fields stores the item type for collection dependencies
        inject_all_fields: dict[str, type[Any]] = {}

        # Get type hints from the class to resolve type aliases
        # Use include_extras=True to preserve Annotated metadata
        try:
            annotations = get_type_hints(cls, include_extras=True)
        except Exception:
            # Fallback to raw annotations if get_type_hints fails
            annotations = getattr(cls, "__annotations__", {})

        for attr_name, annotation in annotations.items():
            origin = get_origin(annotation)

            # Check if this uses the InjectAll TypeAliasType (Python 3.12+)
            if origin is _InjectAllAliasType:
                args = get_args(annotation)
                if args:
                    # First arg is the item type
                    inject_all_fields[attr_name] = args[0]
                continue

            # Check if this uses the Inject TypeAliasType (Python 3.12+)
            # When origin is the Inject TypeAliasType, it's implicitly an inject annotation
            if origin is _InjectAliasType:
                args = get_args(annotation)
                if args:
                    # First arg is the actual type
                    actual_type = args[0]
                    # Remaining args are qualifiers (e.g., Named)
                    named_qualifier: str | None = None
                    for arg in args[1:]:
                        if isinstance(arg, Named):
                            named_qualifier = arg.name
                    inject_fields[attr_name] = (actual_type, named_qualifier)
                continue

            # Also support raw Annotated[...] for compatibility
            if origin is Annotated:
                args = get_args(annotation)
                if len(args) >= 2:
                    # First arg is the actual type, rest are metadata
                    actual_type = args[0]
                    metadata = args[1:]

                    # Check for InjectAll marker first
                    for meta in metadata:
                        if isinstance(meta, _InjectAllMarker):
                            # Extract T from list[T]
                            list_origin = get_origin(actual_type)
                            if list_origin is list:
                                list_args = get_args(actual_type)
                                if list_args:
                                    inject_all_fields[attr_name] = list_args[0]
                            break

                    # Check for Inject marker and Named qualifier
                    if attr_name not in inject_all_fields:
                        has_inject = False
                        named_qualifier = None

                        for meta in metadata:
                            if isinstance(meta, _InjectMarker):
                                has_inject = True
                            elif isinstance(meta, Named):
                                named_qualifier = meta.name

                        if has_inject:
                            inject_fields[attr_name] = (actual_type, named_qualifier)

        # Store inject fields metadata on the class
        setattr(cls, "_inject_fields", inject_fields)
        setattr(cls, "_inject_all_fields", inject_all_fields)

        # Generate __init__ method
        if inject_fields or inject_all_fields:
            # Check if class already has custom __init__
            has_custom_init = "__init__" in cls.__dict__
            original_init = cls.__init__ if has_custom_init else None

            # Create function that accepts dependency parameters
            # Combine both inject_fields and inject_all_fields
            param_names = list(inject_fields.keys()) + list(inject_all_fields.keys())
            param_types: list[type[Any]] = [t for t, _ in inject_fields.values()]
            param_types.extend([list] for _ in inject_all_fields.values())  # type: ignore

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
            init_annotations: dict[str, Any] = {
                name: typ for name, typ in zip(list(inject_fields.keys()), [t for t, _ in inject_fields.values()])
            }
            # Add inject_all fields with list[T] annotation
            for name, item_type in inject_all_fields.items():
                init_annotations[name] = list[item_type]  # type: ignore
            init_annotations["return"] = None
            new_init.__annotations__ = init_annotations

            # Create proper signature
            from inspect import Parameter, Signature

            params = [Parameter("self", Parameter.POSITIONAL_OR_KEYWORD)]
            for name, typ in zip(param_names, param_types):
                params.append(Parameter(name, Parameter.POSITIONAL_OR_KEYWORD, annotation=typ))
            new_init.__signature__ = Signature(params)  # type: ignore

            setattr(cls, "__init__", new_init)


def extract_inject_info(type_hint: Any) -> tuple[type[Any], str | None] | None:
    """Extract type and optional name from an Inject annotation.

    This helper function analyzes a type hint to determine if it's an Inject
    annotation and extracts the actual type and optional Named qualifier.

    Args:
        type_hint: The type annotation to analyze

    Returns:
        A tuple of (actual_type, name | None) if this is an Inject annotation,
        None otherwise.

    Examples:
        >>> extract_inject_info(Inject[Database])
        (Database, None)

        >>> extract_inject_info(Inject[IDatabase, Named("primary")])
        (IDatabase, "primary")

        >>> extract_inject_info(int)
        None
    """
    origin = get_origin(type_hint)

    # Check if this uses the Inject TypeAliasType (Python 3.12+)
    if origin is _InjectAliasType:
        args = get_args(type_hint)
        if not args:
            return None
        actual_type = args[0]
        name: str | None = None
        for arg in args[1:]:
            if isinstance(arg, Named):
                name = arg.name
        return (actual_type, name)

    # Also support raw Annotated[Type, _InjectMarker, ...] for compatibility
    if origin is Annotated:
        args = get_args(type_hint)
        if len(args) < 2:
            return None

        actual_type = args[0]
        metadata = args[1:]

        has_inject = False
        name = None

        for meta in metadata:
            if isinstance(meta, _InjectMarker):
                has_inject = True
            elif isinstance(meta, Named):
                name = meta.name

        if has_inject:
            return (actual_type, name)

    return None


def extract_inject_all_type(type_hint: Any) -> type[Any] | None:
    """Extract item type from InjectAll[T] -> T.

    This helper function analyzes a type hint to determine if it's an InjectAll
    annotation and extracts the collection item type.

    Args:
        type_hint: The type annotation to analyze

    Returns:
        The item type T if this is InjectAll[T], None otherwise.

    Examples:
        >>> extract_inject_all_type(InjectAll[IPlugin])
        IPlugin

        >>> extract_inject_all_type(list[IPlugin])
        None

        >>> extract_inject_all_type(Inject[IPlugin])
        None
    """
    origin = get_origin(type_hint)

    # Check if this uses the InjectAll TypeAliasType (Python 3.12+)
    if origin is _InjectAllAliasType:
        args = get_args(type_hint)
        if args:
            return args[0]
        return None

    # Also support raw Annotated[list[T], _InjectAllMarker] for compatibility
    if origin is Annotated:
        args = get_args(type_hint)
        if len(args) < 2:
            return None

        actual_type = args[0]  # list[T]
        metadata = args[1:]

        for meta in metadata:
            if isinstance(meta, _InjectAllMarker):
                # Extract T from list[T]
                list_origin = get_origin(actual_type)
                if list_origin is list:
                    list_args = get_args(actual_type)
                    if list_args:
                        return list_args[0]
                break

    return None
