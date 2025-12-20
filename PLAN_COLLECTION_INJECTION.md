# Implementation Plan: Collection Injection

## Overview

This plan describes how to implement **collection injection** in inversipy, enabling injection of all registered implementations of an interface as a collection.

## Problem Statement

Currently, registering the same interface multiple times overwrites previous registrations:

```python
container.register(IPlugin, PluginA)
container.register(IPlugin, PluginB)  # Overwrites PluginA!
container.register(IPlugin, PluginC)  # Overwrites PluginB!

plugin = container.get(IPlugin)  # Only gets PluginC
```

This limitation prevents common patterns like:
- Plugin systems with multiple plugins
- Event handlers/listeners
- Middleware chains
- Strategy pattern with multiple strategies
- Validators/processors pipelines

## Design Goals

1. **Non-breaking** - Existing single-registration behavior unchanged
2. **Explicit** - Clear distinction between single and collection registration
3. **Type-safe** - Full typing support for collections
4. **Consistent** - Follow existing API patterns

---

## Syntax Options

### Option A: Separate `register_all` / `get_all` Methods

```python
# Registration
container.register_all(IPlugin, PluginA)
container.register_all(IPlugin, PluginB)
container.register_all(IPlugin, PluginC)

# Resolution
plugins: list[IPlugin] = container.get_all(IPlugin)

# Type annotation
class PluginManager(Injectable):
    plugins: InjectAll[IPlugin]
```

**Pros:**
- Clear separation from single registration
- Explicit intent
- No ambiguity

**Cons:**
- New method to learn
- Separate mental model

### Option B: Automatic Collection via `list[T]` Type

```python
# Registration (unchanged - last wins for single)
container.register(IPlugin, PluginA)
container.register(IPlugin, PluginB)

# Resolution via list type
plugins: list[IPlugin] = container.get(list[IPlugin])

# Type annotation
class PluginManager(Injectable):
    plugins: Inject[list[IPlugin]]
```

**Pros:**
- Uses standard Python typing
- Intuitive for users familiar with DI frameworks
- No new methods

**Cons:**
- Magic behavior based on type
- Ambiguous: does `list[IPlugin]` mean "all plugins" or "a registered list"?

### Option C: Collection Registration with Tags

```python
# Registration with collection tag
container.register(IPlugin, PluginA, collection="plugins")
container.register(IPlugin, PluginB, collection="plugins")

# Resolution
plugins = container.get_collection("plugins")

# Type annotation
class PluginManager(Injectable):
    plugins: Inject[list[IPlugin], Collection("plugins")]
```

**Pros:**
- Explicit grouping
- Multiple collections of same type possible

**Cons:**
- String-based, less type-safe
- More verbose

### Recommended: Option A

Option A provides the clearest semantics with explicit `register_all`/`get_all` methods and `InjectAll[T]` type alias.

---

## Final Syntax Design

```python
# Registration - add to collection
container.register_all(IPlugin, PluginA)
container.register_all(IPlugin, PluginB)
container.register_all(IPlugin, PluginC)

# Can also use factories
container.register_all(IPlugin, factory=create_plugin_d)

# Resolution
plugins: list[IPlugin] = container.get_all(IPlugin)

# Property injection
class PluginManager(Injectable):
    plugins: InjectAll[IPlugin]

    def run_all(self):
        for plugin in self.plugins:
            plugin.execute()

# Constructor injection
class EventBus:
    def __init__(self, handlers: list[IEventHandler]):
        self.handlers = handlers

# With InjectAll annotation
class EventBus:
    def __init__(self, handlers: InjectAll[IEventHandler]):
        self.handlers = handlers
```

---

## Implementation Plan

### Phase 1: Core Data Structures (`container.py`)

#### 1.1 Add Collection Storage

