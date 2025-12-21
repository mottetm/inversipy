"""Container implementation for dependency injection."""

import asyncio
import inspect
from collections.abc import Callable
from typing import Any, Optional, get_type_hints

from .binding_strategies import (
    AsyncRequestStrategy,
    AsyncSingletonStrategy,
    AsyncTransientStrategy,
    BindingStrategy,
    SyncRequestStrategy,
    SyncSingletonStrategy,
    SyncTransientStrategy,
)
from .decorators import extract_inject_info
from .exceptions import (
    CircularDependencyError,
    DependencyNotFoundError,
    RegistrationError,
    ResolutionError,
    ValidationError,
)
from .scopes import Scopes
from .types import DependencyKey, Factory, ModuleProtocol, get_type_from_key, make_key


def _format_dependency(dep_type: type, name: str | None = None) -> str:
    """Format a dependency type and optional name for error messages.

    Args:
        dep_type: The dependency type
        name: Optional name qualifier

    Returns:
        Formatted string like "IDatabase" or "IDatabase[name='primary']"
    """
    if name:
        return f"{dep_type.__name__}[name='{name}']"
    return dep_type.__name__


class Binding:
    """Represents a binding between a type and its implementation.

    Uses strategy pattern to handle different scope types and async/sync factories.
    The appropriate strategy is automatically selected based on:
    - The scope (SINGLETON, TRANSIENT, REQUEST)
    - Whether the factory is async (inspected with inspect.iscoroutinefunction)
    """

    def __init__(
        self,
        key: DependencyKey,
        factory: Factory[Any] | None = None,
        implementation: type[Any] | None = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: Any | None = None,
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

        # Determine if we have an async factory
        self._is_async_factory = inspect.iscoroutinefunction(factory) if factory else False

        # Check if factory has parameters that need resolution
        self._factory_has_params = False
        if factory is not None:
            sig = inspect.signature(factory)
            self._factory_has_params = len(sig.parameters) > 0

        # Select the appropriate strategy based on scope and async/sync
        self._strategy = self._create_strategy(scope, self._is_async_factory)

    def _create_strategy(self, scope: Scopes, is_async: bool) -> BindingStrategy:
        """Create the appropriate binding strategy.

        Args:
            scope: The scope type
            is_async: Whether the factory is async

        Returns:
            The binding strategy instance
        """
        if scope == Scopes.SINGLETON:
            return AsyncSingletonStrategy() if is_async else SyncSingletonStrategy()
        elif scope == Scopes.TRANSIENT:
            return AsyncTransientStrategy() if is_async else SyncTransientStrategy()
        elif scope == Scopes.REQUEST:
            return AsyncRequestStrategy() if is_async else SyncRequestStrategy()
        else:
            raise RegistrationError(f"Unknown scope: {scope}")

    def create_instance(self, container: "Container") -> Any:
        """Create an instance of the dependency (sync context).

        Args:
            container: Container to use for resolving dependencies

        Returns:
            Created instance

        Raises:
            ResolutionError: If trying to resolve async factory in sync context
        """
        # If we have a pre-created instance, return it
        if self.instance is not None:
            return self.instance

        # Build the factory function
        if self.factory is not None:
            if self._factory_has_params:
                # Factory has parameters - resolve them from container
                factory = self.factory  # Capture for closure

                def factory_func() -> Any:
                    return self._call_factory_with_deps(container, factory)

            else:
                # Factory has no parameters - call directly
                factory_func = self.factory
        elif self.implementation is not None:
            # Create a factory from the implementation type
            implementation = self.implementation  # Capture for closure

            def factory_func() -> Any:
                return container._create_instance(implementation)

        else:
            raise ResolutionError(f"Cannot create instance for {self.key}")

        # Use the strategy to manage instance lifecycle
        return self._strategy.get(factory_func)

    def _call_factory_with_deps(self, container: "Container", factory: Callable[..., Any]) -> Any:
        """Call a factory function, resolving its dependencies from the container.

        Supports named dependencies via Inject[Type, Named("qualifier")] annotations.

        Args:
            container: Container to resolve dependencies from
            factory: Factory function to call

        Returns:
            Result of calling the factory

        Raises:
            ResolutionError: If dependencies cannot be resolved
        """
        try:
            sig = inspect.signature(factory)
            type_hints = get_type_hints(factory, include_extras=True)

            kwargs: dict[str, Any] = {}
            for param_name, param in sig.parameters.items():
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue

                param_type = type_hints.get(param_name)
                if param_type is not None:
                    # Check for Inject annotation with optional Named qualifier
                    inject_info = extract_inject_info(param_type)
                    if inject_info:
                        actual_type, dep_name = inject_info
                        try:
                            kwargs[param_name] = container.get(actual_type, name=dep_name)
                        except DependencyNotFoundError:
                            if param.default is inspect.Parameter.empty:
                                raise ResolutionError(
                                    f"Cannot resolve factory parameter '{param_name}' "
                                    f"of type {_format_dependency(actual_type, dep_name)} "
                                    f"for {self.key}"
                                )
                    else:
                        try:
                            kwargs[param_name] = container.get(param_type)
                        except DependencyNotFoundError:
                            if param.default is inspect.Parameter.empty:
                                raise ResolutionError(
                                    f"Cannot resolve factory parameter '{param_name}' "
                                    f"of type {param_type} for {self.key}"
                                )
                elif param.default is inspect.Parameter.empty:
                    raise ResolutionError(
                        f"Factory parameter '{param_name}' has no type hint "
                        f"and no default value for {self.key}"
                    )

            return factory(**kwargs)
        except Exception as e:
            if isinstance(e, (ResolutionError, DependencyNotFoundError, CircularDependencyError)):
                raise
            raise ResolutionError(f"Failed to call factory for {self.key}: {e}")

    async def create_instance_async(self, container: "Container") -> Any:
        """Create an instance of the dependency (async context).

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
            if self._factory_has_params:
                # Factory has parameters - resolve them from container
                factory = self.factory  # Capture for closure

                async def factory_func() -> Any:
                    return await self._call_factory_with_deps_async(container, factory)

            else:
                # Factory has no parameters - call directly
                factory_func = self.factory
        elif self.implementation is not None:
            # Create a factory from the implementation type
            # For async, we need to call _create_instance_async
            implementation = self.implementation  # Capture for closure

            async def factory_func() -> Any:
                return await container._create_instance_async(implementation)

        else:
            raise ResolutionError(f"Cannot create instance for {self.key}")

        # Use the strategy to manage instance lifecycle
        return await self._strategy.get_async(factory_func)

    async def _call_factory_with_deps_async(
        self, container: "Container", factory: Callable[..., Any]
    ) -> Any:
        """Call a factory function asynchronously, resolving its dependencies from the container.

        Supports named dependencies via Inject[Type, Named("qualifier")] annotations.

        Args:
            container: Container to resolve dependencies from
            factory: Factory function to call

        Returns:
            Result of calling the factory

        Raises:
            ResolutionError: If dependencies cannot be resolved
        """
        try:
            sig = inspect.signature(factory)
            type_hints = get_type_hints(factory, include_extras=True)

            kwargs: dict[str, Any] = {}
            for param_name, param in sig.parameters.items():
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue

                param_type = type_hints.get(param_name)
                if param_type is not None:
                    # Check for Inject annotation with optional Named qualifier
                    inject_info = extract_inject_info(param_type)
                    if inject_info:
                        actual_type, dep_name = inject_info
                        try:
                            kwargs[param_name] = await container.get_async(
                                actual_type, name=dep_name
                            )
                        except DependencyNotFoundError:
                            if param.default is inspect.Parameter.empty:
                                raise ResolutionError(
                                    f"Cannot resolve factory parameter '{param_name}' "
                                    f"of type {_format_dependency(actual_type, dep_name)} "
                                    f"for {self.key}"
                                )
                    else:
                        try:
                            kwargs[param_name] = await container.get_async(param_type)
                        except DependencyNotFoundError:
                            if param.default is inspect.Parameter.empty:
                                raise ResolutionError(
                                    f"Cannot resolve factory parameter '{param_name}' "
                                    f"of type {param_type} for {self.key}"
                                )
                elif param.default is inspect.Parameter.empty:
                    raise ResolutionError(
                        f"Factory parameter '{param_name}' has no type hint "
                        f"and no default value for {self.key}"
                    )

            result = factory(**kwargs)
            # If factory is async, await the result
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as e:
            if isinstance(e, (ResolutionError, DependencyNotFoundError, CircularDependencyError)):
                raise
            raise ResolutionError(f"Failed to call factory for {self.key}: {e}")

    def reset(self) -> None:
        """Reset the binding's scope state."""
        self._strategy.reset()


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
        self._bindings: dict[DependencyKey, Binding] = {}
        self._modules: list[ModuleProtocol] = []  # List of registered modules
        self._parent = parent
        # Resolution stack now tracks DependencyKey (type or (type, name) tuple)
        self._resolution_stack: list[DependencyKey] = []

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
        interface: type[T],
        implementation: type[T] | None = None,
        factory: Factory[T] | None = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: T | None = None,
        name: str | None = None,
    ) -> "Container":
        """Register a dependency in the container.

        Args:
            interface: The interface/type to register
            implementation: Optional implementation type
            factory: Optional factory function
            scope: Scope for the dependency lifecycle
            instance: Optional pre-created instance
            name: Optional name qualifier for named bindings

        Returns:
            Self for chaining

        Raises:
            RegistrationError: If registration parameters are invalid

        Example:
            # Unnamed registration (default)
            container.register(IDatabase, PostgresDB)

            # Named registration for multiple implementations
            container.register(IDatabase, PostgresDB, name="primary")
            container.register(IDatabase, MySQLDB, name="replica")
        """
        # If no implementation or factory provided, use interface as implementation
        if implementation is None and factory is None and instance is None:
            implementation = interface

        key = make_key(interface, name)

        binding = Binding(
            key=key,
            factory=factory,
            implementation=implementation,
            scope=scope,
            instance=instance,
        )
        self._bindings[key] = binding
        return self

    def register_factory[T](
        self,
        interface: type[T],
        factory: Factory[T],
        scope: Scopes = Scopes.TRANSIENT,
        name: str | None = None,
    ) -> "Container":
        """Register a factory function for a dependency.

        Args:
            interface: The interface/type to register
            factory: Factory function to create instances
            scope: Scope for the dependency lifecycle
            name: Optional name qualifier for named bindings

        Returns:
            Self for chaining
        """
        return self.register(interface, factory=factory, scope=scope, name=name)

    def register_instance[T](
        self, interface: type[T], instance: T, name: str | None = None
    ) -> "Container":
        """Register a pre-created instance.

        Args:
            interface: The interface/type to register
            instance: Pre-created instance
            name: Optional name qualifier for named bindings

        Returns:
            Self for chaining
        """
        return self.register(interface, instance=instance, scope=Scopes.SINGLETON, name=name)

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

    def get[T](self, interface: type[T], name: str | None = None) -> T:
        """Resolve a dependency from the container.

        Resolution order:
        1. Check local bindings
        2. Check registered modules
        3. Check parent container (if exists)

        Args:
            interface: The type to resolve
            name: Optional name qualifier for named bindings

        Returns:
            Resolved instance

        Raises:
            DependencyNotFoundError: If dependency is not registered
            CircularDependencyError: If circular dependency is detected

        Example:
            # Resolve unnamed dependency
            db = container.get(IDatabase)

            # Resolve named dependency
            primary = container.get(IDatabase, name="primary")
            replica = container.get(IDatabase, name="replica")
        """
        key = make_key(interface, name)

        # Check for circular dependencies
        if key in self._resolution_stack:
            self._resolution_stack.append(key)
            # Extract types for error message
            cycle_types = [get_type_from_key(k) for k in self._resolution_stack]
            raise CircularDependencyError(cycle_types)

        # Try to find binding in this container
        binding = self._bindings.get(key)

        # If not found, try registered modules
        if binding is None:
            for module in self._modules:
                try:
                    # Try to resolve from the module
                    # The module will enforce its own public/private access rules
                    instance = module.get(interface, name=name)
                    return instance
                except DependencyNotFoundError:
                    # This module doesn't have it (or it's private), try next module
                    continue

        # If not found, try parent container
        if binding is None and self._parent is not None:
            return self._parent.get(interface, name=name)

        # If still not found, raise error
        if binding is None:
            raise DependencyNotFoundError(interface, self._name, name=name)

        # Add to resolution stack
        self._resolution_stack.append(key)

        try:
            instance = binding.create_instance(self)
            return instance
        finally:
            # Remove from resolution stack
            self._resolution_stack.pop()

    def try_get[T](self, interface: type[T], name: str | None = None) -> T | None:
        """Try to resolve a dependency, returning None if not found.

        Args:
            interface: The type to resolve
            name: Optional name qualifier for named bindings

        Returns:
            Resolved instance or None
        """
        try:
            return self.get(interface, name=name)
        except DependencyNotFoundError:
            return None

    async def get_async[T](self, interface: type[T], name: str | None = None) -> T:
        """Resolve a dependency from the container asynchronously.

        This method supports async factories and async scopes. It follows the same
        resolution order as get():
        1. Check local bindings
        2. Check registered modules
        3. Check parent container (if exists)

        Args:
            interface: The type to resolve
            name: Optional name qualifier for named bindings

        Returns:
            Resolved instance

        Raises:
            DependencyNotFoundError: If dependency is not registered
            CircularDependencyError: If circular dependency is detected
        """
        key = make_key(interface, name)

        # Check for circular dependencies
        if key in self._resolution_stack:
            self._resolution_stack.append(key)
            cycle_types = [get_type_from_key(k) for k in self._resolution_stack]
            raise CircularDependencyError(cycle_types)

        # Try to find binding in this container
        binding = self._bindings.get(key)

        # If not found, try registered modules
        if binding is None:
            for module in self._modules:
                try:
                    # Try to resolve from the module asynchronously
                    instance = await module.get_async(interface, name=name)
                    return instance
                except DependencyNotFoundError:
                    # This module doesn't have it (or it's private), try next module
                    continue

        # If not found, try parent container
        if binding is None and self._parent is not None:
            return await self._parent.get_async(interface, name=name)

        # If still not found, raise error
        if binding is None:
            raise DependencyNotFoundError(interface, self._name, name=name)

        # Add to resolution stack
        self._resolution_stack.append(key)

        try:
            instance = await binding.create_instance_async(self)
            return instance
        finally:
            # Remove from resolution stack
            self._resolution_stack.pop()

    def has(self, interface: type[Any], name: str | None = None) -> bool:
        """Check if a dependency is registered.

        Args:
            interface: The type to check
            name: Optional name qualifier for named bindings

        Returns:
            True if registered, False otherwise
        """
        key = make_key(interface, name)

        if key in self._bindings:
            return True

        # Check registered modules
        for module in self._modules:
            if module.has(interface, name=name):
                return True

        # Check parent if exists
        if self._parent is not None:
            return self._parent.has(interface, name=name)

        return False

    def run[T](self, func: Callable[..., T], **provided_kwargs: Any) -> T:
        """Run a function with dependency injection using synchronous resolution.

        The function parameters are resolved from the container based on their type hints
        using synchronous get(). Any parameters provided in provided_kwargs are used
        directly instead of being resolved.

        Args:
            func: Function to run with dependency injection (can be sync or async)
            **provided_kwargs: Explicit parameter values (not resolved from container)

        Returns:
            The function's return value. If func is async, returns the coroutine
            (caller must await it). If func is sync, returns the value directly.

        Raises:
            ResolutionError: If dependencies cannot be resolved

        Example:
            ```python
            # Sync function
            def process_users(db: Database, logger: Logger) -> list:
                logger.info("Processing users")
                return db.query("SELECT * FROM users")

            result = container.run(process_users)

            # Async function
            async def process_async(db: Database) -> list:
                return await db.query_async("SELECT * FROM users")

            coro = container.run(process_async)
            result = await coro
            ```
        """
        try:
            # Get type hints for the function (with extras for Annotated support)
            try:
                type_hints = get_type_hints(func, include_extras=True)
            except Exception:
                type_hints = {}

            type_hints.pop("return", None)

            # Get function signature
            sig = inspect.signature(func)

            # Resolve dependencies for parameters not provided
            resolved_kwargs = provided_kwargs.copy()

            for param_name, param in sig.parameters.items():
                # Skip if already provided
                if param_name in provided_kwargs:
                    continue

                # Skip *args and **kwargs
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue

                # Get the type hint
                param_type = type_hints.get(param_name)

                if param_type is not None:
                    # Check for Inject[T, Named(...)] annotations
                    inject_info = extract_inject_info(param_type)
                    if inject_info:
                        actual_type, dep_name = inject_info
                        try:
                            resolved_kwargs[param_name] = self.get(actual_type, name=dep_name)
                        except DependencyNotFoundError:
                            if param.default is inspect.Parameter.empty:
                                raise ResolutionError(
                                    f"Cannot resolve parameter '{param_name}' of type "
                                    f"{_format_dependency(actual_type, dep_name)} "
                                    f"for function '{func.__name__}'"
                                )
                    else:
                        try:
                            resolved_kwargs[param_name] = self.get(param_type)
                        except DependencyNotFoundError:
                            if param.default is inspect.Parameter.empty:
                                raise ResolutionError(
                                    f"Cannot resolve parameter '{param_name}' of type "
                                    f"'{param_type}' for function '{func.__name__}'"
                                )
                elif param.default is inspect.Parameter.empty:
                    raise ResolutionError(
                        f"Parameter '{param_name}' of function '{func.__name__}' "
                        f"has no type annotation and no default value"
                    )

            # Call the function and return result (could be a value or coroutine)
            return func(**resolved_kwargs)

        except Exception as e:
            if isinstance(e, (ResolutionError, DependencyNotFoundError, CircularDependencyError)):
                raise
            raise ResolutionError(f"Failed to run function '{func.__name__}': {e}")

    async def run_async[T](self, func: Callable[..., T], **provided_kwargs: Any) -> T:
        """Run a function with dependency injection using asynchronous resolution.

        The function parameters are resolved from the container based on their type hints
        using asynchronous get_async(). Use this when you have async dependencies that
        need to be awaited during resolution. Any parameters provided in provided_kwargs
        are used directly instead of being resolved.

        Args:
            func: Function to run with dependency injection (can be sync or async)
            **provided_kwargs: Explicit parameter values (not resolved from container)

        Returns:
            The function's return value. If func is async, returns the coroutine
            (caller must await it). If func is sync, returns the value directly.

        Raises:
            ResolutionError: If dependencies cannot be resolved

        Example:
            ```python
            # Async function with async dependencies
            async def process_users(db: AsyncDatabase, logger: Logger) -> list:
                await logger.info("Processing users")
                return await db.query("SELECT * FROM users")

            coro = await container.run_async(process_users)
            result = await coro

            # Or for sync function with async dependencies
            def process_sync(db: AsyncDatabase) -> str:
                return "processed"

            result = await container.run_async(process_sync)
            ```
        """
        try:
            # Get type hints for the function (with extras for Annotated support)
            try:
                type_hints = get_type_hints(func, include_extras=True)
            except Exception:
                type_hints = {}

            type_hints.pop("return", None)

            # Get function signature
            sig = inspect.signature(func)

            # Resolve dependencies for parameters not provided
            resolved_kwargs = provided_kwargs.copy()

            for param_name, param in sig.parameters.items():
                # Skip if already provided
                if param_name in provided_kwargs:
                    continue

                # Skip *args and **kwargs
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue

                # Get the type hint
                param_type = type_hints.get(param_name)

                if param_type is not None:
                    # Check for Inject[T, Named(...)] annotations
                    inject_info = extract_inject_info(param_type)
                    if inject_info:
                        actual_type, dep_name = inject_info
                        try:
                            resolved_kwargs[param_name] = await self.get_async(
                                actual_type, name=dep_name
                            )
                        except DependencyNotFoundError:
                            if param.default is inspect.Parameter.empty:
                                raise ResolutionError(
                                    f"Cannot resolve parameter '{param_name}' of type "
                                    f"{_format_dependency(actual_type, dep_name)} "
                                    f"for function '{func.__name__}'"
                                )
                    else:
                        try:
                            resolved_kwargs[param_name] = await self.get_async(param_type)
                        except DependencyNotFoundError:
                            if param.default is inspect.Parameter.empty:
                                raise ResolutionError(
                                    f"Cannot resolve parameter '{param_name}' of type "
                                    f"'{param_type}' for function '{func.__name__}'"
                                )
                elif param.default is inspect.Parameter.empty:
                    raise ResolutionError(
                        f"Parameter '{param_name}' of function '{func.__name__}' "
                        f"has no type annotation and no default value"
                    )

            # Call the function and return result (could be a value or coroutine)
            return func(**resolved_kwargs)

        except Exception as e:
            if isinstance(e, (ResolutionError, DependencyNotFoundError, CircularDependencyError)):
                raise
            raise ResolutionError(f"Failed to run function '{func.__name__}': {e}")

    def _create_instance[T](self, cls: type[T]) -> T:
        """Create an instance of a class, resolving its dependencies.

        Supports both regular constructor injection and Injectable classes with
        named dependencies via Inject[Type, Named("qualifier")].

        Args:
            cls: The class to instantiate

        Returns:
            Created instance

        Raises:
            ResolutionError: If instance creation fails
        """
        try:
            # Check if this is an Injectable class with named dependency metadata
            inject_fields: dict[str, tuple[type, str | None]] | None = getattr(
                cls, "_inject_fields", None
            )

            if inject_fields:
                # Injectable class - use the stored field metadata
                kwargs: dict[str, Any] = {}
                for field_name, (field_type, dep_name) in inject_fields.items():
                    try:
                        kwargs[field_name] = self.get(field_type, name=dep_name)
                    except DependencyNotFoundError:
                        raise ResolutionError(
                            f"Cannot resolve dependency '{field_name}' of type "
                            f"{_format_dependency(field_type, dep_name)} "
                            f"for class '{cls.__name__}'"
                        )
                return cls(**kwargs)

            # Regular class - use constructor inspection
            init_method = cls.__init__

            # Get type hints for the constructor (with extras for Annotated support)
            try:
                type_hints = get_type_hints(init_method, include_extras=True)
            except Exception:
                # If we can't get type hints, try without dependencies
                type_hints = {}

            # Remove 'return' from type hints
            type_hints.pop("return", None)

            # Get constructor signature
            sig = inspect.signature(init_method)

            # Resolve dependencies
            kwargs = {}
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                # Skip *args and **kwargs
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue

                # Get the type hint for this parameter
                param_type = type_hints.get(param_name)

                if param_type is not None:
                    # Check for Inject annotation with optional Named qualifier
                    inject_info = extract_inject_info(param_type)
                    if inject_info:
                        actual_type, dep_name = inject_info
                        try:
                            kwargs[param_name] = self.get(actual_type, name=dep_name)
                        except DependencyNotFoundError:
                            if param.default is inspect.Parameter.empty:
                                raise ResolutionError(
                                    f"Cannot resolve parameter '{param_name}' of type "
                                    f"{_format_dependency(actual_type, dep_name)} "
                                    f"for class '{cls.__name__}'"
                                )
                    else:
                        # Regular type hint resolution
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

            # Create the instance with resolved dependencies
            return cls(**kwargs)

        except Exception as e:
            if isinstance(e, (ResolutionError, DependencyNotFoundError, CircularDependencyError)):
                raise
            raise ResolutionError(f"Failed to create instance of {cls.__name__}: {e}")

    async def _create_instance_async[T](self, cls: type[T]) -> T:
        """Create an instance of a class asynchronously, resolving its dependencies.

        Supports both regular constructor injection and Injectable classes with
        named dependencies via Inject[Type, Named("qualifier")].

        Args:
            cls: The class to instantiate

        Returns:
            Created instance

        Raises:
            ResolutionError: If instance creation fails
        """
        try:
            # Check if this is an Injectable class with named dependency metadata
            inject_fields: dict[str, tuple[type, str | None]] | None = getattr(
                cls, "_inject_fields", None
            )

            if inject_fields:
                # Injectable class - use the stored field metadata
                kwargs: dict[str, Any] = {}
                for field_name, (field_type, dep_name) in inject_fields.items():
                    try:
                        kwargs[field_name] = await self.get_async(field_type, name=dep_name)
                    except DependencyNotFoundError:
                        raise ResolutionError(
                            f"Cannot resolve dependency '{field_name}' of type "
                            f"{_format_dependency(field_type, dep_name)} "
                            f"for class '{cls.__name__}'"
                        )
                return cls(**kwargs)

            # Regular class - use constructor inspection
            init_method = cls.__init__

            # Get type hints for the constructor (with extras for Annotated support)
            try:
                type_hints = get_type_hints(init_method, include_extras=True)
            except Exception:
                # If we can't get type hints, try without dependencies
                type_hints = {}

            # Remove 'return' from type hints
            type_hints.pop("return", None)

            # Get constructor signature
            sig = inspect.signature(init_method)

            # Resolve dependencies asynchronously
            kwargs = {}
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                # Skip *args and **kwargs
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue

                # Get the type hint for this parameter
                param_type = type_hints.get(param_name)

                if param_type is not None:
                    # Check for Inject annotation with optional Named qualifier
                    inject_info = extract_inject_info(param_type)
                    if inject_info:
                        actual_type, dep_name = inject_info
                        try:
                            kwargs[param_name] = await self.get_async(actual_type, name=dep_name)
                        except DependencyNotFoundError:
                            if param.default is inspect.Parameter.empty:
                                raise ResolutionError(
                                    f"Cannot resolve parameter '{param_name}' of type "
                                    f"{_format_dependency(actual_type, dep_name)} "
                                    f"for class '{cls.__name__}'"
                                )
                    else:
                        # Regular type hint resolution
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

            # Create the instance with resolved dependencies
            return cls(**kwargs)

        except Exception as e:
            if isinstance(e, (ResolutionError, DependencyNotFoundError, CircularDependencyError)):
                raise
            raise ResolutionError(f"Failed to create instance of {cls.__name__}: {e}")

    def create_child(self, name: str | None = None) -> "Container":
        """Create a child container.

        Args:
            name: Optional name for the child container

        Returns:
            New child container
        """
        child_name = name if name else f"{self._name}.Child"
        return Container(parent=self, name=child_name)

    def _get_implementation_dependencies(self, cls: type[Any]) -> list[type[Any]]:
        """Get the dependency types required by a class implementation.

        Args:
            cls: The class to inspect

        Returns:
            List of dependency types required by the class constructor
        """
        dependencies: list[type[Any]] = []
        try:
            init_method = cls.__init__
            try:
                type_hints = get_type_hints(init_method, include_extras=True)
            except Exception:
                return []

            type_hints.pop("return", None)
            sig = inspect.signature(init_method)

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                if param.kind in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                ):
                    continue

                param_type = type_hints.get(param_name)
                if param_type is not None and param.default is inspect.Parameter.empty:
                    # Check for Inject[T, Named(...)] and extract actual type
                    inject_info = extract_inject_info(param_type)
                    if inject_info:
                        dependencies.append(inject_info[0])  # Just the type, not name
                    else:
                        dependencies.append(param_type)
        except Exception:
            pass

        return dependencies

    def _detect_cycles(self) -> list[list[type[Any]]]:
        """Detect circular dependencies in the container.

        Returns:
            List of cycles found, where each cycle is a list of types
        """
        # Build dependency graph for implementations only
        graph: dict[type[Any], list[type[Any]]] = {}

        for key, binding in self._bindings.items():
            if binding.instance is not None or binding.factory is not None:
                continue
            if binding.implementation is not None:
                # Extract the type from the key (handles both type and (type, name) tuples)
                node_type = get_type_from_key(key)
                deps = self._get_implementation_dependencies(binding.implementation)
                # Only include dependencies that are registered in this container
                registered_deps = [
                    d
                    for d in deps
                    if d in self._bindings
                    or any(d in m._bindings for m in self._modules if hasattr(m, "_bindings"))
                ]
                graph[node_type] = registered_deps

        # Also check modules
        for module in self._modules:
            if hasattr(module, "_bindings"):
                for key, binding in module._bindings.items():
                    if binding.instance is not None or binding.factory is not None:
                        continue
                    if binding.implementation is not None:
                        node_type = get_type_from_key(key)
                        deps = self._get_implementation_dependencies(binding.implementation)
                        registered_deps = [
                            d
                            for d in deps
                            if d in self._bindings
                            or d in module._bindings
                            or any(
                                d in m._bindings for m in self._modules if hasattr(m, "_bindings")
                            )
                        ]
                        graph[node_type] = registered_deps

        # DFS to detect cycles
        cycles: list[list[type[Any]]] = []
        visited: set[type[Any]] = set()
        rec_stack: set[type[Any]] = set()
        path: list[type[Any]] = []

        def dfs(node: type[Any]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found a cycle - extract it from the path
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.remove(node)

        for node in graph:
            if node not in visited:
                dfs(node)

        return cycles

    def validate(self) -> None:
        """Validate that all registered dependencies can be resolved.

        This checks:
        - All required dependencies are registered
        - No circular dependencies exist

        Raises:
            ValidationError: If validation fails
        """
        errors: list[str] = []

        # Check for circular dependencies
        cycles = self._detect_cycles()
        for cycle in cycles:
            chain_str = " -> ".join(t.__name__ for t in cycle)
            errors.append(f"Circular dependency detected: {chain_str}")

        for key, binding in self._bindings.items():
            # Skip validation for instances and factories
            if binding.instance is not None or binding.factory is not None:
                continue

            # Validate implementation can be instantiated
            if binding.implementation is not None:
                cls = binding.implementation
                try:
                    # Get type hints for the constructor (with extras for Annotated)
                    init_method = cls.__init__
                    try:
                        type_hints = get_type_hints(init_method, include_extras=True)
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
                        if param.kind in (
                            inspect.Parameter.VAR_POSITIONAL,
                            inspect.Parameter.VAR_KEYWORD,
                        ):
                            continue

                        param_type = type_hints.get(param_name)

                        if param_type is not None:
                            # Check for Inject[T, Named(...)] annotations
                            inject_info = extract_inject_info(param_type)
                            if inject_info:
                                actual_type, dep_name = inject_info
                                dep_key = make_key(actual_type, dep_name)
                                # Check bindings directly (not has()) to include private deps
                                has_dependency = (
                                    dep_key in self._bindings
                                    or any(
                                        dep_key in m._bindings
                                        for m in self._modules
                                        if hasattr(m, "_bindings")
                                    )
                                    or (
                                        self._parent is not None
                                        and self._parent.has(actual_type, name=dep_name)
                                    )
                                )
                                if not has_dependency:
                                    if param.default is inspect.Parameter.empty:
                                        errors.append(
                                            f"Dependency '{cls.__name__}' requires "
                                            f"'{_format_dependency(actual_type, dep_name)}' "
                                            f"(parameter '{param_name}') which is not registered"
                                        )
                            else:
                                # Regular type hint - check if registered
                                has_dependency = (
                                    param_type in self._bindings
                                    or any(
                                        param_type in m._bindings
                                        for m in self._modules
                                        if hasattr(m, "_bindings")
                                    )
                                    or (self._parent is not None and self._parent.has(param_type))
                                )
                                if not has_dependency:
                                    if param.default is inspect.Parameter.empty:
                                        type_name = getattr(param_type, "__name__", str(param_type))
                                        errors.append(
                                            f"Dependency '{cls.__name__}' requires "
                                            f"'{type_name}' (parameter '{param_name}') "
                                            f"which is not registered"
                                        )

                except Exception as e:
                    errors.append(f"Failed to validate dependency '{cls.__name__}': {e}")

        if errors:
            raise ValidationError(errors)

    def __repr__(self) -> str:
        """Get string representation of the container."""
        deps = ", ".join(getattr(k, "__name__", str(k)) for k in self._bindings.keys())
        return f"Container({self._name}, dependencies=[{deps}])"
