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


class CircularA:
    """Service that depends on CircularB."""

    def __init__(self, b: "CircularB") -> None:
        self.b = b


class CircularB:
    """Service that depends on CircularA."""

    def __init__(self, a: CircularA) -> None:
        self.a = a


class CircularC:
    """Service that depends on CircularD."""

    def __init__(self, d: "CircularD") -> None:
        self.d = d


class CircularD:
    """Service that depends on CircularE."""

    def __init__(self, e: "CircularE") -> None:
        self.e = e


class CircularE:
    """Service that depends on CircularC, completing the cycle."""

    def __init__(self, c: CircularC) -> None:
        self.c = c


class SelfDependent:
    """Service that depends on itself."""

    def __init__(self, self_ref: "SelfDependent") -> None:
        self.self_ref = self_ref


class TestCycleDetectionInValidation:
    """Test that validation detects circular dependencies."""

    def test_validation_detects_simple_cycle(self) -> None:
        """Test that validation fails for A -> B -> A cycle."""
        container = Container()
        container.register(CircularA)
        container.register(CircularB)

        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        assert len(exc_info.value.errors) > 0
        error_msg = str(exc_info.value)
        assert "Circular dependency detected" in error_msg
        assert "CircularA" in error_msg
        assert "CircularB" in error_msg

    def test_validation_detects_longer_cycle(self) -> None:
        """Test that validation fails for C -> D -> E -> C cycle."""
        container = Container()
        container.register(CircularC)
        container.register(CircularD)
        container.register(CircularE)

        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        assert len(exc_info.value.errors) > 0
        error_msg = str(exc_info.value)
        assert "Circular dependency detected" in error_msg
        assert "CircularC" in error_msg
        assert "CircularD" in error_msg
        assert "CircularE" in error_msg

    def test_validation_detects_self_dependency(self) -> None:
        """Test that validation fails for self-referential dependency."""
        container = Container()
        container.register(SelfDependent)

        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        assert len(exc_info.value.errors) > 0
        error_msg = str(exc_info.value)
        assert "Circular dependency detected" in error_msg
        assert "SelfDependent" in error_msg

    def test_validation_passes_for_non_circular_dependencies(self) -> None:
        """Test that validation passes for valid dependency chain."""
        container = Container()
        container.register(ServiceA)
        container.register(ServiceB)
        container.register(ServiceC)

        # Should not raise
        container.validate()

    def test_validation_cycle_detection_ignores_factories(self) -> None:
        """Test that cycle detection skips factory registrations."""
        container = Container()
        # Factories can handle circular deps manually, so we don't validate them
        container.register_factory(CircularA, lambda b: CircularA(b))
        container.register_factory(CircularB, lambda a: CircularB(a))

        # Should not raise - factories are skipped
        container.validate()

    def test_validation_cycle_detection_ignores_instances(self) -> None:
        """Test that cycle detection skips instance registrations."""
        container = Container()
        # Pre-created instances don't need resolution
        a = CircularA.__new__(CircularA)
        b = CircularB.__new__(CircularB)
        a.b = b
        b.a = a
        container.register_instance(CircularA, a)
        container.register_instance(CircularB, b)

        # Should not raise - instances are skipped
        container.validate()
