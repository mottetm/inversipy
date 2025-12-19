"""Type definitions and protocols for the inversipy library."""

from collections.abc import Callable
from typing import Any, Protocol

type Factory[T] = Callable[..., T]


class ModuleProtocol(Protocol):
    """Protocol defining the interface required for module registration.

    Any object implementing this protocol can be registered with a Container
    using register_module(). This provides type safety and clear documentation
    of the module contract.

    The module is responsible for enforcing its own access control rules.
    If a requested dependency is not publicly accessible, get() should raise
    DependencyNotFoundError, and has() should return False.
    """

    def get[T](self, interface: type[T]) -> T:
        """Resolve a dependency synchronously.

        Args:
            interface: The type to resolve

        Returns:
            Resolved instance of the dependency

        Raises:
            DependencyNotFoundError: If the dependency is not registered or not public
        """
        ...

    async def get_async[T](self, interface: type[T]) -> T:
        """Resolve a dependency asynchronously.

        Args:
            interface: The type to resolve

        Returns:
            Resolved instance of the dependency

        Raises:
            DependencyNotFoundError: If the dependency is not registered or not public
        """
        ...

    def has(self, interface: type[Any]) -> bool:
        """Check if a dependency is publicly available without creating an instance.

        Args:
            interface: The type to check

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
DependencyKey = type | str
