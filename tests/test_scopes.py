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
    """Test RequestScope with contextvars automatic isolation."""

    def test_returns_same_instance_in_same_context(self) -> None:
        """Test that request scope returns same instance within the same context."""
        Counter.reset_count()
        scope = RequestScope()

        # Within the same context (implicit), we get the same instance
        instance1 = scope.get(Counter)
        instance2 = scope.get(Counter)

        assert instance1 is instance2
        assert Counter._instance_count == 1

    def test_reset_clears_current_context(self) -> None:
        """Test that reset clears instances in the current context."""
        Counter.reset_count()
        scope = RequestScope()

        instance1 = scope.get(Counter)
        scope.reset()
        instance2 = scope.get(Counter)

        # After reset, a new instance is created
        assert instance1 is not instance2
        assert Counter._instance_count == 2

    @pytest.mark.asyncio
    async def test_async_task_isolation(self) -> None:
        """Test that different async tasks get isolated instances automatically."""
        Counter.reset_count()
        scope = RequestScope()

        async def task1() -> Counter:
            # Each async task runs in its own context
            return scope.get(Counter)

        async def task2() -> Counter:
            # Each async task runs in its own context
            return scope.get(Counter)

        # Run tasks concurrently
        instance1, instance2 = await asyncio.gather(task1(), task2())

        # Each async task gets its own instance automatically
        assert instance1 is not instance2
        assert Counter._instance_count == 2

    @pytest.mark.asyncio
    async def test_same_instance_within_async_task(self) -> None:
        """Test that same async task gets same instance."""
        Counter.reset_count()
        scope = RequestScope()

        async def task() -> tuple[Counter, Counter]:
            # Within the same task, we should get the same instance
            instance1 = scope.get(Counter)
            instance2 = scope.get(Counter)
            return instance1, instance2

        instance1, instance2 = await task()

        # Same task should get same instance
        assert instance1 is instance2
        assert Counter._instance_count == 1


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
