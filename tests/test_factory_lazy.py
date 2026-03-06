"""Tests for Factory[T] injectable wrapper type."""

import asyncio
from abc import ABC, abstractmethod

import pytest

from inversipy import (
    Container,
    DependencyNotFoundError,
    Factory,
    Inject,
    Injectable,
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
