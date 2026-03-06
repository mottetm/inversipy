"""Scope definitions for dependency injection."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .binding_strategies import BindingStrategy


class Scopes(StrEnum):
    """Enum defining available dependency scopes.

    Scopes determine the lifecycle of resolved dependencies:
    - SINGLETON: Single instance shared across the entire application
    - TRANSIENT: New instance created for each resolution
    - REQUEST: One instance per request/context (thread or async task)

    For custom scopes, see :class:`CustomScope`.

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


class CustomScope:
    """A custom scope that pairs a name with a BindingStrategy class.

    Custom scopes allow users to define their own lifecycle strategies
    beyond the built-in Singleton, Transient, and Request scopes.

    Example:
        ```python
        from inversipy import BindingStrategy, CustomScope, Container

        class ThreadLocalStrategy(BindingStrategy):
            def __init__(self):
                self._local = threading.local()

            def get(self, factory, is_async_factory):
                if not hasattr(self._local, 'instance'):
                    self._local.instance = factory()
                return self._local.instance

            async def get_async(self, factory):
                return self.get(factory, is_async_factory=False)

        THREAD_LOCAL = CustomScope("thread_local", ThreadLocalStrategy)
        container.register(MyService, scope=THREAD_LOCAL)
        ```
    """

    def __init__(self, name: str, strategy_class: type[BindingStrategy]) -> None:
        from .binding_strategies import BindingStrategy as _BindingStrategy

        if not (isinstance(strategy_class, type) and issubclass(strategy_class, _BindingStrategy)):
            raise TypeError(
                f"strategy_class must be a BindingStrategy subclass, got {strategy_class!r}"
            )
        self._name = name
        self._strategy_class = strategy_class

    @property
    def name(self) -> str:
        """The name of this custom scope."""
        return self._name

    @property
    def strategy_class(self) -> type[BindingStrategy]:
        """The BindingStrategy class associated with this scope."""
        return self._strategy_class

    def __repr__(self) -> str:
        return f"CustomScope({self._name!r}, {self._strategy_class.__name__})"


Scope = Scopes | CustomScope
