# Implementation Plan: Collection Injection

## Overview

This plan describes how to implement **collection injection** in inversipy, enabling multiple implementations of the same interface to coexist and be injected as a collection.

## Problem Statement

Currently, registering the same interface multiple times overwrites previous registrations:

```python
container.register(IPlugin, PluginA)
container.register(IPlugin, PluginB)  # Overwrites PluginA!

plugin = container.get(IPlugin)  # Only gets PluginB
```

This limitation prevents common patterns like:
- Plugin systems with multiple plugins
- Event handlers/listeners
- Middleware chains
- Strategy pattern with multiple strategies
- Validators/processors pipelines

## Design Goals

1. **Minimal API change** - Same `register()` method, add `get_all()`
2. **Fail-fast** - Ambiguous single resolution fails immediately
3. **Type-safe** - Full typing support for collections
4. **Consistent** - Integrates with named bindings feature

---

## Final Syntax Design

```python
# Registration - same method, accumulates
container.register(IPlugin, PluginA)
container.register(IPlugin, PluginB)
container.register(IPlugin, PluginC)

# Single resolution - FAILS (ambiguous)
container.get(IPlugin)  # raises AmbiguousDependencyError

# Collection resolution - returns all
plugins: list[IPlugin] = container.get_all(IPlugin)

# Named resolution - works (unambiguous)
container.register(IPlugin, PluginA, name="primary")
container.get(IPlugin, name="primary")  # Works

# Property injection
class PluginManager(Injectable):
    plugins: InjectAll[IPlugin]
```

### Key Behavior Changes

| Scenario | Current Behavior | New Behavior |
|----------|------------------|--------------|
| Register same interface twice | Overwrites | Accumulates |
| `get()` with single registration | Returns instance | Returns instance |
| `get()` with multiple registrations | Returns last | **Raises AmbiguousDependencyError** |
| `get()` with name | N/A | Returns named instance |
| `get_all()` | N/A | Returns all instances |

---

## Implementation Plan

### Phase 1: Change Binding Storage (`container.py`)

#### 1.1 Update Storage Structure

**Current:**
```python
self._bindings: dict[DependencyKey, Binding] = {}
```

**New:**
```python
self._bindings: dict[DependencyKey, list[Binding]] = {}
```

Each key maps to a **list** of bindings, allowing multiple implementations.

#### 1.2 Update `register()` to Accumulate

```python
def register[T](
    self,
    interface: type[T],
    implementation: type[T] | None = None,
    factory: Factory[T] | None = None,
    scope: Scopes = Scopes.TRANSIENT,
    instance: T | None = None,
    name: str | None = None,
) -> "Container":
    """Register a dependency.

    Multiple implementations can be registered for the same interface.
    Use get_all() to resolve all, or use names to disambiguate get().

    Args:
        interface: The interface/type to register
        implementation: Optional implementation type
        factory: Optional factory function
        scope: Scope for the dependency lifecycle
        instance: Optional pre-created instance
        name: Optional name for disambiguation

    Returns:
        Self for chaining
    """
    key: DependencyKey = (interface, name) if name else interface

    if implementation is None and factory is None and instance is None:
        implementation = interface

    binding = Binding(
        key=key,
        factory=factory,
        implementation=implementation,
        scope=scope,
        instance=instance,
    )

    # Accumulate bindings instead of overwriting
    if key not in self._bindings:
        self._bindings[key] = []
    self._bindings[key].append(binding)

    return self
```

---

### Phase 2: Add AmbiguousDependencyError (`exceptions.py`)

```python
class AmbiguousDependencyError(InversipyError):
    """Raised when multiple implementations exist for a single get() call."""

    def __init__(
        self,
        dependency_type: type[Any],
        count: int,
        container_name: str = "container",
    ) -> None:
        self.dependency_type = dependency_type
        self.count = count
        self.container_name = container_name
        super().__init__(
            f"Ambiguous dependency: {count} implementations of "
            f"'{dependency_type.__name__}' registered in {container_name}. "
            f"Use get_all() for collection injection or register with name= for disambiguation."
        )
```

