"""Tests for decorators."""

import pytest
from typing import Annotated
from inversipy import Container, Scopes, injectable, singleton, transient, inject, Inject, Injectable


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


class TestInjectableDecorator:
    """Test @injectable decorator."""

    def test_injectable_registers_class(self) -> None:
        """Test that @injectable registers the class."""
        container = Container()

        @injectable(container)
        class TestService:
            pass

        assert container.has(TestService)
        service = container.get(TestService)
        assert isinstance(service, TestService)

    def test_injectable_with_interface(self) -> None:
        """Test @injectable with explicit interface."""
        container = Container()

        class IService:
            pass

        @injectable(container, interface=IService)
        class TestService(IService):
            pass

        assert container.has(IService)
        service = container.get(IService)
        assert isinstance(service, TestService)

    def test_injectable_with_scope(self) -> None:
        """Test @injectable with scope."""
        container = Container()

        @injectable(container, scope=Scopes.SINGLETON)
        class TestService:
            pass

        service1 = container.get(TestService)
        service2 = container.get(TestService)

        assert service1 is service2


class TestSingletonDecorator:
    """Test @singleton decorator."""

    def test_singleton_registers_as_singleton(self) -> None:
        """Test that @singleton registers with singleton scope."""
        container = Container()

        @singleton(container)
        class TestService:
            pass

        service1 = container.get(TestService)
        service2 = container.get(TestService)

        assert service1 is service2


class TestTransientDecorator:
    """Test @transient decorator."""

    def test_transient_registers_as_transient(self) -> None:
        """Test that @transient registers with transient scope."""
        container = Container()

        @transient(container)
        class TestService:
            pass

        service1 = container.get(TestService)
        service2 = container.get(TestService)

        assert service1 is not service2


class TestInjectDecorator:
    """Test @inject decorator."""

    def test_inject_resolves_dependencies(self) -> None:
        """Test that @inject resolves function dependencies."""
        container = Container()
        container.register(SimpleService)

        @inject(container)
        def my_function(service: SimpleService) -> str:
            return service.get_value()

        result = my_function()
        assert result == "simple"

    def test_inject_with_explicit_args(self) -> None:
        """Test that @inject allows explicit arguments."""
        container = Container()
        explicit_service = SimpleService()

        @inject(container)
        def my_function(service: SimpleService) -> SimpleService:
            return service

        result = my_function(service=explicit_service)
        assert result is explicit_service

    def test_inject_with_multiple_dependencies(self) -> None:
        """Test @inject with multiple dependencies."""
        container = Container()
        container.register(SimpleService)
        container.register(DependentService)

        @inject(container)
        def my_function(simple: SimpleService, dependent: DependentService) -> str:
            return f"{simple.get_value()},{dependent.get_value()}"

        result = my_function()
        assert result == "simple,dependent:simple"


class TestInjectDescriptor:
    """Test Inject descriptor."""

    def test_inject_descriptor(self) -> None:
        """Test Inject descriptor for property injection."""
        container = Container()
        container.register(SimpleService)

        class MyClass:
            service = Inject(SimpleService)

            def __init__(self, container: Container) -> None:
                self._container = container

            def get_value(self) -> str:
                return self.service.get_value()

        obj = MyClass(container)
        assert obj.get_value() == "simple"

    def test_inject_descriptor_caches_value(self) -> None:
        """Test that Inject descriptor caches the injected value."""
        container = Container()
        container.register(SimpleService)

        class MyClass:
            service = Inject(SimpleService)

            def __init__(self, container: Container) -> None:
                self._container = container

        obj = MyClass(container)
        service1 = obj.service
        service2 = obj.service

        # Should be the same instance because it's cached
        assert service1 is service2

    def test_inject_descriptor_without_container_raises(self) -> None:
        """Test that Inject descriptor raises without _container attribute."""

        class MyClass:
            service = Inject(SimpleService)

        obj = MyClass()

        with pytest.raises(AttributeError):
            _ = obj.service

    def test_inject_descriptor_accessed_on_class(self) -> None:
        """Test that Inject descriptor returns self when accessed on class."""

        class MyClass:
            service = Inject(SimpleService)

        # Accessing descriptor on class (not instance) should return descriptor
        descriptor = MyClass.service
        assert isinstance(descriptor, Inject)

    def test_inject_decorator_with_exception_in_type_hints(self) -> None:
        """Test inject decorator handles exceptions when getting type hints."""
        container = Container()
        container.register(SimpleService)

        # Create a function that will cause issues with get_type_hints
        # This can happen with complex forward references or import issues
        def problematic_function(service=None):  # No type hint but has default
            return "called"

        decorated = inject(container)(problematic_function)
        result = decorated()
        assert result == "called"

    def test_inject_decorator_with_resolution_failure(self) -> None:
        """Test inject decorator handles dependency resolution failures gracefully."""
        container = Container()
        # Don't register SimpleService

        @inject(container)
        def my_function(service: SimpleService) -> str:
            return service.get_value()

        # Should not raise during decoration, only during call
        # And since SimpleService is required but not registered, function gets called without it
        with pytest.raises(TypeError):  # Missing required positional argument
            my_function()


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
