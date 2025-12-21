"""Module implementation for organizing dependencies."""

from typing import Any

from .container import Container
from .exceptions import DependencyNotFoundError, RegistrationError
from .scopes import Scopes
from .types import DependencyKey, Factory, make_key


class Module(Container):
    """A module that extends Container with public/private access control.

    Modules allow you to organize dependencies into logical units where you can
    control which dependencies are exposed publicly and which remain private.
    Modules can also register other modules for composition.

    Supports named dependencies for multiple implementations of the same interface.
    """

    def __init__(self, name: str) -> None:
        """Initialize a module.

        Args:
            name: Name of the module
        """
        super().__init__(parent=None, name=f"Module({name})")
        # Now stores DependencyKey which can be type or (type, name) tuple
        self._public_keys: set[DependencyKey] = set()

    def register[T](
        self,
        interface: type[T],
        implementation: type[T] | None = None,
        factory: Factory[T] | None = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: T | None = None,
        name: str | None = None,
        *,
        public: bool = False,
    ) -> "Module":
        """Register a dependency in the module.

        Args:
            interface: The interface/type to register
            implementation: Optional implementation type
            factory: Optional factory function
            scope: Scope for the dependency lifecycle
            instance: Optional pre-created instance
            name: Optional name qualifier for named bindings
            public: Whether this dependency should be publicly accessible (keyword-only)

        Returns:
            Self for chaining

        Raises:
            RegistrationError: If registration parameters are invalid
        """
        # Use Container's register
        super().register(
            interface=interface,
            implementation=implementation,
            factory=factory,
            scope=scope,
            instance=instance,
            name=name,
        )

        # Track public/private with the appropriate key
        key = make_key(interface, name)
        if public:
            self._public_keys.add(key)

        return self

    def register_factory[T](
        self,
        interface: type[T],
        factory: Factory[T],
        scope: Scopes = Scopes.TRANSIENT,
        name: str | None = None,
        *,
        public: bool = False,
    ) -> "Module":
        """Register a factory function for a dependency.

        Args:
            interface: The interface/type to register
            factory: Factory function to create instances
            scope: Scope for the dependency lifecycle
            name: Optional name qualifier for named bindings
            public: Whether this dependency should be publicly accessible (keyword-only)

        Returns:
            Self for chaining
        """
        return self.register(interface, factory=factory, scope=scope, name=name, public=public)

    def register_instance[T](
        self,
        interface: type[T],
        instance: T,
        name: str | None = None,
        *,
        public: bool = False,
    ) -> "Module":
        """Register a pre-created instance.

        Args:
            interface: The interface/type to register
            instance: Pre-created instance
            name: Optional name qualifier for named bindings
            public: Whether this dependency should be publicly accessible (keyword-only)

        Returns:
            Self for chaining
        """
        return self.register(interface, instance=instance, name=name, public=public)

    def export(self, *interfaces: type[Any]) -> "Module":
        """Mark unnamed dependencies as public/exported.

        This can be used to:
        1. Make a private dependency public
        2. Re-export a dependency from a child module

        For named dependencies, use export_named() instead.

        Args:
            *interfaces: Types to export

        Returns:
            Self for chaining

        Raises:
            RegistrationError: If any interface is not available
        """
        for interface in interfaces:
            # Check if directly registered
            if interface in self._bindings:
                self._public_keys.add(interface)
                continue

            # Check if available from a child module (for re-exporting)
            available_from_child = False
            for module in self._modules:
                if hasattr(module, "is_public") and module.is_public(interface):
                    available_from_child = True
                    break

            if available_from_child:
                self._public_keys.add(interface)
            else:
                raise RegistrationError(
                    f"Cannot export '{interface.__name__}' - "
                    f"not registered in module '{self._name}' "
                    f"and not available from any child module"
                )

        return self

    def export_named(self, interface: type[Any], name: str) -> "Module":
        """Mark a named dependency as public/exported.

        This can be used to:
        1. Make a private named dependency public
        2. Re-export a named dependency from a child module

        Args:
            interface: Type to export
            name: Name qualifier for the dependency

        Returns:
            Self for chaining

        Raises:
            RegistrationError: If the named dependency is not available
        """
        key = make_key(interface, name)

        # Check if directly registered
        if key in self._bindings:
            self._public_keys.add(key)
            return self

        # Check if available from a child module (for re-exporting)
        for module in self._modules:
            if hasattr(module, "is_public") and module.is_public(interface, name=name):
                self._public_keys.add(key)
                return self

        raise RegistrationError(
            f"Cannot export '{interface.__name__}' with name '{name}' - "
            f"not registered in module '{self._name}' "
            f"and not available from any child module"
        )

    def get[T](self, interface: type[T], name: str | None = None) -> T:
        """Resolve a dependency from the module.

        When called externally (from a Container), only public dependencies
        are accessible. When called internally (during dependency resolution),
        all dependencies are accessible.

        Args:
            interface: The type to resolve
            name: Optional name qualifier for named bindings

        Returns:
            Resolved instance

        Raises:
            DependencyNotFoundError: If dependency is not registered or not public
        """
        # If we're in the middle of resolving something (stack not empty),
        # this is an internal call, so allow access to private dependencies
        if self._resolution_stack:
            return super().get(interface, name=name)

        # External call - check if dependency is public
        if not self.is_public(interface, name=name):
            raise DependencyNotFoundError(interface, self._name, name=name)

        # Public dependency - resolve it
        return super().get(interface, name=name)

    async def get_async[T](self, interface: type[T], name: str | None = None) -> T:
        """Resolve a dependency from the module asynchronously.

        When called externally (from a Container), only public dependencies
        are accessible. When called internally (during dependency resolution),
        all dependencies are accessible.

        Args:
            interface: The type to resolve
            name: Optional name qualifier for named bindings

        Returns:
            Resolved instance

        Raises:
            DependencyNotFoundError: If dependency is not registered or not public
        """
        # If we're in the middle of resolving something (stack not empty),
        # this is an internal call, so allow access to private dependencies
        if self._resolution_stack:
            return await super().get_async(interface, name=name)

        # External call - check if dependency is public
        if not self.is_public(interface, name=name):
            raise DependencyNotFoundError(interface, self._name, name=name)

        # Public dependency - resolve it
        return await super().get_async(interface, name=name)

    def has(self, interface: type[Any], name: str | None = None) -> bool:
        """Check if a dependency is publicly available.

        This satisfies the ModuleProtocol requirement.

        Args:
            interface: The type to check
            name: Optional name qualifier for named bindings

        Returns:
            True if the dependency is registered and public, False otherwise
        """
        return self.is_public(interface, name=name)

    def count(self, interface: type[Any], name: str | None = None) -> int:
        """Count public implementations registered for an interface.

        Args:
            interface: The interface type
            name: Optional name qualifier for named bindings

        Returns:
            Number of public registered implementations
        """
        key = make_key(interface, name)
        # Only count if this key is public
        if key not in self._public_keys:
            return 0
        return len(self._bindings.get(key, []))

    def get_all[T](self, interface: type[T]) -> list[T]:
        """Resolve all public implementations of an interface.

        Args:
            interface: The interface type to resolve

        Returns:
            List of all public registered implementations (empty if none)
        """
        # If we're in the middle of resolving something, allow internal access
        if self._resolution_stack:
            return super().get_all(interface)

        # External call - only return if the interface key is public
        if interface not in self._public_keys:
            return []

        # Only resolve from local bindings (don't include child modules)
        instances: list[T] = []
        bindings = self._bindings.get(interface, [])
        for binding in bindings:
            instance = binding.create_instance(self)
            instances.append(instance)
        return instances

    async def get_all_async[T](self, interface: type[T]) -> list[T]:
        """Resolve all public implementations asynchronously.

        Args:
            interface: The interface type to resolve

        Returns:
            List of all public registered implementations (empty if none)
        """
        # If we're in the middle of resolving something, allow internal access
        if self._resolution_stack:
            return await super().get_all_async(interface)

        # External call - only return if the interface key is public
        if interface not in self._public_keys:
            return []

        # Only resolve from local bindings (don't include child modules)
        instances: list[T] = []
        bindings = self._bindings.get(interface, [])
        for binding in bindings:
            instance = await binding.create_instance_async(self)
            instances.append(instance)
        return instances

    def is_public(self, interface: type[Any], name: str | None = None) -> bool:
        """Check if a dependency is public.

        Visibility is NOT transitive. Dependencies from child modules are only
        accessible internally for dependency resolution, not externally.
        To expose a child module's dependency externally, use export().

        Args:
            interface: Type to check
            name: Optional name qualifier for named bindings

        Returns:
            True if public, False otherwise
        """
        # Only check if directly registered/exported as public
        # Child module dependencies are not transitively public
        key = make_key(interface, name)
        return key in self._public_keys

    def get_public_dependencies(self) -> list[DependencyKey]:
        """Get list of all public dependency keys.

        Returns:
            List of public dependency keys (type or (type, name) tuples)
        """
        return list(self._public_keys)

    def __repr__(self) -> str:
        """Get string representation of the module."""

        def key_name(key: DependencyKey) -> str:
            if isinstance(key, tuple):
                return f"{key[0].__name__}[{key[1]}]"
            elif isinstance(key, type):
                return key.__name__
            return str(key)

        public_deps = ", ".join(key_name(dep) for dep in self._public_keys)
        all_deps_count = len(self._bindings)
        return (
            f"Module({self._name}, "
            f"public=[{public_deps}], "
            f"total_dependencies={all_deps_count})"
        )


