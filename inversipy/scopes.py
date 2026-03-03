"""Scope definitions for dependency injection."""

from enum import StrEnum


class Scopes(StrEnum):
    """Enum defining available dependency scopes.

    Scopes determine the lifecycle of resolved dependencies:
    - SINGLETON: Single instance shared across the entire application
    - TRANSIENT: New instance created for each resolution
    - REQUEST: One instance per request/context (thread or async task)

    The container automatically detects async factories and handles them appropriately.

    Example:
        ```python
        from inversipy import Container, Scopes

        # Sync factory with singleton scope
        container.register(DatabaseService, scope=Scopes.SINGLETON)

        # Async factory - automatically handled
        async def create_async_service():
            return await AsyncService.create()

        container.register_factory(AsyncService, create_async_service, scope=Scopes.SINGLETON)
        service = await container.get_async(AsyncService)
        ```
    """

    SINGLETON = "singleton"
    TRANSIENT = "transient"
    REQUEST = "request"
