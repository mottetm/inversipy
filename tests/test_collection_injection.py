"""Tests for collection injection feature.

This module tests the ability to register multiple implementations of the same
interface and inject them as a collection.
"""

import pytest

from inversipy import (
    Container,
    DependencyNotFoundError,
    Inject,
    Injectable,
    Module,
    Named,
    Scopes,
    ValidationError,
)

# These imports will fail until the feature is implemented
try:
    from inversipy import AmbiguousDependencyError, InjectAll, InjectAllNamed
except ImportError:
    # Placeholder for tests to run (they will fail with appropriate errors)
    AmbiguousDependencyError = None  # type: ignore
    InjectAll = None  # type: ignore
    InjectAllNamed = None  # type: ignore


# =============================================================================
# Test Fixtures - Interfaces and Implementations
# =============================================================================


class IPlugin:
    """Interface for plugins."""

    def execute(self) -> str:
        raise NotImplementedError


class PluginA(IPlugin):
    """Plugin A implementation."""

    def execute(self) -> str:
        return "PluginA"


class PluginB(IPlugin):
    """Plugin B implementation."""

    def execute(self) -> str:
        return "PluginB"


class PluginC(IPlugin):
    """Plugin C implementation."""

    def execute(self) -> str:
        return "PluginC"


class IValidator:
    """Interface for validators."""

    def validate(self, value: str) -> bool:
        raise NotImplementedError


class LengthValidator(IValidator):
    """Validates string length."""

    def validate(self, value: str) -> bool:
        return len(value) > 0


class AlphaValidator(IValidator):
    """Validates string contains only alpha characters."""

    def validate(self, value: str) -> bool:
        return value.isalpha()


class IService:
    """Generic service interface."""

    pass


class ServiceImpl(IService):
    """Service implementation."""

    pass


class CircularA:
    """Service A for circular dependency test."""

    def __init__(self, b: "CircularB") -> None:
        self.b = b


class CircularB:
    """Service B for circular dependency test."""

    def __init__(self, a: CircularA) -> None:
        self.a = a


# =============================================================================
# Test Classes: Accumulation Behavior
# =============================================================================


class TestAccumulationBehavior:
    """Test that multiple register() calls accumulate bindings."""

    def test_multiple_register_calls_accumulate(self) -> None:
        """Multiple register() calls for same interface should accumulate."""
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(IPlugin, PluginC)

        # Should have 3 implementations
        assert container.count(IPlugin) == 3

    def test_same_implementation_can_be_registered_twice(self) -> None:
        """Same implementation can be registered multiple times."""
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginA)

        assert container.count(IPlugin) == 2

    def test_register_returns_self_for_chaining(self) -> None:
        """register() should return self for method chaining."""
        container = Container()
        result = (
            container.register(IPlugin, PluginA)
            .register(IPlugin, PluginB)
            .register(IPlugin, PluginC)
        )

        assert result is container
        assert container.count(IPlugin) == 3

    def test_named_and_unnamed_registrations_are_separate(self) -> None:
        """Named and unnamed registrations should be tracked separately."""
        container = Container()
        container.register(IPlugin, PluginA)  # Unnamed
        container.register(IPlugin, PluginB, name="special")  # Named

        # Unnamed count should be 1
        assert container.count(IPlugin) == 1
        # Named should exist separately
        assert container.has(IPlugin, name="special")


# =============================================================================
# Test Classes: Single Resolution Ambiguity
# =============================================================================


