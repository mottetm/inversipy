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

## Final Syntax Design

After extensive exploration, we settled on this syntax:

```python
# Type alias with variadic markers
type Inject[T, *ExtraMarkers] = Annotated[T, InjectMarker, *ExtraMarkers]

# Usage
class MyService:
    # Unnamed - clean syntax (most common case)
    db: Inject[IDatabase]
    logger: Inject[Logger]

    # Named - add Named("qualifier") marker
    primary_db: Inject[IDatabase, Named("primary")]
    replica_db: Inject[IDatabase, Named("replica")]
```

### Type Checker Support

| Type Checker | Support | Solution |
|--------------|---------|----------|
| **mypy** | ✅ Full (with plugin) | Ship `inversipy.mypy_plugin` |
| **pyright** | ⚠️ Partial | Use `# pyright: ignore` or explicit `Annotated` |

**Mypy limitation:** mypy validates type arguments before expanding type aliases, rejecting `Named("x")` as a call expression. A simple plugin (~20 lines) resolves this.

**Pyright limitation:** No plugin system. Users can:
1. Use `# pyright: ignore` on named binding lines
2. Use explicit `Annotated[T, Inject, Named("x")]` syntax
3. Wait for upstream support

---

## Implementation Plan

### Phase 1: Core Types (`types.py`)

#### 1.1 Update DependencyKey Type

```python
# A binding key uniquely identifies a dependency
# Can be: type alone, string name, or (type, name) tuple for named bindings
type BindingKey = type | str | tuple[type, str]

# Alias for backwards compatibility
DependencyKey = BindingKey
```

#### 1.2 Add Named Marker Class

```python
class Named:
    """Qualifier for named dependency injection.

    Usage in type annotations:
        primary_db: Inject[IDatabase, Named("primary")]

    Usage in registration:
        container.register(IDatabase, PostgresDB, name="primary")
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f'Named("{self.name}")'

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Named) and other.name == self.name

    def __hash__(self) -> int:
        return hash(("Named", self.name))
```

---

### Phase 2: Update Inject Type Alias (`decorators.py`)

#### 2.1 Replace Current Inject Definition

**Current:**
```python
type Inject[T] = Annotated[T, _inject_marker]
```

**New:**
```python
class InjectMarker:
    """Internal marker for dependency injection."""
    pass

_inject_marker = InjectMarker()

type Inject[T, *ExtraMarkers] = Annotated[T, _inject_marker, *ExtraMarkers]
```

This allows:
- `Inject[IDatabase]` → `Annotated[IDatabase, _inject_marker]`
- `Inject[IDatabase, Named("primary")]` → `Annotated[IDatabase, _inject_marker, Named("primary")]`

#### 2.2 Update Injectable Base Class

Update `__init_subclass__` to extract Named qualifiers:

```python
def __init_subclass__(cls, **kwargs: Any) -> None:
    super().__init_subclass__(**kwargs)

    # Now stores (type, name) tuples
    inject_fields: dict[str, tuple[type[Any], str | None]] = {}

    annotations = get_type_hints(cls, include_extras=True)

    for attr_name, annotation in annotations.items():
        origin = get_origin(annotation)

        if origin is Annotated:
            args = get_args(annotation)
            actual_type = args[0]
            metadata = args[1:]

            has_inject = False
            named_qualifier: str | None = None

            for meta in metadata:
                if isinstance(meta, InjectMarker):
                    has_inject = True
                elif isinstance(meta, Named):
                    named_qualifier = meta.name

            if has_inject:
                inject_fields[attr_name] = (actual_type, named_qualifier)

    # Store for container resolution
    setattr(cls, "_inject_fields", inject_fields)

    # Generate __init__ (updated to pass name info)
    # ... rest of __init__ generation ...
```

---

### Phase 3: Container Updates (`container.py`)

#### 3.1 Update Registration Methods

```python
def register[T](
    self,
    interface: type[T],
    implementation: type[T] | None = None,
    factory: Factory[T] | None = None,
    scope: Scopes = Scopes.TRANSIENT,
    instance: T | None = None,
    name: str | None = None,  # NEW
) -> "Container":
    """Register a dependency, optionally with a name qualifier."""
    key: BindingKey = (interface, name) if name else interface

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

#### 3.2 Update Resolution Methods

```python
def get[T](self, interface: type[T], name: str | None = None) -> T:
    """Resolve a dependency, optionally by name."""
    key: BindingKey = (interface, name) if name else interface

    # Check for circular dependencies
    if key in self._resolution_stack:
        self._resolution_stack.append(key)
        raise CircularDependencyError(self._resolution_stack[:])

    binding = self._bindings.get(key)
    # ... rest of resolution ...
