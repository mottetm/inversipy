"""Tests for Factory[T] and Lazy[T] injectable wrapper types."""

import asyncio
from abc import ABC, abstractmethod

import pytest

from inversipy import (
    AmbiguousDependencyError,
    CircularDependencyError,
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

    def test_lazy_ambiguous_bindings_raises_eagerly(self) -> None:
        """Ambiguous bindings for Lazy[T] should raise at resolution time, not call time."""
        container = Container()
        container.register(IService, ServiceA)
        container.register(IService, ServiceB)

        class Consumer:
            def __init__(self, service: Lazy[IService]) -> None:
                self.service = service

        container.register(Consumer)

        with pytest.raises(AmbiguousDependencyError):
            container.get(Consumer)

    def test_async_lazy_ambiguous_bindings_raises_eagerly(self) -> None:
        """Ambiguous bindings for Lazy[T] should raise at async resolution time."""
        container = Container()
        container.register(IService, ServiceA)
        container.register(IService, ServiceB)

        class Consumer:
            def __init__(self, service: Lazy[IService]) -> None:
                self.service = service

        container.register(Consumer)

        async def run() -> None:
            await container.get_async(Consumer)

        with pytest.raises(AmbiguousDependencyError):
            asyncio.run(run())

    def test_lazy_ambiguous_after_resolution_raises_at_call_time(self) -> None:
        """If container becomes ambiguous after Lazy is created, error at call time."""
        container = Container()
        container.register(IService, ServiceA)

        class Consumer:
            def __init__(self, service: Lazy[IService]) -> None:
                self.service = service

        container.register(Consumer)

        # Resolve with a single binding — Lazy wrapper is created successfully
        consumer = container.get(Consumer)

        # Now add a second binding, making it ambiguous
        container.register(IService, ServiceB)

        # The Lazy's resolver calls container.get(), which detects ambiguity
        with pytest.raises(AmbiguousDependencyError):
            consumer.service()


class TestFactoryAcall:
    def test_acall_uses_async_resolver(self) -> None:
        """Test that Factory.acall() uses the async resolver when provided."""
        container = Container()
        container.register(SimpleService)
        container.register(DependentService)

        async def run() -> SimpleService:
            dep = await container.get_async(DependentService)
            return await dep.factory.acall()

        instance = asyncio.run(run())
        assert isinstance(instance, SimpleService)

    def test_acall_falls_back_to_sync(self) -> None:
        """Test that Factory.acall() falls back to sync resolver when no async resolver."""
        container = Container()
        container.register(SimpleService)
        container.register(DependentService)

        # Sync resolution produces Factory without async_resolver
        dep = container.get(DependentService)

        async def run() -> SimpleService:
            return await dep.factory.acall()

        instance = asyncio.run(run())
        assert isinstance(instance, SimpleService)

    def test_acall_resolves_fresh_each_time(self) -> None:
        """Test that Factory.acall() resolves a new instance each call (transient)."""
        container = Container()
        container.register(SimpleService)
        container.register(DependentService)

        async def run() -> tuple[SimpleService, SimpleService]:
            dep = await container.get_async(DependentService)
            a = await dep.factory.acall()
            b = await dep.factory.acall()
            return a, b

        a, b = asyncio.run(run())
        assert isinstance(a, SimpleService)
        assert a is not b


class TestLazyAcall:
    def test_acall_uses_async_resolver(self) -> None:
        """Test that Lazy.acall() uses the async resolver when provided."""
        container = Container()
        container.register(SimpleService)
        container.register(DependentWithLazy)

        async def run() -> SimpleService:
            dep = await container.get_async(DependentWithLazy)
            return await dep.lazy.acall()

        instance = asyncio.run(run())
        assert isinstance(instance, SimpleService)

    def test_acall_caches_result(self) -> None:
        """Test that Lazy.acall() caches the resolved instance."""
        container = Container()
        container.register(SimpleService)
        container.register(DependentWithLazy)

        async def run() -> tuple[SimpleService, SimpleService]:
            dep = await container.get_async(DependentWithLazy)
            a = await dep.lazy.acall()
            b = await dep.lazy.acall()
            return a, b

        a, b = asyncio.run(run())
        assert a is b

    def test_acall_falls_back_to_sync(self) -> None:
        """Test that Lazy.acall() falls back to sync resolver when no async resolver."""
        container = Container()
        container.register(SimpleService)
        container.register(DependentWithLazy)

        # Sync resolution produces Lazy without async_resolver
        dep = container.get(DependentWithLazy)

        async def run() -> SimpleService:
            return await dep.lazy.acall()

        instance = asyncio.run(run())
        assert isinstance(instance, SimpleService)


class TestAsyncResolutionEdgeCases:
    def test_run_async_skips_provided_kwargs(self) -> None:
        """Test that _resolve_deps_async skips already-provided kwargs."""
        container = Container()
        container.register(SimpleService)

        def func(svc: SimpleService) -> SimpleService:
            return svc

        provided = SimpleService()

        async def run() -> SimpleService:
            return await container.run_async(func, svc=provided)

        result = asyncio.run(run())
        assert result is provided

    def test_run_async_missing_type_hint_raises(self) -> None:
        """Test that _resolve_deps_async raises on missing type hint."""
        container = Container()

        def func(param) -> None:  # type: ignore[no-untyped-def]
            pass

        async def run() -> None:
            await container.run_async(func)

        with pytest.raises(ResolutionError, match="has no type hint"):
            asyncio.run(run())

    def test_run_async_missing_required_dep_raises(self) -> None:
        """Test that _resolve_deps_async raises on missing required dependency."""
        container = Container()

        def func(svc: SimpleService) -> None:
            pass

        async def run() -> None:
            await container.run_async(func)

        with pytest.raises(ResolutionError, match="Cannot resolve parameter"):
            asyncio.run(run())

    def test_async_lazy_without_binding_gets_async_resolver(self) -> None:
        """Test _make_wrapper_async Lazy fallback when no binding exists."""
        container = Container()
        # Register IService with multiple implementations so _find_binding
        # returns None (it only returns for single bindings)
        container.register(IService, ServiceA, name="a")
        container.register(IService, ServiceB, name="b")

        class Holder:
            def __init__(self, lazy: Lazy[IService]) -> None:
                self.lazy = lazy

        # Use a factory that takes Lazy[IService] (unnamed) — no single binding
        # exists, so _make_wrapper_async hits the fallback path
        def create_holder(lazy: Lazy[IService]) -> Holder:
            return Holder(lazy)

        container.register_factory(Holder, create_holder)

        async def run() -> Holder:
            return await container.get_async(Holder)

        # The Lazy is created but calling it will fail since IService
        # (unnamed) has no single binding. We just need to verify the
        # wrapper was created with async support.
        holder = asyncio.run(run())
        assert holder.lazy._async_resolver is not None


class _CircA:
    def __init__(self, b: "_CircB") -> None:
        self.b = b


class _CircB:
    def __init__(self, a: _CircA) -> None:
        self.a = a


class TestCircularDependencyStackCleanup:
    def test_stack_not_leaked_on_circular_dependency(self) -> None:
        """Test that the resolution stack is not corrupted by circular dependency detection."""
        container = Container()
        container.register(_CircA)
        container.register(_CircB)

        with pytest.raises(CircularDependencyError):
            container.get(_CircA)

        # After the error, the resolution stack should be clean
        container.register(SimpleService)
        instance = container.get(SimpleService)
        assert isinstance(instance, SimpleService)

    def test_async_stack_not_leaked_on_circular_dependency(self) -> None:
        """Test that the async resolution stack is not corrupted by circular dependency."""
        container = Container()
        container.register(_CircA)
        container.register(_CircB)

        async def run() -> SimpleService:
            with pytest.raises(CircularDependencyError):
                await container.get_async(_CircA)

            container.register(SimpleService)
            return await container.get_async(SimpleService)

        instance = asyncio.run(run())
        assert isinstance(instance, SimpleService)