class TestSingleResolutionAmbiguity:
    """Test that get() raises AmbiguousDependencyError when multiple exist."""

    def test_get_with_single_binding_works(self) -> None:
        """get() with single binding should work as before."""
        container = Container()
        container.register(IPlugin, PluginA)

        plugin = container.get(IPlugin)
        assert isinstance(plugin, PluginA)
        assert plugin.execute() == "PluginA"

    def test_get_with_multiple_bindings_raises_ambiguous_error(self) -> None:
        """get() with multiple bindings should raise AmbiguousDependencyError."""
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)

        with pytest.raises(AmbiguousDependencyError) as exc_info:
            container.get(IPlugin)

        assert exc_info.value.dependency_type is IPlugin
        assert exc_info.value.count == 2
        assert "IPlugin" in str(exc_info.value)
        assert "2" in str(exc_info.value)

    def test_get_with_name_works_when_multiple_exist(self) -> None:
        """get() with name should work even when multiple unnamed exist."""
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(IPlugin, PluginC, name="primary")

        # Named resolution should work
        plugin = container.get(IPlugin, name="primary")
        assert isinstance(plugin, PluginC)

    def test_get_with_name_not_affected_by_unnamed_bindings(self) -> None:
        """Named get() should not be affected by unnamed bindings count."""
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(IPlugin, PluginC, name="main")

        # Should resolve the named one without ambiguity
        plugin = container.get(IPlugin, name="main")
        assert isinstance(plugin, PluginC)

    def test_ambiguous_error_message_is_helpful(self) -> None:
        """AmbiguousDependencyError message should suggest fixes."""
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(IPlugin, PluginC)

        with pytest.raises(AmbiguousDependencyError) as exc_info:
            container.get(IPlugin)

        error_msg = str(exc_info.value)
        # Should mention get_all()
        assert "get_all" in error_msg.lower()
        # Should mention using names
        assert "name" in error_msg.lower()

    def test_try_get_with_multiple_bindings_raises(self) -> None:
        """try_get() should also raise AmbiguousDependencyError."""
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)

        # try_get should raise on ambiguity, not return None
        with pytest.raises(AmbiguousDependencyError):
            container.try_get(IPlugin)


# =============================================================================
# Test Classes: Collection Resolution
# =============================================================================


class TestCollectionResolution:
    """Test get_all() method for resolving all implementations."""

    def test_get_all_returns_all_implementations(self) -> None:
        """get_all() should return all registered implementations."""
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(IPlugin, PluginC)

        plugins = container.get_all(IPlugin)

        assert len(plugins) == 3
        assert any(isinstance(p, PluginA) for p in plugins)
        assert any(isinstance(p, PluginB) for p in plugins)
        assert any(isinstance(p, PluginC) for p in plugins)

    def test_get_all_returns_empty_list_when_none_registered(self) -> None:
        """get_all() should return empty list when no implementations."""
        container = Container()

        plugins = container.get_all(IPlugin)

        assert plugins == []
        assert isinstance(plugins, list)

    def test_get_all_preserves_registration_order(self) -> None:
        """get_all() should return implementations in registration order."""
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(IPlugin, PluginC)

        plugins = container.get_all(IPlugin)

        assert isinstance(plugins[0], PluginA)
        assert isinstance(plugins[1], PluginB)
        assert isinstance(plugins[2], PluginC)

    def test_get_all_with_single_implementation(self) -> None:
        """get_all() with single implementation should return list with one item."""
        container = Container()
        container.register(IPlugin, PluginA)

        plugins = container.get_all(IPlugin)

        assert len(plugins) == 1
        assert isinstance(plugins[0], PluginA)

    def test_get_all_does_not_include_named_bindings(self) -> None:
        """get_all() should only return unnamed bindings."""
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(IPlugin, PluginC, name="special")

        plugins = container.get_all(IPlugin)

        assert len(plugins) == 2
        assert not any(isinstance(p, PluginC) for p in plugins)

    def test_get_all_creates_new_instances_for_transient(self) -> None:
        """get_all() should create new instances for transient scope."""
        container = Container()
        container.register(IPlugin, PluginA, scope=Scopes.TRANSIENT)

        plugins1 = container.get_all(IPlugin)
        plugins2 = container.get_all(IPlugin)

        assert plugins1[0] is not plugins2[0]


# =============================================================================
# Test Classes: Async Collection Resolution
# =============================================================================


class TestAsyncCollectionResolution:
    """Test get_all_async() method."""

    @pytest.mark.asyncio
    async def test_get_all_async_returns_all_implementations(self) -> None:
        """get_all_async() should return all registered implementations."""
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)

        plugins = await container.get_all_async(IPlugin)

        assert len(plugins) == 2
        assert any(isinstance(p, PluginA) for p in plugins)
        assert any(isinstance(p, PluginB) for p in plugins)

    @pytest.mark.asyncio
    async def test_get_all_async_returns_empty_list_when_none(self) -> None:
        """get_all_async() should return empty list when none registered."""
        container = Container()

        plugins = await container.get_all_async(IPlugin)

        assert plugins == []

    @pytest.mark.asyncio
    async def test_get_all_async_with_async_factory(self) -> None:
        """get_all_async() should work with async factories."""
        container = Container()

        async def create_plugin_a() -> PluginA:
            return PluginA()

        async def create_plugin_b() -> PluginB:
            return PluginB()

        container.register_factory(IPlugin, create_plugin_a)
        container.register_factory(IPlugin, create_plugin_b)

        plugins = await container.get_all_async(IPlugin)

        assert len(plugins) == 2