---

### Phase 3: Update Resolution Methods (`container.py`)

#### 3.1 Update `get()` to Fail on Ambiguity

```python
def get[T](self, interface: type[T], name: str | None = None) -> T:
    """Resolve a single dependency.

    Args:
        interface: The type to resolve
        name: Optional name for disambiguation

    Returns:
        Resolved instance

    Raises:
        DependencyNotFoundError: If no implementation registered
        AmbiguousDependencyError: If multiple implementations without name
        CircularDependencyError: If circular dependency detected
    """
    key: DependencyKey = (interface, name) if name else interface

    # Check for circular dependencies
    if key in self._resolution_stack:
        self._resolution_stack.append(key)
        raise CircularDependencyError(self._resolution_stack[:])

    # Try to find bindings in this container
    bindings = self._bindings.get(key, [])

    # Check for ambiguity
    if len(bindings) > 1:
        raise AmbiguousDependencyError(interface, len(bindings), self._name)

    if len(bindings) == 1:
        self._resolution_stack.append(key)
        try:
            return bindings[0].create_instance(self)
        finally:
            self._resolution_stack.pop()

    # Try registered modules
    for module in self._modules:
        try:
            return module.get(interface)
        except DependencyNotFoundError:
            continue
        except AmbiguousDependencyError:
            raise  # Propagate ambiguity

    # Try parent container
    if self._parent is not None:
        return self._parent.get(interface, name=name)

    raise DependencyNotFoundError(interface, self._name, name)
```

#### 3.2 Add `get_all()` Method

```python
def get_all[T](self, interface: type[T]) -> list[T]:
    """Resolve all implementations of an interface.

    Args:
        interface: The interface type to resolve

    Returns:
        List of all registered implementations (empty if none)

    Example:
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        plugins = container.get_all(IPlugin)  # [PluginA(), PluginB()]
    """
    instances: list[T] = []

    # Get from local bindings (unnamed only for collections)
    bindings = self._bindings.get(interface, [])
    for binding in bindings:
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

#### 3.3 Add Async Variants

```python
async def get_all_async[T](self, interface: type[T]) -> list[T]:
    """Resolve all implementations asynchronously."""
    instances: list[T] = []

    bindings = self._bindings.get(interface, [])
    for binding in bindings:
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

#### 3.4 Update `has()` Method

```python
def has(self, interface: type[Any], name: str | None = None) -> bool:
    """Check if a dependency is registered.

    Args:
        interface: The type to check
        name: Optional name qualifier

    Returns:
        True if at least one implementation registered
    """
    key: DependencyKey = (interface, name) if name else interface

    if key in self._bindings and self._bindings[key]:
        return True

    for module in self._modules:
        if module.has(interface):
            return True

    if self._parent is not None:
        return self._parent.has(interface, name=name)

    return False
```

#### 3.5 Add `count()` Method

```python
def count(self, interface: type[Any]) -> int:
    """Count implementations registered for an interface.

    Args:
        interface: The interface type

    Returns:
        Number of registered implementations
    """
    total = len(self._bindings.get(interface, []))

    for module in self._modules:
        if hasattr(module, "count"):
            total += module.count(interface)

    if self._parent is not None:
        total += self._parent.count(interface)

    return total
```

---

### Phase 4: Type Alias for InjectAll (`decorators.py`)

#### 4.1 Add InjectAll Type Alias

```python
class _InjectAllMarker:
    """Internal marker for collection injection."""
    pass

_inject_all_marker = _InjectAllMarker()

type InjectAll[T] = Annotated[list[T], _inject_all_marker]
```

#### 4.2 Update Injectable to Handle InjectAll

