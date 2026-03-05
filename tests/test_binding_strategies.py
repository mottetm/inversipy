"""Tests for binding strategy edge cases."""

import pytest

from inversipy.binding_strategies import (
    RequestStrategy,
    SingletonStrategy,
    TransientStrategy,
)
from inversipy.exceptions import ResolutionError


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
