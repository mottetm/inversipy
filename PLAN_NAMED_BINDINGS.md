# Implementation Plan: Named Bindings / Qualifiers

## Overview

This plan describes how to implement **named bindings** (also known as qualifiers) in inversipy, enabling multiple implementations of the same interface to coexist in a container.

## Problem Statement

Currently, only one implementation can be registered per type:
```python
container.register(IDatabase, PostgresDB)
container.register(IDatabase, MySQLDB)  # Overwrites PostgresDB!
```

This limitation prevents common patterns like:
- Primary/replica database connections
- Different implementations for different environments
- Multiple instances of the same service with different configurations

## Design Goals

1. **Backwards compatible** - All existing code must continue to work
2. **Type-safe** - IDE/mypy support for named injections
3. **Ergonomic API** - Simple to use for common cases
4. **Consistent** - Follow existing patterns in the codebase

---

## Implementation Plan

### Phase 1: Core Infrastructure

#### 1.1 Update DependencyKey Type (`types.py`)

**Current:**
```python
DependencyKey = type | str
```

**New:**
```python
# A binding key uniquely identifies a dependency
# Can be: type alone, string name, or (type, name) tuple for named bindings
type BindingKey = type | str | tuple[type, str]

# Alias for backwards compatibility
DependencyKey = BindingKey
```

**Rationale:** Using `(type, name)` tuples as keys allows direct dictionary lookup without additional data structures. The existing `type | str` cases remain valid.

#### 1.2 Add Named Type Helper (`types.py`)

```python
def named(interface: type[T], name: str) -> tuple[type[T], str]:
    """Create a named binding key.

    Args:
        interface: The interface type
        name: The qualifier name

    Returns:
        A tuple key for named binding lookup

    Example:
        container.register(named(IDatabase, "primary"), PostgresDB)
        db = container.get(named(IDatabase, "primary"))
    """
    return (interface, name)
```

---

### Phase 2: Container Updates

#### 2.1 Update Registration Methods (`container.py`)

**Update `register()` signature:**
```python
def register[T](
    self,
    interface: type[T],
    implementation: type[T] | None = None,
    factory: Factory[T] | None = None,
    scope: Scopes = Scopes.TRANSIENT,
    instance: T | None = None,
    name: str | None = None,  # NEW PARAMETER
) -> "Container":
```

**Implementation changes:**
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
    # Determine the binding key
    key: BindingKey = (interface, name) if name else interface

    # If no implementation or factory provided, use interface as implementation
    if implementation is None and factory is None and instance is None:
        implementation = interface

    binding = Binding(
        key=key,
        factory=factory,
        implementation=implementation,
        scope=scope,
        instance=instance,
    )
    self._bindings[key] = binding
    return self
```

#### 2.2 Update Resolution Methods (`container.py`)

**Update `get()` signature:**
```python
def get[T](self, interface: type[T], name: str | None = None) -> T:
```

**Implementation changes:**
```python
def get[T](self, interface: type[T], name: str | None = None) -> T:
    # Determine the binding key
    key: BindingKey = (interface, name) if name else interface

    # Check for circular dependencies
    if key in self._resolution_stack:
        self._resolution_stack.append(key)
        raise CircularDependencyError(self._resolution_stack[:])

    # Try to find binding in this container
    binding = self._bindings.get(key)

    # ... rest of resolution logic
```

**Also update:**
- `get_async()` - Add `name` parameter
- `try_get()` - Add `name` parameter
- `has()` - Add `name` parameter

#### 2.3 Update Convenience Methods

```python
def register_factory[T](
    self,
    interface: type[T],
    factory: Factory[T],
    scope: Scopes = Scopes.TRANSIENT,
    name: str | None = None,  # NEW
) -> "Container":
    return self.register(interface, factory=factory, scope=scope, name=name)

def register_instance[T](
    self,
    interface: type[T],
    instance: T,
    name: str | None = None,  # NEW
) -> "Container":
    return self.register(interface, instance=instance, scope=Scopes.SINGLETON, name=name)