# =============================================================================
# Test Classes: Scopes in Collections
# =============================================================================


class TestScopesInCollections:
    """Test that scopes work correctly with collection injection."""

    def test_singleton_scope_returns_same_instances(self) -> None:
        """Singleton scoped items should return same instances across calls."""
        container = Container()
        container.register(IPlugin, PluginA, scope=Scopes.SINGLETON)
        container.register(IPlugin, PluginB, scope=Scopes.SINGLETON)

        plugins1 = container.get_all(IPlugin)
        plugins2 = container.get_all(IPlugin)

        assert plugins1[0] is plugins2[0]
        assert plugins1[1] is plugins2[1]

    def test_transient_scope_returns_new_instances(self) -> None:
        """Transient scoped items should return new instances each call."""
        container = Container()
        container.register(IPlugin, PluginA, scope=Scopes.TRANSIENT)
        container.register(IPlugin, PluginB, scope=Scopes.TRANSIENT)

        plugins1 = container.get_all(IPlugin)
        plugins2 = container.get_all(IPlugin)

        assert plugins1[0] is not plugins2[0]
        assert plugins1[1] is not plugins2[1]

    def test_mixed_scopes_in_collection(self) -> None:
        """Collection can have items with different scopes."""
        container = Container()
        container.register(IPlugin, PluginA, scope=Scopes.SINGLETON)
        container.register(IPlugin, PluginB, scope=Scopes.TRANSIENT)

        plugins1 = container.get_all(IPlugin)
        plugins2 = container.get_all(IPlugin)

        # PluginA is singleton - same instance
        assert plugins1[0] is plugins2[0]
        # PluginB is transient - different instances
        assert plugins1[1] is not plugins2[1]


# =============================================================================
# Test Classes: InjectAll Type Alias
# =============================================================================


class TestInjectAllTypeAlias:
    """Test InjectAll[T] type alias for property/constructor injection."""

    def test_inject_all_property_injection(self) -> None:
        """InjectAll should work with Injectable property injection."""

        class PluginManager(Injectable):
            plugins: InjectAll[IPlugin]

            def run_all(self) -> list[str]:
                return [p.execute() for p in self.plugins]

        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(PluginManager)

        manager = container.get(PluginManager)

        assert len(manager.plugins) == 2
        results = manager.run_all()
        assert "PluginA" in results
        assert "PluginB" in results

    def test_inject_all_constructor_injection(self) -> None:
        """InjectAll should work with constructor injection."""

        class PluginRunner:
            def __init__(self, plugins: InjectAll[IPlugin]) -> None:
                self.plugins = plugins

            def run_all(self) -> list[str]:
                return [p.execute() for p in self.plugins]

        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(PluginRunner)

        runner = container.get(PluginRunner)

        assert len(runner.plugins) == 2

    def test_inject_all_with_empty_collection(self) -> None:
        """InjectAll should inject empty list when no implementations."""

        class OptionalPluginManager(Injectable):
            plugins: InjectAll[IPlugin]

        container = Container()
        container.register(OptionalPluginManager)

        manager = container.get(OptionalPluginManager)

        assert manager.plugins == []
        assert isinstance(manager.plugins, list)

    def test_inject_all_combined_with_inject(self) -> None:
        """InjectAll can be used alongside Inject."""

        class ComplexService(Injectable):
            plugins: InjectAll[IPlugin]
            primary: Inject[IService]

        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(IService, ServiceImpl)
        container.register(ComplexService)

        service = container.get(ComplexService)

        assert len(service.plugins) == 2
        assert isinstance(service.primary, ServiceImpl)

    def test_inject_all_with_named_inject(self) -> None:
        """InjectAll can be used alongside named Inject."""

        class MixedService(Injectable):
            all_plugins: InjectAll[IPlugin]
            main_plugin: Inject[IPlugin, Named("main")]

        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(IPlugin, PluginC, name="main")
        container.register(MixedService)

        service = container.get(MixedService)

        assert len(service.all_plugins) == 2
        assert isinstance(service.main_plugin, PluginC)