class ModuleBuilder:
    """Builder for creating modules with a fluent API."""

    def __init__(self, name: str) -> None:
        """Initialize the module builder.

        Args:
            name: Name of the module
        """
        self._module = Module(name)

    def bind[T](
        self,
        interface: type[T],
        implementation: type[T] | None = None,
        factory: Factory[T] | None = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: T | None = None,
        name: str | None = None,
    ) -> "ModuleBuilder":
        """Bind a dependency (private by default).

        Args:
            interface: The interface/type to register
            implementation: Optional implementation type
            factory: Optional factory function
            scope: Scope for the dependency lifecycle
            instance: Optional pre-created instance
            name: Optional name qualifier for named bindings

        Returns:
            Self for chaining
        """
        self._module.register(
            interface=interface,
            implementation=implementation,
            factory=factory,
            scope=scope,
            instance=instance,
            public=False,
            name=name,
        )
        return self

    def bind_public[T](
        self,
        interface: type[T],
        implementation: type[T] | None = None,
        factory: Factory[T] | None = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: T | None = None,
        name: str | None = None,
    ) -> "ModuleBuilder":
        """Bind a public dependency.

        Args:
            interface: The interface/type to register
            implementation: Optional implementation type
            factory: Optional factory function
            scope: Scope for the dependency lifecycle
            instance: Optional pre-created instance
            name: Optional name qualifier for named bindings

        Returns:
            Self for chaining
        """
        self._module.register(
            interface=interface,
            implementation=implementation,
            factory=factory,
            scope=scope,
            instance=instance,
            public=True,
            name=name,
        )
        return self

    def export(self, *interfaces: type[Any]) -> "ModuleBuilder":
        """Mark unnamed dependencies as public/exported.

        For named dependencies, use export_named() instead.

        Args:
            *interfaces: Types to export

        Returns:
            Self for chaining
        """
        self._module.export(*interfaces)
        return self

    def export_named(self, interface: type[Any], name: str) -> "ModuleBuilder":
        """Mark a named dependency as public/exported.

        Args:
            interface: Type to export
            name: Name qualifier for the dependency

        Returns:
            Self for chaining
        """
        self._module.export_named(interface, name)
        return self

    def build(self) -> Module:
        """Build and return the module.

        Returns:
            The constructed module
        """
        return self._module