```python
def __init_subclass__(cls, **kwargs: Any) -> None:
    super().__init_subclass__(**kwargs)

    inject_fields: dict[str, tuple[type[Any], str | None]] = {}
    inject_all_fields: dict[str, type[Any]] = {}

    annotations = get_type_hints(cls, include_extras=True)

    for attr_name, annotation in annotations.items():
        origin = get_origin(annotation)

        if origin is Annotated:
            args = get_args(annotation)
            actual_type = args[0]
            metadata = args[1:]

            for meta in metadata:
                if isinstance(meta, _InjectAllMarker):
                    # Extract T from list[T]
                    if get_origin(actual_type) is list:
                        item_type = get_args(actual_type)[0]
                        inject_all_fields[attr_name] = item_type
                    break
                elif isinstance(meta, _InjectMarker):
                    named_qualifier = None
                    for m in metadata:
                        if isinstance(m, Named):
                            named_qualifier = m.name
                    inject_fields[attr_name] = (actual_type, named_qualifier)
                    break

    setattr(cls, "_inject_fields", inject_fields)
    setattr(cls, "_inject_all_fields", inject_all_fields)

    # Generate __init__ handling both types
    _generate_init(cls, inject_fields, inject_all_fields)
```

---

### Phase 5: Update Instance Creation (`container.py`)

#### 5.1 Handle InjectAll in Constructor Resolution

```python
def _create_instance[T](self, cls: type[T]) -> T:
    # ... get type_hints and sig ...

    kwargs: dict[str, Any] = {}

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        param_type = type_hints.get(param_name)
        if param_type is None:
            continue

        # Check for InjectAll[T]
        inject_all_type = self._extract_inject_all_type(param_type)
        if inject_all_type is not None:
            kwargs[param_name] = self.get_all(inject_all_type)
            continue

        # Check for Inject[T] or Inject[T, Named("x")]
        inject_info = self._extract_inject_info(param_type)
        if inject_info is not None:
            actual_type, dep_name = inject_info
            kwargs[param_name] = self.get(actual_type, name=dep_name)
            continue

        # Regular type resolution
        try:
            kwargs[param_name] = self.get(param_type)
        except DependencyNotFoundError:
            if param.default is inspect.Parameter.empty:
                raise
        except AmbiguousDependencyError:
            # Re-raise with helpful message
            raise

    return cls(**kwargs)
```

#### 5.2 Helper Method

```python
def _extract_inject_all_type(self, type_hint: Any) -> type | None:
    """Extract item type from InjectAll[T] -> T."""
    origin = get_origin(type_hint)

    if origin is not Annotated:
        return None

    args = get_args(type_hint)
    actual_type = args[0]  # list[T]
    metadata = args[1:]

    for meta in metadata:
        if isinstance(meta, _InjectAllMarker):
            if get_origin(actual_type) is list:
                list_args = get_args(actual_type)
                if list_args:
                    return list_args[0]
            break

    return None
```

---

### Phase 6: Module Updates (`module.py`)

#### 6.1 Update Module Storage

```python
class Module(Container):
    def __init__(self, name: str) -> None:
        super().__init__(parent=None, name=f"Module({name})")
        self._public_keys: set[DependencyKey] = set()
```

#### 6.2 Update Module get() for Ambiguity

```python
def get[T](self, interface: type[T], name: str | None = None) -> T:
    """Resolve with visibility check and ambiguity detection."""
    key: DependencyKey = (interface, name) if name else interface

    # Internal call - allow private access
    if self._resolution_stack:
        return super().get(interface, name=name)

    # External call - check public
    if not self.is_public(key):
        raise DependencyNotFoundError(interface, self._name, name)

    return super().get(interface, name=name)
```

#### 6.3 Add get_all() to Module

```python
def get_all[T](self, interface: type[T]) -> list[T]:
    """Get all public implementations."""
    # External call - only return public bindings
    if not self._resolution_stack:
        if not self.is_public(interface):
            return []

    return super().get_all(interface)
```

---

### Phase 7: Validation Updates (`container.py`)

#### 7.1 Update Validation