# =============================================================================
# Test Classes: Module Collections
# =============================================================================


class TestModuleCollections:
    """Test collection injection with modules."""

    def test_module_get_all_respects_public_visibility(self) -> None:
        """Module get_all() returns empty list when key is not public."""
        module = Module("plugins")
        # Register all as private - key is never made public
        module.register(IPlugin, PluginA, public=False)
        module.register(IPlugin, PluginB, public=False)

        plugins = module.get_all(IPlugin)

        # No plugins returned since key is not public
        assert len(plugins) == 0

    def test_module_get_all_returns_all_when_key_public(self) -> None:
        """Module get_all() returns all implementations when key is public."""
        module = Module("plugins")
        # First registration makes the key public
        module.register(IPlugin, PluginA, public=True)
        # Second registration - key is already public
        module.register(IPlugin, PluginB, public=True)

        plugins = module.get_all(IPlugin)

        # All implementations under the public key are returned
        assert len(plugins) == 2
        assert isinstance(plugins[0], PluginA)
        assert isinstance(plugins[1], PluginB)

    def test_container_aggregates_from_modules(self) -> None:
        """Container should aggregate implementations from registered modules."""
        module = Module("plugins")
        module.register(IPlugin, PluginA, public=True)
        module.register(IPlugin, PluginB, public=True)

        container = Container()
        container.register(IPlugin, PluginC)
        container.register_module(module)

        plugins = container.get_all(IPlugin)

        assert len(plugins) == 3

    def test_container_aggregates_from_multiple_modules(self) -> None:
        """Container should aggregate from multiple modules."""
        module1 = Module("module1")
        module1.register(IPlugin, PluginA, public=True)

        module2 = Module("module2")
        module2.register(IPlugin, PluginB, public=True)

        container = Container()
        container.register_module(module1)
        container.register_module(module2)

        plugins = container.get_all(IPlugin)

        assert len(plugins) == 2

    def test_parent_container_aggregation(self) -> None:
        """Child container should aggregate from parent."""
        parent = Container()
        parent.register(IPlugin, PluginA)

        child = parent.create_child()
        child.register(IPlugin, PluginB)

        plugins = child.get_all(IPlugin)

        assert len(plugins) == 2

    def test_module_count_only_counts_public(self) -> None:
        """Module count() returns 0 when key is not public."""
        module = Module("plugins")
        # All private - key is never made public
        module.register(IPlugin, PluginA, public=False)
        module.register(IPlugin, PluginB, public=False)

        # Module should report 0 since key is not public
        assert module.count(IPlugin) == 0

    def test_module_count_returns_all_when_key_public(self) -> None:
        """Module count() returns count of all implementations when key is public."""
        module = Module("plugins")
        module.register(IPlugin, PluginA, public=True)
        module.register(IPlugin, PluginB, public=True)
        module.register(IPlugin, PluginC, public=True)

        # Module should report all 3 since key is public
        assert module.count(IPlugin) == 3


# =============================================================================
# Test Classes: Validation
# =============================================================================


