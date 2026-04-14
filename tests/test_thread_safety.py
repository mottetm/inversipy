"""Tests for concurrent resolution stack isolation.

Uses async factories with deferred promises (asyncio.Event) to deterministically
prove that each async task gets its own resolution stack. This avoids the
non-determinism of thread-based tests.
"""

import asyncio
import threading
import time

import pytest

from inversipy import CircularDependencyError, Container, Lazy
from tests._concurrency import CountingResolver


class ServiceA:
    pass


class ServiceB:
    def __init__(self, a: ServiceA) -> None:
        self.a = a


class ServiceC:
    def __init__(self, b: ServiceB) -> None:
        self.b = b


class ServiceD:
    def __init__(self, c: ServiceC) -> None:
        self.c = c


class CircularX:
    def __init__(self, y: "CircularY") -> None:  # type: ignore
        self.y = y


class CircularY:
    def __init__(self, x: CircularX) -> None:
        self.x = x


class TestResolutionStackIsolation:
    """Prove that concurrent async tasks get isolated resolution stacks."""

    @pytest.mark.asyncio
    async def test_concurrent_resolution_no_false_cycle(self) -> None:
        """Two concurrent get_async calls for the same type must not interfere.

        With a shared stack, Task 2 would see ServiceA (pushed by Task 1) and
        falsely raise CircularDependencyError.
        """
        gate = asyncio.Event()

        async def deferred_factory() -> ServiceA:
            await gate.wait()
            return ServiceA()

        container = Container()
        container.register_factory(ServiceA, deferred_factory)

        async def release() -> None:
            await asyncio.sleep(0)  # yield so both tasks block on the gate
            gate.set()

        r1, r2, _ = await asyncio.gather(
            container.get_async(ServiceA),
            container.get_async(ServiceA),
            release(),
        )
        assert isinstance(r1, ServiceA)
        assert isinstance(r2, ServiceA)

    @pytest.mark.asyncio
    async def test_deep_chain_concurrent_no_false_cycle(self) -> None:
        """Concurrent resolution of a deep chain must not see each other's stacks.

        Each task builds stack [D, C, B, A] then blocks on A's factory.
        With a shared stack, Task 2 would see D already present and falsely
        raise CircularDependencyError.
        """
        gate = asyncio.Event()

        async def deferred_leaf() -> ServiceA:
            await gate.wait()
            return ServiceA()

        container = Container()
        container.register_factory(ServiceA, deferred_leaf)
        container.register(ServiceB)
        container.register(ServiceC)
        container.register(ServiceD)

        async def release() -> None:
            await asyncio.sleep(0)
            gate.set()

        r1, r2, _ = await asyncio.gather(
            container.get_async(ServiceD),
            container.get_async(ServiceD),
            release(),
        )
        assert isinstance(r1, ServiceD)
        assert isinstance(r1.c.b.a, ServiceA)
        assert isinstance(r2, ServiceD)
        assert isinstance(r2.c.b.a, ServiceA)

    @pytest.mark.asyncio
    async def test_cycle_detection_works_per_task(self) -> None:
        """Each concurrent task must independently detect real cycles."""
        container = Container()
        container.register(CircularX)
        container.register(CircularY)

        async def resolve() -> CircularDependencyError | None:
            try:
                await container.get_async(CircularX)
                return None
            except CircularDependencyError as e:
                return e

        results = await asyncio.gather(resolve(), resolve(), resolve())

        for result in results:
            assert isinstance(result, CircularDependencyError)


class TestLazyThreadSafety:
    def test_lazy_resolver_invoked_once_under_contention(self) -> None:
        """Concurrent calls to Lazy[T] must invoke the resolver exactly once."""
        release = threading.Event()

        resolver = CountingResolver(wait=lambda: release.wait())
        lazy = Lazy[object](resolver)

        t1 = threading.Thread(target=lazy)
        t2 = threading.Thread(target=lazy)

        t1.start()
        assert resolver.in_resolver.wait(), "t1 never entered the resolver"

        # t1 is parked inside the resolver.
        # Start t2: Lazy should prevent t2 to enter the resolver
        # using its internal lock. We can't observe "blocked on a lock" from
        # outside, so we give t2 a short window to reach that state.
        t2.start()
        time.sleep(0.05)

        release.set()
        t1.join(timeout=1.0)
        t2.join(timeout=1.0)

        assert not t1.is_alive() and not t2.is_alive(), "worker thread hung"
        assert (
            resolver.call_count == 1
        ), f"resolver was called {resolver.call_count} times — Lazy is not thread-safe"
