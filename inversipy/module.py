"""Module implementation for organizing dependencies."""

from typing import Any, Callable, List, Optional, Set, Type, TypeVar

from .container import Container
from .exceptions import DependencyNotFoundError, RegistrationError
from .scopes import TRANSIENT
from .types import Factory, Scope

T = TypeVar("T")


class Module:
    """A module that encapsulates dependencies with public/private access control.

    Modules allow you to organize dependencies into logical units where you can
    control which dependencies are exposed publicly and which remain private.
    """

    def __init__(self, name: str) -> None:
        """Initialize a module.

        Args:
            name: Name of the module
        """
        self._name = name
        self._container = Container(name=f"Module({name})")
        self._public_keys: Set[Type[Any]] = set()

    @property
    def name(self) -> str:
        """Get the module name."""
        return self._name

    def register(
        self,
        interface: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Factory[T]] = None,
        scope: Scope = TRANSIENT,
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
        """
        self._container.register(
            interface=interface,
            implementation=implementation,
            factory=factory,
            scope=scope,
            instance=instance,
        )

        if public:
            self._public_keys.add(interface)

        return self

    def register_factory(
        self,
        interface: Type[T],
        factory: Factory[T],
        scope: Scope = TRANSIENT,
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

    def register_instance(
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
            if not self._container.has(interface):
                raise RegistrationError(
                    f"Cannot export '{interface.__name__}' - not registered in module '{self._name}'"
                )
            self._public_keys.add(interface)

        return self

    def is_public(self, interface: Type[Any]) -> bool:
        """Check if a dependency is public.

        Args:
            interface: Type to check

        Returns:
            True if public, False otherwise
        """
        return interface in self._public_keys

    def get_public_dependencies(self) -> List[Type[Any]]:
        """Get list of all public dependencies.

        Returns:
            List of public dependency types
        """
        return list(self._public_keys)

    def validate(self) -> None:
        """Validate that all dependencies in the module can be resolved.

        This validates the internal container.

        Raises:
            ValidationError: If validation fails
        """
        self._container.validate()

    def load_into(self, container: Container) -> None:
        """Load this module's public dependencies into a container.

        Args:
            container: Target container to load dependencies into
        """
        for key in self._public_keys:
            # Get the binding from the module's container
            binding = self._container._bindings.get(key)
            if binding is not None:
                # Register in the target container
                container.register(
                    interface=key,
                    implementation=binding.implementation,
                    factory=binding.factory,
                    scope=binding.scope,
                    instance=binding.instance,
                )

    def __repr__(self) -> str:
        """Get string representation of the module."""
        public_deps = ", ".join(dep.__name__ for dep in self._public_keys)
        all_deps_count = len(self._container._bindings)
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

    def bind(
        self,
        interface: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Factory[T]] = None,
        scope: Scope = TRANSIENT,
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

    def bind_public(
        self,
        interface: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Factory[T]] = None,
        scope: Scope = TRANSIENT,
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
