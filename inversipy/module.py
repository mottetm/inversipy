"""Module implementation for organizing dependencies."""

import inspect
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Type,
    get_type_hints,
    cast,
)

from .exceptions import (
    CircularDependencyError,
    DependencyNotFoundError,
    RegistrationError,
    ResolutionError,
    ValidationError,
)
from .scopes import TRANSIENT, SingletonScope
from .types import DependencyKey, Factory, Scope


class Binding:
    """Represents a binding between a type and its implementation."""

    def __init__(
        self,
        key: DependencyKey,
        factory: Optional[Factory[Any]] = None,
        implementation: Optional[Type[Any]] = None,
        scope: Scope = TRANSIENT,
        instance: Optional[Any] = None,
    ) -> None:
        """Initialize a binding.

        Args:
            key: The dependency key (type or string identifier)
            factory: Optional factory function to create instances
            implementation: Optional implementation type
            scope: Scope for the dependency lifecycle
            instance: Optional pre-created instance
        """
        self.key = key
        self.factory = factory
        self.implementation = implementation
        self.scope = scope
        self.instance = instance

        # Validate that we have at least one way to create instances
        if factory is None and implementation is None and instance is None:
            raise RegistrationError(
                f"Must provide either factory, implementation, or instance for {key}"
            )

    def create_instance(self, module: "Module") -> Any:
        """Create an instance of the dependency.

        Args:
            module: Module to use for resolving dependencies

        Returns:
            Created instance
        """
        # If we have a pre-created instance, return it
        if self.instance is not None:
            return self.instance

        # Build the factory function
        if self.factory is not None:
            factory_func = self.factory
        elif self.implementation is not None:
            # Create a factory from the implementation type
            factory_func = lambda: module._create_instance(self.implementation)  # type: ignore
        else:
            raise ResolutionError(f"Cannot create instance for {self.key}")

        # Use the scope to manage instance lifecycle
        return self.scope.get(factory_func)