```python
class Container:
    def __init__(self, parent: Optional["Container"] = None, name: str = "Container") -> None:
        self._name = name
        self._bindings: dict[DependencyKey, Binding] = {}
        self._collections: dict[type, list[Binding]] = {}  # NEW
        self._modules: list[ModuleProtocol] = []
        self._parent = parent
        self._resolution_stack: list[type[Any]] = []
```

#### 1.2 Add `register_all` Method

```python
def register_all[T](
    self,
    interface: type[T],
    implementation: type[T] | None = None,
    factory: Factory[T] | None = None,
    scope: Scopes = Scopes.TRANSIENT,
    instance: T | None = None,
) -> "Container":
    """Register an implementation to a collection.

    Multiple implementations can be registered for the same interface.
    Use get_all() to resolve all implementations.

    Args:
        interface: The interface type for the collection
        implementation: Optional implementation type
        factory: Optional factory function
        scope: Scope for each instance
        instance: Optional pre-created instance

    Returns:
        Self for chaining

    Example:
        container.register_all(IPlugin, PluginA)
        container.register_all(IPlugin, PluginB)
        plugins = container.get_all(IPlugin)  # [PluginA(), PluginB()]
    """
    if implementation is None and factory is None and instance is None:
        implementation = interface

    binding = Binding(
        key=interface,
        factory=factory,
        implementation=implementation,
        scope=scope,
        instance=instance,
    )

    if interface not in self._collections:
        self._collections[interface] = []

    self._collections[interface].append(binding)
    return self
```

#### 1.3 Add `get_all` Method

```python
def get_all[T](self, interface: type[T]) -> list[T]:
    """Resolve all implementations registered for an interface.

    Args:
        interface: The interface type to resolve

    Returns:
        List of all registered implementations

    Raises:
        CircularDependencyError: If circular dependency detected

    Example:
        plugins = container.get_all(IPlugin)
        for plugin in plugins:
            plugin.execute()
    """
    instances: list[T] = []

    # Get from local collections
    if interface in self._collections:
        for binding in self._collections[interface]:
            instance = binding.create_instance(self)
            instances.append(instance)

    # Get from registered modules
    for module in self._modules:
        if hasattr(module, "get_all"):
            try:
                module_instances = module.get_all(interface)
                instances.extend(module_instances)
            except Exception:
                pass

    # Get from parent container
    if self._parent is not None:
        parent_instances = self._parent.get_all(interface)
        instances.extend(parent_instances)

    return instances
```

#### 1.4 Add Async Variant

```python
async def get_all_async[T](self, interface: type[T]) -> list[T]:
    """Resolve all implementations asynchronously.

    Args:
        interface: The interface type to resolve

    Returns:
        List of all registered implementations
    """
    instances: list[T] = []

    if interface in self._collections:
        for binding in self._collections[interface]:
            instance = await binding.create_instance_async(self)
            instances.append(instance)

    for module in self._modules:
        if hasattr(module, "get_all_async"):
            try:
                module_instances = await module.get_all_async(interface)
                instances.extend(module_instances)
            except Exception:
                pass

    if self._parent is not None:
        parent_instances = await self._parent.get_all_async(interface)
        instances.extend(parent_instances)

    return instances
```

#### 1.5 Add `has_all` Check

```python
def has_all(self, interface: type[Any]) -> bool:
    """Check if any implementations are registered for collection injection.

    Args:
        interface: The interface type to check

    Returns:
        True if at least one implementation is registered
    """
    if interface in self._collections and self._collections[interface]:
        return True

    for module in self._modules:
        if hasattr(module, "has_all") and module.has_all(interface):
            return True

    if self._parent is not None:
        return self._parent.has_all(interface)

    return False
```

---

### Phase 2: Type Alias (`decorators.py`)

#### 2.1 Add `InjectAll` Type Alias

```python
class _InjectAllMarker:
    """Internal marker for collection injection."""
    pass

_inject_all_marker = _InjectAllMarker()

type InjectAll[T] = Annotated[list[T], _inject_all_marker]
```

This makes:
- `InjectAll[IPlugin]` → `Annotated[list[IPlugin], _inject_all_marker]`

