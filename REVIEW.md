# Code Review: Named Dependencies Feature (Round 2)

**Branch:** `claude/implement-named-dependencies-BOhgM`
**Commit:** `320d7f8`
**Test Status:** 157 passed, 2 skipped

---

## Overview

This PR implements **named dependencies** (qualifiers) to support registering and resolving multiple implementations of the same interface. This is a common DI pattern for scenarios like primary/replica databases, different cache implementations, etc.

---

## Issues Addressed Since Last Review

| Issue | Status | How Fixed |
|-------|--------|-----------|
| `has()` doesn't check modules for named deps | **Fixed** | Now passes `name` to `module.has()` |
| Validation ignores named deps in constructors | **Partial** | Uses `extract_inject_info()` but cycle detection broken |
| `export()` doesn't support named deps | **Fixed** | Added `export_named(interface, name)` method |
| No circular dep tests with named bindings | **Partial** | Tests runtime detection, not `validate()` |
| `Named("")` accepted (no validation) | **Fixed** | Raises `ValueError` for empty/whitespace |
| `get_type_from_key` lost error handling | **Fixed** | Restored `ValueError` for invalid keys |

---

## NEW BLOCKING ISSUE

### `_detect_cycles()` Skips Named Bindings Entirely

**Severity:** High

In `container.py` line 1082:
```python
if binding.implementation is not None and isinstance(key, type):
    deps = self._get_implementation_dependencies(binding.implementation)
```

When the key is a tuple like `(IDatabase, "special")`, `isinstance(key, type)` returns `False`, so **named bindings are completely excluded from cycle detection**.

**Proof:**
```python
class ServiceA:
    def __init__(self, b: Inject[IDatabase, Named("special")]): ...

class ServiceB(IDatabase):
    def __init__(self, a: ServiceA): ...

container.register(ServiceA)
container.register(IDatabase, ServiceB, name="special")
container.register(ServiceB)

container.validate()  # PASSES - does not detect cycle!
container.get(ServiceA)  # Raises CircularDependencyError
```

**Impact:** Users relying on `validate()` to catch cycles before runtime will get false confidence. The cycle only manifests when `get()` is called.

**Fix:** Update `_detect_cycles()` to handle tuple keys:
```python
if binding.implementation is not None:
    # Extract type from key (handles both type and (type, name) tuple)
    key_type = get_type_from_key(key) if isinstance(key, tuple) else key
    if isinstance(key_type, type):
        deps = self._get_implementation_dependencies(binding.implementation)
        ...
```

---

## Strengths

### 1. Clean API Design

The API follows intuitive patterns consistent with other DI frameworks.

### 2. Excellent Type Annotation Integration

The `Inject[T, Named("...")]` syntax is elegant.

### 3. Runtime Circular Dependency Detection Works

The runtime detection via `get()` correctly catches cycles - only `validate()` is broken.

### 4. Backward Compatibility

Fully backward compatible with existing code.

---

## Remaining Minor Issues

### 1. Mypy Plugin Has No Tests

**Severity:** Low

### 2. Docstring Placement

**Severity:** Low

### 3. Injectable Signature Loses Qualifier Info

**Severity:** Low

---

## Summary

| Category | Count |
|----------|-------|
| Blocking Issues | **1** |
| Non-blocking Issues | 3 (all Low severity) |
| Tests Added | 8 new tests |
| Total Test Coverage | 157 tests passing |

---

## Verdict

**NOT ready to merge.**

The `_detect_cycles()` method completely ignores named bindings, making `validate()` unreliable for detecting circular dependencies when named dependencies are involved. The test `test_circular_dependency_with_named_bindings` only tests runtime detection, masking this bug.

### Required Before Merge

1. Fix `_detect_cycles()` to include named bindings in the dependency graph
2. Add test that `validate()` (not just `get()`) detects cycles with named deps

### Follow-up PRs (Non-blocking)

1. Mypy plugin tests
2. Docstring placement
3. Injectable signature info
