"""Type definitions and protocols for the inversipy library."""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

type FactoryCallable[T] = Callable[..., T]


class Factory[T]:
    """Callable wrapper injected by the container.

    Each call resolves T from the container, respecting registered scopes.
    """

    __slots__ = ("_resolver", "_async_resolver")

    def __init__(
        self,
        resolver: Callable[[], T],
        async_resolver: Callable[[], Any] | None = None,
    ) -> None:
        self._resolver = resolver
        self._async_resolver = async_resolver

    def __call__(self) -> T:
        return self._resolver()

    async def acall(self) -> T:
        """Resolve T asynchronously."""
        if self._async_resolver is not None:
            return await self._async_resolver()  # type: ignore[no-any-return]
        return self._resolver()


class Lazy[T]:
    """Callable wrapper injected by the container.

    First call resolves T from the container. Subsequent calls return the cached instance.
    """

    __slots__ = ("_resolver", "_async_resolver", "_value", "_resolved", "_lock")

    def __init__(
        self,
        resolver: Callable[[], T],
        async_resolver: Callable[[], Any] | None = None,
    ) -> None:
        self._resolver = resolver
        self._async_resolver = async_resolver
        self._value: T | None = None
        self._resolved = False
        self._lock = threading.Lock()

    def __call__(self) -> T:
        if not self._resolved:
            with self._lock:
                if not self._resolved:
                    self._value = self._resolver()
                    self._resolved = True
        return self._value  # type: ignore[return-value]

    async def acall(self) -> T:
        """Resolve T asynchronously, caching the result."""
        if self._resolved:
            return self._value  # type: ignore[return-value]
        # Resolve outside the lock so awaits don't block other threads.
        if self._async_resolver is not None:
            value = await self._async_resolver()
        else:
            value = self._resolver()
        with self._lock:
            if not self._resolved:
                self._value = value
                self._resolved = True
        return self._value


@dataclass(frozen=True, slots=True, eq=False)
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

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(f"Named qualifier must be a string, got {type(self.name).__name__}")
        if not self.name or not self.name.strip():
            raise ValueError("Named qualifier cannot be empty or whitespace-only")

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

    def count(self, interface: type[Any], name: str | None = None) -> int:
        """Count the number of public implementations registered for an interface.

        Args:
            interface: The type to count implementations for
            name: Optional name qualifier for named bindings

        Returns:
            Number of registered public implementations
        """
        ...

    def get_all[T](self, interface: type[T], *, name: str | None = None) -> list[T]:
        """Resolve all public implementations of an interface synchronously.

        Args:
            interface: The type to resolve
            name: Optional name qualifier for named bindings

        Returns:
            List of resolved instances
        """
        ...

    async def get_all_async[T](self, interface: type[T], *, name: str | None = None) -> list[T]:
        """Resolve all public implementations of an interface asynchronously.

        Args:
            interface: The type to resolve
            name: Optional name qualifier for named bindings

        Returns:
            List of resolved instances
        """
        ...

    def freeze(self) -> None:
        """Freeze the module, preventing further registrations.

        After freezing, any registration method should raise RegistrationError.
        """
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
