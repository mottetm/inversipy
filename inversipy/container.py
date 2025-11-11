"""Container implementation for dependency injection."""

from typing import Any, Optional, Type

from .module import Module
from .scopes import TRANSIENT
from .types import Factory, Scope


class Container(Module):
    """Dependency injection container.

    A Container is a special type of Module where all dependencies are public
    and which supports parent-child hierarchies for dependency inheritance.
    """

    def __init__(self, parent: Optional["Container"] = None, name: str = "Container") -> None:
        """Initialize a container.

        Args:
            parent: Optional parent container for hierarchical resolution
            name: Name for this container (used in error messages)
        """
        super().__init__(name)
        self._parent = parent

    @property
    def parent(self) -> Optional["Container"]:
        """Get the parent container."""
        return self._parent

    def register[T](
        self,
        interface: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Factory[T]] = None,
        scope: Scope = TRANSIENT,
        instance: Optional[T] = None,
    ) -> "Container":
        """Register a dependency in the container.

        All dependencies in a Container are public by default.

        Args:
            interface: The interface/type to register
            implementation: Optional implementation type
            factory: Optional factory function
            scope: Scope for the dependency lifecycle
            instance: Optional pre-created instance

        Returns:
            Self for chaining

        Raises:
            RegistrationError: If registration parameters are invalid
        """
        # Container always registers dependencies as public
        super().register(
            interface=interface,
            implementation=implementation,
            factory=factory,
            scope=scope,
            instance=instance,
            public=True,
        )
        return self

    def register_factory[T](
        self, interface: Type[T], factory: Factory[T], scope: Scope = TRANSIENT
    ) -> "Container":
        """Register a factory function for a dependency.

        Args:
            interface: The interface/type to register
            factory: Factory function to create instances
            scope: Scope for the dependency lifecycle

        Returns:
            Self for chaining
        """
        return self.register(interface, factory=factory, scope=scope)

    def register_instance[T](self, interface: Type[T], instance: T) -> "Container":
        """Register a pre-created instance.

        Args:
            interface: The interface/type to register
            instance: Pre-created instance

        Returns:
            Self for chaining
        """
        return self.register(interface, instance=instance)

    def register_module(self, module: Module) -> "Container":
        """Register a module as a provider of dependencies.

        The module will be consulted when resolving dependencies. Only the module's
        public dependencies are accessible to the container.

        Args:
            module: Module to register (from inversipy.module import Module)

        Returns:
            Self for chaining

        Example:
            db_module = Module("Database")
            db_module.register(Database, public=True)

            container = Container()
            container.register_module(db_module)  # Module provides Database

            db = container.get(Database)  # Resolved from module
        """
        super().register_module(module)
        return self

    def get[T](self, interface: Type[T]) -> T:
        """Resolve a dependency from the container.

        Resolution order:
        1. Check local bindings
        2. Check registered modules
        3. Check parent container (if exists)

        Args:
            interface: The type to resolve

        Returns:
            Resolved instance

        Raises:
            DependencyNotFoundError: If dependency is not registered
            CircularDependencyError: If circular dependency is detected
        """
        # Try to resolve from this container or its modules
        try:
            return super().get(interface)
        except Exception as e:
            # If not found and we have a parent, try the parent
            if self._parent is not None:
                # Import here to avoid circular dependency check issues
                from .exceptions import DependencyNotFoundError
                if isinstance(e, DependencyNotFoundError):
                    return self._parent.get(interface)
            # Re-raise if not a DependencyNotFoundError or no parent
            raise

    def has(self, interface: Type[Any]) -> bool:
        """Check if a dependency is registered.

        Checks both local container and parent hierarchy.

        Args:
            interface: The type to check

        Returns:
            True if registered, False otherwise
        """
        # Check locally first
        if super().has(interface):
            return True

        # Check parent if exists
        if self._parent is not None:
            return self._parent.has(interface)

        return False

    def create_child(self, name: Optional[str] = None) -> "Container":
        """Create a child container.

        Args:
            name: Optional name for the child container

        Returns:
            New child container
        """
        child_name = name if name else f"{self._name}.Child"
        return Container(parent=self, name=child_name)

    def __repr__(self) -> str:
        """Get string representation of the container."""
        deps = ", ".join(
            getattr(k, "__name__", str(k)) for k in self._bindings.keys()
        )
        return f"Container({self._name}, dependencies=[{deps}])"
