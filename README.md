# inversipy

A powerful and type-safe dependency injection/IoC (Inversion of Control) library for Python.

## Features

- **Type annotation-based dependency resolution** - Dependencies are resolved using Python type hints
- **Container validation** - Ensure all dependencies can be resolved before runtime
- **Module system** - Organize dependencies with public/private access control
- **Parent-child container hierarchy** - Create child containers that inherit from parent
- **Multiple scopes** - Singleton, Transient, Request, and AsyncSingleton scopes
- **Decorator support** - Convenient decorators for registration and injection
- **Async support** - First-class support for async dependencies
- **Type-safe** - Full type hint support for better IDE integration

## Installation

```bash
pip install inversipy
```

For development:

```bash
pip install inversipy[dev]
```

## Quick Start

```python
from inversipy import Container, SINGLETON

# Define your services
class Database:
    def query(self, sql: str) -> list:
        return ["result"]

class UserRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_users(self) -> list:
        return self.db.query("SELECT * FROM users")

class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def list_users(self) -> list:
        return self.repo.get_users()

# Create container and register dependencies
container = Container()
container.register(Database, scope=SINGLETON)
container.register(UserRepository)
container.register(UserService)

# Validate container (optional but recommended)
container.validate()

# Resolve dependencies
service = container.get(UserService)
users = service.list_users()
```

## Core Concepts

### Container

The `Container` is the main component that manages dependency registration and resolution.

```python
from inversipy import Container, SINGLETON, TRANSIENT

container = Container()

# Register with automatic resolution
container.register(MyService)

# Register with explicit implementation
container.register(IService, implementation=MyServiceImpl)

# Register with factory function
container.register_factory(MyService, lambda: MyService("config"))

# Register with pre-created instance
instance = MyService()
container.register_instance(MyService, instance)

# Resolve dependencies
service = container.get(MyService)

# Check if registered
if container.has(MyService):
    service = container.get(MyService)

# Try to get (returns None if not found)
service = container.try_get(MyService)
```

### Scopes

Scopes control the lifecycle of dependencies.

#### Singleton Scope

Creates one instance and reuses it for all requests:

```python
from inversipy import Container, SINGLETON

container = Container()
container.register(Database, scope=SINGLETON)

db1 = container.get(Database)
db2 = container.get(Database)
assert db1 is db2  # Same instance
```

#### Transient Scope

Creates a new instance for each request:

```python
from inversipy import Container, TRANSIENT

container = Container()
container.register(RequestHandler, scope=TRANSIENT)

handler1 = container.get(RequestHandler)
handler2 = container.get(RequestHandler)
assert handler1 is not handler2  # Different instances
```

#### Request Scope

Creates one instance per request/context:

```python
from inversipy import Container, REQUEST

container = Container()
container.register(RequestContext, scope=REQUEST)

# Set context for current request
REQUEST.set_context("request-123")

ctx1 = container.get(RequestContext)
ctx2 = container.get(RequestContext)
assert ctx1 is ctx2  # Same instance within request

# Clean up after request
REQUEST.clear_context("request-123")
```

#### Async Singleton Scope

For async dependencies:

```python
from inversipy.scopes import AsyncSingletonScope

async_scope = AsyncSingletonScope()

async def get_service():
    scope = AsyncSingletonScope()

    async def factory():
        return await create_async_service()

    service = await scope.get_async(factory)
    return service
```

### Modules

Modules allow you to organize dependencies with public/private access control.

```python
from inversipy import Module, Container, SINGLETON

# Create a database module
db_module = Module("Database")

# Register private dependencies
db_module.register(DatabaseConnection, scope=SINGLETON, public=False)
db_module.register(QueryBuilder, public=False)

# Register public dependencies
db_module.register(Database, scope=SINGLETON, public=True)
db_module.register(UserRepository, public=True)

# Or use export to make dependencies public
db_module.export(Database, UserRepository)

# Load module into container
container = Container()
db_module.load_into(container)

# Only public dependencies are accessible
database = container.get(Database)  # ✓ Works
user_repo = container.get(UserRepository)  # ✓ Works
# connection = container.get(DatabaseConnection)  # ✗ Not accessible
```

Using ModuleBuilder:

```python
from inversipy import ModuleBuilder, SINGLETON

module = (
    ModuleBuilder("Database")
    .bind(DatabaseConnection, scope=SINGLETON)  # Private
    .bind(QueryBuilder)  # Private
    .bind_public(Database, scope=SINGLETON)  # Public
    .bind_public(UserRepository)  # Public
    .build()
)
```

### Parent-Child Containers

Create container hierarchies where children can access parent dependencies:

```python
from inversipy import Container, SINGLETON

# Parent container with shared services
parent = Container(name="Parent")
parent.register(Database, scope=SINGLETON)
parent.register(Config, scope=SINGLETON)

# Child container for a specific context
child = parent.create_child(name="RequestContainer")
child.register(RequestContext)
child.register(RequestHandler)

# Child can access parent dependencies
db = child.get(Database)  # Resolved from parent
handler = child.get(RequestHandler)  # Resolved from child

# Parent is not affected by child registrations
assert not parent.has(RequestHandler)
```

### Validation

Validate that all dependencies can be resolved:

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

### Decorators

Use decorators for convenient registration:

```python
from inversipy import Container, singleton, transient, inject

container = Container()

# Register as singleton
@singleton(container)
class Database:
    def query(self, sql: str) -> list:
        return []

# Register as transient
@transient(container)
class RequestHandler:
    def __init__(self, db: Database) -> None:
        self.db = db

# Inject dependencies into functions
@inject(container)
def handle_request(handler: RequestHandler) -> dict:
    return {"status": "ok"}

result = handle_request()  # Dependencies automatically injected
```

Property injection using descriptors:

```python
from inversipy import Container, Inject

container = Container()
container.register(Database)

class UserService:
    database = Inject(Database)

    def __init__(self, container: Container) -> None:
        self._container = container

    def get_users(self) -> list:
        return self.database.query("SELECT * FROM users")

service = UserService(container)
users = service.get_users()
```

## Advanced Usage

### Factory Functions with Dependencies

```python
from inversipy import Container

container = Container()
container.register(Config)

def create_database(config: Config) -> Database:
    return Database(config.db_url)

container.register_factory(
    Database,
    lambda: create_database(container.get(Config))
)
```

### Conditional Registration

```python
from inversipy import Container

container = Container()

if is_production:
    container.register(ICache, implementation=RedisCache)
else:
    container.register(ICache, implementation=InMemoryCache)
```

### Multiple Containers

```python
from inversipy import Container

# Application-wide container
app_container = Container(name="Application")
app_container.register(Database, scope=SINGLETON)

# Request-specific container
def handle_request(request):
    request_container = app_container.create_child(name="Request")
    request_container.register_instance(Request, request)

    handler = request_container.get(RequestHandler)
    return handler.handle()
```

### Testing with Containers

```python
import pytest
from inversipy import Container

@pytest.fixture
def container():
    container = Container()
    # Register test doubles
    container.register(IDatabase, implementation=MockDatabase)
    container.register(IEmailService, implementation=FakeEmailService)
    return container

def test_user_service(container):
    container.register(UserService)
    service = container.get(UserService)

    result = service.create_user("test@example.com")
    assert result is not None
```

## Best Practices

1. **Validate early**: Call `container.validate()` at application startup to catch configuration errors early

2. **Use scopes appropriately**:
   - `SINGLETON` for expensive resources (database connections, caches)
   - `TRANSIENT` for stateful services (request handlers, commands)
   - `REQUEST` for request-scoped resources (in web applications)

3. **Organize with modules**: Group related dependencies into modules with clear public interfaces

4. **Prefer constructor injection**: Use type-annotated constructors for dependency injection

5. **Use interfaces**: Register interfaces and bind to implementations for better testability

6. **Child containers for isolation**: Use child containers for request-scoped or test-specific dependencies

7. **Document public module interfaces**: Clearly document which dependencies are public in your modules

## Error Handling

Inversipy provides clear error messages:

```python
from inversipy import (
    DependencyNotFoundError,
    CircularDependencyError,
    ValidationError,
    RegistrationError,
    ResolutionError,
)

try:
    service = container.get(UnregisteredService)
except DependencyNotFoundError as e:
    print(f"Dependency not found: {e}")

try:
    container.validate()
except ValidationError as e:
    print(f"Validation failed: {len(e.errors)} errors")
    for error in e.errors:
        print(f"  - {error}")
```

## Type Safety

Inversipy is fully typed for better IDE support:

```python
from inversipy import Container

container = Container()
container.register(Database)

# Type checkers understand the return type
db: Database = container.get(Database)

# IDE autocomplete works
db.query("SELECT * FROM users")
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.

## Similar Projects

If inversipy doesn't fit your needs, check out these alternatives:

- [dependency-injector](https://python-dependency-injector.ets-labs.org/)
- [injector](https://github.com/alecthomas/injector)
- [pinject](https://github.com/google/pinject)

## Why "inversipy"?

The name combines "inversion" (as in Inversion of Control) with "py" (Python). It's about inverting control flow - instead of your code creating dependencies, the container provides them.