#### 2.2 Update `Injectable` to Handle `InjectAll`

```python
def __init_subclass__(cls, **kwargs: Any) -> None:
    super().__init_subclass__(**kwargs)

    inject_fields: dict[str, tuple[type[Any], str | None]] = {}
    inject_all_fields: dict[str, type[Any]] = {}  # NEW

    annotations = get_type_hints(cls, include_extras=True)

    for attr_name, annotation in annotations.items():
        origin = get_origin(annotation)

        if origin is Annotated:
            args = get_args(annotation)
            actual_type = args[0]
            metadata = args[1:]

            # Check for InjectAll marker
            for meta in metadata:
                if isinstance(meta, _InjectAllMarker):
                    # actual_type is list[T], extract T
                    list_origin = get_origin(actual_type)
                    if list_origin is list:
                        item_type = get_args(actual_type)[0]
                        inject_all_fields[attr_name] = item_type
                    break
                elif isinstance(meta, _InjectMarker):
                    # Regular Inject handling
                    named_qualifier = None
                    for m in metadata:
                        if isinstance(m, Named):
                            named_qualifier = m.name
                    inject_fields[attr_name] = (actual_type, named_qualifier)
                    break

    setattr(cls, "_inject_fields", inject_fields)
    setattr(cls, "_inject_all_fields", inject_all_fields)  # NEW

    # Generate __init__ that handles both
    # ...
```

---

### Phase 3: Container Resolution Updates (`container.py`)

#### 3.1 Update `_create_instance` for Collection Injection

```python
def _create_instance[T](self, cls: type[T]) -> T:
    # ... existing code ...

    kwargs: dict[str, Any] = {}

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        param_type = type_hints.get(param_name)
        if param_type is None:
            continue

        # Check for InjectAll annotation
        inject_all_type = self._extract_inject_all_type(param_type)
        if inject_all_type:
            kwargs[param_name] = self.get_all(inject_all_type)
            continue

        # Check for regular Inject annotation
        inject_info = self._extract_inject_info(param_type)
        if inject_info:
            actual_type, dep_name = inject_info
            kwargs[param_name] = self.get(actual_type, name=dep_name)
            continue

        # Check for list[T] type (auto-collection)
        if self._is_list_type(param_type):
            item_type = self._get_list_item_type(param_type)
            if item_type and self.has_all(item_type):
                kwargs[param_name] = self.get_all(item_type)
                continue

        # Regular resolution
        try:
            kwargs[param_name] = self.get(param_type)
        except DependencyNotFoundError:
            if param.default is inspect.Parameter.empty:
                raise

    return cls(**kwargs)
```

#### 3.2 Helper Methods

```python
def _extract_inject_all_type(self, type_hint: Any) -> type | None:
    """Extract the item type from InjectAll[T] annotation."""
    origin = get_origin(type_hint)

    if origin is not Annotated:
        return None

    args = get_args(type_hint)
    actual_type = args[0]  # list[T]
    metadata = args[1:]

    for meta in metadata:
        if isinstance(meta, _InjectAllMarker):
            # Extract T from list[T]
            list_origin = get_origin(actual_type)
            if list_origin is list:
                list_args = get_args(actual_type)
                if list_args:
                    return list_args[0]

    return None

def _is_list_type(self, type_hint: Any) -> bool:
    """Check if type hint is list[T]."""
    return get_origin(type_hint) is list

def _get_list_item_type(self, type_hint: Any) -> type | None:
    """Get the item type from list[T]."""
    if get_origin(type_hint) is list:
        args = get_args(type_hint)
        if args:
            return args[0]
    return None
```

---

### Phase 4: Module Support (`module.py`)

#### 4.1 Add Collection Methods to Module

