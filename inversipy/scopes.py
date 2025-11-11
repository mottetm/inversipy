"""Scope implementations for dependency injection."""

import asyncio
from typing import Any, Optional, Dict
from .types import Scope, AsyncScope as AsyncScopeBase, Factory, T


class SingletonScope(Scope):
    """Scope that ensures only one instance is created and reused."""

    def __init__(self) -> None:
        self._instance: Optional[Any] = None
        self._initialized = False

    def get(self, factory: Factory[T], *args: Any, **kwargs: Any) -> T:
        """Get or create the singleton instance.

        Args:
            factory: Factory function to create the instance
            *args: Positional arguments for the factory
            **kwargs: Keyword arguments for the factory

        Returns:
            The singleton instance
        """
        if not self._initialized:
            self._instance = factory(*args, **kwargs)
            self._initialized = True
        return self._instance  # type: ignore

    def reset(self) -> None:
        """Reset the singleton instance."""
        self._instance = None
        self._initialized = False


class TransientScope(Scope):
    """Scope that creates a new instance every time."""

    def get(self, factory: Factory[T], *args: Any, **kwargs: Any) -> T:
        """Create a new instance.

        Args:
            factory: Factory function to create the instance
            *args: Positional arguments for the factory
            **kwargs: Keyword arguments for the factory

        Returns:
            A new instance
        """
        return factory(*args, **kwargs)

    def reset(self) -> None:
        """No-op for transient scope."""
        pass


class RequestScope(Scope):
    """Scope that creates one instance per request/context.

    This scope maintains instances per context identifier.
    Useful for web frameworks where you want one instance per request.
    """

    def __init__(self) -> None:
        self._instances: Dict[str, Any] = {}
        self._current_context: Optional[str] = None

    def set_context(self, context_id: str) -> None:
        """Set the current context identifier.

        Args:
            context_id: Unique identifier for the current context
        """
        self._current_context = context_id

    def clear_context(self, context_id: str) -> None:
        """Clear instances for a specific context.

        Args:
            context_id: Context identifier to clear
        """
        self._instances.pop(context_id, None)

    def get(self, factory: Factory[T], *args: Any, **kwargs: Any) -> T:
        """Get or create an instance for the current context.

        Args:
            factory: Factory function to create the instance
            *args: Positional arguments for the factory
            **kwargs: Keyword arguments for the factory

        Returns:
            Instance for the current context

        Raises:
            RuntimeError: If no context is set
        """
        if self._current_context is None:
            raise RuntimeError("No context set for RequestScope")

        if self._current_context not in self._instances:
            self._instances[self._current_context] = factory(*args, **kwargs)

        return self._instances[self._current_context]

    def reset(self) -> None:
        """Clear all instances and reset the context."""
        self._instances.clear()
        self._current_context = None


class AsyncSingletonScope(AsyncScopeBase):
    """Async scope that ensures only one instance is created and reused."""

    def __init__(self) -> None:
        self._instance: Optional[Any] = None
        self._initialized = False
        self._lock = asyncio.Lock()

    async def get_async(self, factory: Factory[T], *args: Any, **kwargs: Any) -> T:
        """Get or create the singleton instance asynchronously.

        Args:
            factory: Factory function to create the instance
            *args: Positional arguments for the factory
            **kwargs: Keyword arguments for the factory

        Returns:
            The singleton instance
        """
        if not self._initialized:
            async with self._lock:
                if not self._initialized:  # Double-check locking
                    result = factory(*args, **kwargs)
                    # Handle async factories
                    if asyncio.iscoroutine(result):
                        self._instance = await result
                    else:
                        self._instance = result
                    self._initialized = True
        return self._instance  # type: ignore

    def get(self, factory: Factory[T], *args: Any, **kwargs: Any) -> T:
        """Synchronous get is not supported for async scope.

        Raises:
            NotImplementedError: Always raised
        """
        raise NotImplementedError("Use get_async for AsyncSingletonScope")

    def reset(self) -> None:
        """Reset the singleton instance."""
        self._instance = None
        self._initialized = False


# Convenience instances for common use cases
SINGLETON = SingletonScope()
TRANSIENT = TransientScope()
REQUEST = RequestScope()
