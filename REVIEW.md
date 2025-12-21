# Code Review: Named Dependencies Feature

**Branch:** `claude/implement-named-dependencies-BOhgM`
**Commit:** `134af40`
**Test Status:** 149 passed, 2 skipped

---

## Overview

This PR implements **named dependencies** (qualifiers) to support registering and resolving multiple implementations of the same interface. This is a common DI pattern for scenarios like primary/replica databases, different cache implementations, etc.

---

## Strengths

### 1. Clean API Design

The API follows intuitive patterns consistent with other DI frameworks:

```python
# Registration
container.register(IDatabase, PostgresDB, name="primary")
container.register(IDatabase, MySQLDB, name="replica")

# Resolution
primary = container.get(IDatabase, name="primary")
replica = container.get(IDatabase, name="replica")
```

### 2. Excellent Type Annotation Integration

The `Inject[T, Named("...")]` syntax is elegant and leverages Python's type system:

```python
class UserService(Injectable):
    primary_db: Inject[IDatabase, Named("primary")]
    replica_db: Inject[IDatabase, Named("replica")]
```

### 3. Comprehensive Test Coverage

The test suite (`test_named_bindings.py`, 539 lines) covers:
- Basic registration/resolution
- All registration methods (`register`, `register_factory`, `register_instance`)
- Scopes with named bindings
- `has()` and `try_get()` methods
- Injectable class integration
- Module integration
- Parent-child container hierarchy
- Async resolution
- Factory functions with named dependencies
- Error messages

### 4. Backward Compatibility

The implementation is fully backward compatible:
- Unnamed bindings continue to work unchanged
- Named and unnamed bindings coexist
- Existing code requires no changes

### 5. Code Consolidation

- `extract_inject_info()` is now a public helper reused across modules
- `make_key()` and `get_type_from_key()` centralized in `types.py`
- `_format_dependency()` helper for consistent error messages

---

## Issues

### 1. `has()` Method Inconsistency with Module Named Dependencies

**Severity:** High

In `container.py:611-615`:
```python
# Check registered modules (only for unnamed dependencies)
if name is None:
    for module in self._modules:
        if module.has(interface):
            return True
```

But `get()` now passes `name` to modules. This is inconsistent:
- `container.get(IDatabase, name="primary")` - Checks modules with name
- `container.has(IDatabase, name="primary")` - Skips modules entirely

**Impact:** `has()` returns `False` for named dependencies in modules even when `get()` would succeed.

**Recommendation:** Update `has()` to pass `name` to modules:
```python
for module in self._modules:
    if module.has(interface, name=name):
        return True
```

---

### 2. `Module.export()` Doesn't Support Named Dependencies

**Severity:** Medium

In `module.py:110-133`, the `export()` method only takes raw types:
```python
def export(self, *interfaces: type[Any]) -> "Module":
```

There's no way to export a named binding after registration:
```python
module.register(IDatabase, PostgresDB, name="primary", public=False)
module.export(IDatabase)  # Exports UNNAMED binding, not "primary"
```

**Recommendation:** Either:
1. Add `export_named(interface, name)` method, or
2. Accept tuples: `export((IDatabase, "primary"))`

---

### 3. Validation Doesn't Check Named Dependencies

**Severity:** High

The `_validate_sync()` and `_validate_async()` methods iterate over `self._bindings` but don't consider named dependencies when checking transitive dependencies.

For example:
```python
container.register(IService, MyService)  # MyService needs IDatabase[name="primary"]
container.register(IDatabase, PostgresDB, name="primary")
container.validate()  # Should pass but may not detect the named dependency
```

The validation logic doesn't use `extract_inject_info()` when inspecting constructor dependencies.

**Recommendation:** Update validation to parse `Inject[T, Named(...)]` annotations.

---

### 4. No Circular Dependency Tests with Named Bindings

**Severity:** Medium

The test suite doesn't verify circular dependency detection with named dependencies:
```python
class A:
    def __init__(self, b: Inject[B, Named("special")]): ...

class B:
    def __init__(self, a: Inject[A, Named("primary")]): ...
```

**Recommendation:** Add test cases for this scenario.

---

### 5. `Named` Accepts Invalid Strings

**Severity:** Low

```python
Named("")      # Empty string - likely a bug
Named("  ")    # Whitespace only - likely a bug
```

**Recommendation:** Add validation in `Named.__init__`:
```python
def __init__(self, name: str) -> None:
    if not name or not name.strip():
        raise ValueError("Named qualifier cannot be empty")
    self.name = name
```

---

### 6. Mypy Plugin Has No Tests

**Severity:** Medium

The `mypy_plugin.py` file is 94 lines with zero test coverage. The plugin could break silently with mypy updates.

**Recommendation:** Add integration tests that run mypy on sample code.

---

### 7. Docstring Placement Issue

**Severity:** Low

In `decorators.py:25-48`:
```python
_InjectAliasType = Inject  # type: ignore[type-arg]
"""Type alias for dependency injection..."""
```

The docstring attaches to `_InjectAliasType` (private), not `Inject`. `help(Inject)` won't show this documentation.

---

### 8. Injectable Signature Loses Qualifier Info

**Severity:** Low

The generated `__init__` signature shows `db: IDatabase` instead of `db: Inject[IDatabase, Named("primary")]`:

```python
param_types = [t for t, _ in inject_fields.values()]  # Drops Named qualifier
```

IDE tooling loses information about which named binding is expected.

---

### 9. `get_type_from_key` Lost Error Handling

**Severity:** Low

The function no longer validates input:
```python
def get_type_from_key(key: DependencyKey) -> type:
    if isinstance(key, tuple):
        return key[0]
    return key  # No validation if key is invalid
```

Previous version had `raise ValueError` fallback.

---

## Summary Table

| Issue | Severity | Category |
|-------|----------|----------|
| `has()` doesn't check modules for named deps | High | Bug |
| Validation ignores named deps in constructors | High | Bug |
| `export()` doesn't support named deps | Medium | Feature Gap |
| No circular dep tests with named bindings | Medium | Test Gap |
| Mypy plugin has no tests | Medium | Test Gap |
| `Named("")` accepted (no validation) | Low | Robustness |
| Docstring on wrong symbol | Low | Documentation |
| Injectable signature loses qualifier info | Low | DX |
| `get_type_from_key` lost error handling | Low | Robustness |

---

## Recommendations

### Before Merge (Blocking)

1. Fix `has()` to check modules with named dependencies
2. Update validation to understand `Inject[T, Named(...)]` annotations
3. Add circular dependency test with named bindings

### Follow-up PRs (Non-blocking)

1. Add `export()` support for named dependencies
2. Add mypy plugin tests
3. Validate `Named` constructor input
4. Improve docstring placement

---

## Verdict

The implementation is well-designed with clean APIs and comprehensive happy-path tests. The major architectural concerns from the initial review were addressed. However, there are consistency bugs (`has()` vs `get()`) and validation gaps that should be fixed before merging to prevent production surprises.
