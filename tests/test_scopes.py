"""Tests for scope implementations."""

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
    """Test RequestScope."""

    def test_returns_same_instance_in_context(self) -> None:
        """Test that request scope returns same instance in a context."""
        Counter.reset_count()
        scope = RequestScope()
        scope.set_context("request-1")

        instance1 = scope.get(Counter)
        instance2 = scope.get(Counter)

        assert instance1 is instance2
        assert Counter._instance_count == 1

    def test_returns_different_instances_in_different_contexts(self) -> None:
        """Test that different contexts get different instances."""
        Counter.reset_count()
        scope = RequestScope()

        scope.set_context("request-1")
        instance1 = scope.get(Counter)

        scope.set_context("request-2")
        instance2 = scope.get(Counter)

        assert instance1 is not instance2
        assert Counter._instance_count == 2

    def test_raises_without_context(self) -> None:
        """Test that error is raised when no context is set."""
        scope = RequestScope()

        with pytest.raises(RuntimeError, match="No context set"):
            scope.get(Counter)

    def test_clear_context(self) -> None:
        """Test clearing a specific context."""
        Counter.reset_count()
        scope = RequestScope()

        scope.set_context("request-1")
        instance1 = scope.get(Counter)

        scope.clear_context("request-1")
        scope.set_context("request-1")
        instance2 = scope.get(Counter)

        assert instance1 is not instance2
        assert Counter._instance_count == 2

    def test_reset_clears_all(self) -> None:
        """Test that reset clears all contexts."""
        Counter.reset_count()
        scope = RequestScope()

        scope.set_context("request-1")
        scope.get(Counter)

        scope.reset()

        with pytest.raises(RuntimeError, match="No context set"):
            scope.get(Counter)


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
