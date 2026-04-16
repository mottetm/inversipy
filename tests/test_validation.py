"""Tests for container validation."""

import pytest

from inversipy import Container, Factory, InjectAll, Lazy, ValidationError


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


class LazyConsumerA:
    """Service that lazily depends on LazyDepB."""

    def __init__(self, b: Lazy["LazyDepB"]) -> None:
        self.b = b


class LazyDepB:
    """Service that depends on LazyConsumerA."""

    def __init__(self, a: LazyConsumerA) -> None:
        self.a = a


class LazyRootA:
    """Service that lazily depends on InternalCycleB."""

    def __init__(self, b: Lazy["InternalCycleB"]) -> None:
        self.b = b


class InternalCycleB:
    """Service in B <-> C cycle, reachable via Lazy from LazyRootA."""

    def __init__(self, c: "InternalCycleC") -> None:
        self.c = c


class InternalCycleC:
    """Service in B <-> C cycle."""

    def __init__(self, b: InternalCycleB) -> None:
        self.b = b


class FactoryConsumerA:
    """Service that depends on FactoryDepB via Factory wrapper."""

    def __init__(self, b: Factory["FactoryDepB"]) -> None:
        self.b = b


class FactoryDepB:
    """Service that depends on FactoryConsumerA."""

    def __init__(self, a: FactoryConsumerA) -> None:
        self.a = a


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

    def test_validation_skips_factories_without_type_hints(self) -> None:
        """Factories with untyped parameters produce no cycle-detection edges."""
        container = Container()
        # Untyped lambdas: analyze_parameters() cannot resolve their deps,
        # so no graph edges are produced — no cycle is reported.
        container.register_factory(CircularA, lambda b: CircularA(b))
        container.register_factory(CircularB, lambda a: CircularB(a))

        container.validate()  # Should not raise

    def test_validation_detects_typed_factory_cycle(self) -> None:
        """Two typed factories forming A <-> B cycle should be detected."""
        container = Container()

        def make_a(b: CircularB) -> CircularA:
            return CircularA(b)

        def make_b(a: CircularA) -> CircularB:
            return CircularB(a)

        container.register_factory(CircularA, make_a)
        container.register_factory(CircularB, make_b)

        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        error_msg = str(exc_info.value)
        assert "Circular dependency detected" in error_msg
        assert "CircularA" in error_msg
        assert "CircularB" in error_msg

    def test_validation_detects_longer_typed_factory_cycle(self) -> None:
        """Three typed factories forming C -> D -> E -> C should be detected."""
        container = Container()

        def make_c(d: CircularD) -> CircularC:
            return CircularC(d)

        def make_d(e: CircularE) -> CircularD:
            return CircularD(e)

        def make_e(c: CircularC) -> CircularE:
            return CircularE(c)

        container.register_factory(CircularC, make_c)
        container.register_factory(CircularD, make_d)
        container.register_factory(CircularE, make_e)

        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        error_msg = str(exc_info.value)
        assert "Circular dependency detected" in error_msg
        assert "CircularC" in error_msg
        assert "CircularD" in error_msg
        assert "CircularE" in error_msg

    def test_validation_detects_self_referential_typed_factory(self) -> None:
        """A factory whose typed param is its own return type should be detected."""
        container = Container()

        def make_self(s: SelfDependent) -> SelfDependent:
            return SelfDependent(s)

        container.register_factory(SelfDependent, make_self)

        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        error_msg = str(exc_info.value)
        assert "Circular dependency detected" in error_msg
        assert "SelfDependent" in error_msg

    def test_validation_detects_mixed_factory_and_class_cycle(self) -> None:
        """A cycle spanning a class registration and a typed factory should be detected."""
        container = Container()

        def make_b(a: CircularA) -> CircularB:
            return CircularB(a)

        container.register(CircularA)  # class: depends on CircularB
        container.register_factory(CircularB, make_b)  # factory: depends on CircularA

        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        error_msg = str(exc_info.value)
        assert "Circular dependency detected" in error_msg
        assert "CircularA" in error_msg
        assert "CircularB" in error_msg

    def test_validation_passes_for_typed_factory_without_cycle(self) -> None:
        """A typed factory with non-cyclic deps should pass validation."""
        container = Container()

        def make_c(a: ServiceA) -> ServiceC:
            return ServiceC(ServiceB(a))

        container.register(ServiceA)
        container.register_factory(ServiceC, make_c)

        container.validate()  # Should not raise

    def test_validation_lazy_breaks_direct_cycle(self) -> None:
        """Lazy[T] breaks a direct cycle: A(b: Lazy[B]) + B(a: A) is not circular."""
        container = Container()
        container.register(LazyConsumerA)
        container.register(LazyDepB)

        container.validate()  # Should not raise — Lazy breaks the cycle

    def test_validation_lazy_does_not_hide_internal_cycle(self) -> None:
        """Lazy breaks the outer edge but internal subgraph cycles are still caught."""
        container = Container()
        container.register(LazyRootA)
        container.register(InternalCycleB)
        container.register(InternalCycleC)

        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        error_msg = str(exc_info.value)
        assert "Circular dependency detected" in error_msg
        assert "InternalCycleB" in error_msg
        assert "InternalCycleC" in error_msg

    def test_validation_factory_wrapper_breaks_cycle(self) -> None:
        """Factory[T] breaks a direct cycle the same way Lazy[T] does."""
        container = Container()
        container.register(FactoryConsumerA)
        container.register(FactoryDepB)

        container.validate()  # Should not raise — Factory breaks the cycle

    def test_validation_optional_dep_skipped_when_missing(self) -> None:
        """Optional deps that are not registered don't produce cycle-detection edges."""

        class OptionalConsumer:
            def __init__(self, a: ServiceA, b: ServiceB | None = None) -> None:
                self.a = a
                self.b = b

        container = Container()
        container.register(ServiceA)
        container.register(OptionalConsumer)
        # ServiceB is NOT registered — optional dep should be silently skipped

        container.validate()  # Should not raise

    def test_validation_collection_dep_does_not_introduce_false_cycle(self) -> None:
        """InjectAll deps fan out to all matching bindings without false cycles."""

        class PluginConsumer:
            def __init__(self, plugins: InjectAll[ServiceA]) -> None:
                self.plugins = plugins

        container = Container()
        container.register(ServiceA)
        container.register(PluginConsumer)

        container.validate()  # Should not raise

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