class TestValidation:
    """Test validation with collection injection."""

    def test_validation_passes_with_inject_all_empty(self) -> None:
        """Validation should pass when InjectAll dependency has no implementations."""
        # Use regular class with constructor injection instead of Injectable
        # to test InjectAll validation in constructor parameters
        class OptionalPlugins:
            def __init__(self, plugins: InjectAll[IPlugin]) -> None:
                self.plugins = plugins

        container = Container()
        container.register(OptionalPlugins)

        # Should not raise - InjectAll is always valid (returns empty list if none)
        container.validate()

    def test_validation_detects_ambiguous_dependency(self) -> None:
        """Validation should detect ambiguous dependencies."""

        class NeedsPlugin:
            def __init__(self, plugin: IPlugin) -> None:
                self.plugin = plugin

        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(NeedsPlugin)

        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        error_msg = str(exc_info.value)
        assert "IPlugin" in error_msg
        assert "2" in error_msg or "multiple" in error_msg.lower()

    def test_validation_error_suggests_named_or_inject_all(self) -> None:
        """Validation error for ambiguity should suggest fixes."""

        class NeedsPlugin:
            def __init__(self, plugin: IPlugin) -> None:
                self.plugin = plugin

        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(NeedsPlugin)

        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        error_msg = str(exc_info.value)
        # Should suggest Named() or InjectAll
        assert "Named" in error_msg or "InjectAll" in error_msg

    def test_validation_passes_with_named_dependency(self) -> None:
        """Validation should pass when ambiguity is resolved with Named."""

        class NeedsPlugin:
            def __init__(self, plugin: Inject[IPlugin, Named("main")]) -> None:
                self.plugin = plugin

        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        container.register(IPlugin, PluginC, name="main")
        container.register(NeedsPlugin)

        # Should not raise - named dependency resolves ambiguity
        container.validate()

    def test_validation_passes_with_single_implementation(self) -> None:
        """Validation should pass with single implementation (no ambiguity)."""

        class NeedsPlugin:
            def __init__(self, plugin: IPlugin) -> None:
                self.plugin = plugin

        container = Container()
        container.register(IPlugin, PluginA)
        container.register(NeedsPlugin)

        # Should not raise - only one implementation
        container.validate()


# =============================================================================
# Test Classes: Container.run() Integration
# =============================================================================


class TestContainerRunIntegration:
    """Test that container.run() works with collection injection."""

    def test_run_with_inject_all_parameter(self) -> None:
        """container.run() should resolve InjectAll parameters."""

        def process_plugins(plugins: InjectAll[IPlugin]) -> list[str]:
            return [p.execute() for p in plugins]

        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)

        results = container.run(process_plugins)

        assert len(results) == 2
        assert "PluginA" in results
        assert "PluginB" in results

    def test_run_with_ambiguous_dependency_raises(self) -> None:
        """container.run() should raise on ambiguous dependencies."""

        def process_plugin(plugin: IPlugin) -> str:
            return plugin.execute()

        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)

        with pytest.raises(AmbiguousDependencyError):
            container.run(process_plugin)

    @pytest.mark.asyncio
    async def test_run_async_with_inject_all(self) -> None:
        """container.run_async() should resolve InjectAll parameters."""

        def process_plugins(plugins: InjectAll[IPlugin]) -> list[str]:
            return [p.execute() for p in plugins]

        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)

        results = await container.run_async(process_plugins)

        assert len(results) == 2


# =============================================================================
# Test Classes: has() and count() Methods
# =============================================================================


class TestHasAndCount:
    """Test has() and count() methods with collections."""

    def test_has_returns_true_with_multiple_implementations(self) -> None:
        """has() should return True when any implementations exist."""
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)

        assert container.has(IPlugin) is True

    def test_has_returns_false_when_none_registered(self) -> None:
        """has() should return False when no implementations."""
        container = Container()

        assert container.has(IPlugin) is False

    def test_count_returns_number_of_implementations(self) -> None:
        """count() should return the number of registered implementations."""
        container = Container()

        assert container.count(IPlugin) == 0

        container.register(IPlugin, PluginA)
        assert container.count(IPlugin) == 1

        container.register(IPlugin, PluginB)
        assert container.count(IPlugin) == 2

        container.register(IPlugin, PluginC)
        assert container.count(IPlugin) == 3

    def test_count_includes_parent_implementations(self) -> None:
        """count() should include implementations from parent container."""
        parent = Container()
        parent.register(IPlugin, PluginA)

        child = parent.create_child()
        child.register(IPlugin, PluginB)

        assert child.count(IPlugin) == 2

    def test_count_includes_module_implementations(self) -> None:
        """count() should include public implementations from modules."""
        module = Module("plugins")
        module.register(IPlugin, PluginA, public=True)
        module.register(IPlugin, PluginB, public=True)

        container = Container()
        container.register(IPlugin, PluginC)
        container.register_module(module)

        assert container.count(IPlugin) == 3