```python
def validate(self) -> None:
    """Validate container configuration.

    Checks:
    - Circular dependencies
    - Missing dependencies
    - Ambiguous dependencies (multiple implementations without name)
    """
    errors: list[str] = []

    # Check for cycles
    cycles = self._detect_cycles()
    for cycle in cycles:
        chain_str = " -> ".join(t.__name__ for t in cycle)
        errors.append(f"Circular dependency detected: {chain_str}")

    # Validate each binding
    for key, bindings in self._bindings.items():
        for binding in bindings:
            if binding.implementation is not None:
                cls = binding.implementation
                try:
                    type_hints = get_type_hints(cls.__init__)
                    sig = inspect.signature(cls.__init__)

                    for param_name, param in sig.parameters.items():
                        if param_name == "self":
                            continue

                        param_type = type_hints.get(param_name)
                        if param_type is None:
                            continue

                        # Check InjectAll - valid even if empty
                        inject_all_type = self._extract_inject_all_type(param_type)
                        if inject_all_type is not None:
                            continue

                        # Check regular dependency (Inject or plain type)
                        inject_info = self._extract_inject_info(param_type)
                        if inject_info:
                            actual_type, dep_name = inject_info
                            dep_key = (actual_type, dep_name) if dep_name else actual_type
                        else:
                            actual_type = param_type
                            dep_name = None
                            dep_key = param_type

                        # Check if dependency exists
                        if not self.has(actual_type, name=dep_name):
                            if param.default is inspect.Parameter.empty:
                                name_suffix = f" (name='{dep_name}')" if dep_name else ""
                                errors.append(
                                    f"'{cls.__name__}' requires '{actual_type.__name__}'"
                                    f"{name_suffix} which is not registered"
                                )
                            continue

                        # Check for ambiguous dependency (multiple without name)
                        if dep_name is None:
                            count = self.count(actual_type)
                            if count > 1:
                                errors.append(
                                    f"'{cls.__name__}' requires '{actual_type.__name__}' "
                                    f"but {count} implementations are registered. "
                                    f"Use Inject[{actual_type.__name__}, Named('...')] to disambiguate "
                                    f"or InjectAll[{actual_type.__name__}] for collection injection."
                                )

                except Exception as e:
                    errors.append(f"Failed to validate '{cls.__name__}': {e}")

    if errors:
        raise ValidationError(errors)
```

This validation will catch ambiguous dependencies at startup rather than at runtime, providing early feedback about configuration issues.

---

### Phase 8: FastAPI Integration (`fastapi.py`)

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

            # Check InjectAll
            inject_all_type = _extract_inject_all_type(param_type)
            if inject_all_type is not None:
                kwargs[param_name] = await container.get_all_async(inject_all_type)
                continue

            # Check Inject with optional name
            inject_info = _extract_inject_info(param_type)
            if inject_info is not None:
                actual_type, dep_name = inject_info
                kwargs[param_name] = await container.get_async(actual_type, name=dep_name)

        return await func(*args, **kwargs)

    return wrapper
```

---

### Phase 9: Documentation & Examples

#### 9.1 Update README.md

```markdown
## Collection Injection

Register multiple implementations and inject them as a collection:

### Registration

```python
# Multiple registrations accumulate (no overwriting)
container.register(IPlugin, PluginA)
container.register(IPlugin, PluginB)
container.register(IPlugin, PluginC)
```

### Single Resolution

```python
# Fails - ambiguous (3 implementations)
container.get(IPlugin)  # raises AmbiguousDependencyError

# Use names to disambiguate
container.register(IPlugin, PluginA, name="main")
container.get(IPlugin, name="main")  # Works
```