```python
class Module(Container):
    def __init__(self, name: str) -> None:
        super().__init__(parent=None, name=f"Module({name})")
        self._public_keys: set[type[Any]] = set()
        self._public_collections: set[type[Any]] = set()  # NEW

    def register_all[T](
        self,
        interface: type[T],
        implementation: type[T] | None = None,
        factory: Factory[T] | None = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: T | None = None,
        public: bool = False,  # Module-specific
    ) -> "Module":
        """Register to collection with public/private visibility."""
        super().register_all(
            interface=interface,
            implementation=implementation,
            factory=factory,
            scope=scope,
            instance=instance,
        )

        if public:
            self._public_collections.add(interface)

        return self

    def get_all[T](self, interface: type[T]) -> list[T]:
        """Get all implementations, respecting visibility."""
        # External call - check if collection is public
        if not self._resolution_stack:
            if interface not in self._public_collections:
                return []

        return super().get_all(interface)

    def has_all(self, interface: type[Any]) -> bool:
        """Check if public collection exists."""
        return interface in self._public_collections

    def export_all(self, *interfaces: type[Any]) -> "Module":
        """Export collection interfaces as public."""
        for interface in interfaces:
            if interface in self._collections:
                self._public_collections.add(interface)
            else:
                raise RegistrationError(
                    f"Cannot export collection '{interface.__name__}' - not registered"
                )
        return self
```

#### 4.2 Update ModuleBuilder

```python
class ModuleBuilder:
    def bind_all[T](
        self,
        interface: type[T],
        implementation: type[T] | None = None,
        factory: Factory[T] | None = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: T | None = None,
    ) -> "ModuleBuilder":
        """Add to collection (private)."""
        self._module.register_all(
            interface=interface,
            implementation=implementation,
            factory=factory,
            scope=scope,
            instance=instance,
            public=False,
        )
        return self

    def bind_all_public[T](
        self,
        interface: type[T],
        implementation: type[T] | None = None,
        factory: Factory[T] | None = None,
        scope: Scopes = Scopes.TRANSIENT,
        instance: T | None = None,
    ) -> "ModuleBuilder":
        """Add to public collection."""
        self._module.register_all(
            interface=interface,
            implementation=implementation,
            factory=factory,
            scope=scope,
            instance=instance,
            public=True,
        )
        return self

    def export_all(self, *interfaces: type[Any]) -> "ModuleBuilder":
        """Export collections as public."""
        self._module.export_all(*interfaces)
        return self
```

---

### Phase 5: Validation Updates (`container.py`)

#### 5.1 Update Validation to Check Collections

```python
def validate(self) -> None:
    """Validate container configuration."""
    errors: list[str] = []

    # Existing validation...

    # Validate collection bindings
    for interface, bindings in self._collections.items():
        for binding in bindings:
            if binding.implementation is not None:
                cls = binding.implementation
                # Check each implementation can be instantiated
                deps = self._get_implementation_dependencies(cls)
                for dep in deps:
                    if not self.has(dep) and not self.has_all(dep):
                        errors.append(
                            f"Collection '{interface.__name__}' implementation "
                            f"'{cls.__name__}' requires '{dep.__name__}' which is not registered"
                        )

    # Check for InjectAll in regular bindings
    for key, binding in self._bindings.items():
        if binding.implementation is not None:
            cls = binding.implementation
            # Check if any parameter uses InjectAll
            # and verify the collection is registered
            try:
                type_hints = get_type_hints(cls.__init__)
                for param_type in type_hints.values():
                    inject_all_type = self._extract_inject_all_type(param_type)
                    if inject_all_type and not self.has_all(inject_all_type):
                        errors.append(
                            f"'{cls.__name__}' requires collection of "
                            f"'{inject_all_type.__name__}' but none registered"
                        )
            except Exception:
                pass

    if errors:
        raise ValidationError(errors)
```

---

### Phase 6: FastAPI Integration (`fastapi.py`)

#### 6.1 Update `@inject` Decorator