```

---

### Phase 3: Dependency Resolution with Names

#### 3.1 Update `_create_instance` Methods (`container.py`)

The core challenge is resolving named dependencies in constructors. We need to:
1. Detect which parameters need named resolution
2. Extract the name from type annotations

**Add Named marker class (`decorators.py`):**
```python
class Named:
    """Marker for named dependency injection.

    Use with Annotated to specify a named dependency:
        database: Annotated[IDatabase, Named("primary")]
    """
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"Named({self.name!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Named) and other.name == self.name

    def __hash__(self) -> int:
        return hash(self.name)
```

**Update `_create_instance()` to handle Named annotations:**
```python
def _create_instance[T](self, cls: type[T]) -> T:
    # ... existing code to get type_hints and sig ...

    kwargs: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        # ... skip *args/**kwargs ...

        param_type = type_hints.get(param_name)

        if param_type is not None:
            # Extract name from Annotated[Type, Named("name")] if present
            dependency_name = self._extract_named_qualifier(param_type)
            actual_type = self._extract_actual_type(param_type)

            try:
                kwargs[param_name] = self.get(actual_type, name=dependency_name)
            except DependencyNotFoundError:
                # ... existing default value handling ...
```

**Helper methods:**
```python
def _extract_named_qualifier(self, type_hint: Any) -> str | None:
    """Extract Named qualifier from an Annotated type hint."""
    from typing import get_origin, get_args, Annotated

    if get_origin(type_hint) is Annotated:
        args = get_args(type_hint)
        for arg in args[1:]:  # Skip the actual type
            if isinstance(arg, Named):
                return arg.name
    return None

def _extract_actual_type(self, type_hint: Any) -> type:
    """Extract the actual type from an Annotated type hint."""
    from typing import get_origin, get_args, Annotated

    if get_origin(type_hint) is Annotated:
        return get_args(type_hint)[0]
    return type_hint
```

---

### Phase 4: Injectable and Inject Updates

#### 4.1 Update Inject Type Alias (`decorators.py`)

**Add Named-aware Inject variant:**
```python
# Base Inject type alias (unchanged)
type Inject[T] = Annotated[T, _inject_marker]

# Named Inject type alias
type InjectNamed[T, N: str] = Annotated[T, _inject_marker, Named(N)]  # Won't work directly

# Alternative: Use a function to create the annotated type
def inject_named(type_: type[T], name: str) -> type[Annotated[T, ...]]:
    """Create a named injection type annotation.

    Example:
        class Service(Injectable):
            primary_db: inject_named(IDatabase, "primary")
            backup_db: inject_named(IDatabase, "backup")
    """
    return Annotated[type_, _inject_marker, Named(name)]
```

**Note:** Due to Python's type system limitations with literal strings in generics, we'll use a helper function approach.

#### 4.2 Update Injectable Base Class (`decorators.py`)

Update `__init_subclass__` to handle Named qualifiers:

```python
def __init_subclass__(cls, **kwargs: Any) -> None:
    super().__init_subclass__(**kwargs)

    inject_fields: dict[str, tuple[type[Any], str | None]] = {}  # (type, name)

    # ... get annotations ...

    for attr_name, annotation in annotations.items():
        origin = get_origin(annotation)

        if origin is Annotated:
            args = get_args(annotation)
            actual_type = args[0]
            metadata = args[1:]

            has_inject = False
            named_qualifier: str | None = None

            for meta in metadata:
                if isinstance(meta, _InjectMarker):
                    has_inject = True
                elif isinstance(meta, Named):
                    named_qualifier = meta.name

            if has_inject:
                inject_fields[attr_name] = (actual_type, named_qualifier)

    # ... generate __init__ with named resolution ...
