"""Binding strategies for different scopes.

This module provides strategies for managing dependency lifecycle based on scope.
Each strategy handles both sync and async contexts internally.
"""

import asyncio
import contextvars
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class BindingStrategy(ABC):
    """Abstract base class for binding strategies.

    Each concrete strategy handles both sync and async contexts, managing the
    lifecycle of dependencies according to its scope semantics.
    """

    @abstractmethod
    def get(self, factory: Callable[[], Any], is_async_factory: bool) -> Any:
        """Get an instance using the factory (sync context).

        Args:
            factory: Factory function to create the instance
            is_async_factory: Whether the original factory is async

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


class SingletonStrategy(BindingStrategy):
    """Singleton strategy - one instance per container.

    Handles both sync and async factories, ensuring only one instance is created.
    Thread-safe for both sync and async contexts.
    """

    def __init__(self) -> None:
        self._instance: Any | None = None
        self._initialized = False
        self._sync_lock = threading.Lock()
        self._async_lock = asyncio.Lock()

    def get(self, factory: Callable[[], Any], is_async_factory: bool) -> Any:
        if is_async_factory:
            from .exceptions import ResolutionError

            raise ResolutionError(
                "Cannot use synchronous get() with async factory. Use get_async() instead."
            )

        if not self._initialized:
            with self._sync_lock:
                if not self._initialized:  # Double-checked locking
                    self._instance = factory()
                    self._initialized = True
        return self._instance

    async def get_async(self, factory: Callable[[], Any]) -> Any:
        if not self._initialized:
            async with self._async_lock:
                if not self._initialized:
                    result = factory()
                    if asyncio.iscoroutine(result):
                        self._instance = await result
                    else:
                        self._instance = result
                    self._initialized = True
        return self._instance


class TransientStrategy(BindingStrategy):
    """Transient strategy - new instance per request.

    Creates a fresh instance each time, handling both sync and async factories.
    """

    def get(self, factory: Callable[[], Any], is_async_factory: bool) -> Any:
        if is_async_factory:
            from .exceptions import ResolutionError

            raise ResolutionError(
                "Cannot use synchronous get() with async factory. Use get_async() instead."
            )
        return factory()

    async def get_async(self, factory: Callable[[], Any]) -> Any:
        result = factory()
        if asyncio.iscoroutine(result):
            return await result
        return result


class RequestStrategy(BindingStrategy):
    """Request strategy - one instance per request context.

    Uses contextvars to maintain one instance per async context/request,
    handling both sync and async factories. Thread-safe for sync contexts.
    """

    def __init__(self) -> None:
        self._context_instance: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
            "request_scope_instance", default=None
        )
        self._sync_lock = threading.Lock()

    def get(self, factory: Callable[[], Any], is_async_factory: bool) -> Any:
        if is_async_factory:
            from .exceptions import ResolutionError

            raise ResolutionError(
                "Cannot use synchronous get() with async factory. Use get_async() instead."
            )

        instance = self._context_instance.get()
        if instance is None:
            with self._sync_lock:
                # Re-check after acquiring lock (double-checked locking)
                instance = self._context_instance.get()
                if instance is None:
                    instance = factory()
                    self._context_instance.set(instance)
        return instance

    async def get_async(self, factory: Callable[[], Any]) -> Any:
        instance = self._context_instance.get()
        if instance is None:
            result = factory()
            if asyncio.iscoroutine(result):
                instance = await result
            else:
                instance = result
            self._context_instance.set(instance)
        return instance