# =============================================================================
# Test Classes: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_get_all_with_instance_registrations(self) -> None:
        """get_all() should work with pre-created instances."""
        instance_a = PluginA()
        instance_b = PluginB()

        container = Container()
        container.register_instance(IPlugin, instance_a)
        container.register_instance(IPlugin, instance_b)

        plugins = container.get_all(IPlugin)

        assert len(plugins) == 2
        assert instance_a in plugins
        assert instance_b in plugins

    def test_get_all_with_factory_registrations(self) -> None:
        """get_all() should work with factory registrations."""
        container = Container()

        def create_a() -> IPlugin:
            return PluginA()

        def create_b() -> IPlugin:
            return PluginB()

        container.register_factory(IPlugin, create_a)
        container.register_factory(IPlugin, create_b)

        plugins = container.get_all(IPlugin)

        assert len(plugins) == 2

    def test_get_all_with_mixed_registration_types(self) -> None:
        """get_all() should work with mixed registration types."""
        instance_a = PluginA()

        def create_b() -> IPlugin:
            return PluginB()

        container = Container()
        container.register_instance(IPlugin, instance_a)
        container.register_factory(IPlugin, create_b)
        container.register(IPlugin, PluginC)

        plugins = container.get_all(IPlugin)

        assert len(plugins) == 3

    def test_circular_dependency_in_collection_item(self) -> None:
        """Circular dependency in a collection item should be detected."""
        from inversipy import CircularDependencyError

        container = Container()
        container.register(CircularA)
        container.register(CircularB)

        with pytest.raises(CircularDependencyError):
            container.get_all(CircularA)

    def test_get_async_with_multiple_bindings_raises(self) -> None:
        """get_async() should also raise AmbiguousDependencyError."""

        @pytest.mark.asyncio
        async def test() -> None:
            container = Container()
            container.register(IPlugin, PluginA)
            container.register(IPlugin, PluginB)

            with pytest.raises(AmbiguousDependencyError):
                await container.get_async(IPlugin)

    def test_repr_with_multiple_bindings(self) -> None:
        """Container repr should handle multiple bindings gracefully."""
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)

        repr_str = repr(container)
        assert "Container" in repr_str


# =============================================================================
# Test Classes: Named Collection Injection
# =============================================================================


class TestNamedCollectionInjection:
    """Test named collection injection feature."""

    def test_get_all_with_name_returns_named_bindings(self) -> None:
        """get_all(T, name='x') should return all bindings with that name."""
        container = Container()
        container.register(IPlugin, PluginA, name="core")
        container.register(IPlugin, PluginB, name="core")
        container.register(IPlugin, PluginC, name="optional")

        core_plugins = container.get_all(IPlugin, name="core")

        assert len(core_plugins) == 2
        assert any(isinstance(p, PluginA) for p in core_plugins)
        assert any(isinstance(p, PluginB) for p in core_plugins)
        assert not any(isinstance(p, PluginC) for p in core_plugins)

    def test_get_all_named_returns_empty_list_when_none(self) -> None:
        """get_all(T, name='x') returns empty list when no named bindings exist."""
        container = Container()
        container.register(IPlugin, PluginA)  # Unnamed

        plugins = container.get_all(IPlugin, name="nonexistent")

        assert plugins == []
        assert isinstance(plugins, list)

    def test_get_all_named_preserves_registration_order(self) -> None:
        """get_all(T, name='x') should preserve registration order."""
        container = Container()
        container.register(IPlugin, PluginA, name="ordered")
        container.register(IPlugin, PluginB, name="ordered")
        container.register(IPlugin, PluginC, name="ordered")

        plugins = container.get_all(IPlugin, name="ordered")

        assert isinstance(plugins[0], PluginA)
        assert isinstance(plugins[1], PluginB)
        assert isinstance(plugins[2], PluginC)

    def test_get_all_named_does_not_include_unnamed(self) -> None:
        """get_all(T, name='x') should not include unnamed bindings."""
        container = Container()
        container.register(IPlugin, PluginA)  # Unnamed
        container.register(IPlugin, PluginB, name="group")
        container.register(IPlugin, PluginC, name="group")

        plugins = container.get_all(IPlugin, name="group")

        assert len(plugins) == 2
        assert not any(isinstance(p, PluginA) for p in plugins)

    def test_get_all_named_does_not_include_other_names(self) -> None:
        """get_all(T, name='x') should not include bindings with other names."""
        container = Container()
        container.register(IPlugin, PluginA, name="group1")
        container.register(IPlugin, PluginB, name="group2")

        plugins = container.get_all(IPlugin, name="group1")

        assert len(plugins) == 1
        assert isinstance(plugins[0], PluginA)

    def test_count_with_name_returns_named_count(self) -> None:
        """count(T, name='x') should return count of named bindings."""
        container = Container()
        container.register(IPlugin, PluginA, name="core")
        container.register(IPlugin, PluginB, name="core")
        container.register(IPlugin, PluginC)  # Unnamed

        assert container.count(IPlugin, name="core") == 2
        assert container.count(IPlugin) == 1  # Only unnamed

    @pytest.mark.asyncio
    async def test_get_all_async_with_name(self) -> None:
        """get_all_async(T, name='x') should return all named bindings."""
        container = Container()
        container.register(IPlugin, PluginA, name="async_group")
        container.register(IPlugin, PluginB, name="async_group")

        plugins = await container.get_all_async(IPlugin, name="async_group")

        assert len(plugins) == 2

    def test_get_all_named_with_singleton_scope(self) -> None:
        """Named collection should respect singleton scope."""
        container = Container()
        container.register(IPlugin, PluginA, name="single", scope=Scopes.SINGLETON)
        container.register(IPlugin, PluginB, name="single", scope=Scopes.SINGLETON)

        plugins1 = container.get_all(IPlugin, name="single")
        plugins2 = container.get_all(IPlugin, name="single")

        assert plugins1[0] is plugins2[0]
        assert plugins1[1] is plugins2[1]

    def test_get_all_named_with_transient_scope(self) -> None:
        """Named collection should respect transient scope."""
        container = Container()
        container.register(IPlugin, PluginA, name="transient", scope=Scopes.TRANSIENT)

        plugins1 = container.get_all(IPlugin, name="transient")
        plugins2 = container.get_all(IPlugin, name="transient")

        assert plugins1[0] is not plugins2[0]


