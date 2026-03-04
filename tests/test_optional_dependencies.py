"""Tests for Optional[T] / T | None soft dependency support."""

from __future__ import annotations

import pytest

from inversipy import Container, ResolutionError, Scopes


class Logger:
    """Simple logger service."""

    def log(self, msg: str) -> str:
        return f"logged: {msg}"


class Cache:
    """Simple cache service."""

    def get(self, key: str) -> str:
        return f"cached: {key}"


class ServiceWithOptional:
    """Service with an optional dependency using T | None syntax."""

    def __init__(self, logger: Logger, cache: Cache | None) -> None:
        self.logger = logger
        self.cache = cache


class ServiceWithOptionalDefault:
    """Service with an optional dependency that also has a default."""

    def __init__(self, logger: Logger, cache: Cache | None = None) -> None:
        self.logger = logger
        self.cache = cache


class ServiceWithMultipleOptionals:
    """Service with multiple optional dependencies."""

    def __init__(self, cache: Cache | None, logger: Logger | None) -> None:
        self.cache = cache
        self.logger = logger


class TestOptionalDependencyResolution:
    """Test that T | None parameters resolve to None when unregistered."""

    def test_optional_resolved_to_none_when_not_registered(self) -> None:
        """T | None without a default should resolve to None."""
        container = Container()
        container.register(Logger)
        container.register(ServiceWithOptional)

        service = container.get(ServiceWithOptional)
        assert service.logger is not None
        assert service.cache is None

    def test_optional_resolved_when_registered(self) -> None:
        """T | None should resolve to the registered instance when available."""
        container = Container()
        container.register(Logger)
        container.register(Cache)
        container.register(ServiceWithOptional)

        service = container.get(ServiceWithOptional)
        assert service.logger is not None
        assert service.cache is not None
        assert isinstance(service.cache, Cache)

    def test_optional_with_default_resolved_to_none(self) -> None:
        """T | None = None should also resolve to None when not registered."""
        container = Container()
        container.register(Logger)
        container.register(ServiceWithOptionalDefault)

        service = container.get(ServiceWithOptionalDefault)
        assert service.cache is None

    def test_optional_with_default_resolved_when_registered(self) -> None:
        """T | None = None should resolve to registered instance when available."""
        container = Container()
        container.register(Logger)
        container.register(Cache)
        container.register(ServiceWithOptionalDefault)

        service = container.get(ServiceWithOptionalDefault)
        assert isinstance(service.cache, Cache)

    def test_multiple_optionals_all_none(self) -> None:
        """Multiple T | None params should all resolve to None."""
        container = Container()
        container.register(ServiceWithMultipleOptionals)

        service = container.get(ServiceWithMultipleOptionals)
        assert service.cache is None
        assert service.logger is None

    def test_multiple_optionals_some_registered(self) -> None:
        """Some T | None params resolve, others get None."""
        container = Container()
        container.register(Logger)
        container.register(ServiceWithMultipleOptionals)

        service = container.get(ServiceWithMultipleOptionals)
        assert service.cache is None
        assert isinstance(service.logger, Logger)

    def test_non_optional_still_raises(self) -> None:
        """Non-optional unregistered deps should still raise."""
        container = Container()
        container.register(ServiceWithOptional)  # Logger not registered

        with pytest.raises(ResolutionError):
            container.get(ServiceWithOptional)


class TestOptionalInFactory:
    """Test Optional[T] in factory functions."""

    def test_factory_with_optional_param(self) -> None:
        """Factory with T | None param gets None when dep is missing."""
        container = Container()
        container.register(Logger)

        def create_service(logger: Logger, cache: Cache | None) -> ServiceWithOptional:
            return ServiceWithOptional(logger, cache)

        container.register_factory(ServiceWithOptional, create_service)
        service = container.get(ServiceWithOptional)
        assert service.logger is not None
        assert service.cache is None

    def test_factory_with_optional_resolved(self) -> None:
        """Factory with T | None param gets instance when dep is registered."""
        container = Container()
        container.register(Logger)
        container.register(Cache)

        def create_service(logger: Logger, cache: Cache | None) -> ServiceWithOptional:
            return ServiceWithOptional(logger, cache)

        container.register_factory(ServiceWithOptional, create_service)
        service = container.get(ServiceWithOptional)
        assert isinstance(service.cache, Cache)


class TestOptionalInRun:
    """Test Optional[T] in container.run()."""

    def test_run_with_optional(self) -> None:
        """container.run() with T | None injects None for missing deps."""
        container = Container()
        container.register(Logger)

        def my_func(logger: Logger, cache: Cache | None) -> str:
            return f"cache={cache}"

        result = container.run(my_func)
        assert result == "cache=None"

    def test_run_with_optional_provided(self) -> None:
        """container.run() with T | None injects instance when registered."""
        container = Container()
        container.register(Logger)
        container.register(Cache)

        def my_func(logger: Logger, cache: Cache | None) -> str:
            return f"cache={type(cache).__name__}"

        result = container.run(my_func)
        assert result == "cache=Cache"


class TestOptionalAsync:
    """Test Optional[T] in async resolution paths."""

    async def test_async_optional_resolved_to_none(self) -> None:
        """Async resolution with T | None injects None."""
        container = Container()
        container.register(Logger)
        container.register(ServiceWithOptional)

        service = await container.get_async(ServiceWithOptional)
        assert service.cache is None

    async def test_async_optional_resolved_when_registered(self) -> None:
        """Async resolution with T | None injects instance when available."""
        container = Container()
        container.register(Logger)
        container.register(Cache)
        container.register(ServiceWithOptional)

        service = await container.get_async(ServiceWithOptional)
        assert isinstance(service.cache, Cache)

    async def test_run_async_with_optional(self) -> None:
        """run_async() with T | None injects None for missing deps."""
        container = Container()
        container.register(Logger)

        def my_func(logger: Logger, cache: Cache | None) -> str:
            return f"cache={cache}"

        result = await container.run_async(my_func)
        assert result == "cache=None"


class TestOptionalWithScopes:
    """Test Optional[T] works correctly with different scopes."""

    def test_optional_singleton_resolved(self) -> None:
        """Singleton optional dep is shared across resolutions."""
        container = Container()
        container.register(Logger)
        container.register(Cache, scope=Scopes.SINGLETON)
        container.register(ServiceWithOptional)

        s1 = container.get(ServiceWithOptional)
        s2 = container.get(ServiceWithOptional)
        assert s1.cache is s2.cache
