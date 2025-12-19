"""Binding strategies for different scopes and sync/async scenarios."""

import asyncio
import contextvars
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class BindingStrategy(ABC):
    """Abstract base class for binding strategies."""

    @abstractmethod
    def get(self, factory: Callable[[], Any]) -> Any:
        """Get an instance using the factory (sync context).

        Args:
            factory: Factory function to create the instance

        Returns:
            Instance of the dependency

        Raises:
            ResolutionError: If async factory is used in sync context
        """
        pass

    @abstractmethod
    async def get_async(self, factory: Callable[[], Any]) -> Any:
        """Get an instance using the factory (async context).

        Args:
            factory: Factory function to create the instance

        Returns:
            Instance of the dependency
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset the strategy state."""
        pass


class SyncSingletonStrategy(BindingStrategy):
    """Singleton strategy for synchronous factories."""

    def __init__(self) -> None:
        self._instance: Any | None = None
        self._initialized = False

    def get(self, factory: Callable[[], Any]) -> Any:
        if not self._initialized:
            self._instance = factory()
            self._initialized = True
        return self._instance

    async def get_async(self, factory: Callable[[], Any]) -> Any:
        # Handle both sync and async factories in async context
        if not self._initialized:
            result = factory()
            if asyncio.iscoroutine(result):
                self._instance = await result
            else:
                self._instance = result
            self._initialized = True
        return self._instance

    def reset(self) -> None:
        self._instance = None
        self._initialized = False


class AsyncSingletonStrategy(BindingStrategy):
    """Singleton strategy for asynchronous factories."""

    def __init__(self) -> None:
        self._instance: Any | None = None
        self._initialized = False
        self._lock = asyncio.Lock()

    def get(self, factory: Callable[[], Any]) -> Any:
        from .exceptions import ResolutionError

        raise ResolutionError(
            "Cannot use synchronous get() with async factory. " "Use get_async() instead."
        )

    async def get_async(self, factory: Callable[[], Any]) -> Any:
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    self._instance = await factory()
                    self._initialized = True
        return self._instance

    def reset(self) -> None:
        self._instance = None
        self._initialized = False


class SyncTransientStrategy(BindingStrategy):
    """Transient strategy for synchronous factories."""

    def get(self, factory: Callable[[], Any]) -> Any:
        return factory()

    async def get_async(self, factory: Callable[[], Any]) -> Any:
        # Handle both sync and async factories in async context
        result = factory()
        if asyncio.iscoroutine(result):
            return await result
        return result

    def reset(self) -> None:
        pass


class AsyncTransientStrategy(BindingStrategy):
    """Transient strategy for asynchronous factories."""

    def get(self, factory: Callable[[], Any]) -> Any:
        from .exceptions import ResolutionError

        raise ResolutionError(
            "Cannot use synchronous get() with async factory. " "Use get_async() instead."
        )

    async def get_async(self, factory: Callable[[], Any]) -> Any:
        return await factory()

    def reset(self) -> None:
        pass


class SyncRequestStrategy(BindingStrategy):
    """Request strategy for synchronous factories using contextvars."""

    def __init__(self) -> None:
        self._context_instances: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
            "sync_request_scope_instance", default=None
        )

    def get(self, factory: Callable[[], Any]) -> Any:
        instance = self._context_instances.get()
        if instance is None:
            instance = factory()
            self._context_instances.set(instance)
        return instance

    async def get_async(self, factory: Callable[[], Any]) -> Any:
        # Handle both sync and async factories - contextvars work in async contexts
        instance = self._context_instances.get()
        if instance is None:
            result = factory()
            if asyncio.iscoroutine(result):
                instance = await result
            else:
                instance = result
            self._context_instances.set(instance)
        return instance

    def reset(self) -> None:
        self._context_instances.set(None)


class AsyncRequestStrategy(BindingStrategy):
    """Request strategy for asynchronous factories using contextvars."""

    def __init__(self) -> None:
        self._context_instances: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
            "async_request_scope_instance", default=None
        )

    def get(self, factory: Callable[[], Any]) -> Any:
        from .exceptions import ResolutionError

        raise ResolutionError(
            "Cannot use synchronous get() with async factory. " "Use get_async() instead."
        )

    async def get_async(self, factory: Callable[[], Any]) -> Any:
        instance = self._context_instances.get()
        if instance is None:
            instance = await factory()
            self._context_instances.set(instance)
        return instance

    def reset(self) -> None:
        self._context_instances.set(None)
