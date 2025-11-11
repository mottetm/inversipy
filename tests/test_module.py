"""Tests for the Module class."""

import pytest
from inversipy import Container, Module, ModuleBuilder, SINGLETON, RegistrationError


class PublicService:
    """Service intended to be public."""

    def get_value(self) -> str:
        return "public"


class PrivateService:
    """Service intended to be private."""

    def get_value(self) -> str:
        return "private"


class DependentService:
    """Service that depends on PrivateService."""

    def __init__(self, private: PrivateService) -> None:
        self.private = private

    def get_value(self) -> str:
        return f"dependent:{self.private.get_value()}"


class TestModuleBasics:
    """Test basic module functionality."""

    def test_register_public_dependency(self) -> None:
        """Test registering a public dependency."""
        module = Module("TestModule")
        module.register(PublicService, public=True)

        assert module.is_public(PublicService)
        assert PublicService in module.get_public_dependencies()

    def test_register_private_dependency(self) -> None:
        """Test registering a private dependency."""
        module = Module("TestModule")
        module.register(PrivateService, public=False)

        assert not module.is_public(PrivateService)
        assert PrivateService not in module.get_public_dependencies()

    def test_export_dependency(self) -> None:
        """Test exporting a dependency."""
        module = Module("TestModule")
        module.register(PublicService, public=False)
        module.export(PublicService)

        assert module.is_public(PublicService)

    def test_export_unregistered_raises_error(self) -> None:
        """Test that exporting an unregistered dependency raises error."""
        module = Module("TestModule")

        with pytest.raises(RegistrationError):
            module.export(PublicService)

    def test_register_instance(self) -> None:
        """Test registering an instance."""
        module = Module("TestModule")
        instance = PublicService()
        module.register_instance(PublicService, instance, public=True)

        assert module.is_public(PublicService)

    def test_register_factory(self) -> None:
        """Test registering a factory."""
        module = Module("TestModule")

        def factory() -> PublicService:
            return PublicService()

        module.register_factory(PublicService, factory, public=True)

        assert module.is_public(PublicService)


class TestModuleLoading:
    """Test registering modules as providers."""

    def test_register_module_with_public_dependencies(self) -> None:
        """Test registering a module with public dependencies."""
        module = Module("TestModule")
        module.register(PublicService, public=True)
        module.register(PrivateService, public=False)

        container = Container()
        container.register_module(module)

        # Public dependency should be available
        assert container.has(PublicService)
        service = container.get(PublicService)
        assert isinstance(service, PublicService)

        # Private dependency should not be available
        assert not container.has(PrivateService)

    def test_module_preserves_scopes(self) -> None:
        """Test that module preserves dependency scopes."""
        module = Module("TestModule")
        module.register(PublicService, public=True, scope=SINGLETON)

        container = Container()
        container.register_module(module)

        service1 = container.get(PublicService)
        service2 = container.get(PublicService)

        assert service1 is service2

    def test_register_multiple_modules(self) -> None:
        """Test registering multiple modules."""
        module1 = Module("Module1")
        module1.register(PublicService, public=True)

        module2 = Module("Module2")
        module2.register(PrivateService, public=True)

        container = Container()
        container.register_module(module1)
        container.register_module(module2)

        assert container.has(PublicService)
        assert container.has(PrivateService)

    def test_module_internal_dependencies(self) -> None:
        """Test that modules can resolve internal dependencies."""
        module = Module("TestModule")
        module.register(PrivateService, public=False)
        module.register(DependentService, public=True)

        container = Container()
        container.register_module(module)

        # DependentService should be available and resolve correctly
        # The module resolves its own internal dependencies
        assert container.has(DependentService)
        service = container.get(DependentService)
        assert isinstance(service, DependentService)
        assert isinstance(service.private, PrivateService)

    def test_module_remains_live(self) -> None:
        """Test that modules remain live providers after registration."""
        module = Module("TestModule")
        module.register(PublicService, public=True)

        container = Container()
        container.register_module(module)

        # Initially can resolve
        assert container.has(PublicService)
        service1 = container.get(PublicService)

        # Add a new public dependency to the module
        module.register(PrivateService, public=True)

        # Container should now be able to resolve it
        assert container.has(PrivateService)
        service2 = container.get(PrivateService)
        assert isinstance(service2, PrivateService)


class TestModuleBuilder:
    """Test ModuleBuilder."""

    def test_builder_bind(self) -> None:
        """Test binding with builder."""
        module = (
            ModuleBuilder("TestModule")
            .bind(PrivateService)
            .bind_public(PublicService)
            .build()
        )

        assert not module.is_public(PrivateService)
        assert module.is_public(PublicService)

    def test_builder_export(self) -> None:
        """Test exporting with builder."""
        module = (
            ModuleBuilder("TestModule")
            .bind(PublicService)
            .export(PublicService)
            .build()
        )

        assert module.is_public(PublicService)

    def test_builder_with_scopes(self) -> None:
        """Test builder with different scopes."""
        module = (
            ModuleBuilder("TestModule")
            .bind_public(PublicService, scope=SINGLETON)
            .build()
        )

        container = Container()
        container.register_module(module)

        service1 = container.get(PublicService)
        service2 = container.get(PublicService)

        assert service1 is service2


class TestModuleValidation:
    """Test module validation."""

    def test_validate_passes_for_valid_module(self) -> None:
        """Test that validation passes for valid module."""
        module = Module("TestModule")
        module.register(PrivateService)
        module.register(DependentService)

        # Should not raise
        module.validate()

    def test_module_repr(self) -> None:
        """Test module string representation."""
        module = Module("TestModule")
        module.register(PublicService, public=True)
        module.register(PrivateService, public=False)

        repr_str = repr(module)
        assert "TestModule" in repr_str
        assert "PublicService" in repr_str
        assert "total_dependencies=2" in repr_str
