"""Container implementation for dependency injection."""

import asyncio
import inspect
from typing import (
    Any,
    Dict,
    List,
    Optional,
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
from .scopes import TRANSIENT, SingletonScope, TransientScope, RequestScope
from .types import DependencyKey, Factory, Scope, ModuleProtocol


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
        self._async_scope_cache: Dict[Any, Any] = {}  # Cache for async resolution with non-async scopes

        # Validate that we have at least one way to create instances
        if factory is None and implementation is None and instance is None:
            raise RegistrationError(
                f"Must provide either factory, implementation, or instance for {key}"
            )

    def create_instance(self, container: "Container") -> Any:
        """Create an instance of the dependency.

        Args:
            container: Container to use for resolving dependencies

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
            factory_func = lambda: container._create_instance(self.implementation)  # type: ignore
        else:
            raise ResolutionError(f"Cannot create instance for {self.key}")

        # Use the scope to manage instance lifecycle
        return self.scope.get(factory_func)

    async def create_instance_async(self, container: "Container") -> Any:
        """Create an instance of the dependency asynchronously.

        Args:
            container: Container to use for resolving dependencies

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
            # For async, we need to call _create_instance_async
            async def async_impl_factory():  # type: ignore
                return await container._create_instance_async(self.implementation)  # type: ignore
            factory_func = async_impl_factory
        else:
            raise ResolutionError(f"Cannot create instance for {self.key}")

        # Use the scope to manage instance lifecycle
        from .types import AsyncScope
        if isinstance(self.scope, AsyncScope):
            return await self.scope.get_async(factory_func)
        else:
            # For non-async scopes with async resolution, handle caching manually
            # because scopes cache coroutines instead of awaited results

            # Determine cache key based on scope type
            cache_key = None
            if isinstance(self.scope, SingletonScope):
                cache_key = "singleton"
            elif isinstance(self.scope, RequestScope):
                # For RequestScope, use asyncio task id as cache key
                # Each async task gets its own context automatically
                current_task = asyncio.current_task()
                if current_task is not None:
                    cache_key = f"request_{id(current_task)}"
                else:
                    cache_key = "request_main"
            elif isinstance(self.scope, TransientScope):
                # No caching for transient
                cache_key = None
            else:
                # For unknown scopes, use a fixed key (behave like singleton)
                cache_key = "default"

            # Check cache
            if cache_key is not None and cache_key in self._async_scope_cache:
                return self._async_scope_cache[cache_key]

            # Create instance
            result = factory_func()
            if asyncio.iscoroutine(result):
                instance = await result
            else:
                instance = result

            # Store in cache if needed
            if cache_key is not None:
                self._async_scope_cache[cache_key] = instance

            return instance


class Container:
    """Dependency injection container.

    A Container manages dependency registration and resolution with support for:
    - Parent-child hierarchies for dependency inheritance
    - Module registration for composition
    - All dependencies are public by default
    """

    def __init__(self, parent: Optional["Container"] = None, name: str = "Container") -> None:
        """Initialize a container.

        Args:
            parent: Optional parent container for hierarchical resolution
            name: Name for this container (used in error messages)
        """
        self._name = name
        self._bindings: Dict[DependencyKey, Binding] = {}
        self._modules: List[ModuleProtocol] = []  # List of registered modules
        self._parent = parent
        self._resolution_stack: List[Type[Any]] = []

    @property
    def name(self) -> str:
        """Get the container name."""
        return self._name

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
        # If no implementation or factory provided, use interface as implementation
        if implementation is None and factory is None and instance is None:
            implementation = interface

        # Create a new scope instance to avoid sharing state between bindings
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
        return self.register(interface, instance=instance, scope=SingletonScope())

    def register_module(self, module: ModuleProtocol) -> "Container":
        """Register a module as a provider of dependencies.

        The module will be consulted when resolving dependencies. Only the module's
        public dependencies are accessible to the container.

        Args:
            module: Module to register (must implement ModuleProtocol)

        Returns:
            Self for chaining

        Example:
            db_module = Module("Database")
            db_module.register(Database, public=True)

            container = Container()
            container.register_module(db_module)

            db = container.get(Database)  # Resolved from module
        """
        self._modules.append(module)
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
        # Check for circular dependencies
        if interface in self._resolution_stack:
            self._resolution_stack.append(interface)
            raise CircularDependencyError(self._resolution_stack[:])

        # Try to find binding in this container
        binding = self._bindings.get(interface)

        # If not found, try registered modules
        if binding is None:
            for module in self._modules:
                try:
                    # Try to resolve from the module
                    # The module will enforce its own public/private access rules
                    instance = module.get(interface)
                    return cast(T, instance)
                except DependencyNotFoundError:
                    # This module doesn't have it (or it's private), try next module
                    continue

        # If not found, try parent container
        if binding is None and self._parent is not None:
            return self._parent.get(interface)

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

    async def get_async[T](self, interface: Type[T]) -> T:
        """Resolve a dependency from the container asynchronously.

        This method supports async factories and async scopes. It follows the same
        resolution order as get():
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
        # Check for circular dependencies
        if interface in self._resolution_stack:
            self._resolution_stack.append(interface)
            raise CircularDependencyError(self._resolution_stack[:])

        # Try to find binding in this container
        binding = self._bindings.get(interface)

        # If not found, try registered modules
        if binding is None:
            for module in self._modules:
                try:
                    # Try to resolve from the module asynchronously
                    instance = await module.get_async(interface)
                    return cast(T, instance)
                except DependencyNotFoundError:
                    # This module doesn't have it (or it's private), try next module
                    continue

        # If not found, try parent container
        if binding is None and self._parent is not None:
            return await self._parent.get_async(interface)

        # If still not found, raise error
        if binding is None:
            raise DependencyNotFoundError(interface, self._name)

        # Add to resolution stack
        self._resolution_stack.append(interface)

        try:
            instance = await binding.create_instance_async(self)
            return cast(T, instance)
        finally:
            # Remove from resolution stack
            self._resolution_stack.pop()

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
            if module.has(interface):
                return True

        # Check parent if exists
        if self._parent is not None:
            return self._parent.has(interface)

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
                    # Try to resolve from container
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

    async def _create_instance_async[T](self, cls: Type[T]) -> T:
        """Create an instance of a class asynchronously, resolving its dependencies.

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

            # Resolve dependencies asynchronously
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
                    # Try to resolve from container asynchronously
                    try:
                        kwargs[param_name] = await self.get_async(param_type)
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

    def create_child(self, name: Optional[str] = None) -> "Container":
        """Create a child container.

        Args:
            name: Optional name for the child container

        Returns:
            New child container
        """
        child_name = name if name else f"{self._name}.Child"
        return Container(parent=self, name=child_name)

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
                            # Check if dependency is registered (check all dependencies, not just public)
                            has_dependency = (
                                param_type in self._bindings
                                or any(param_type in m._bindings for m in self._modules if hasattr(m, '_bindings'))
                                or (self._parent is not None and self._parent.has(param_type))
                            )
                            if not has_dependency:
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
        """Get string representation of the container."""
        deps = ", ".join(
            getattr(k, "__name__", str(k)) for k in self._bindings.keys()
        )
        return f"Container({self._name}, dependencies=[{deps}])"