```python
def inject(func: Callable[P, T]) -> Callable[P, T]:
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        request = _find_request(args, kwargs)
        container = request.app.state.container

        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        for param_name, param in sig.parameters.items():
            if param_name in kwargs:
                continue

            param_type = type_hints.get(param_name)
            if param_type is None:
                continue

            # Check for InjectAll
            inject_all_type = _extract_inject_all_type(param_type)
            if inject_all_type:
                kwargs[param_name] = await container.get_all_async(inject_all_type)
                continue

            # Check for regular Inject
            inject_info = _extract_inject_info(param_type)
            if inject_info:
                actual_type, dep_name = inject_info
                if container.has(actual_type, name=dep_name):
                    kwargs[param_name] = await container.get_async(actual_type, name=dep_name)

        return await func(*args, **kwargs)

    return wrapper
```

---

### Phase 7: Ordering Support (Optional Enhancement)

Allow controlling the order of collection items:

```python
def register_all[T](
    self,
    interface: type[T],
    implementation: type[T] | None = None,
    factory: Factory[T] | None = None,
    scope: Scopes = Scopes.TRANSIENT,
    instance: T | None = None,
    order: int = 0,  # NEW - lower values come first
) -> "Container":
    """Register with optional ordering."""
    binding = Binding(
        key=interface,
        factory=factory,
        implementation=implementation,
        scope=scope,
        instance=instance,
    )
    binding.order = order  # Store order on binding

    if interface not in self._collections:
        self._collections[interface] = []

    self._collections[interface].append(binding)
    # Keep sorted by order
    self._collections[interface].sort(key=lambda b: getattr(b, 'order', 0))
    return self
```

Usage:
```python
container.register_all(IMiddleware, LoggingMiddleware, order=10)
container.register_all(IMiddleware, AuthMiddleware, order=20)
container.register_all(IMiddleware, CorsMiddleware, order=5)

middlewares = container.get_all(IMiddleware)
# [CorsMiddleware, LoggingMiddleware, AuthMiddleware]
```

---

### Phase 8: Documentation & Examples

#### 8.1 Update README.md

```markdown
## Collection Injection

Register multiple implementations and inject them as a collection:

### Registration

```python
container.register_all(IPlugin, PluginA)
container.register_all(IPlugin, PluginB)
container.register_all(IPlugin, PluginC)
```

### Resolution

```python
plugins: list[IPlugin] = container.get_all(IPlugin)
for plugin in plugins:
    plugin.execute()
```

### Property Injection

```python
class PluginManager(Injectable):
    plugins: InjectAll[IPlugin]

    def run_all(self):
        for plugin in self.plugins:
            plugin.execute()
```

### Ordering

Control execution order with the `order` parameter:

```python
container.register_all(IMiddleware, AuthMiddleware, order=10)
container.register_all(IMiddleware, LoggingMiddleware, order=20)

# AuthMiddleware will be first in the list
```
```

#### 8.2 Add Example File

Create `examples/collection_injection_example.py`:

```python
"""Example: Plugin system with collection injection."""

from inversipy import Container, Injectable, InjectAll, Scopes

# Plugin interface
class IPlugin:
    def name(self) -> str: ...
    def execute(self) -> None: ...

# Plugin implementations
class LoggingPlugin(IPlugin):
    def name(self) -> str:
        return "Logging"
    def execute(self) -> None:
        print("Logging plugin executed")

class MetricsPlugin(IPlugin):
    def name(self) -> str:
        return "Metrics"
    def execute(self) -> None:
        print("Metrics plugin executed")

class CachePlugin(IPlugin):
    def name(self) -> str:
        return "Cache"
    def execute(self) -> None:
        print("Cache plugin executed")

# Plugin manager using collection injection
class PluginManager(Injectable):
    plugins: InjectAll[IPlugin]

    def list_plugins(self) -> list[str]:
        return [p.name() for p in self.plugins]

    def run_all(self) -> None:
        for plugin in self.plugins:
            plugin.execute()

# Setup
container = Container()
container.register_all(IPlugin, LoggingPlugin)
container.register_all(IPlugin, MetricsPlugin)
container.register_all(IPlugin, CachePlugin)
container.register(PluginManager)

# Usage
manager = container.get(PluginManager)
print(f"Loaded plugins: {manager.list_plugins()}")
manager.run_all()
```