### Collection Resolution

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
```

#### 9.2 Add Example

Create `examples/collection_injection_example.py` demonstrating plugin system pattern.

---

## File Changes Summary

| File | Changes |
|------|---------|
| `container.py` | Change `_bindings` to `dict[key, list[Binding]]`, add `get_all`, `count`, update `get` for ambiguity |
| `decorators.py` | Add `InjectAll[T]` type alias, update `Injectable` |
| `exceptions.py` | Add `AmbiguousDependencyError` |
| `module.py` | Update for list-based bindings, add `get_all` |
| `fastapi.py` | Support `InjectAll` in `@inject` |
| `__init__.py` | Export `InjectAll`, `AmbiguousDependencyError` |
| `README.md` | Document collection injection |
| `examples/collection_injection_example.py` | **NEW** |

---

## Test Plan

### Update Existing Tests

Some existing tests may assume overwrite behavior - update them.

### New Test File: `tests/test_collection_injection.py`

1. **Accumulation Behavior**
   - Multiple `register()` calls accumulate
   - Same implementation can be registered twice

2. **Single Resolution Ambiguity**
   - `get()` with one binding works
   - `get()` with multiple bindings raises `AmbiguousDependencyError`
   - `get()` with name works when named

3. **Collection Resolution**
   - `get_all()` returns all implementations
   - `get_all()` returns empty list when none
   - Order is registration order

4. **InjectAll Type Alias**
   - Property injection works
   - Constructor injection works

5. **Scopes in Collections**
   - SINGLETON: same instance across get_all calls
   - TRANSIENT: new instances each call

6. **Module Collections**
   - Public/private visibility
   - Aggregation from modules

7. **Validation**
   - Validates collection dependencies
   - `InjectAll` with empty collection is valid
   - **Detects ambiguous dependencies at validation time**
   - Provides helpful error message with fix suggestions

8. **Error Messages**
   - `AmbiguousDependencyError` message is helpful
   - Validation error for ambiguity suggests `Named()` or `InjectAll`

---

## Migration Guide

### Breaking Change

Code that relies on overwrite behavior will break:

```python
# Before: PluginB overwrites PluginA
container.register(IPlugin, PluginA)
container.register(IPlugin, PluginB)
container.get(IPlugin)  # Returns PluginB

# After: Raises AmbiguousDependencyError
container.register(IPlugin, PluginA)
container.register(IPlugin, PluginB)
container.get(IPlugin)  # Raises!

# Fix: Use name or get_all
container.get(IPlugin, name="...")  # If using named bindings
container.get_all(IPlugin)[-1]      # If you really want "last"
```

### Recommended Migration

1. Search for multiple `register()` calls with same interface
2. Either:
   - Add `name=` to disambiguate
   - Change to `get_all()` if collection intended
   - Remove duplicate registrations if unintentional

---

## API Summary

### Container Methods

```python
# Registration (accumulates)
container.register(IPlugin, PluginA)
container.register(IPlugin, PluginB)

# Single resolution (fails if ambiguous)
container.get(IPlugin)  # Raises if multiple
container.get(IPlugin, name="x")  # Works with name

# Collection resolution
container.get_all(IPlugin) -> list[IPlugin]
container.get_all_async(IPlugin) -> list[IPlugin]

# Inspection
container.has(IPlugin) -> bool
container.count(IPlugin) -> int
```

### Type Annotations

```python
# Single injection (requires unambiguous or named)
db: Inject[IDatabase]
primary: Inject[IDatabase, Named("primary")]

# Collection injection
plugins: InjectAll[IPlugin]
```

---

## Backwards Compatibility

| Pattern | Before | After |
|---------|--------|-------|
| Single registration | ✅ Works | ✅ Works |
| Multiple registrations | Overwrites | **Accumulates** |
| `get()` with one impl | Returns it | Returns it |
| `get()` with multiple | Returns last | **Raises error** |
| `get_all()` | N/A | Returns all |

**This is a breaking change** for code that intentionally or accidentally registers the same interface multiple times and expects overwrite behavior.

---

## Success Criteria

1. ✅ Multiple registrations accumulate
2. ✅ `get()` raises `AmbiguousDependencyError` when ambiguous
3. ✅ `get_all()` returns all implementations
4. ✅ `InjectAll[T]` works for property/constructor injection
5. ✅ Integrates with named bindings feature
6. ✅ Documentation covers migration
