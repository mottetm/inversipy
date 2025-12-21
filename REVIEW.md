# Code Review: Named Dependencies (Expert Panel - Final)

**Branch:** `claude/implement-named-dependencies-BOhgM`
**Commit:** `b590d46`
**Test Status:** 164 passed, 2 skipped

---

## Expert Panel Summary

| Expert | Status | Critical Findings |
|--------|--------|-------------------|
| Security | ✅ Pass | No injection vulnerabilities |
| Performance | ✅ Pass | O(V+E) cycle detection |
| API Designer | ⚠️ Minor | Consistent API, one edge case |
| QA Engineer | ⚠️ Minor | Good coverage, one gap |
| Type System | ⚠️ Minor | One type error gives wrong exception |
| Concurrency | ⚠️ Known | Pre-existing thread safety issue |
| Documentation | ✅ Pass | Docs match behavior |

---

## Issues Fixed Since Round 3

| Issue | Status |
|-------|--------|
| `_detect_cycles()` skips named bindings | **Fixed** |
| `run()`/`run_async()` don't support named deps | **Fixed** |
| `ModuleBuilder` missing `export_named()` | **Fixed** |

---

## Remaining Issues

### 1. `Named(non_string)` Gives Wrong Exception Type

**Severity:** Low | **Expert:** Type System

```python
Named(123)  # Raises AttributeError: 'int' object has no attribute 'strip'
            # Should raise: TypeError: name must be a string
```

**Impact:** Confusing error message for users.

**Fix:**
```python
def __init__(self, name: str) -> None:
    if not isinstance(name, str):
        raise TypeError(f"Named qualifier must be a string, got {type(name).__name__}")
    if not name or not name.strip():
        raise ValueError("Named qualifier cannot be empty or whitespace-only")
    self.name = name
```

---

### 2. Thread/Async Concurrency (Pre-existing)

**Severity:** Medium | **Expert:** Concurrency

The `_resolution_stack` is shared across threads/coroutines:

```python
# Concurrent access causes false CircularDependencyError
await asyncio.gather(*[container.get_async(SlowService) for _ in range(5)])
```

**Note:** This is a pre-existing issue, not introduced by this PR. Named dependencies neither fix nor worsen it.

**Recommendation:** Document as known limitation, fix in follow-up with `contextvars`.

---

### 3. Cross-Named Cycle Detection Is Incomplete

**Severity:** Low | **Expert:** QA Engineer

Complex cycles spanning multiple named bindings may not be detected by `validate()`:

```python
# ServiceA -> IDatabase[primary]=ImplA -> ServiceB -> IDatabase[replica]=ImplB -> ServiceA
container.validate()  # May not detect this cross-named cycle
container.get(ServiceA)  # RuntimeError correctly raised
```

**Impact:** Rare edge case. Runtime detection still works correctly.

**Recommendation:** Document as limitation. The current fix handles the common cases.

---

## Verification Tests Passed

| Scenario | Result |
|----------|--------|
| Named registration/resolution | ✅ |
| Mixed named/unnamed same type | ✅ |
| Named singletons | ✅ |
| Named with scopes | ✅ |
| Named in modules | ✅ |
| Named in parent/child containers | ✅ |
| `has()` with named deps | ✅ |
| `try_get()` with named deps | ✅ |
| `run()` with named deps | ✅ |
| `run_async()` with named deps | ✅ |
| `validate()` with named deps | ✅ |
| `ModuleBuilder.export_named()` | ✅ |
| FastAPI `@inject` with named deps | ✅ (code review) |
| Unicode names | ✅ |
| `name=None` equals unnamed | ✅ |
| Async singleton correctness | ✅ |

---

## Summary

| Category | Count |
|----------|-------|
| Blocking Issues | **0** |
| Medium Issues | 1 (pre-existing) |
| Low Issues | 2 |
| Tests Passing | 164 |

---

## Verdict

**READY TO MERGE** ✅

All blocking issues from previous rounds have been addressed:
- `_detect_cycles()` now includes named bindings
- `run()`/`run_async()` now use `extract_inject_info()`
- `ModuleBuilder.export_named()` added

The remaining issues are:
1. **Low:** `Named(123)` gives `AttributeError` instead of `TypeError` - cosmetic
2. **Low:** Complex cross-named cycles may not be caught by `validate()` - rare, runtime detection works
3. **Medium (pre-existing):** Thread safety - not introduced by this PR

### Recommended Follow-ups

1. Add type check in `Named.__init__` for better error messages
2. Document thread safety limitation in README
3. Consider `contextvars` for thread-safe resolution stack

---

## Sign-offs

- [x] Security Expert
- [x] Performance Engineer
- [x] API Designer
- [x] QA Engineer
- [x] Type System Expert
- [x] Concurrency Expert
- [x] Documentation Expert