class Module:
    """A module that encapsulates dependencies with public/private access control.

    Modules allow you to organize dependencies into logical units where you can
    control which dependencies are exposed publicly and which remain private.
    Modules can also register other modules for composition.
    """

    def __init__(self, name: str) -> None:
        """Initialize a module.

        Args:
            name: Name of the module
        """
        self._name = name
        self._bindings: Dict[DependencyKey, Binding] = {}
        self._modules: List["Module"] = []
        self._public_keys: Set[Type[Any]] = set()
        self._resolution_stack: List[Type[Any]] = []

    @property
    def name(self) -> str:
        """Get the module name."""
        return self._name

    def register[T](
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

        Raises:
            RegistrationError: If registration parameters are invalid
        """
        # If no implementation or factory provided, use interface as implementation
        if implementation is None and factory is None and instance is None:
            implementation = interface

        # Create a new scope instance to avoid sharing state between bindings
        from .scopes import SingletonScope, TransientScope, RequestScope

        actual_scope = scope
        if isinstance(scope, SingletonScope):
            actual_scope = SingletonScope()
        elif isinstance(scope, TransientScope):
            actual_scope = TransientScope()
        elif isinstance(scope, RequestScope):
            # For RequestScope, we might want to share it, so keep the original
            actual_scope = scope

        binding = Binding(
            key=interface,
            factory=factory,
            implementation=implementation,
            scope=actual_scope,
            instance=instance,
        )
        self._bindings[interface] = binding

        if public:
            self._public_keys.add(interface)

        return self

    def register_factory[T](
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
        return self.register(interface, instance=instance, scope=SingletonScope(), public=public)

    def register_module(self, module: "Module") -> "Module":
        """Register another module as a provider of dependencies.

        The registered module will be consulted when resolving dependencies.
        Only the module's public dependencies are accessible.

        Args:
            module: Module to register

        Returns:
            Self for chaining

        Example:
            db_module = Module("Database")
            db_module.register(Database, public=True)

            app_module = Module("App")
            app_module.register_module(db_module)

            db = app_module.get(Database)  # Resolved from db_module
        """
        self._modules.append(module)
        return self

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
            if not self.has(interface):
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

    def get[T](self, interface: Type[T]) -> T:
        """Resolve a dependency from the module.

        Args:
            interface: The type to resolve

        Returns:
            Resolved instance

        Raises:
            DependencyNotFoundError: If dependency is not registered
            CircularDependencyError: If circular dependency is detected
        """
        # Check for circular dependencies
        if interface in self._resolution_stack:
            self._resolution_stack.append(interface)
            raise CircularDependencyError(self._resolution_stack[:])

        # Try to find binding in this module
        binding = self._bindings.get(interface)

        # If not found, try registered modules
        if binding is None:
            for module in self._modules:
                if module.is_public(interface):
                    # Add to resolution stack
                    self._resolution_stack.append(interface)
                    try:
                        # Resolve from the module
                        instance = module.get(interface)
                        return cast(T, instance)
                    finally:
                        # Remove from resolution stack
                        self._resolution_stack.pop()

        # If still not found, raise error
        if binding is None:
            raise DependencyNotFoundError(interface, self._name)

        # Add to resolution stack
        self._resolution_stack.append(interface)

        try:
            instance = binding.create_instance(self)
            return cast(T, instance)
        finally:
            # Remove from resolution stack
            self._resolution_stack.pop()

    def try_get[T](self, interface: Type[T]) -> Optional[T]:
        """Try to resolve a dependency, returning None if not found.

        Args:
            interface: The type to resolve

        Returns:
            Resolved instance or None
        """
        try:
            return self.get(interface)
        except DependencyNotFoundError:
            return None

    def has(self, interface: Type[Any]) -> bool:
        """Check if a dependency is registered.

        Args:
            interface: The type to check

        Returns:
            True if registered, False otherwise
        """
        if interface in self._bindings:
            return True

        # Check registered modules
        for module in self._modules:
            if module.is_public(interface):
                return True

        return False

    def _create_instance[T](self, cls: Type[T]) -> T:
        """Create an instance of a class, resolving its dependencies.

        Args:
            cls: The class to instantiate

        Returns:
            Created instance

        Raises:
            ResolutionError: If instance creation fails
        """
        try:
            # Get the __init__ method
            init_method = cls.__init__  # type: ignore

            # Get type hints for the constructor
            try:
                type_hints = get_type_hints(init_method)
            except Exception:
                # If we can't get type hints, try without dependencies
                type_hints = {}

            # Remove 'return' from type hints
            type_hints.pop("return", None)

            # Get constructor signature
            sig = inspect.signature(init_method)

            # Resolve dependencies
            kwargs: Dict[str, Any] = {}
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                # Skip *args and **kwargs
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue

                # Get the type hint for this parameter
                param_type = type_hints.get(param_name)

                if param_type is not None:
                    # Try to resolve from module
                    try:
                        kwargs[param_name] = self.get(param_type)
                    except DependencyNotFoundError:
                        # Check if parameter has a default value
                        if param.default is inspect.Parameter.empty:
                            raise ResolutionError(
                                f"Cannot resolve parameter '{param_name}' of type "
                                f"'{param_type}' for class '{cls.__name__}'"
                            )
                elif param.default is inspect.Parameter.empty:
                    raise ResolutionError(
                        f"Parameter '{param_name}' of class '{cls.__name__}' "
                        f"has no type annotation and no default value"
                    )

            # Create the instance
            return cls(**kwargs)

        except Exception as e:
            if isinstance(e, (ResolutionError, DependencyNotFoundError, CircularDependencyError)):
                raise
            raise ResolutionError(f"Failed to create instance of {cls.__name__}: {e}")

    def validate(self) -> None:
        """Validate that all registered dependencies can be resolved.

        Raises:
            ValidationError: If validation fails
        """
        errors: List[str] = []

        for key, binding in self._bindings.items():
            # Skip validation for instances and factories
            if binding.instance is not None or binding.factory is not None:
                continue

            # Validate implementation can be instantiated
            if binding.implementation is not None:
                cls = binding.implementation
                try:
                    # Get type hints for the constructor
                    init_method = cls.__init__  # type: ignore
                    try:
                        type_hints = get_type_hints(init_method)
                    except Exception:
                        continue  # Skip if we can't get type hints

                    type_hints.pop("return", None)

                    # Get constructor signature
                    sig = inspect.signature(init_method)

                    # Check each parameter
                    for param_name, param in sig.parameters.items():
                        if param_name == "self":
                            continue

                        # Skip *args and **kwargs
                        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                            continue

                        param_type = type_hints.get(param_name)

                        if param_type is not None:
                            # Check if dependency is registered
                            if not self.has(param_type):
                                # Check if parameter has a default
                                if param.default is inspect.Parameter.empty:
                                    type_name = getattr(param_type, "__name__", str(param_type))
                                    errors.append(
                                        f"Dependency '{cls.__name__}' requires "
                                        f"'{type_name}' (parameter '{param_name}') "
                                        f"which is not registered"
                                    )

                except Exception as e:
                    errors.append(
                        f"Failed to validate dependency '{cls.__name__}': {e}"
                    )

        if errors:
            raise ValidationError(errors)

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

    def bind_public[T](
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
