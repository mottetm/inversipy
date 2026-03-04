"""Tests for container freezing / immutability."""

import pytest

from inversipy import Container, RegistrationError, Scopes
from inversipy.module import Module


class SimpleService:
    def get_value(self) -> str:
        return "simple"


class OtherService:
    def __init__(self, simple: SimpleService) -> None:
        self.simple = simple


class TestContainerFreeze:
    """Test that frozen containers reject registrations."""

    def test_freeze_returns_self(self) -> None:
        """freeze() returns self for chaining."""
        container = Container()
        result = container.freeze()
        assert result is container

    def test_frozen_property(self) -> None:
        """frozen property reflects freeze state."""
        container = Container()
        assert container.frozen is False
        container.freeze()
        assert container.frozen is True

    def test_frozen_register_raises(self) -> None:
        """register() raises RegistrationError after freeze."""
        container = Container()
        container.freeze()

        with pytest.raises(RegistrationError, match="frozen"):
            container.register(SimpleService)

    def test_frozen_register_factory_raises(self) -> None:
        """register_factory() raises RegistrationError after freeze."""
        container = Container()
        container.freeze()

        with pytest.raises(RegistrationError, match="frozen"):
            container.register_factory(SimpleService, lambda: SimpleService())

    def test_frozen_register_instance_raises(self) -> None:
        """register_instance() raises RegistrationError after freeze."""
        container = Container()
        container.freeze()

        with pytest.raises(RegistrationError, match="frozen"):
            container.register_instance(SimpleService, SimpleService())

    def test_frozen_register_module_raises(self) -> None:
        """register_module() raises RegistrationError after freeze."""
        container = Container()
        container.freeze()

        module = Module("test")
        module.register(SimpleService, public=True)

        with pytest.raises(RegistrationError, match="frozen"):
            container.register_module(module)

    def test_frozen_resolution_still_works(self) -> None:
        """Frozen containers can still resolve registered deps."""
        container = Container()
        container.register(SimpleService)
        container.register(OtherService)
        container.freeze()

        service = container.get(OtherService)
        assert isinstance(service, OtherService)
        assert isinstance(service.simple, SimpleService)

    def test_register_before_freeze_works(self) -> None:
        """Registrations before freeze are preserved."""
        container = Container()
        container.register(SimpleService, scope=Scopes.SINGLETON)
        container.freeze()

        s1 = container.get(SimpleService)
        s2 = container.get(SimpleService)
        assert s1 is s2

    def test_child_container_not_frozen_by_parent(self) -> None:
        """Freezing parent doesn't freeze child containers."""
        parent = Container()
        parent.register(SimpleService)
        parent.freeze()

        child = parent.create_child()
        # Child should still be writable
        child.register(OtherService)
        service = child.get(OtherService)
        assert isinstance(service, OtherService)

    def test_freeze_chaining(self) -> None:
        """freeze() supports method chaining from register()."""
        container = Container()
        container.register(SimpleService).register(OtherService).freeze()

        assert container.frozen is True
        service = container.get(OtherService)
        assert isinstance(service, OtherService)

    def test_freeze_cascades_to_modules(self) -> None:
        """Freezing a container also freezes its registered modules."""
        module = Module("test")
        module.register(SimpleService, public=True)

        container = Container()
        container.register_module(module)
        container.freeze()

        assert module.frozen is True
        with pytest.raises(RegistrationError, match="frozen"):
            module.register(OtherService, public=True)

    def test_freeze_cascades_to_parent(self) -> None:
        """Freezing a child container also freezes the parent."""
        parent = Container()
        parent.register(SimpleService)

        child = parent.create_child()
        child.freeze()

        assert parent.frozen is True
        with pytest.raises(RegistrationError, match="frozen"):
            parent.register(OtherService)

    def test_freeze_cascades_to_nested_modules(self) -> None:
        """Freezing cascades through nested modules."""
        inner = Module("inner")
        inner.register(SimpleService, public=True)

        outer = Module("outer")
        outer.register_module(inner)

        container = Container()
        container.register_module(outer)
        container.freeze()

        assert outer.frozen is True
        assert inner.frozen is True

    def test_freeze_does_not_cascade_to_children(self) -> None:
        """Freezing a parent does NOT freeze child containers."""
        parent = Container()
        parent.register(SimpleService)

        child = parent.create_child()
        child.register(OtherService)

        parent.freeze()

        assert child.frozen is False
        child.register(SimpleService)
