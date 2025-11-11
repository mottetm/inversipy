"""Type definitions and protocols for the inversipy library."""

from typing import Any, Callable, Protocol, Type, Union
from abc import ABC, abstractmethod

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

    def get[T](self, interface: Type[T]) -> T:
        """Resolve a dependency synchronously.

        Args:
            interface: The type to resolve

        Returns:
            Resolved instance of the dependency

        Raises:
            DependencyNotFoundError: If the dependency is not registered or not public
        """
        ...

    async def get_async[T](self, interface: Type[T]) -> T:
        """Resolve a dependency asynchronously.

        Args:
            interface: The type to resolve

        Returns:
            Resolved instance of the dependency

        Raises:
            DependencyNotFoundError: If the dependency is not registered or not public
        """
        ...

    def has(self, interface: Type[Any]) -> bool:
        """Check if a dependency is publicly available without creating an instance.

        Args:
            interface: The type to check

        Returns:
            True if the dependency is registered and public, False otherwise
        """
        ...


class Scope(ABC):
    """Abstract base class for dependency scopes."""

    @abstractmethod
    def get[T](self, factory: Factory[T], *args: Any, **kwargs: Any) -> T:
        """Get an instance using the factory function.

        Args:
            factory: Factory function to create the instance
            *args: Positional arguments for the factory
            **kwargs: Keyword arguments for the factory

        Returns:
            Instance of type T
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset the scope state (if applicable)."""
        pass


class AsyncScope(Scope):
    """Abstract base class for async scopes."""

    @abstractmethod
    async def get_async[T](self, factory: Factory[T], *args: Any, **kwargs: Any) -> T:
        """Asynchronously get an instance using the factory function.

        Args:
            factory: Factory function to create the instance
            *args: Positional arguments for the factory
            **kwargs: Keyword arguments for the factory

        Returns:
            Instance of type T
        """
        pass


class Provider[T](Protocol):
    """Protocol for dependency providers."""

    def __call__(self) -> T:
        """Provide an instance of the dependency."""
        ...


# Type alias for dependency identifiers
DependencyKey = Union[type, str]
