"""Scope implementations for dependency injection."""

import asyncio
import contextvars
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
    """Scope that creates one instance per request/context using contextvars.

    This scope leverages Python's contextvars module to maintain instances
    per async context or thread. Each context (async task, thread, etc.)
    automatically gets its own instance.

    Usage:
        # Automatic context isolation in async/threaded environments
        container.register(RequestService, scope=REQUEST)

        # Or use explicit context management
        with REQUEST.context():
            service = container.get(RequestService)
    """

    def __init__(self) -> None:
        # ContextVar to store the context-specific instance cache
        self._context_instances: contextvars.ContextVar[Dict[int, Any]] = (
            contextvars.ContextVar('request_scope_instances', default=None)
        )

    def context(self) -> "RequestScopeContext":
        """Create a new context scope for this request.

        Returns:
            Context manager for the request scope

        Example:
            with REQUEST.context():
                service = container.get(RequestService)
                # service is unique to this context
        """
        return RequestScopeContext(self)

    def get(self, factory: Factory[T], *args: Any, **kwargs: Any) -> T:
        """Get or create an instance for the current context.

        Args:
            factory: Factory function to create the instance
            *args: Positional arguments for the factory
            **kwargs: Keyword arguments for the factory

        Returns:
            Instance for the current context
        """
        # Get or create the instances dict for this context
        instances = self._context_instances.get()
        if instances is None:
            instances = {}
            self._context_instances.set(instances)

        # Use factory id as key
        factory_id = id(factory)

        if factory_id not in instances:
            instances[factory_id] = factory(*args, **kwargs)

        return instances[factory_id]

    def reset(self) -> None:
        """Clear all instances in the current context."""
        instances = self._context_instances.get()
        if instances is not None:
            instances.clear()


class RequestScopeContext:
    """Context manager for RequestScope.

    Creates a new context with isolated instances.
    """

    def __init__(self, scope: RequestScope) -> None:
        self._scope = scope
        self._token: Optional[contextvars.Token[Optional[Dict[int, Any]]]] = None

    def __enter__(self) -> "RequestScopeContext":
        """Enter the context and create a new isolated scope."""
        # Create a new empty dict for this context
        self._token = self._scope._context_instances.set({})
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context and restore the previous scope."""
        if self._token is not None:
            self._scope._context_instances.reset(self._token)


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
