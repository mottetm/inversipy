"""Tests for binding strategy edge cases."""

import asyncio
import threading
import time

import pytest

from inversipy.binding_strategies import (
    RequestStrategy,
    SingletonStrategy,
    TransientStrategy,
)
from inversipy.exceptions import ResolutionError
from tests._concurrency import CountingResolver


class TestSingletonStrategyAsync:
    """Test SingletonStrategy async edge cases."""

    async def test_get_async_with_sync_factory(self) -> None:
        """get_async() with a sync factory should work without awaiting."""
        strategy = SingletonStrategy()
        result = await strategy.get_async(lambda: "sync_value")
        assert result == "sync_value"

    async def test_get_async_with_async_factory(self) -> None:
        """get_async() with an async factory should await the coroutine."""
        strategy = SingletonStrategy()

        async def async_factory():
            return "async_value"

        result = await strategy.get_async(async_factory)
        assert result == "async_value"

    async def test_get_async_returns_cached_on_second_call(self) -> None:
        """get_async() should return the cached instance on subsequent calls."""
        strategy = SingletonStrategy()
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return f"value_{call_count}"

        result1 = await strategy.get_async(factory)
        result2 = await strategy.get_async(factory)
        assert result1 == "value_1"
        assert result2 == "value_1"
        assert call_count == 1


class TestTransientStrategyEdgeCases:
    """Test TransientStrategy edge cases."""

    def test_get_with_async_factory_raises(self) -> None:
        """get() with is_async_factory=True should raise ResolutionError."""
        strategy = TransientStrategy()
        with pytest.raises(ResolutionError, match="async factory"):
            strategy.get(lambda: "value", is_async_factory=True)

    async def test_get_async_with_sync_factory(self) -> None:
        """get_async() with a sync factory should return without awaiting."""
        strategy = TransientStrategy()
        result = await strategy.get_async(lambda: "sync_value")
        assert result == "sync_value"

    async def test_get_async_with_async_factory(self) -> None:
        """get_async() with an async factory should await the coroutine."""
        strategy = TransientStrategy()

        async def async_factory():
            return "async_value"

        result = await strategy.get_async(async_factory)
        assert result == "async_value"


class TestRequestStrategyEdgeCases:
    """Test RequestStrategy edge cases."""

    def test_get_with_async_factory_raises(self) -> None:
        """get() with is_async_factory=True should raise ResolutionError."""
        strategy = RequestStrategy()
        with pytest.raises(ResolutionError, match="async factory"):
            strategy.get(lambda: "value", is_async_factory=True)

    async def test_get_async_with_sync_factory(self) -> None:
        """get_async() with a sync factory should work."""
        strategy = RequestStrategy()
        result = await strategy.get_async(lambda: "sync_value")
        assert result == "sync_value"

    async def test_get_async_with_async_factory(self) -> None:
        """get_async() with an async factory should await the coroutine."""
        strategy = RequestStrategy()

        async def async_factory():
            return "async_value"

        result = await strategy.get_async(async_factory)
        assert result == "async_value"

    async def test_get_async_returns_cached_in_context(self) -> None:
        """get_async() should return the same instance within the same context."""
        strategy = RequestStrategy()
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return f"value_{call_count}"

        result1 = await strategy.get_async(factory)
        result2 = await strategy.get_async(factory)
        assert result1 == "value_1"
        assert result2 == "value_1"
        assert call_count == 1


class TestSingletonStrategyMixedMode:
    def test_mixed_sync_async_single_instance(self) -> None:
        """Concurrent sync + async resolution must call the factory exactly once."""
        release = threading.Event()
        factory = CountingResolver(wait=lambda: release.wait())
        strategy = SingletonStrategy()

        sync_result: object | None = None
        async_result: object | None = None

        def sync_worker() -> None:
            nonlocal sync_result
            sync_result = strategy.get(factory, is_async_factory=False)

        def async_worker() -> None:
            nonlocal async_result
            async_result = asyncio.run(strategy.get_async(factory))

        t_sync = threading.Thread(target=sync_worker)
        t_async = threading.Thread(target=async_worker)

        t_sync.start()
        assert factory.in_resolver.wait(), "sync caller never entered the factory"

        # Sync caller is parked inside the factory holding the singleton's lock.
        # Start the async caller: SingletonStrategy should serialize it on the
        # same lock. We can't observe "blocked on a lock" from outside, so
        # we give it a short window to reach that state.
        t_async.start()
        time.sleep(0.05)

        release.set()
        t_sync.join(timeout=1.0)
        t_async.join(timeout=1.0)

        assert not t_sync.is_alive() and not t_async.is_alive(), "worker thread hung"
        assert (
            factory.call_count == 1
        ), f"factory was called {factory.call_count} times — SingletonStrategy is not thread-safe"
        assert sync_result is async_result
