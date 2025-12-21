"""Collection injection example for inversipy.

This example demonstrates:
- Registering multiple implementations of an interface
- Collection injection with InjectAll[T]
- Named collection injection with InjectAll[T, Named("x")]
- Using get_all() for programmatic collection resolution
- Plugin system pattern with grouped plugins
"""

from inversipy import (
    Container,
    Injectable,
    InjectAll,
    Named,
)

# =============================================================================
# Plugin Interface and Implementations
# =============================================================================


class IPlugin:
    """Interface for plugins."""

    def get_name(self) -> str:
        raise NotImplementedError

    def execute(self) -> str:
        raise NotImplementedError


class LoggingPlugin(IPlugin):
    """Plugin that logs operations."""

    def get_name(self) -> str:
        return "LoggingPlugin"

    def execute(self) -> str:
        return "Logging operation executed"


class MetricsPlugin(IPlugin):
    """Plugin that collects metrics."""

    def get_name(self) -> str:
        return "MetricsPlugin"

    def execute(self) -> str:
        return "Metrics collected"


class AuthPlugin(IPlugin):
    """Plugin that handles authentication."""

    def get_name(self) -> str:
        return "AuthPlugin"

    def execute(self) -> str:
        return "Authentication validated"


class CachePlugin(IPlugin):
    """Plugin that provides caching."""

    def get_name(self) -> str:
        return "CachePlugin"

    def execute(self) -> str:
        return "Cache warmed up"


# =============================================================================
# Plugin Manager using Collection Injection
# =============================================================================


class PluginManager(Injectable):
    """Manager that uses all registered plugins via InjectAll."""

    plugins: InjectAll[IPlugin]

    def run_all(self) -> list[str]:
        """Execute all plugins and return results."""
        return [plugin.execute() for plugin in self.plugins]

    def list_plugins(self) -> list[str]:
        """Get names of all registered plugins."""
        return [plugin.get_name() for plugin in self.plugins]


# =============================================================================
# Grouped Plugin Manager using Named Collection Injection
# =============================================================================


class GroupedPluginManager(Injectable):
    """Manager that uses plugins grouped by category."""

    core_plugins: InjectAll[IPlugin, Named("core")]
    optional_plugins: InjectAll[IPlugin, Named("optional")]

    def run_core(self) -> list[str]:
        """Execute only core plugins."""
        return [plugin.execute() for plugin in self.core_plugins]

    def run_optional(self) -> list[str]:
        """Execute only optional plugins."""
        return [plugin.execute() for plugin in self.optional_plugins]

    def run_all(self) -> list[str]:
        """Execute all plugins (core + optional)."""
        results = []
        results.extend(self.run_core())
        results.extend(self.run_optional())
        return results

    def get_summary(self) -> dict[str, list[str]]:
        """Get summary of registered plugins by group."""
        return {
            "core": [p.get_name() for p in self.core_plugins],
            "optional": [p.get_name() for p in self.optional_plugins],
        }


# =============================================================================
# Example Functions
# =============================================================================


def basic_collection_example() -> None:
    """Demonstrate basic collection injection with InjectAll."""
    print("\n=== Basic Collection Injection ===\n")

    container = Container()

    # Register multiple implementations - they accumulate!
    container.register(IPlugin, LoggingPlugin)
    container.register(IPlugin, MetricsPlugin)
    container.register(IPlugin, AuthPlugin)

    # Direct API: get_all() returns all implementations
    plugins = container.get_all(IPlugin)
    print(f"Registered {len(plugins)} plugins:")
    for plugin in plugins:
        print(f"  - {plugin.get_name()}: {plugin.execute()}")

    # Property injection: PluginManager gets all plugins
    container.register(PluginManager)
    manager = container.get(PluginManager)

    print(f"\nPluginManager.plugins: {manager.list_plugins()}")
    print(f"Results: {manager.run_all()}")


def named_collection_example() -> None:
    """Demonstrate named collection injection with InjectAll."""
    print("\n=== Named Collection Injection ===\n")

    container = Container()

    # Register plugins in named groups
    # Core plugins (required for system operation)
    container.register(IPlugin, LoggingPlugin, name="core")
    container.register(IPlugin, AuthPlugin, name="core")

    # Optional plugins (can be disabled)
    container.register(IPlugin, MetricsPlugin, name="optional")
    container.register(IPlugin, CachePlugin, name="optional")

    # Direct API: get_all() with name parameter
    core = container.get_all(IPlugin, name="core")
    optional = container.get_all(IPlugin, name="optional")

    print(f"Core plugins ({len(core)}):")
    for plugin in core:
        print(f"  - {plugin.get_name()}")

    print(f"\nOptional plugins ({len(optional)}):")
    for plugin in optional:
        print(f"  - {plugin.get_name()}")

    # Property injection: GroupedPluginManager gets plugins by group
    container.register(GroupedPluginManager)
    manager = container.get(GroupedPluginManager)

    print(f"\nPlugin summary: {manager.get_summary()}")
    print(f"Core results: {manager.run_core()}")
    print(f"Optional results: {manager.run_optional()}")


def mixed_example() -> None:
    """Demonstrate mixing unnamed and named collections."""
    print("\n=== Mixed Collection Injection ===\n")

    container = Container()

    # Unnamed registrations (for get_all without name)
    container.register(IPlugin, LoggingPlugin)
    container.register(IPlugin, MetricsPlugin)

    # Named registrations (for get_all with name)
    container.register(IPlugin, AuthPlugin, name="security")
    container.register(IPlugin, CachePlugin, name="security")

    # Get unnamed plugins
    unnamed = container.get_all(IPlugin)
    print(f"Unnamed plugins: {[p.get_name() for p in unnamed]}")

    # Get named plugins
    security = container.get_all(IPlugin, name="security")
    print(f"Security plugins: {[p.get_name() for p in security]}")

    # Note: Named and unnamed are completely separate!
    print(f"\nTotal unnamed: {container.count(IPlugin)}")
    print(f"Total security: {container.count(IPlugin, name='security')}")


def run_function_example() -> None:
    """Demonstrate collection injection with container.run()."""
    print("\n=== Collection Injection with container.run() ===\n")

    container = Container()
    container.register(IPlugin, LoggingPlugin)
    container.register(IPlugin, MetricsPlugin)

    # Function with InjectAll parameter
    def process_with_plugins(plugins: InjectAll[IPlugin]) -> str:
        names = [p.get_name() for p in plugins]
        return f"Processed with: {', '.join(names)}"

    result = container.run(process_with_plugins)
    print(result)

    # Named collection in function
    container.register(IPlugin, AuthPlugin, name="critical")

    def process_critical(plugins: InjectAll[IPlugin, Named("critical")]) -> str:
        return f"Critical plugins: {len(plugins)}"

    result = container.run(process_critical)
    print(result)


def main() -> None:
    """Run all collection injection examples."""
    basic_collection_example()
    named_collection_example()
    mixed_example()
    run_function_example()

    print("\n=== All examples completed! ===\n")


if __name__ == "__main__":
    main()
