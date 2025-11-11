"""Tests for scope implementations."""

import asyncio
import pytest
from inversipy.scopes import (
    SingletonScope,
    TransientScope,
    RequestScope,
    AsyncSingletonScope,
)


class Counter:
    """Simple counter class for testing."""

    _instance_count = 0

    def __init__(self) -> None:
        Counter._instance_count += 1
        self.id = Counter._instance_count

    @classmethod
    def reset_count(cls) -> None:
        cls._instance_count = 0


class TestSingletonScope:
    """Test SingletonScope."""

    def test_returns_same_instance(self) -> None:
        """Test that singleton returns the same instance."""
        Counter.reset_count()
        scope = SingletonScope()

        instance1 = scope.get(Counter)
        instance2 = scope.get(Counter)

        assert instance1 is instance2
        assert Counter._instance_count == 1

    def test_reset_clears_instance(self) -> None:
        """Test that reset clears the cached instance."""
        Counter.reset_count()
        scope = SingletonScope()

        instance1 = scope.get(Counter)
        scope.reset()
        instance2 = scope.get(Counter)

        assert instance1 is not instance2
        assert Counter._instance_count == 2


class TestTransientScope:
    """Test TransientScope."""

    def test_returns_different_instances(self) -> None:
        """Test that transient returns different instances."""
        Counter.reset_count()
        scope = TransientScope()

        instance1 = scope.get(Counter)
        instance2 = scope.get(Counter)

        assert instance1 is not instance2
        assert Counter._instance_count == 2

    def test_reset_does_nothing(self) -> None:
        """Test that reset does nothing for transient scope."""
        Counter.reset_count()
        scope = TransientScope()

        instance1 = scope.get(Counter)
        scope.reset()
        instance2 = scope.get(Counter)

        assert instance1 is not instance2
        assert Counter._instance_count == 2


class TestRequestScope:
    """Test RequestScope with contextvars."""

    def test_returns_same_instance_in_context(self) -> None:
        """Test that request scope returns same instance within a context."""
        Counter.reset_count()
        scope = RequestScope()

        with scope.context():
            instance1 = scope.get(Counter)
            instance2 = scope.get(Counter)

            assert instance1 is instance2
            assert Counter._instance_count == 1

    def test_returns_different_instances_in_different_contexts(self) -> None:
        """Test that different contexts get different instances."""
        Counter.reset_count()
        scope = RequestScope()

        with scope.context():
            instance1 = scope.get(Counter)

        with scope.context():
            instance2 = scope.get(Counter)

        assert instance1 is not instance2
        assert Counter._instance_count == 2

    def test_automatic_context_isolation(self) -> None:
        """Test that instances are automatically isolated without explicit context manager."""
        Counter.reset_count()
        scope = RequestScope()

        # Without explicit context manager, each call creates a new context
        instance1 = scope.get(Counter)
        instance2 = scope.get(Counter)

        # Within the same implicit context, we get the same instance
        assert instance1 is instance2
        assert Counter._instance_count == 1

    def test_nested_contexts(self) -> None:
        """Test that nested contexts are properly isolated."""
        Counter.reset_count()
        scope = RequestScope()

        with scope.context():
            instance1 = scope.get(Counter)

            with scope.context():
                instance2 = scope.get(Counter)
                assert instance1 is not instance2

            # Back to outer context
            instance3 = scope.get(Counter)
            assert instance1 is instance3

        assert Counter._instance_count == 2

    def test_reset_clears_current_context(self) -> None:
        """Test that reset clears instances in the current context."""
        Counter.reset_count()
        scope = RequestScope()

        with scope.context():
            instance1 = scope.get(Counter)
            scope.reset()
            instance2 = scope.get(Counter)

            assert instance1 is not instance2
            assert Counter._instance_count == 2

    @pytest.mark.asyncio
    async def test_async_context_isolation(self) -> None:
        """Test that async contexts are properly isolated."""
        Counter.reset_count()
        scope = RequestScope()

        async def task1() -> Counter:
            with scope.context():
                return scope.get(Counter)

        async def task2() -> Counter:
            with scope.context():
                return scope.get(Counter)

        instance1, instance2 = await asyncio.gather(task1(), task2())

        # Each async task gets its own instance
        assert instance1 is not instance2
        assert Counter._instance_count == 2


class TestAsyncSingletonScope:
    """Test AsyncSingletonScope."""

    @pytest.mark.asyncio
    async def test_returns_same_instance(self) -> None:
        """Test that async singleton returns the same instance."""
        Counter.reset_count()
        scope = AsyncSingletonScope()

        instance1 = await scope.get_async(Counter)
        instance2 = await scope.get_async(Counter)

        assert instance1 is instance2
        assert Counter._instance_count == 1

    @pytest.mark.asyncio
    async def test_handles_async_factory(self) -> None:
        """Test that async singleton handles async factories."""
        Counter.reset_count()
        scope = AsyncSingletonScope()

        async def async_factory() -> Counter:
            return Counter()

        instance1 = await scope.get_async(async_factory)
        instance2 = await scope.get_async(async_factory)

        assert instance1 is instance2
        assert Counter._instance_count == 1

    def test_sync_get_raises(self) -> None:
        """Test that synchronous get raises NotImplementedError."""
        scope = AsyncSingletonScope()

        with pytest.raises(NotImplementedError):
            scope.get(Counter)

    @pytest.mark.asyncio
    async def test_reset_clears_instance(self) -> None:
        """Test that reset clears the cached instance."""
        Counter.reset_count()
        scope = AsyncSingletonScope()

        instance1 = await scope.get_async(Counter)
        scope.reset()
        instance2 = await scope.get_async(Counter)

        assert instance1 is not instance2
        assert Counter._instance_count == 2