```

---

### Phase 5: Module Updates

#### 5.1 Update Module Class (`module.py`)

Add `name` parameter to all registration methods:

```python
def register[T](
    self,
    interface: type[T],
    implementation: type[T] | None = None,
    factory: Factory[T] | None = None,
    scope: Scopes = Scopes.TRANSIENT,
    instance: T | None = None,
    public: bool = False,
    name: str | None = None,  # NEW
) -> "Module":
    # Use Container's register
    super().register(
        interface=interface,
        implementation=implementation,
        factory=factory,
        scope=scope,
        instance=instance,
        name=name,  # Pass through
    )

    # Track public/private with named key
    key = (interface, name) if name else interface
    if public:
        self._public_keys.add(key)

    return self
```

#### 5.2 Update ModuleBuilder (`module.py`)

Add `name` parameter to builder methods:
```python
def bind[T](
    self,
    interface: type[T],
    implementation: type[T] | None = None,
    factory: Factory[T] | None = None,
    scope: Scopes = Scopes.TRANSIENT,
    instance: T | None = None,
    name: str | None = None,  # NEW
) -> "ModuleBuilder":
```

---

### Phase 6: Validation Updates

#### 6.1 Update Cycle Detection (`container.py`)

Update `_detect_cycles()` to handle named bindings in the dependency graph.

#### 6.2 Update Validation (`container.py`)

Update `validate()` to check named dependencies are registered.

---

### Phase 7: FastAPI Integration

#### 7.1 Update `@inject` Decorator (`fastapi.py`)

The decorator should respect Named annotations in route parameters:

```python
# In inject decorator
for param_name, param in sig.parameters.items():
    param_type = type_hints.get(param_name)
    if param_type is not None:
        named_qualifier = extract_named_qualifier(param_type)
        actual_type = extract_actual_type(param_type)

        if container.has(actual_type, name=named_qualifier):
            # Inject this parameter
            resolved = container.get(actual_type, name=named_qualifier)
```

---

### Phase 8: Documentation & Examples

#### 8.1 Update README.md

Add section on named bindings with examples:
- Basic named binding registration
- Constructor injection with Named
- Injectable with named dependencies
- Use cases (primary/replica, env-specific)

#### 8.2 Add Named Bindings Example

Create `examples/named_bindings_example.py`:
```python
"""Example demonstrating named bindings for multiple implementations."""

from typing import Annotated
from inversipy import Container, Injectable, Inject, Named, Scopes

class IDatabase:
    def query(self, sql: str) -> list: ...

class PostgresDB(IDatabase):
    def __init__(self, connection_string: str):
        self.conn = connection_string
    def query(self, sql: str) -> list:
        return [f"postgres: {sql}"]

class UserService(Injectable):
    primary_db: Annotated[IDatabase, Inject, Named("primary")]
    replica_db: Annotated[IDatabase, Inject, Named("replica")]

    def get_user(self, id: int):
        return self.primary_db.query(f"SELECT * FROM users WHERE id={id}")

    def get_users_readonly(self):
        return self.replica_db.query("SELECT * FROM users")

# Registration
container = Container()
container.register_instance(
    IDatabase,
    PostgresDB("postgres://primary:5432"),
    name="primary"
)
container.register_instance(
    IDatabase,
    PostgresDB("postgres://replica:5432"),
    name="replica"
)
container.register(UserService)

