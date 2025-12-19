"""Module implementation for organizing dependencies."""

from typing import Any

from .container import Container
from .exceptions import DependencyNotFoundError, RegistrationError
from .scopes import Scopes
from .types import Factory


class Module(Container):
    """A module that extends Container with public/private access control.

    Modules allow you to organize dependencies into logical units where you can
    control which dependencies are exposed publicly and which remain private.
    Modules can also register other modules for composition.
    """

    def __init__(self, name: str) -> None:
        """Initialize a module.

        Args:
            name: Name of the module
        """
        super().__init__(parent=None, name=f"Module({name})")
        self._public_keys: set[type[Any]] = set()

    def register[T](
        self,
        interface: type[T],
        implementation: type[T] | None = None,
        factory: Factory[T] | None = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: T | None = None,
        public: bool = False,
    ) -> "Module":
        """Register a dependency in the module.

        Args:
            interface: The interface/type to register
            implementation: Optional implementation type
            factory: Optional factory function
            scope: Scope for the dependency lifecycle
            instance: Optional pre-created instance
            public: Whether this dependency should be publicly accessible

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
        )

        # Track public/private
        if public:
            self._public_keys.add(interface)

        return self

    def register_factory[T](
        self,
        interface: type[T],
        factory: Factory[T],
        scope: Scopes = Scopes.TRANSIENT,
        public: bool = False,
    ) -> "Module":
        """Register a factory function for a dependency.

        Args:
            interface: The interface/type to register
            factory: Factory function to create instances
            scope: Scope for the dependency lifecycle
            public: Whether this dependency should be publicly accessible

        Returns:
            Self for chaining
        """
        return self.register(interface, factory=factory, scope=scope, public=public)

    def register_instance[T](
        self, interface: type[T], instance: T, public: bool = False
    ) -> "Module":
        """Register a pre-created instance.

        Args:
            interface: The interface/type to register
            instance: Pre-created instance
            public: Whether this dependency should be publicly accessible

        Returns:
            Self for chaining
        """
        return self.register(interface, instance=instance, public=public)

    def export(self, *interfaces: type[Any]) -> "Module":
        """Mark dependencies as public/exported.

        This can be used to:
        1. Make a private dependency public
        2. Re-export a dependency from a child module

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

    def get[T](self, interface: type[T]) -> T:
        """Resolve a dependency from the module.

        When called externally (from a Container), only public dependencies
        are accessible. When called internally (during dependency resolution),
        all dependencies are accessible.

        Args:
            interface: The type to resolve

        Returns:
            Resolved instance

        Raises:
            DependencyNotFoundError: If dependency is not registered or not public
        """
        # If we're in the middle of resolving something (stack not empty),
        # this is an internal call, so allow access to private dependencies
        if self._resolution_stack:
            return super().get(interface)

        # External call - check if dependency is public
        if not self.is_public(interface):
            raise DependencyNotFoundError(interface, self._name)

        # Public dependency - resolve it
        return super().get(interface)

    async def get_async[T](self, interface: type[T]) -> T:
        """Resolve a dependency from the module asynchronously.

        When called externally (from a Container), only public dependencies
        are accessible. When called internally (during dependency resolution),
        all dependencies are accessible.

        Args:
            interface: The type to resolve

        Returns:
            Resolved instance

        Raises:
            DependencyNotFoundError: If dependency is not registered or not public
        """
        # If we're in the middle of resolving something (stack not empty),
        # this is an internal call, so allow access to private dependencies
        if self._resolution_stack:
            return await super().get_async(interface)

        # External call - check if dependency is public
        if not self.is_public(interface):
            raise DependencyNotFoundError(interface, self._name)

        # Public dependency - resolve it
        return await super().get_async(interface)

    def has(self, interface: type[Any]) -> bool:
        """Check if a dependency is publicly available.

        This satisfies the ModuleProtocol requirement.

        Args:
            interface: The type to check

        Returns:
            True if the dependency is registered and public, False otherwise
        """
        return self.is_public(interface)

    def is_public(self, interface: type[Any]) -> bool:
        """Check if a dependency is public.

        Visibility is NOT transitive. Dependencies from child modules are only
        accessible internally for dependency resolution, not externally.
        To expose a child module's dependency externally, use export().

        Args:
            interface: Type to check

        Returns:
            True if public, False otherwise
        """
        # Only check if directly registered/exported as public
        # Child module dependencies are not transitively public
        return interface in self._public_keys

    def get_public_dependencies(self) -> list[type[Any]]:
        """Get list of all public dependencies.

        Returns:
            List of public dependency types
        """
        return list(self._public_keys)

    def __repr__(self) -> str:
        """Get string representation of the module."""
        public_deps = ", ".join(dep.__name__ for dep in self._public_keys)
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
    ) -> "ModuleBuilder":
        """Bind a dependency (private by default).

        Args:
            interface: The interface/type to register
            implementation: Optional implementation type
            factory: Optional factory function
            scope: Scope for the dependency lifecycle
            instance: Optional pre-created instance

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
        )
        return self

    def bind_public[T](
        self,
        interface: type[T],
        implementation: type[T] | None = None,
        factory: Factory[T] | None = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: T | None = None,
    ) -> "ModuleBuilder":
        """Bind a public dependency.

        Args:
            interface: The interface/type to register
            implementation: Optional implementation type
            factory: Optional factory function
            scope: Scope for the dependency lifecycle
            instance: Optional pre-created instance

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
        )
        return self

    def export(self, *interfaces: type[Any]) -> "ModuleBuilder":
        """Mark dependencies as public/exported.

        Args:
            *interfaces: Types to export

        Returns:
            Self for chaining
        """
        self._module.export(*interfaces)
        return self

    def build(self) -> Module:
        """Build and return the module.

        Returns:
            The constructed module
        """
        return self._module
