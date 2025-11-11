"""Tests for the Container class."""

import pytest
from inversipy import (
    Container,
    SINGLETON,
    TRANSIENT,
    DependencyNotFoundError,
    CircularDependencyError,
    ResolutionError,
)


class SimpleService:
    """Simple service with no dependencies."""

    def get_value(self) -> str:
        return "simple"


class DependentService:
    """Service that depends on SimpleService."""

    def __init__(self, simple: SimpleService) -> None:
        self.simple = simple

    def get_value(self) -> str:
        return f"dependent:{self.simple.get_value()}"


class MultiDependentService:
    """Service with multiple dependencies."""

    def __init__(self, simple: SimpleService, dependent: DependentService) -> None:
        self.simple = simple
        self.dependent = dependent

    def get_value(self) -> str:
        return f"multi:{self.simple.get_value()}:{self.dependent.get_value()}"


class CircularA:
    """Service A for circular dependency test."""

    def __init__(self, b: "CircularB") -> None:  # type: ignore
        self.b = b


class CircularB:
    """Service B for circular dependency test."""

    def __init__(self, a: CircularA) -> None:
        self.a = a


class TestContainerBasics:
    """Test basic container functionality."""

    def test_register_and_resolve_simple(self) -> None:
        """Test registering and resolving a simple dependency."""
        container = Container()
        container.register(SimpleService)

        service = container.get(SimpleService)
        assert isinstance(service, SimpleService)
        assert service.get_value() == "simple"

    def test_register_with_implementation(self) -> None:
        """Test registering with explicit implementation."""
        container = Container()
        container.register(SimpleService, implementation=SimpleService)

        service = container.get(SimpleService)
        assert isinstance(service, SimpleService)

    def test_register_instance(self) -> None:
        """Test registering a pre-created instance."""
        container = Container()
        instance = SimpleService()
        container.register_instance(SimpleService, instance)

        service = container.get(SimpleService)
        assert service is instance

    def test_register_factory(self) -> None:
        """Test registering a factory function."""
        container = Container()
        call_count = {"count": 0}

        def factory() -> SimpleService:
            call_count["count"] += 1
            return SimpleService()

        container.register_factory(SimpleService, factory)

        service = container.get(SimpleService)
        assert isinstance(service, SimpleService)
        assert call_count["count"] == 1

    def test_has_dependency(self) -> None:
        """Test checking if a dependency is registered."""
        container = Container()
        assert not container.has(SimpleService)

        container.register(SimpleService)
        assert container.has(SimpleService)

    def test_try_get_returns_none_if_not_found(self) -> None:
        """Test try_get returns None for unregistered dependencies."""
        container = Container()
        service = container.try_get(SimpleService)
        assert service is None

    def test_get_raises_if_not_found(self) -> None:
        """Test get raises DependencyNotFoundError for unregistered dependencies."""
        container = Container()
        with pytest.raises(DependencyNotFoundError):
            container.get(SimpleService)


class TestDependencyResolution:
    """Test dependency resolution."""

    def test_resolve_with_dependencies(self) -> None:
        """Test resolving a service with dependencies."""
        container = Container()
        container.register(SimpleService)
        container.register(DependentService)

        service = container.get(DependentService)
        assert isinstance(service, DependentService)
        assert isinstance(service.simple, SimpleService)
        assert service.get_value() == "dependent:simple"

    def test_resolve_with_multiple_dependencies(self) -> None:
        """Test resolving a service with multiple dependencies."""
        container = Container()
        container.register(SimpleService)
        container.register(DependentService)
        container.register(MultiDependentService)

        service = container.get(MultiDependentService)
        assert isinstance(service, MultiDependentService)
        assert isinstance(service.simple, SimpleService)
        assert isinstance(service.dependent, DependentService)
        assert service.get_value() == "multi:simple:dependent:simple"

    def test_circular_dependency_detection(self) -> None:
        """Test that circular dependencies are detected."""
        container = Container()
        container.register(CircularA)
        container.register(CircularB)

        with pytest.raises(CircularDependencyError) as exc_info:
            container.get(CircularA)

        # Check that both types are in the dependency chain
        assert CircularA in exc_info.value.dependency_chain
        assert CircularB in exc_info.value.dependency_chain


class TestScopes:
    """Test dependency scopes."""

    def test_singleton_scope(self) -> None:
        """Test that singleton scope returns the same instance."""
        container = Container()
        container.register(SimpleService, scope=SINGLETON)

        service1 = container.get(SimpleService)
        service2 = container.get(SimpleService)

        assert service1 is service2

    def test_transient_scope(self) -> None:
        """Test that transient scope returns different instances."""
        container = Container()
        container.register(SimpleService, scope=TRANSIENT)

        service1 = container.get(SimpleService)
        service2 = container.get(SimpleService)

        assert service1 is not service2

    def test_factory_with_singleton(self) -> None:
        """Test factory with singleton scope."""
        container = Container()
        call_count = {"count": 0}

        def factory() -> SimpleService:
            call_count["count"] += 1
            return SimpleService()

        container.register_factory(SimpleService, factory, scope=SINGLETON)

        service1 = container.get(SimpleService)
        service2 = container.get(SimpleService)

        assert service1 is service2
        assert call_count["count"] == 1

    def test_factory_with_transient(self) -> None:
        """Test factory with transient scope."""
        container = Container()
        call_count = {"count": 0}

        def factory() -> SimpleService:
            call_count["count"] += 1
            return SimpleService()

        container.register_factory(SimpleService, factory, scope=TRANSIENT)

        service1 = container.get(SimpleService)
        service2 = container.get(SimpleService)

        assert service1 is not service2
        assert call_count["count"] == 2


class TestChildContainers:
    """Test parent-child container hierarchy."""

    def test_child_resolves_from_parent(self) -> None:
        """Test that child can resolve dependencies from parent."""
        parent = Container(name="Parent")
        parent.register(SimpleService)

        child = parent.create_child("Child")

        service = child.get(SimpleService)
        assert isinstance(service, SimpleService)

    def test_child_overrides_parent(self) -> None:
        """Test that child registrations override parent."""
        parent = Container(name="Parent")
        parent_instance = SimpleService()
        parent.register_instance(SimpleService, parent_instance)

        child = parent.create_child("Child")
        child_instance = SimpleService()
        child.register_instance(SimpleService, child_instance)

        service = child.get(SimpleService)
        assert service is child_instance
        assert service is not parent_instance

    def test_parent_unaffected_by_child(self) -> None:
        """Test that parent is not affected by child registrations."""
        parent = Container(name="Parent")
        child = parent.create_child("Child")
        child.register(DependentService)

        assert not parent.has(DependentService)
        assert child.has(DependentService)

    def test_parent_property(self) -> None:
        """Test parent property."""
        parent = Container()
        child = parent.create_child()

        assert child.parent is parent
        assert parent.parent is None
