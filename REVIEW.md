# Code Review: Named Dependencies Feature (Round 3 - Multi-Persona)

**Branch:** `claude/implement-named-dependencies-BOhgM`
**Commit:** `320d7f8`
**Test Status:** 157 passed, 2 skipped

---

## Overview

This PR implements **named dependencies** (qualifiers) to support registering and resolving multiple implementations of the same interface.

---

## BLOCKING ISSUES

### 1. `_detect_cycles()` Skips Named Bindings

**Severity:** High | **Persona:** Maintainer

In `container.py` line 1082:
```python
if binding.implementation is not None and isinstance(key, type):
```

When key is `(IDatabase, "special")`, `isinstance(key, type)` is `False`, so named bindings are **excluded from cycle detection**.

```python
container.validate()  # PASSES - misses cycle!
container.get(ServiceA)  # Raises CircularDependencyError
```

---

### 2. `run()` and `run_async()` Don't Support Named Dependencies

**Severity:** High | **Persona:** User

The `run()` method doesn't handle `Inject[T, Named(...)]`:

```python
container.register(IDatabase, PostgresDB, name='primary')

def my_func(db: Inject[IDatabase, Named('primary')]) -> str:
    return db.query('SELECT 1')

container.run(my_func)  # FAILS: Cannot resolve parameter 'db'
```

**Root cause:** `run()` uses `get_type_hints(func)` without `include_extras=True` and doesn't call `extract_inject_info()`.

**Location:** `container.py` lines 678-710 (`run`) and 723-790 (`run_async`)

---

## MEDIUM ISSUES

### 3. `ModuleBuilder` Missing `export_named()`

**Severity:** Medium | **Persona:** API Designer

`Module` has `export_named()` but `ModuleBuilder` doesn't:

```python
module = Module("test")
module.export_named(IDatabase, "primary")  # Works

builder = ModuleBuilder("test")
builder.export_named  # AttributeError!
```

**Impact:** API inconsistency. Users of `ModuleBuilder` can't export named deps.

---

### 4. Thread/Async Safety (Pre-existing)

**Severity:** Medium | **Persona:** Performance Engineer

The `_resolution_stack` is instance-level, not thread-local or contextvars-based:

```python
# Concurrent access causes false circular dependency errors
threads = [threading.Thread(target=lambda: container.get(SlowService)) for _ in range(5)]
# -> Raises CircularDependencyError falsely
```

Same issue with async:
```python
await asyncio.gather(*[container.get_async(SlowService) for _ in range(5)])
# -> Raises CircularDependencyError falsely
```

**Note:** This is pre-existing, not introduced by this PR, but named dependencies don't fix it either.

---

## Issues Addressed Since Round 1

| Issue | Status |
|-------|--------|
| `has()` doesn't check modules for named deps | **Fixed** |
| Validation ignores named deps in constructors | **Partial** (cycle detection broken) |
| `export()` doesn't support named deps | **Fixed** |
| `Named("")` accepted | **Fixed** |
| `get_type_from_key` error handling | **Fixed** |

---

## Strengths

1. **Clean API** - Intuitive patterns consistent with other DI frameworks
2. **Type Integration** - `Inject[T, Named("...")]` is elegant
3. **Runtime Detection Works** - `get()` correctly catches cycles
4. **Backward Compatible** - Existing code unchanged
5. **Mixed Named/Unnamed** - Same type with different names works correctly

---

## Minor Issues (Non-blocking)

1. Mypy plugin has no tests
2. Docstring on `_InjectAliasType` not on `Inject`
3. Injectable signature loses qualifier info
4. Duplicate named registration silently overwrites (expected but undocumented)

---

## Summary

| Category | Count |
|----------|-------|
| Blocking Issues | **2** |
| Medium Issues | **2** |
| Low Issues | 4 |
| Tests Passing | 157 |

---

## Verdict

**NOT ready to merge.**

### Required Before Merge

1. Fix `_detect_cycles()` to include named bindings
2. Fix `run()` and `run_async()` to use `extract_inject_info()`
3. Add `export_named()` to `ModuleBuilder`
4. Add tests:
   - `validate()` detects cycles with named deps
   - `run()` works with `Inject[T, Named(...)]`

### Follow-up PRs

1. Thread/async safety for `_resolution_stack` (use `contextvars`)
2. Mypy plugin tests
3. Document that duplicate registration overwrites
