# Testing

Since inversipy uses pure classes with no framework coupling, testing is straightforward.

## Test Container Pattern

Create a dedicated container with test doubles:

```python
import pytest
from inversipy import Container

@pytest.fixture
def container():
    container = Container()
    container.register(IDatabase, implementation=MockDatabase)
    container.register(IEmailService, implementation=FakeEmailService)
    return container

def test_user_service(container):
    container.register(UserService)
    service = container.get(UserService)

    result = service.create_user("test@example.com")
    assert result is not None
```

## Child Container Pattern

Use a parent container for shared setup and child containers for test-specific overrides:

```python
@pytest.fixture
def base_container():
    container = Container()
    container.register(Config, instance=Config(env="test"))
    container.register(Logger)
    return container

def test_with_real_db(base_container):
    child = base_container.create_child()
    child.register(IDatabase, implementation=TestDatabase)
    child.register(UserService)

    service = child.get(UserService)
    assert service.list_users() == []

def test_with_mock_db(base_container):
    child = base_container.create_child()
    child.register_instance(IDatabase, MockDatabase(users=["alice"]))
    child.register(UserService)

    service = child.get(UserService)
    assert service.list_users() == ["alice"]
```

## Direct Instantiation

Classes are pure, so you can always instantiate them directly:

```python
def test_user_service_directly():
    mock_db = MockDatabase()
    mock_logger = MockLogger()
    service = UserService(db=mock_db, logger=mock_logger)

    result = service.create_user("test@example.com")
    assert result is not None
```
