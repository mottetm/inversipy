"""Tests for container validation."""

import pytest

from inversipy import Container, ValidationError


class ServiceA:
    """Service with no dependencies."""

    pass


class ServiceB:
    """Service that depends on ServiceA."""

    def __init__(self, a: ServiceA) -> None:
        self.a = a


class ServiceC:
    """Service that depends on ServiceB."""

    def __init__(self, b: ServiceB) -> None:
        self.b = b


class ServiceWithMissingDependency:
    """Service with an unregistered dependency."""

    def __init__(self, missing: "UnregisteredService") -> None:  # type: ignore
        self.missing = missing


class UnregisteredService:
    """Service that is not registered."""

    pass


class ServiceWithOptionalDependency:
    """Service with an optional dependency."""

    def __init__(self, a: ServiceA, optional: str = "default") -> None:
        self.a = a
        self.optional = optional


class TestContainerValidation:
    """Test container validation."""

    def test_validation_passes_for_valid_container(self) -> None:
        """Test that validation passes when all dependencies are registered."""
        container = Container()
        container.register(ServiceA)
        container.register(ServiceB)
        container.register(ServiceC)

        # Should not raise
        container.validate()

    def test_validation_fails_for_missing_dependency(self) -> None:
        """Test that validation fails when dependencies are missing."""
        container = Container()
        container.register(ServiceWithMissingDependency)

        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        assert len(exc_info.value.errors) > 0
        assert "UnregisteredService" in exc_info.value.errors[0]

    def test_validation_passes_with_optional_dependency(self) -> None:
        """Test that validation passes with optional dependencies."""
        container = Container()
        container.register(ServiceA)
        container.register(ServiceWithOptionalDependency)

        # Should not raise
        container.validate()

    def test_validation_passes_for_factory_registrations(self) -> None:
        """Test that validation passes for factory registrations."""
        container = Container()

        def factory() -> ServiceA:
            return ServiceA()

        container.register_factory(ServiceA, factory)

        # Should not raise - factories are not validated
        container.validate()

    def test_validation_passes_for_instance_registrations(self) -> None:
        """Test that validation passes for instance registrations."""
        container = Container()
        instance = ServiceA()
        container.register_instance(ServiceA, instance)

        # Should not raise - instances are not validated
        container.validate()

    def test_validation_with_child_container(self) -> None:
        """Test validation considers parent container dependencies."""
        parent = Container()
        parent.register(ServiceA)

        child = parent.create_child()
        child.register(ServiceB)

        # Should not raise - ServiceB can get ServiceA from parent
        child.validate()

    def test_validation_error_message(self) -> None:
        """Test that validation error has useful error messages."""
        container = Container()
        container.register(ServiceB)  # Missing ServiceA

        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        error = exc_info.value
        assert len(error.errors) > 0
        assert "ServiceB" in str(error)
        assert "ServiceA" in str(error)


class TestValidationEdgeCases:
    """Test validation edge cases."""

    def test_empty_container_validates(self) -> None:
        """Test that an empty container validates successfully."""
        container = Container()
        container.validate()  # Should not raise

    def test_container_with_only_instances_validates(self) -> None:
        """Test that a container with only instances validates."""
        container = Container()
        container.register_instance(ServiceA, ServiceA())
        container.register_instance(ServiceB, ServiceB(ServiceA()))

        container.validate()  # Should not raise

    def test_container_with_only_factories_validates(self) -> None:
        """Test that a container with only factories validates."""
        container = Container()
        container.register_factory(ServiceA, lambda: ServiceA())
        container.register_factory(ServiceB, lambda: ServiceB(ServiceA()))

        container.validate()  # Should not raise