service = container.get(UserService)
```

---

## File Changes Summary

| File | Changes |
|------|---------|
| `types.py` | Add `BindingKey` type, `named()` helper function |
| `decorators.py` | Add `Named` class, update `Injectable` for named resolution |
| `container.py` | Add `name` param to register/get methods, update resolution logic |
| `module.py` | Add `name` param to Module and ModuleBuilder methods |
| `fastapi.py` | Update `@inject` to handle Named annotations |
| `exceptions.py` | Update `DependencyNotFoundError` to include name |
| `__init__.py` | Export `Named`, `named` |
| `README.md` | Add named bindings documentation |
| `examples/named_bindings_example.py` | New example file |

---

## Test Plan

### New Test File: `tests/test_named_bindings.py`

1. **Basic Named Registration**
   - Register same interface with different names
   - Verify correct instance returned for each name
   - Verify unnamed and named don't conflict

2. **Named Resolution**
   - Constructor injection with Named annotation
   - Factory with named dependencies
   - Injectable with named properties

3. **Named with Scopes**
   - Singleton scope respects names separately
   - Request scope respects names separately
   - Transient creates new instances per name

4. **Named in Modules**
   - Public/private with named bindings
   - Export named bindings
   - Module composition with named

5. **Validation**
   - Missing named dependency detected
   - Cycle detection with named bindings

6. **Error Cases**
   - Named dependency not found - clear error message
   - Name without registration

7. **FastAPI Integration**
   - Route with named dependencies
   - Mixed named and unnamed parameters

---

## Implementation Order

1. **Phase 1: Core Infrastructure** (types.py)
   - Low risk, foundation for everything else

2. **Phase 2: Container Updates** (container.py)
   - Core functionality, enables testing

3. **Phase 3: Dependency Resolution** (container.py)
   - Named annotation handling

4. **Phase 4: Injectable Updates** (decorators.py)
   - Property injection support

5. **Phase 5: Module Updates** (module.py)
   - Extend to module system

6. **Phase 6: Validation Updates** (container.py)
   - Ensure correctness

7. **Phase 7: FastAPI Integration** (fastapi.py)
   - Web framework support

8. **Phase 8: Documentation** (README.md, examples/)
   - User-facing docs

---

## API Usage Examples

### Registration
```python
# Named registration
container.register(IDatabase, PostgresDB, name="primary")
container.register(IDatabase, MySQLDB, name="backup")

# Helper function
container.register(named(IDatabase, "primary"), PostgresDB)

# Named factory
container.register_factory(IDatabase, create_primary_db, name="primary")

# Named instance
container.register_instance(IDatabase, my_db, name="primary")
```

### Resolution
```python
# Direct resolution
primary = container.get(IDatabase, name="primary")
backup = container.get(IDatabase, name="backup")

# Helper function
primary = container.get(named(IDatabase, "primary"))
```

### Constructor Injection
```python
class Service:
    def __init__(
        self,
        primary_db: Annotated[IDatabase, Named("primary")],
        backup_db: Annotated[IDatabase, Named("backup")],
    ):
        self.primary = primary_db
        self.backup = backup_db
```

### Injectable
```python
class Service(Injectable):
    primary_db: Annotated[IDatabase, Inject, Named("primary")]
    backup_db: Annotated[IDatabase, Inject, Named("backup")]
```

---

## Backwards Compatibility

All existing code continues to work:
- `container.register(IFoo, Foo)` - Works (name=None internally)
- `container.get(IFoo)` - Works (name=None internally)
- `Inject[T]` - Works (no Named qualifier)
- Unnamed bindings don't conflict with named ones

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Performance impact from tuple keys | Tuples are hashable and fast; profile if concerns |
| Type system complexity | Keep simple; helper functions hide complexity |
| Breaking changes | Thorough testing; all new params have defaults |
| Confusion with string DependencyKey | Document clearly; prefer `named()` helper |

---

## Open Questions

1. **Should `name` be allowed without a type?**
   - Current: `DependencyKey = type | str` allows string-only keys
   - Named bindings would use `(type, str)` tuples
   - Could allow `container.get("my-service")` string lookup separately

2. **Should we support qualifier classes beyond strings?**
   - e.g., `@Primary`, `@Replica` marker classes
   - Decision: Start with strings, add markers later if needed

3. **Default name behavior?**
   - Should `get(IDatabase)` fall back to any named binding if no unnamed exists?
   - Decision: No fallback - explicit is better than implicit

---

## Success Criteria

1. All existing tests pass
2. New named bindings tests pass
3. Documentation is clear and complete
4. API is consistent with existing patterns
5. Type checker (mypy) passes
6. Performance is not significantly impacted