class TestInjectAllNamedTypeAlias:
    """Test InjectAllNamed[T, Named('x')] type alias for property/constructor injection."""

    def test_inject_all_named_property_injection(self) -> None:
        """InjectAllNamed should work with Injectable property injection."""

        class PluginManager(Injectable):
            core_plugins: InjectAllNamed[IPlugin, Named("core")]

            def run_core(self) -> list[str]:
                return [p.execute() for p in self.core_plugins]

        container = Container()
        container.register(IPlugin, PluginA, name="core")
        container.register(IPlugin, PluginB, name="core")
        container.register(IPlugin, PluginC, name="optional")
        container.register(PluginManager)

        manager = container.get(PluginManager)

        assert len(manager.core_plugins) == 2
        results = manager.run_core()
        assert "PluginA" in results
        assert "PluginB" in results
        assert "PluginC" not in results

    def test_inject_all_named_constructor_injection(self) -> None:
        """InjectAllNamed should work with constructor injection."""

        class PluginRunner:
            def __init__(self, plugins: InjectAllNamed[IPlugin, Named("runner")]) -> None:
                self.plugins = plugins

        container = Container()
        container.register(IPlugin, PluginA, name="runner")
        container.register(IPlugin, PluginB, name="runner")
        container.register(PluginRunner)

        runner = container.get(PluginRunner)

        assert len(runner.plugins) == 2

    def test_inject_all_named_with_empty_collection(self) -> None:
        """InjectAllNamed should inject empty list when no matching named bindings."""

        class OptionalManager(Injectable):
            plugins: InjectAllNamed[IPlugin, Named("missing")]

        container = Container()
        container.register(OptionalManager)

        manager = container.get(OptionalManager)

        assert manager.plugins == []
        assert isinstance(manager.plugins, list)

    def test_inject_all_named_combined_with_inject_all(self) -> None:
        """InjectAllNamed can be used alongside InjectAll."""

        class ComplexManager(Injectable):
            all_plugins: InjectAll[IPlugin]
            core_plugins: InjectAllNamed[IPlugin, Named("core")]

        container = Container()
        container.register(IPlugin, PluginA)  # Unnamed
        container.register(IPlugin, PluginB)  # Unnamed
        container.register(IPlugin, PluginC, name="core")  # Named

        # Note: Named bindings are separate from unnamed
        container.register(IPlugin, PluginA, name="core")  # Named
        container.register(ComplexManager)

        manager = container.get(ComplexManager)

        # all_plugins gets unnamed bindings
        assert len(manager.all_plugins) == 2
        # core_plugins gets named "core" bindings
        assert len(manager.core_plugins) == 2

    def test_inject_all_named_with_inject(self) -> None:
        """InjectAllNamed can be used alongside regular Inject."""

        class MixedService(Injectable):
            core_plugins: InjectAllNamed[IPlugin, Named("core")]
            primary: Inject[IService]

        container = Container()
        container.register(IPlugin, PluginA, name="core")
        container.register(IPlugin, PluginB, name="core")
        container.register(IService, ServiceImpl)
        container.register(MixedService)

        service = container.get(MixedService)

        assert len(service.core_plugins) == 2
        assert isinstance(service.primary, ServiceImpl)

    def test_multiple_inject_all_named_different_groups(self) -> None:
        """Multiple InjectAllNamed with different groups."""

        class MultiGroupManager(Injectable):
            core_plugins: InjectAllNamed[IPlugin, Named("core")]
            optional_plugins: InjectAllNamed[IPlugin, Named("optional")]

        container = Container()
        container.register(IPlugin, PluginA, name="core")
        container.register(IPlugin, PluginB, name="core")
        container.register(IPlugin, PluginC, name="optional")
        container.register(MultiGroupManager)

        manager = container.get(MultiGroupManager)

        assert len(manager.core_plugins) == 2
        assert len(manager.optional_plugins) == 1
        assert isinstance(manager.optional_plugins[0], PluginC)


