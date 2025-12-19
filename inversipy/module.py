"""Module implementation for organizing dependencies."""

from typing import Any, List, Optional, Set, Type

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
        self._public_keys: Set[Type[Any]] = set()

    def register[T](
        self,
        interface: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Factory[T]] = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: Optional[T] = None,
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
        interface: Type[T],
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
        self, interface: Type[T], instance: T, public: bool = False
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

    def export(self, *interfaces: Type[Any]) -> "Module":
        """Mark dependencies as public/exported.

        Args:
            *interfaces: Types to export

        Returns:
            Self for chaining

        Raises:
            RegistrationError: If any interface is not registered
        """
        for interface in interfaces:
            if interface not in self._bindings:
                raise RegistrationError(
                    f"Cannot export '{interface.__name__}' - not registered in module '{self._name}'"
                )
            self._public_keys.add(interface)

        return self

    def get[T](self, interface: Type[T]) -> T:
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

    async def get_async[T](self, interface: Type[T]) -> T:
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

    def has(self, interface: Type[Any]) -> bool:
        """Check if a dependency is publicly available.

        This satisfies the ModuleProtocol requirement.

        Args:
            interface: The type to check

        Returns:
            True if the dependency is registered and public, False otherwise
        """
        return self.is_public(interface)

    def is_public(self, interface: Type[Any]) -> bool:
        """Check if a dependency is public.

        Args:
            interface: Type to check

        Returns:
            True if public, False otherwise
        """
        # Check if directly registered as public
        if interface in self._public_keys:
            return True

        # Check if available from a registered module
        for module in self._modules:
            if module.is_public(interface):
                return True

        return False

    def get_public_dependencies(self) -> List[Type[Any]]:
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
        interface: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Factory[T]] = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: Optional[T] = None,
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
        interface: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Factory[T]] = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: Optional[T] = None,
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

    def export(self, *interfaces: Type[Any]) -> "ModuleBuilder":
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
