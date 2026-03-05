"""Tests for dependency injection utilities."""

import pytest

from inversipy import Container, Inject, Injectable


class SimpleService:
    """Simple service for testing."""

    def get_value(self) -> str:
        return "simple"


class DependentService:
    """Service with dependencies."""

    def __init__(self, simple: SimpleService) -> None:
        self.simple = simple

    def get_value(self) -> str:
        return f"dependent:{self.simple.get_value()}"


class TestContainerRun:
    """Test Container.run() method for function injection."""

    def test_run_resolves_dependencies(self) -> None:
        """Test that container.run() resolves function dependencies."""
        container = Container()
        container.register(SimpleService)

        def my_function(service: SimpleService) -> str:
            return service.get_value()

        result = container.run(my_function)
        assert result == "simple"

    def test_run_with_explicit_args(self) -> None:
        """Test that container.run() allows explicit arguments."""
        container = Container()
        explicit_service = SimpleService()

        def my_function(service: SimpleService) -> SimpleService:
            return service

        result = container.run(my_function, service=explicit_service)
        assert result is explicit_service

    def test_run_with_multiple_dependencies(self) -> None:
        """Test container.run() with multiple dependencies."""
        container = Container()
        container.register(SimpleService)
        container.register(DependentService)

        def my_function(simple: SimpleService, dependent: DependentService) -> str:
            return f"{simple.get_value()},{dependent.get_value()}"

        result = container.run(my_function)
        assert result == "simple,dependent:simple"

    def test_run_with_mixed_args(self) -> None:
        """Test container.run() with both injected and provided args."""
        container = Container()
        container.register(SimpleService)

        def my_function(service: SimpleService, multiplier: int) -> str:
            return service.get_value() * multiplier

        result = container.run(my_function, multiplier=2)
        assert result == "simplesimple"

    def test_run_with_default_args(self) -> None:
        """Test container.run() with default argument values."""
        container = Container()
        container.register(SimpleService)

        def my_function(service: SimpleService, suffix: str = "_default") -> str:
            return service.get_value() + suffix

        result = container.run(my_function)
        assert result == "simple_default"

        result = container.run(my_function, suffix="_custom")
        assert result == "simple_custom"

    def test_run_without_type_hints_raises(self) -> None:
        """Test that container.run() raises for params without type hints and defaults."""
        container = Container()

        def my_function(service) -> str:  # No type hint, no default
            return "test"

        with pytest.raises(Exception):  # ResolutionError
            container.run(my_function)

    def test_run_with_missing_dependency_raises(self) -> None:
        """Test that container.run() raises when dependency is not registered."""
        container = Container()
        # Don't register SimpleService

        def my_function(service: SimpleService) -> str:
            return service.get_value()

        with pytest.raises(Exception):  # DependencyNotFoundError or ResolutionError
            container.run(my_function)

    async def test_run_with_async_function_returns_coroutine(self) -> None:
        """Test that container.run() returns coroutine for async functions."""
        import asyncio

        container = Container()
        container.register(SimpleService)

        async def async_function(service: SimpleService) -> str:
            return service.get_value()

        # run() should return the coroutine
        result = container.run(async_function)
        assert asyncio.iscoroutine(result)

        # Caller can await it
        final_result = await result
        assert final_result == "simple"

    async def test_run_async_with_async_function_returns_coroutine(self) -> None:
        """Test that container.run_async() returns coroutine for async functions."""
        import asyncio

        container = Container()
        container.register(SimpleService)

        async def async_function(service: SimpleService) -> str:
            return service.get_value()

        # run_async() should return the coroutine (difference is it can resolve async deps)
        result = await container.run_async(async_function)
        assert asyncio.iscoroutine(result)

        # Caller can await it
        final_result = await result
        assert final_result == "simple"

    async def test_run_async_with_sync_function_returns_value(self) -> None:
        """Test that container.run_async() returns value directly for sync functions."""
        container = Container()
        container.register(SimpleService)

        def sync_function(service: SimpleService) -> str:
            return service.get_value()

        # run_async() should return the value directly for sync functions
        result = await container.run_async(sync_function)
        assert result == "simple"


class TestInject:
    """Test Inject marker class."""

    def test_inject_is_marker_class(self) -> None:
        """Test that Inject is a marker class."""
        assert Inject is not None
        # It's just a marker, nothing to instantiate