```

**Also update:**
- `get_async()` - Add `name` parameter
- `try_get()` - Add `name` parameter
- `has()` - Add `name` parameter

#### 3.3 Update Instance Creation

Add helper to extract Named qualifier from type hints:

```python
def _extract_inject_info(self, type_hint: Any) -> tuple[type, str | None] | None:
    """Extract type and optional name from Inject annotation."""
    origin = get_origin(type_hint)

    if origin is not Annotated:
        return None

    args = get_args(type_hint)
    actual_type = args[0]

    has_inject = False
    name: str | None = None

    for arg in args[1:]:
        if isinstance(arg, InjectMarker):
            has_inject = True
        elif isinstance(arg, Named):
            name = arg.name

    if has_inject:
        return (actual_type, name)
    return None
```

Update `_create_instance()` to use named resolution:

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

        # Check for Inject annotation with optional Named
        inject_info = self._extract_inject_info(param_type)
        if inject_info:
            actual_type, dep_name = inject_info
            try:
                kwargs[param_name] = self.get(actual_type, name=dep_name)
            except DependencyNotFoundError:
                if param.default is inspect.Parameter.empty:
                    raise
        else:
            # Regular type hint resolution (existing behavior)
            try:
                kwargs[param_name] = self.get(param_type)
            except DependencyNotFoundError:
                if param.default is inspect.Parameter.empty:
                    raise

    return cls(**kwargs)
```

---

### Phase 4: Mypy Plugin (`mypy_plugin.py`)

```python
"""Mypy plugin for Inject[T, Named("x")] support."""
from mypy.plugin import Plugin, AnalyzeTypeContext
from mypy.types import Type


class InversipyPlugin(Plugin):
    """Plugin to support Inject[T, Named("x")] syntax."""

    def get_type_analyze_hook(self, fullname: str):
        if fullname == "inversipy.decorators.Inject" or fullname.endswith(".Inject"):
            return inject_type_callback
        return None


def inject_type_callback(ctx: AnalyzeTypeContext) -> Type:
    """Transform Inject[T, ...] to T for type checking.

    This allows mypy to understand that:
        db: Inject[IDatabase, Named("primary")]

    Should be treated as type IDatabase for attribute access.
    """
    args = ctx.type.args

    if not args:
        ctx.api.fail("Inject requires at least one type argument", ctx.context)
        return ctx.api.named_type("builtins.object", [])

    # Return the first type argument (T)
    # This makes self.db.query() work correctly
    return ctx.api.analyze_type(args[0])


def plugin(version: str):
    return InversipyPlugin
```

**Usage in `pyproject.toml` or `mypy.ini`:**
```ini
[mypy]
plugins = inversipy.mypy_plugin
```

---

### Phase 5: Module Updates (`module.py`)

Add `name` parameter to Module registration:

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
    super().register(
        interface=interface,
        implementation=implementation,
        factory=factory,
        scope=scope,
        instance=instance,
        name=name,
    )

    # Track visibility with named key
    key = (interface, name) if name else interface
    if public:
        self._public_keys.add(key)

    return self
```

Also update:
- `register_factory()` - Add `name` parameter
- `register_instance()` - Add `name` parameter
- `export()` - Support named keys
- `ModuleBuilder.bind()` / `bind_public()` - Add `name` parameter

---

### Phase 6: Validation Updates (`container.py`)

#### 6.1 Update Error Messages

```python
class DependencyNotFoundError(InversipyError):
    def __init__(
        self,
        dependency_type: type[Any],
        container_name: str = "container",
        name: str | None = None,  # NEW
    ) -> None:
        self.dependency_type = dependency_type
        self.container_name = container_name
        self.name = name

        if name:
            msg = f"Dependency '{dependency_type.__name__}' with name '{name}' not found in {container_name}"
        else:
            msg = f"Dependency '{dependency_type.__name__}' not found in {container_name}"
        super().__init__(msg)
```

#### 6.2 Update Cycle Detection

Update `_detect_cycles()` to handle `(type, name)` keys in the dependency graph.

#### 6.3 Update Validation

Update `validate()` to check named dependencies exist.

---

### Phase 7: FastAPI Integration (`fastapi.py`)

Update `@inject` decorator to extract Named qualifiers:

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

            # Check for Inject with optional Named
            inject_info = _extract_inject_info(param_type)
            if inject_info:
                actual_type, dep_name = inject_info
                if container.has(actual_type, name=dep_name):
                    kwargs[param_name] = await container.get_async(actual_type, name=dep_name)

        return await func(*args, **kwargs)

    return wrapper
```

---

### Phase 8: Documentation & Examples

#### 8.1 Update README.md

