# Inversipy Examples

This directory contains comprehensive examples demonstrating various features of the inversipy library.

## Available Examples

### 1. Basic Usage (`basic_usage.py`)

Demonstrates the fundamentals of inversipy:
- Creating a container
- Registering dependencies
- Automatic constructor injection
- Container validation
- Dependency resolution

**Run:**
```bash
python -m examples.basic_usage
```

### 2. Scopes (`scopes_example.py`)

Shows different dependency scopes:
- **Singleton**: One instance for the entire application
- **Transient**: New instance for each request
- **Request**: One instance per context (using contextvars)

**Run:**
```bash
python -m examples.scopes_example
```

### 3. Modules (`modules_example.py`)

Demonstrates the module system:
- Creating modules with public/private dependencies
- Using ModuleBuilder for fluent API
- Module composition
- Dynamic module updates

**Run:**
```bash
python -m examples.modules_example
```

### 4. Decorators (`decorators_example.py`)

Shows decorator-based registration and injection:
- `@singleton` and `@transient` decorators
- `@inject` decorator for functions
- `Injectable` base class for property injection
- `Annotated[Type, Inject]` for marking injectable properties

**Run:**
```bash
python -m examples.decorators_example
```

### 5. FastAPI Integration (`fastapi_example.py`)

Demonstrates FastAPI integration:
- Setting up container with FastAPI
- Using `@inject` in route handlers
- Request-scoped dependencies
- Dependency injection in async routes

**Requirements:**
```bash
pip install fastapi uvicorn
```

**Run:**
```bash
uvicorn examples.fastapi_example:app --reload
```

Then visit http://localhost:8000/docs for interactive API documentation.

## Running All Examples

You can run all examples at once:

```bash
python -m examples.basic_usage
python -m examples.scopes_example
python -m examples.modules_example
python -m examples.decorators_example
python -m examples.fastapi_example
```

## Testing the Examples

The examples are tested automatically as part of the test suite:

```bash
# Run all tests including example tests
pytest

# Run only example tests
pytest tests/test_examples.py

# Run with verbose output
pytest tests/test_examples.py -v
```

## Type Checking

All examples are fully typed and can be type-checked with mypy:

```bash
# Type check all examples
mypy examples/

# Type check a specific example
mypy examples/basic_usage.py
```

## What Each Example Teaches

| Example | Concepts | Difficulty |
|---------|----------|-----------|
| basic_usage.py | Container basics, registration, validation | Beginner |
| scopes_example.py | Singleton, Transient, Request scopes | Beginner |
| modules_example.py | Modules, public/private, composition | Intermediate |
| decorators_example.py | @singleton, @transient, @inject, Injectable | Intermediate |
| fastapi_example.py | FastAPI integration, async, request scope | Advanced |

## Contributing Examples

When adding new examples:

1. Create a new `.py` file in this directory
2. Include a detailed docstring explaining what the example demonstrates
3. Add a `main()` function that can be run standalone
4. Ensure all code is fully typed with type annotations
5. Add tests in `tests/test_examples.py`
6. Update this README with a description of your example

## Example Structure

Each example should follow this structure:

```python
"""Example description.

This example demonstrates:
- Feature 1
- Feature 2
- Feature 3
"""

from inversipy import Container

# Define classes and functions

def main() -> None:
    """Run the example."""
    # Example code here
    print("✓ Example completed successfully")

if __name__ == "__main__":
    main()
```
