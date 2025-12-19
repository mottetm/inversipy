"""Tests for dependency injection utilities."""

import pytest
from typing import Annotated
from inversipy import Container, Scopes, Inject, Injectable


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


class TestInject:
    """Test Inject marker class."""

    def test_inject_is_marker_class(self) -> None:
        """Test that Inject is a marker class."""
        assert Inject is not None
        # It's just a marker, nothing to instantiate


class TestInjectable:
    """Test Injectable base class with Annotated[Type, Inject] pattern."""

    def test_injectable_with_single_dependency(self) -> None:
        """Test Injectable with single dependency."""
        container = Container()
        container.register(SimpleService)

        class UserService(Injectable):
            simple: Annotated[SimpleService, Inject]

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
            simple: Annotated[SimpleService, Inject]
            dependent: Annotated[DependentService, Inject]

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
            simple: Annotated[SimpleService, Inject]

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
            simple: Annotated[SimpleService, Inject]

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
            simple: Annotated[SimpleService, Inject]

            def get_value(self) -> str:
                return f"user:{self.simple.get_value()}"

        # Check signature
        import inspect
        sig = inspect.signature(UserService.__init__)
        params = list(sig.parameters.keys())

        assert 'self' in params
        assert 'simple' in params
        assert len(params) == 2  # self + simple

        # Check type annotations
        assert UserService.__init__.__annotations__['simple'] == SimpleService
        assert UserService.__init__.__annotations__['return'] is None


class TestContainerInjectionBlocked:
    """Test that Container cannot be injected as a dependency."""

    def test_container_injection_not_allowed(self) -> None:
        """Test that services cannot request Container as dependency."""
        from inversipy import Container, ResolutionError, DependencyNotFoundError

        container = Container()

        class BadService:
            def __init__(self, container: Container):
                self.container = container

        container.register(BadService)

        # Should fail - Container is not registered and shouldn't auto-inject
        with pytest.raises((ResolutionError, DependencyNotFoundError)):
            container.get(BadService)
