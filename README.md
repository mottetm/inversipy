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

### Architecture Overview

Inversipy's architecture is built on two core abstractions:

- **Container**: The base class that provides dependency registration, resolution, and composition. Supports parent-child hierarchies and module registration. All dependencies are public by default.
- **Module**: Extends Container to add public/private access control. Modules can selectively expose dependencies and register other modules for composition.

This design eliminates code duplication while providing proper specialization - use Container for simplicity, and Module when you need encapsulation.

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

Creates one instance per request/context using Python's `contextvars` module. **Automatically isolates instances per async task or thread** - no manual context management needed:

```python
from inversipy import Container, REQUEST

container = Container()
container.register(RequestService, scope=REQUEST)

# Automatic isolation - each async task gets its own instance
async def handle_request():
    service = container.get(RequestService)
    # Each concurrent request automatically gets isolated instances
    # The framework's context (async task, thread) is automatically used
    return service.process()

# Within the same context, you get the same instance
def sync_handler():
    service1 = container.get(RequestService)
    service2 = container.get(RequestService)
    assert service1 is service2  # Same instance in same context
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

Modules allow you to organize dependencies with public/private access control. Modules are registered as **live providers** - they remain the source of truth for their dependencies.

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

# Register module as a provider in the container
container = Container()
container.register_module(db_module)

# Only public dependencies are accessible
database = container.get(Database)  # ✓ Works
user_repo = container.get(UserRepository)  # ✓ Works
# connection = container.get(DatabaseConnection)  # ✗ Not accessible (private)

# Module remains live - add new dependencies dynamically
db_module.register(CacheService, public=True)
cache = container.get(CacheService)  # ✓ Works! Module is still connected
```

Modules can also register other modules for composition:

```python
# Create specialized modules
auth_module = Module("Auth")
auth_module.register(AuthService, public=True)
auth_module.register(TokenValidator, public=False)

db_module = Module("Database")
db_module.register(Database, public=True)

# Create an app module that composes other modules
app_module = Module("App")
app_module.register_module(auth_module)  # Import auth module
app_module.register_module(db_module)    # Import db module
app_module.register(AppService, public=True)

# App module can access public dependencies from registered modules
container = Container()
container.register_module(app_module)

# All public dependencies are accessible
auth = container.get(AuthService)  # From auth_module
db = container.get(Database)       # From db_module
app = container.get(AppService)    # From app_module
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

### RequestScope with Web Frameworks

RequestScope uses `contextvars` for automatic context isolation. **No explicit context management needed** - each request/thread/async task is automatically isolated:

```python
from inversipy import Container, REQUEST
from fastapi import FastAPI

app = FastAPI()
container = Container()

# Register request-scoped services
container.register(RequestLogger, scope=REQUEST)
container.register(DatabaseSession, scope=REQUEST)

@app.get("/api/users")
async def get_users():
    # Each request automatically gets its own instances
    # No context manager needed - FastAPI tasks are already isolated!
    logger = container.get(RequestLogger)
    db = container.get(DatabaseSession)

    await logger.log("Fetching users")
    users = await db.query("SELECT * FROM users")
    return {"users": users}

@app.post("/api/users")
async def create_user(user_data: dict):
    # Different concurrent requests get different instances automatically
    logger = container.get(RequestLogger)
    db = container.get(DatabaseSession)

    await logger.log(f"Creating user: {user_data}")
    # Each request has its own db session - thread-safe by default
    await db.execute("INSERT INTO users ...", user_data)
    return {"status": "created"}
```

Works with Flask (threading-based) too:

```python
from flask import Flask

app = Flask(__name__)

@app.route('/api/users')
def get_users():
    # Each thread (request) automatically gets isolated instances
    logger = container.get(RequestLogger)
    db = container.get(DatabaseSession)

    logger.log("Processing request")
    users = db.query("SELECT * FROM users")
    return {"users": users}
```

The `contextvars`-based implementation provides:

- **Zero configuration**: Automatic isolation per request/task/thread
- **Thread-safe**: Each thread gets its own context automatically
- **Async-aware**: Works seamlessly with asyncio and concurrent requests
- **Framework agnostic**: Works with FastAPI, Flask, Starlette, etc.
- **No manual management**: The library leverages existing contexts created by your framework

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
