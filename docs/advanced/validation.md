# Validation

Validate that all dependencies can be resolved before runtime.

## Usage

```python
from inversipy import Container, ValidationError

container = Container()
container.register(ServiceA)
container.register(ServiceB)  # Depends on ServiceA
container.register(ServiceC)  # Depends on ServiceX (not registered)

try:
    container.validate()
except ValidationError as e:
    print(f"Validation failed with {len(e.errors)} errors:")
    for error in e.errors:
        print(f"  - {error}")
```

## What's Checked

- **Circular dependencies** - detected via depth-first search on the dependency graph
- **Missing dependencies** - every registered type must have all required parameters resolvable
- **Ambiguous dependencies** - multiple implementations without named disambiguation

All errors are collected and reported at once, so you can fix them in a single pass.

!!! tip
    Call `container.validate()` at application startup to catch configuration errors early.