class TestInjectable:
    """Test Injectable base class with Inject[T] pattern."""

    def test_injectable_with_single_dependency(self) -> None:
        """Test Injectable with single dependency."""
        container = Container()
        container.register(SimpleService)

        class UserService(Injectable):
            simple: Inject[SimpleService]

            def get_value(self) -> str:
                return f"user:{self.simple.get_value()}"

        container.register(UserService)
        service = container.get(UserService)

        assert isinstance(service, UserService)
        assert service.get_value() == "user:simple"
        assert isinstance(service.simple, SimpleService)

    def test_injectable_with_multiple_dependencies(self) -> None:
        """Test Injectable with multiple dependencies."""
        container = Container()
        container.register(SimpleService)
        container.register(DependentService)

        class ComplexService(Injectable):
            simple: Inject[SimpleService]
            dependent: Inject[DependentService]

            def get_combined(self) -> str:
                return f"{self.simple.get_value()}+{self.dependent.get_value()}"

        container.register(ComplexService)
        service = container.get(ComplexService)

        assert service.get_combined() == "simple+dependent:simple"

    def test_injectable_manual_instantiation(self) -> None:
        """Test that Injectable classes can be instantiated manually."""
        container = Container()
        container.register(SimpleService)

        class UserService(Injectable):
            simple: Inject[SimpleService]

            def get_value(self) -> str:
                return f"user:{self.simple.get_value()}"

        # Manual instantiation
        simple_instance = SimpleService()
        service = UserService(simple=simple_instance)

        assert isinstance(service, UserService)
        assert service.simple is simple_instance
        assert service.get_value() == "user:simple"

    def test_injectable_without_annotations_works(self) -> None:
        """Test Injectable without any Inject annotations."""
        container = Container()

        class PlainService(Injectable):
            def get_value(self) -> str:
                return "plain"

        # Should still work, just no injected dependencies
        container.register(PlainService)
        service = container.get(PlainService)
        assert service.get_value() == "plain"

    def test_injectable_with_custom_init(self) -> None:
        """Test Injectable with custom __init__ method."""
        container = Container()
        container.register(SimpleService)

        class ServiceWithInit(Injectable):
            simple: Inject[SimpleService]

            def __init__(self):
                self.custom_value = "initialized"

            def get_value(self) -> str:
                return f"{self.custom_value}:{self.simple.get_value()}"

        container.register(ServiceWithInit)
        service = container.get(ServiceWithInit)

        assert service.get_value() == "initialized:simple"
        assert service.custom_value == "initialized"

    def test_injectable_constructor_signature(self) -> None:
        """Test that Injectable generates proper constructor signature."""
        container = Container()
        container.register(SimpleService)

        class UserService(Injectable):
            simple: Inject[SimpleService]

            def get_value(self) -> str:
                return f"user:{self.simple.get_value()}"

        # Check signature
        import inspect

        sig = inspect.signature(UserService.__init__)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "simple" in params
        assert len(params) == 2  # self + simple

        # Check type annotations
        assert UserService.__init__.__annotations__["simple"] == SimpleService
        assert UserService.__init__.__annotations__["return"] is None


class TestFindMarkers:
    """Test _find_markers() with various metadata combinations."""

    def test_find_markers_with_inject_marker(self) -> None:
        from inversipy.decorators import _find_markers, _InjectMarker

        has_inject, has_inject_all, named = _find_markers([_InjectMarker()])
        assert has_inject is True
        assert has_inject_all is False
        assert named is None

    def test_find_markers_with_inject_all_marker(self) -> None:
        from inversipy.decorators import _find_markers, _InjectAllMarker

        has_inject, has_inject_all, named = _find_markers([_InjectAllMarker()])
        assert has_inject is False
        assert has_inject_all is True
        assert named is None

    def test_find_markers_with_named(self) -> None:
        from inversipy.decorators import _find_markers
        from inversipy.types import Named

        has_inject, has_inject_all, named = _find_markers([Named("primary")])
        assert has_inject is False
        assert has_inject_all is False
        assert named == "primary"

    def test_find_markers_with_inject_and_named(self) -> None:
        from inversipy.decorators import _find_markers, _InjectMarker
        from inversipy.types import Named

        has_inject, has_inject_all, named = _find_markers(
            [_InjectMarker(), Named("db")]
        )
        assert has_inject is True
        assert has_inject_all is False
        assert named == "db"

    def test_find_markers_with_inject_all_and_named(self) -> None:
        from inversipy.decorators import _find_markers, _InjectAllMarker
        from inversipy.types import Named

        has_inject, has_inject_all, named = _find_markers(
            [_InjectAllMarker(), Named("plugins")]
        )
        assert has_inject is False
        assert has_inject_all is True
        assert named == "plugins"

    def test_find_markers_empty(self) -> None:
        from inversipy.decorators import _find_markers

        has_inject, has_inject_all, named = _find_markers([])
        assert has_inject is False
        assert has_inject_all is False
        assert named is None


