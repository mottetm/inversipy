"""Tests for Factory[T] and Lazy[T] injectable wrapper types."""

import asyncio
from abc import ABC, abstractmethod

import pytest

from inversipy import (
    Container,
    DependencyNotFoundError,
    Factory,
    Inject,
    Injectable,
    Lazy,
    Named,
    ResolutionError,
    Scopes,
)


class IService(ABC):
    @abstractmethod
    def value(self) -> str: ...


class ServiceA(IService):
    def value(self) -> str:
        return "A"


class ServiceB(IService):
    def value(self) -> str:
        return "B"


class SimpleService:
    pass


class DependentService:
    def __init__(self, factory: Factory[SimpleService]) -> None:
        self.factory = factory


class DependentWithLazy:
    def __init__(self, lazy: Lazy[SimpleService]) -> None:
        self.lazy = lazy


class TestFactory:
    def test_basic_transient_injection(self) -> None:
        container = Container()
        container.register(SimpleService)
        container.register(DependentService)

        dep = container.get(DependentService)
        instance1 = dep.factory()
        instance2 = dep.factory()

        assert isinstance(instance1, SimpleService)
        assert isinstance(instance2, SimpleService)
        assert instance1 is not instance2

    def test_singleton_scope(self) -> None:
        container = Container()
        container.register(SimpleService, scope=Scopes.SINGLETON)
        container.register(DependentService)

        dep = container.get(DependentService)
        instance1 = dep.factory()
        instance2 = dep.factory()

        assert instance1 is instance2

    def test_named_via_inject(self) -> None:
        class Consumer:
            def __init__(
                self, fa: Inject[Factory[IService], Named("a")]  # type: ignore[type-arg]
            ) -> None:
                self.fa = fa

        container = Container()
        container.register(IService, ServiceA, name="a")
        container.register(IService, ServiceB, name="b")
        container.register(Consumer)

        consumer = container.get(Consumer)
        svc = consumer.fa()
        assert isinstance(svc, ServiceA)
        assert svc.value() == "A"

    def test_via_container_run(self) -> None:
        container = Container()
        container.register(SimpleService)

        def func(factory: Factory[SimpleService]) -> SimpleService:
            return factory()

        result = container.run(func)
        assert isinstance(result, SimpleService)

    def test_via_injectable(self) -> None:
        class MyInjectable(Injectable):
            factory: Inject[Factory[SimpleService]]  # type: ignore[type-arg]

        container = Container()
        container.register(SimpleService)
        container.register(MyInjectable)

        obj = container.get(MyInjectable)
        instance = obj.factory()
        assert isinstance(instance, SimpleService)

    def test_async_resolution(self) -> None:
        container = Container()
        container.register(SimpleService)
        container.register(DependentService)

        async def run() -> DependentService:
            return await container.get_async(DependentService)

        dep = asyncio.run(run())
        instance = dep.factory()
        assert isinstance(instance, SimpleService)

    def test_async_run(self) -> None:
        container = Container()
        container.register(SimpleService)

        def func(factory: Factory[SimpleService]) -> SimpleService:
            return factory()

        async def run() -> SimpleService:
            return await container.run_async(func)

        result = asyncio.run(run())
        assert isinstance(result, SimpleService)

    def test_error_deferred_to_call_time(self) -> None:
        container = Container()
        container.register(DependentService)

        dep = container.get(DependentService)
        # Factory is injected but SimpleService is not registered
        with pytest.raises((DependencyNotFoundError, ResolutionError)):
            dep.factory()


class TestLazy:
    def test_basic_caching(self) -> None:
        container = Container()
        container.register(SimpleService)
        container.register(DependentWithLazy)

        dep = container.get(DependentWithLazy)
        instance1 = dep.lazy()
        instance2 = dep.lazy()

        assert isinstance(instance1, SimpleService)
        assert instance1 is instance2

    def test_named_via_inject(self) -> None:
        class Consumer:
            def __init__(
                self, la: Inject[Lazy[IService], Named("a")]  # type: ignore[type-arg]
            ) -> None:
                self.la = la

        container = Container()
        container.register(IService, ServiceA, name="a")
        container.register(Consumer)

        consumer = container.get(Consumer)
        svc = consumer.la()
        assert isinstance(svc, ServiceA)
        # Verify caching
        assert consumer.la() is svc

    def test_via_container_run(self) -> None:
        container = Container()
        container.register(SimpleService)

        def func(lazy: Lazy[SimpleService]) -> SimpleService:
            return lazy()

        result = container.run(func)
        assert isinstance(result, SimpleService)

    def test_via_injectable(self) -> None:
        class MyInjectable(Injectable):
            lazy: Inject[Lazy[SimpleService]]  # type: ignore[type-arg]

        container = Container()
        container.register(SimpleService)
        container.register(MyInjectable)

        obj = container.get(MyInjectable)
        instance = obj.lazy()
        assert isinstance(instance, SimpleService)
        assert obj.lazy() is instance

    def test_async_resolution(self) -> None:
        container = Container()
        container.register(SimpleService)
        container.register(DependentWithLazy)

        async def run() -> DependentWithLazy:
            return await container.get_async(DependentWithLazy)

        dep = asyncio.run(run())
        instance1 = dep.lazy()
        instance2 = dep.lazy()
        assert instance1 is instance2

    def test_singleton_scope(self) -> None:
        container = Container()
        container.register(SimpleService, scope=Scopes.SINGLETON)
        container.register(DependentWithLazy)

        dep = container.get(DependentWithLazy)
        instance1 = dep.lazy()
        instance2 = dep.lazy()

        assert instance1 is instance2

    def test_request_scope_isolates_across_tasks(self) -> None:
        container = Container()
        container.register(SimpleService, scope=Scopes.REQUEST)
        container.register(DependentWithLazy)

        async def task() -> SimpleService:
            dep = await container.get_async(DependentWithLazy)
            # Within same task, Lazy should cache
            instance1 = dep.lazy()
            instance2 = dep.lazy()
            assert instance1 is instance2
            return instance1

        async def run() -> tuple[SimpleService, SimpleService]:
            return await asyncio.gather(task(), task())

        svc1, svc2 = asyncio.run(run())
        # Across different tasks (request contexts), should get different instances
        assert svc1 is not svc2

    def test_request_scope_caches_within_task(self) -> None:
        container = Container()
        container.register(SimpleService, scope=Scopes.REQUEST)
        container.register(DependentWithLazy)

        async def run() -> None:
            dep = await container.get_async(DependentWithLazy)
            instance1 = dep.lazy()
            instance2 = dep.lazy()
            assert instance1 is instance2

        asyncio.run(run())

    def test_error_deferred_to_call_time(self) -> None:
        container = Container()
        container.register(DependentWithLazy)

        dep = container.get(DependentWithLazy)
        with pytest.raises((DependencyNotFoundError, ResolutionError)):
            dep.lazy()