Add section on named bindings:

```markdown
## Named Bindings

Register multiple implementations of the same interface using names:

### Registration

```python
container.register(IDatabase, PostgresDB, name="primary")
container.register(IDatabase, PostgresDB, name="replica")
```

### Resolution

```python
primary = container.get(IDatabase, name="primary")
replica = container.get(IDatabase, name="replica")
```

### Property Injection

```python
class UserService(Injectable):
    primary_db: Inject[IDatabase, Named("primary")]
    replica_db: Inject[IDatabase, Named("replica")]

    def get_user(self, id: int):
        return self.primary_db.query(f"SELECT * FROM users WHERE id = {id}")

    def list_users(self):
        # Use replica for read-only queries
        return self.replica_db.query("SELECT * FROM users")
```

### Type Checker Configuration

For mypy, add to your configuration:

```ini
[mypy]
plugins = inversipy.mypy_plugin
```

For pyright, named bindings require either:
- `# pyright: ignore` comments on named binding lines, or
- Explicit `Annotated` syntax: `Annotated[IDatabase, Inject, Named("primary")]`
```

#### 8.2 Add Example File

Create `examples/named_bindings_example.py` demonstrating:
- Primary/replica database pattern
- Environment-specific implementations
- Named singletons with different configurations

---

## File Changes Summary

| File | Changes |
|------|---------|
| `types.py` | Add `BindingKey` type, `Named` class |
| `decorators.py` | Update `Inject` type alias to variadic, update `Injectable` |
| `container.py` | Add `name` param to register/get, update resolution logic |
| `module.py` | Add `name` param to Module and ModuleBuilder |
| `fastapi.py` | Update `@inject` to handle Named |
| `exceptions.py` | Update errors to include name |
| `mypy_plugin.py` | **NEW** - Mypy plugin for Inject support |
| `__init__.py` | Export `Named` |
| `README.md` | Add named bindings docs |
| `examples/named_bindings_example.py` | **NEW** |

---

## Test Plan

### New Test File: `tests/test_named_bindings.py`

1. **Basic Registration & Resolution**
   - Register same interface with different names
   - Verify correct instance returned for each name
   - Verify unnamed and named don't conflict

2. **Inject Syntax**
   - `Inject[T]` works (backwards compat)
   - `Inject[T, Named("x")]` works
   - Runtime extraction of name

3. **Injectable Class**
   - Named properties resolved correctly
   - Mixed named and unnamed properties

4. **Scopes with Names**
   - Singleton scope respects names separately
   - Transient creates new instances per name
   - Request scope isolated per name

5. **Modules**
   - Public/private with named bindings
   - Export named bindings

6. **Validation**
   - Missing named dependency detected
   - Cycle detection with named bindings

7. **FastAPI**
   - Route with named dependencies

### Mypy Plugin Tests

Add tests to verify plugin works:
```python
# tests/test_mypy_plugin.py
def test_inject_type_checking():
    """Verify mypy accepts Inject[T, Named("x")] syntax."""
    # Run mypy on test file and verify no errors
```

---

## API Usage Examples

### Registration
```python
# Named registration
container.register(IDatabase, PostgresDB, name="primary")
container.register(IDatabase, MySQLDB, name="backup")

# Named factory
container.register_factory(ICache, create_redis_cache, name="session")

# Named instance
container.register_instance(Config, prod_config, name="prod")
```

### Resolution
```python
# By name
primary = container.get(IDatabase, name="primary")
backup = container.get(IDatabase, name="backup")
```

### Type Annotations
```python
# Simple (unchanged)
db: Inject[IDatabase]

# Named
primary: Inject[IDatabase, Named("primary")]
replica: Inject[IDatabase, Named("replica")]
```

### Injectable Class
```python
class OrderService(Injectable):
    primary_db: Inject[IDatabase, Named("primary")]
    replica_db: Inject[IDatabase, Named("replica")]
    cache: Inject[ICache]  # Unnamed still works
```

---

## Backwards Compatibility

All existing code continues to work unchanged:

| Pattern | Status |
|---------|--------|
| `container.register(IFoo, Foo)` | ✅ Works |
| `container.get(IFoo)` | ✅ Works |
| `Inject[T]` | ✅ Works |
| `Injectable` with `Inject[T]` | ✅ Works |

The `name` parameter defaults to `None`, and unnamed bindings use the type directly as the key (not a tuple).

---

## Success Criteria

1. ✅ All existing tests pass
2. ✅ New named bindings tests pass
3. ✅ `Inject[T, Named("x")]` syntax works at runtime
4. ✅ Mypy passes with plugin
5. ✅ Documentation is clear
6. ✅ Backwards compatible