---

## File Changes Summary

| File | Changes |
|------|---------|
| `container.py` | Add `_collections` storage, `register_all`, `get_all`, `get_all_async`, `has_all` |
| `decorators.py` | Add `InjectAll` type alias, update `Injectable` |
| `module.py` | Add collection methods with visibility |
| `fastapi.py` | Update `@inject` for collections |
| `types.py` | Export `InjectAll` |
| `__init__.py` | Export `InjectAll` |
| `README.md` | Add collection injection docs |
| `examples/collection_injection_example.py` | **NEW** |

---

## Test Plan

### New Test File: `tests/test_collection_injection.py`

1. **Basic Collection Registration & Resolution**
   - Register multiple implementations
   - `get_all()` returns all in order
   - Empty list when none registered

2. **Collection Scopes**
   - TRANSIENT: new instances each call
   - SINGLETON: same instances each call
   - REQUEST: per-request instances

3. **InjectAll Type Alias**
   - Property injection works
   - Constructor injection works
   - Runtime extraction correct

4. **Injectable with Collections**
   - Class with `InjectAll[T]` property
   - Mixed `Inject[T]` and `InjectAll[T]`

5. **Module Collections**
   - Public/private collections
   - Export collections
   - Module composition

6. **Ordering**
   - `order` parameter respected
   - Default order (registration order)

7. **Validation**
   - Missing collection dependencies detected
   - Collection binding validation

8. **Async**
   - `get_all_async()` works
   - Async factories in collections

9. **FastAPI Integration**
   - Route with `InjectAll` parameter

---

## API Summary

### Container Methods

```python
# Registration
container.register_all(IPlugin, PluginA)
container.register_all(IPlugin, PluginB, scope=Scopes.SINGLETON)
container.register_all(IPlugin, factory=create_plugin, order=10)

# Resolution
plugins: list[IPlugin] = container.get_all(IPlugin)
plugins: list[IPlugin] = await container.get_all_async(IPlugin)

# Check
has_plugins: bool = container.has_all(IPlugin)
```

### Type Annotations

```python
# Property injection
class Manager(Injectable):
    plugins: InjectAll[IPlugin]

# Constructor injection
class Manager:
    def __init__(self, plugins: InjectAll[IPlugin]):
        self.plugins = plugins
```

### Module Methods

```python
module.register_all(IPlugin, PluginA, public=True)
module.export_all(IPlugin)
module.get_all(IPlugin)
module.has_all(IPlugin)
```

---

## Backwards Compatibility

All existing code continues to work unchanged:

| Pattern | Status |
|---------|--------|
| `container.register(IFoo, Foo)` | ✅ Works (single registration) |
| `container.get(IFoo)` | ✅ Works (single resolution) |
| `Inject[T]` | ✅ Works |
| Collections are opt-in via `register_all` | ✅ New feature |

**Note:** `register()` and `register_all()` use separate storage. They don't interfere with each other.

---

## Open Questions

1. **Should `get_all()` return empty list or raise if none registered?**
   - Recommendation: Return empty list (more flexible for optional plugins)

2. **Should collections inherit from parent container?**
   - Recommendation: Yes, aggregate parent + child collections

3. **Should there be a `try_get_all()` variant?**
   - Recommendation: Not needed since `get_all()` returns empty list

4. **Should `register_all` with same implementation twice add duplicates?**
   - Recommendation: Allow duplicates (user's responsibility)

---

## Success Criteria

1. ✅ All existing tests pass
2. ✅ New collection tests pass
3. ✅ `InjectAll[T]` syntax works at runtime
4. ✅ Collections respect scopes
5. ✅ Module visibility works for collections
6. ✅ Documentation is clear
7. ✅ Backwards compatible
