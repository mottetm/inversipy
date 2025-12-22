"""Type definitions and protocols for the inversipy library."""

from collections.abc import Callable
from typing import Any, Protocol

type Factory[T] = Callable[..., T]


class Named:
    """Qualifier for named dependency injection.

    Use Named to distinguish between multiple implementations of the same interface.

    Usage in type annotations:
        primary_db: Inject[IDatabase, Named("primary")]
        replica_db: Inject[IDatabase, Named("replica")]

    Usage in registration:
        container.register(IDatabase, PostgresDB, name="primary")
        container.register(IDatabase, MySQLDB, name="replica")

    Usage in resolution:
        primary = container.get(IDatabase, name="primary")
        replica = container.get(IDatabase, name="replica")
    """

    __slots__ = ("name",)
    __match_args__ = ("name",)

    def __init__(self, name: str) -> None:
        """Initialize a Named qualifier.

        Args:
            name: The qualifier name for this dependency

        Raises:
            TypeError: If name is not a string
            ValueError: If name is empty or whitespace-only
        """
        if not isinstance(name, str):
            raise TypeError(f"Named qualifier must be a string, got {type(name).__name__}")
        if not name or not name.strip():
            raise ValueError("Named qualifier cannot be empty or whitespace-only")
        self.name = name

    def __repr__(self) -> str:
        return f'Named("{self.name}")'

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Named) and other.name == self.name

    def __hash__(self) -> int:
        return hash(("Named", self.name))


class ModuleProtocol(Protocol):
    """Protocol defining the interface required for module registration.

    Any object implementing this protocol can be registered with a Container
    using register_module(). This provides type safety and clear documentation
    of the module contract.

    The module is responsible for enforcing its own access control rules.
    If a requested dependency is not publicly accessible, get() should raise
    DependencyNotFoundError, and has() should return False.
    """

    def get[T](self, interface: type[T], name: str | None = None) -> T:
        """Resolve a dependency synchronously.

        Args:
            interface: The type to resolve
            name: Optional name qualifier for named bindings

        Returns:
            Resolved instance of the dependency

        Raises:
            DependencyNotFoundError: If the dependency is not registered or not public
        """
        ...

    async def get_async[T](self, interface: type[T], name: str | None = None) -> T:
        """Resolve a dependency asynchronously.

        Args:
            interface: The type to resolve
            name: Optional name qualifier for named bindings

        Returns:
            Resolved instance of the dependency

        Raises:
            DependencyNotFoundError: If the dependency is not registered or not public
        """
        ...

    def has(self, interface: type[Any], name: str | None = None) -> bool:
        """Check if a dependency is publicly available without creating an instance.

        Args:
            interface: The type to check
            name: Optional name qualifier for named bindings

        Returns:
            True if the dependency is registered and public, False otherwise
        """
        ...


class Provider[T](Protocol):
    """Protocol for dependency providers."""

    def __call__(self) -> T:
        """Provide an instance of the dependency."""
        ...


# Type alias for dependency identifiers
# Can be: type alone, or (type, name) tuple for named bindings
type DependencyKey = type | tuple[type, str]


def make_key(interface: type, name: str | None) -> DependencyKey:
    """Create a dependency key from type and optional name.

    Args:
        interface: The type to create a key for
        name: Optional name qualifier

    Returns:
        The dependency key: type if no name, (type, name) tuple if named
    """
    return (interface, name) if name else interface


def get_type_from_key(key: DependencyKey) -> type:
    """Extract the type from a dependency key.

    Args:
        key: The dependency key

    Returns:
        The type part of the key

    Raises:
        ValueError: If key is not a valid DependencyKey
    """
    match key:
        case (t, _):
            return t  # type: ignore[return-value]
        case _:
            return key  # type: ignore[return-value]
