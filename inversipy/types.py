"""Type definitions and protocols for the inversipy library."""

from typing import Any, Callable, Protocol, Union
from abc import ABC, abstractmethod

type Factory[T] = Callable[..., T]


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
