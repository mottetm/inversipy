"""Tests for custom scope support via CustomScope."""

import asyncio
import threading
from collections.abc import Callable
from typing import Any

import pytest

from inversipy import (
    BindingStrategy,
    Container,
    CustomScope,
    InvalidScopeError,
    Module,
    ModuleBuilder,
    Scopes,
)

# --- Test strategies ---


class CountingStrategy(BindingStrategy):
    """Strategy that creates a new instance each time, tracking call count."""

    def __init__(self) -> None:
        self.call_count = 0

    def get(self, factory: Callable[[], Any], is_async_factory: bool) -> Any:
        self.call_count += 1
        return factory()

    async def get_async(self, factory: Callable[[], Any]) -> Any:
        self.call_count += 1
        result = factory()
        if asyncio.iscoroutine(result):
            return await result
        return result


class ThreadLocalStrategy(BindingStrategy):
    """One instance per thread."""

    def __init__(self) -> None:
        self._local = threading.local()

    def get(self, factory: Callable[[], Any], is_async_factory: bool) -> Any:
        if not hasattr(self._local, "instance"):
            self._local.instance = factory()
        return self._local.instance

    async def get_async(self, factory: Callable[[], Any]) -> Any:
        if not hasattr(self._local, "instance"):
            result = factory()
            if asyncio.iscoroutine(result):
                self._local.instance = await result
            else:
                self._local.instance = result
        return self._local.instance


# --- Test fixtures ---

COUNTING = CustomScope("counting", CountingStrategy)
THREAD_LOCAL = CustomScope("thread_local", ThreadLocalStrategy)


class Service:
    pass


class AsyncService:
    @classmethod
    async def create(cls) -> "AsyncService":
        return cls()


# --- Tests ---


class TestCustomScopeBasic:
    """Basic custom scope functionality."""

    def test_custom_scope_resolve(self) -> None:
        container = Container()
        container.register(Service, scope=COUNTING)
        s1 = container.get(Service)
        s2 = container.get(Service)
        assert isinstance(s1, Service)
        assert isinstance(s2, Service)
        # CountingStrategy creates new instance each time
        assert s1 is not s2

    def test_custom_scope_name_property(self) -> None:
        scope = CustomScope("my_scope", CountingStrategy)
        assert scope.name == "my_scope"

    def test_custom_scope_strategy_class_property(self) -> None:
        scope = CustomScope("test", CountingStrategy)
        assert scope.strategy_class is CountingStrategy

    def test_custom_scope_invalid_strategy_class(self) -> None:
        with pytest.raises(TypeError, match="BindingStrategy subclass"):
            CustomScope("bad", str)  # type: ignore[arg-type]

    def test_custom_scope_invalid_strategy_not_a_class(self) -> None:
        with pytest.raises(TypeError, match="BindingStrategy subclass"):
            CustomScope("bad", lambda: None)  # type: ignore[arg-type]

    def test_two_scopes_same_name_different_strategies(self) -> None:
        scope_a = CustomScope("same_name", CountingStrategy)
        scope_b = CustomScope("same_name", ThreadLocalStrategy)
        # They are distinct objects even with the same name
        assert scope_a is not scope_b
        assert scope_a.strategy_class is not scope_b.strategy_class

    def test_repr(self) -> None:
        scope = CustomScope("counting", CountingStrategy)
        assert repr(scope) == "CustomScope('counting', CountingStrategy)"


class TestCustomScopeAsync:
    """Custom scope with async factories."""

    async def test_async_factory_with_custom_scope(self) -> None:
        container = Container()
        container.register_factory(AsyncService, AsyncService.create, scope=COUNTING)
        service = await container.get_async(AsyncService)
        assert isinstance(service, AsyncService)

    async def test_thread_local_scope_async(self) -> None:
        container = Container()
        container.register(Service, scope=THREAD_LOCAL)
        s1 = await container.get_async(Service)
        s2 = await container.get_async(Service)
        # Same thread, so same instance
        assert s1 is s2


class TestCustomScopeWithThreadLocal:
    """Thread-local custom scope behavior."""

    def test_thread_local_same_thread(self) -> None:
        container = Container()
        container.register(Service, scope=THREAD_LOCAL)
        s1 = container.get(Service)
        s2 = container.get(Service)
        assert s1 is s2

    def test_thread_local_different_threads(self) -> None:
        container = Container()
        container.register(Service, scope=THREAD_LOCAL)

        results: dict[str, Service] = {}

        def resolve_in_thread(key: str) -> None:
            results[key] = container.get(Service)

        t1 = threading.Thread(target=resolve_in_thread, args=("t1",))
        t2 = threading.Thread(target=resolve_in_thread, args=("t2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["t1"] is not results["t2"]


class TestCustomScopeBuiltinUnchanged:
    """Built-in scopes continue to work."""

    def test_singleton_still_works(self) -> None:
        container = Container()
        container.register(Service, scope=Scopes.SINGLETON)
        assert container.get(Service) is container.get(Service)

    def test_transient_still_works(self) -> None:
        container = Container()
        container.register(Service, scope=Scopes.TRANSIENT)
        assert container.get(Service) is not container.get(Service)


class TestCustomScopeErrors:
    """Error handling for invalid scopes."""

    def test_unknown_string_scope_raises(self) -> None:
        container = Container()
        with pytest.raises(InvalidScopeError, match="Unknown scope"):
            container.register(Service, scope="nonexistent")  # type: ignore[arg-type]


class TestCustomScopeWithModules:
    """Custom scopes in modules."""

    def test_module_with_custom_scope(self) -> None:
        module = Module("test")
        module.register(Service, scope=COUNTING, public=True)

        container = Container()
        container.register_module(module)
        s = container.get(Service)
        assert isinstance(s, Service)

    def test_module_builder_with_custom_scope(self) -> None:
        module = ModuleBuilder("test").bind_public(Service, scope=COUNTING).build()

        container = Container()
        container.register_module(module)
        s = container.get(Service)
        assert isinstance(s, Service)


class TestCustomScopeWithContainerHierarchy:
    """Custom scopes with parent-child containers."""

    def test_child_container_with_custom_scope(self) -> None:
        parent = Container()
        parent.register(Service, scope=THREAD_LOCAL)

        child = Container(parent=parent)
        s = child.get(Service)
        assert isinstance(s, Service)

    def test_custom_scope_in_child_bindings(self) -> None:
        parent = Container()
        child = Container(parent=parent)
        child.register(Service, scope=COUNTING)
        s = child.get(Service)
        assert isinstance(s, Service)


class TestCustomScopeValidation:
    """Custom scopes work with container validation."""

    def test_validate_with_custom_scope(self) -> None:
        container = Container()
        container.register(Service, scope=COUNTING)
        # Should not raise
        container.validate()

    def test_frozen_container_with_custom_scope(self) -> None:
        container = Container()
        container.register(Service, scope=COUNTING)
        container.freeze()
        s = container.get(Service)
        assert isinstance(s, Service)
