# Pytest Integration

Inversipy provides a pytest plugin for dependency injection in tests.

## Setup

The plugin is automatically registered when inversipy is installed. It provides a default `container` fixture that returns an empty `Container()`. Override it in your `conftest.py`:

```python
# conftest.py
import pytest
from inversipy import Container

@pytest.fixture
def container():
    c = Container()
    c.register(Database, PostgresDB)
    c.register(UserService)
    return c
```

## Using `@inject` in Tests

Use `@inject` to auto-resolve `Inject[T]` parameters from the container fixture:

```python
from inversipy.decorators import Inject
from inversipy_pytest import inject

@inject
def test_user_creation(service: Inject[UserService]):
    assert service.create("alice") is not None
```

## Mixing Fixtures and Injected Dependencies

Non-injected parameters are passed through for normal pytest fixture resolution. This means you can freely combine standard pytest fixtures with `Inject[T]` parameters in the same test:

```python
@pytest.fixture
def username():
    return "Bob"

@inject
def test_with_fixture(username, service: Inject[UserService]):
    # `username` comes from the pytest fixture
    # `service` is resolved from the container
    assert service.find(username) is not None
```

## Overriding Dependencies

Use child containers for test-specific overrides:

```python
@pytest.fixture
def container(container):
    child = container.create_child()
    child.register(IDatabase, MockDatabase)
    return child

@inject
def test_with_mock(db: Inject[IDatabase]):
    assert db.query() == "mock data"
```

## Installation

```bash
pip install inversipy
```

The pytest plugin is registered automatically via entry points.