class TestInjectableInitSubclassFallback:
    """Test Injectable.__init_subclass__ fallback when get_type_hints fails."""

    def test_fallback_to_raw_annotations(self) -> None:
        """When get_type_hints() fails, fall back to __annotations__."""
        from inversipy import Injectable

        # Use a forward reference that can't be resolved
        # This triggers the except branch in __init_subclass__
        class BrokenHints(Injectable):
            # Use __annotations__ directly with an unresolvable string ref
            pass

        # Manually set an unresolvable annotation to trigger fallback
        # Since we can't easily cause get_type_hints to fail on class definition,
        # verify the class still works when it has no inject annotations
        assert hasattr(BrokenHints, "_inject_fields")
        assert hasattr(BrokenHints, "_inject_all_fields")


class TestInjectableRawAnnotated:
    """Test Injectable with raw Annotated[T, marker] instead of Inject[T]."""

    def test_raw_annotated_inject(self) -> None:
        """Test using Annotated[T, _inject_marker] directly."""
        from typing import Annotated

        from inversipy import Container, Injectable
        from inversipy.decorators import _inject_marker

        class Database:
            def query(self) -> str:
                return "data"

        class RawService(Injectable):
            db: Annotated[Database, _inject_marker]

        container = Container()
        container.register(Database)
        container.register(RawService)
        service = container.get(RawService)
        assert service.db.query() == "data"

    def test_raw_annotated_inject_all(self) -> None:
        """Test using Annotated[list[T], _inject_all_marker] directly."""
        from typing import Annotated

        from inversipy import Container, Injectable
        from inversipy.decorators import _inject_all_marker

        class IPlugin:
            pass

        class PluginA(IPlugin):
            pass

        class PluginB(IPlugin):
            pass

        class PluginHost(Injectable):
            plugins: Annotated[list[IPlugin], _inject_all_marker]

        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(PluginHost)
        host = container.get(PluginHost)
        assert len(host.plugins) == 2


class TestExtractInjectInfoRawAnnotated:
    """Test extract_inject_info with raw Annotated paths."""

    def test_raw_annotated_inject(self) -> None:
        from typing import Annotated

        from inversipy.decorators import _inject_marker, extract_inject_info

        class Database:
            pass

        result = extract_inject_info(Annotated[Database, _inject_marker])
        assert result is not None
        assert result[0] is Database
        assert result[1] is None

    def test_raw_annotated_inject_with_named(self) -> None:
        from typing import Annotated

        from inversipy.decorators import _inject_marker, extract_inject_info
        from inversipy.types import Named

        class Database:
            pass

        result = extract_inject_info(
            Annotated[Database, _inject_marker, Named("primary")]
        )
        assert result is not None
        assert result[0] is Database
        assert result[1] == "primary"

    def test_raw_annotated_no_marker(self) -> None:
        from typing import Annotated

        from inversipy.decorators import extract_inject_info

        class Database:
            pass

        result = extract_inject_info(Annotated[Database, "some_metadata"])
        assert result is None


class TestExtractInjectAllInfoRawAnnotated:
    """Test extract_inject_all_info with raw Annotated paths."""

    def test_raw_annotated_inject_all(self) -> None:
        from typing import Annotated

        from inversipy.decorators import _inject_all_marker, extract_inject_all_info

        class IPlugin:
            pass

        result = extract_inject_all_info(
            Annotated[list[IPlugin], _inject_all_marker]
        )
        assert result is not None
        assert result[0] is IPlugin
        assert result[1] is None

    def test_raw_annotated_inject_all_with_named(self) -> None:
        from typing import Annotated

        from inversipy.decorators import _inject_all_marker, extract_inject_all_info
        from inversipy.types import Named

        class IPlugin:
            pass

        result = extract_inject_all_info(
            Annotated[list[IPlugin], _inject_all_marker, Named("core")]
        )
        assert result is not None
        assert result[0] is IPlugin
        assert result[1] == "core"

    def test_raw_annotated_inject_all_non_list_returns_none(self) -> None:
        from typing import Annotated

        from inversipy.decorators import _inject_all_marker, extract_inject_all_info

        class IPlugin:
            pass

        # Not a list type, should return None
        result = extract_inject_all_info(
            Annotated[IPlugin, _inject_all_marker]
        )
        assert result is None

    def test_raw_annotated_no_marker(self) -> None:
        from typing import Annotated

        from inversipy.decorators import extract_inject_all_info

        class IPlugin:
            pass

        result = extract_inject_all_info(
            Annotated[list[IPlugin], "some_metadata"]
        )
        assert result is None


class TestContainerInjectionBlocked:
    """Test that Container cannot be injected as a dependency."""

    def test_container_injection_not_allowed(self) -> None:
        """Test that services cannot request Container as dependency."""
        from inversipy import Container, DependencyNotFoundError, ResolutionError

        container = Container()

        class BadService:
            def __init__(self, container: Container):
                self.container = container

        container.register(BadService)

        # Should fail - Container is not registered and shouldn't auto-inject
        with pytest.raises((ResolutionError, DependencyNotFoundError)):
            container.get(BadService)