class TestNamedCollectionWithModules:
    """Test named collection injection with modules."""

    def test_module_get_all_with_name(self) -> None:
        """Module get_all(T, name='x') should work with named bindings."""
        module = Module("plugins")
        module.register(IPlugin, PluginA, name="core", public=True)
        module.register(IPlugin, PluginB, name="core", public=True)

        plugins = module.get_all(IPlugin, name="core")

        assert len(plugins) == 2

    def test_module_count_with_name(self) -> None:
        """Module count(T, name='x') should count named bindings."""
        module = Module("plugins")
        module.register(IPlugin, PluginA, name="core", public=True)
        module.register(IPlugin, PluginB, name="core", public=True)
        module.register(IPlugin, PluginC, public=True)

        assert module.count(IPlugin, name="core") == 2
        assert module.count(IPlugin) == 1

    def test_container_aggregates_named_from_modules(self) -> None:
        """Container should aggregate named implementations from modules."""
        module = Module("plugins")
        module.register(IPlugin, PluginA, name="core", public=True)
        module.register(IPlugin, PluginB, name="core", public=True)

        container = Container()
        container.register(IPlugin, PluginC, name="core")
        container.register_module(module)

        plugins = container.get_all(IPlugin, name="core")

        assert len(plugins) == 3

    def test_parent_container_named_aggregation(self) -> None:
        """Child container should aggregate named bindings from parent."""
        parent = Container()
        parent.register(IPlugin, PluginA, name="shared")

        child = parent.create_child()
        child.register(IPlugin, PluginB, name="shared")

        plugins = child.get_all(IPlugin, name="shared")

        assert len(plugins) == 2


class TestNamedCollectionContainerRun:
    """Test container.run() with named collection injection."""

    def test_run_with_inject_all_named_parameter(self) -> None:
        """container.run() should resolve InjectAllNamed parameters."""

        def process_core(plugins: InjectAllNamed[IPlugin, Named("core")]) -> list[str]:
            return [p.execute() for p in plugins]

        container = Container()
        container.register(IPlugin, PluginA, name="core")
        container.register(IPlugin, PluginB, name="core")
        container.register(IPlugin, PluginC, name="optional")

        results = container.run(process_core)

        assert len(results) == 2
        assert "PluginA" in results
        assert "PluginB" in results
        assert "PluginC" not in results

    @pytest.mark.asyncio
    async def test_run_async_with_inject_all_named(self) -> None:
        """container.run_async() should resolve InjectAllNamed parameters."""

        def process_core(plugins: InjectAllNamed[IPlugin, Named("core")]) -> list[str]:
            return [p.execute() for p in plugins]

        container = Container()
        container.register(IPlugin, PluginA, name="core")
        container.register(IPlugin, PluginB, name="core")

        results = await container.run_async(process_core)

        assert len(results) == 2
