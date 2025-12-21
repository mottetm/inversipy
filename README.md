# inversipy

A powerful and type-safe dependency injection/IoC (Inversion of Control) library for Python.

## Features

- **Type annotation-based dependency resolution** - Dependencies are resolved using Python type hints
- **Container validation** - Ensure all dependencies can be resolved before runtime
- **Module system** - Organize dependencies with public/private access control
- **Parent-child container hierarchy** - Create child containers that inherit from parent
- **Multiple scopes** - Singleton, Transient, and Request scopes
- **Function injection** - Run functions with automatic dependency injection via `container.run()`
- **Property injection** - Injectable base class for clean, declarative dependency injection
- **Named dependencies** - Register multiple implementations with names for disambiguation
- **Collection injection** - Register multiple implementations and inject as a collection with `InjectAll`
- **Named collections** - Group implementations by name and inject with `InjectAllNamed`
- **Async support** - First-class support for async dependencies
- **Type-safe** - Full type hint support for better IDE integration
- **Pure classes** - No container coupling - classes remain framework-agnostic

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
from inversipy import Container, Scopes

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
from inversipy import Container, Scopes, TRANSIENT

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
from inversipy import Container, Scopes

container = Container()
container.register(Database, scope=SINGLETON)

db1 = container.get(Database)
db2 = container.get(Database)
assert db1 is db2  # Same instance
```

#### Transient Scope

Creates a new instance for each request:

```python
from inversipy import Container, Scopes

container = Container()
container.register(RequestHandler, scope=TRANSIENT)

handler1 = container.get(RequestHandler)
handler2 = container.get(RequestHandler)
assert handler1 is not handler2  # Different instances
```

#### Request Scope

Creates one instance per request/context using Python's `contextvars` module. **Automatically isolates instances per async task or thread** - no manual context management needed:

```python
from inversipy import Container, Scopes

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

### Modules

Modules allow you to organize dependencies with public/private access control. **Dependencies are private by default** - you must explicitly mark them as public. Modules are registered as **live providers** - they remain the source of truth for their dependencies.

```python
from inversipy import Module, Container, Scopes

# Create a database module
db_module = Module("Database")

# Register private dependencies (public=False is the default)
db_module.register(DatabaseConnection, scope=Scopes.SINGLETON)  # Private by default
db_module.register(QueryBuilder)  # Private by default

# Register public dependencies (must explicitly set public=True)
db_module.register(Database, scope=Scopes.SINGLETON, public=True)
db_module.register(UserRepository, public=True)

# Or use export to make dependencies public after registration
db_module.export(Database, UserRepository)

# Register module as a provider in the container
container = Container()
container.register_module(db_module)

# Only public dependencies are accessible
database = container.get(Database)  # ✓ Works - public
user_repo = container.get(UserRepository)  # ✓ Works - public
# connection = container.get(DatabaseConnection)  # ✗ DependencyNotFoundError - private

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
from inversipy import Container, Scopes

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

### Function Injection with Container.run()

Run functions with automatic dependency injection using `container.run()`:

```python
from inversipy import Container, Scopes

container = Container()

# Pure classes - no decorator coupling
class Database:
    def query(self, sql: str) -> list:
        return []

class RequestHandler:
    def __init__(self, db: Database) -> None:
        self.db = db

# Register with pure registration
container.register(Database, scope=Scopes.SINGLETON)
container.register(RequestHandler)

# Pure function - no decorators
def handle_request(handler: RequestHandler) -> dict:
    return {"status": "ok"}

# Use container.run() to inject dependencies
result = container.run(handle_request)  # Dependencies automatically resolved

# Can also provide some arguments explicitly
result = container.run(handle_request, custom_arg="value")
```

### Property Injection with Injectable

Property injection using `Injectable` base class:

```python
from typing import Annotated
from inversipy import Container, Injectable, Inject

container = Container()
container.register(Database)
container.register(Logger)

class UserService(Injectable):
    database: Annotated[Database, Inject]
    logger: Annotated[Logger, Inject]

    def get_users(self) -> list:
        self.logger.info("Fetching users")
        return self.database.query("SELECT * FROM users")

container.register(UserService)
service = container.get(UserService)  # Dependencies auto-injected!
users = service.get_users()
```

The `Injectable` base class automatically:
- Scans for `Annotated[Type, Inject]` properties
- Generates a constructor that accepts these dependencies as parameters
- Keeps classes pure - they can be instantiated manually or via container

Classes using `Injectable` remain container-agnostic and can be used standalone:

```python
# Manual instantiation - class is pure
my_db = Database()
my_logger = Logger()
service = UserService(database=my_db, logger=my_logger)
```

### Named Dependencies

Register multiple implementations of the same interface using named dependencies:

```python
from inversipy import Container, Inject, Named

class IDatabase:
    pass

class PostgresDB(IDatabase):
    pass

class SQLiteDB(IDatabase):
    pass

container = Container()
container.register(IDatabase, PostgresDB, name="primary")
container.register(IDatabase, SQLiteDB, name="backup")

# Resolve by name
primary_db = container.get(IDatabase, name="primary")
backup_db = container.get(IDatabase, name="backup")
```

With property injection:

```python
from inversipy import Injectable, Inject, Named

class DataService(Injectable):
    primary_db: Inject[IDatabase, Named("primary")]
    backup_db: Inject[IDatabase, Named("backup")]
```

### Collection Injection

Register multiple implementations and inject them as a collection using `InjectAll`:

```python
from inversipy import Container, InjectAll, Injectable

class IPlugin:
    def execute(self) -> str:
        raise NotImplementedError

class PluginA(IPlugin):
    def execute(self) -> str:
        return "PluginA executed"

class PluginB(IPlugin):
    def execute(self) -> str:
        return "PluginB executed"

# Multiple registrations accumulate (no overwriting)
container = Container()
container.register(IPlugin, PluginA)
container.register(IPlugin, PluginB)

# Get all implementations
plugins = container.get_all(IPlugin)  # [PluginA(), PluginB()]
for plugin in plugins:
    print(plugin.execute())

# Single resolution fails when ambiguous
# container.get(IPlugin)  # raises AmbiguousDependencyError
```

With property injection:

```python
class PluginManager(Injectable):
    plugins: InjectAll[IPlugin]

    def run_all(self) -> list[str]:
        return [plugin.execute() for plugin in self.plugins]

container.register(PluginManager)
manager = container.get(PluginManager)
results = manager.run_all()  # ['PluginA executed', 'PluginB executed']
```

### Named Collection Injection

Combine named dependencies with collection injection using `InjectAllNamed`:

```python
from inversipy import Container, InjectAllNamed, Named, Injectable

# Register plugins in named groups
container = Container()
container.register(IPlugin, PluginA, name="core")
container.register(IPlugin, PluginB, name="core")
container.register(IPlugin, PluginC, name="optional")

# Get all implementations in a named group
core_plugins = container.get_all(IPlugin, name="core")  # [PluginA(), PluginB()]
optional_plugins = container.get_all(IPlugin, name="optional")  # [PluginC()]
```

With property injection:

```python
class PluginManager(Injectable):
    core_plugins: InjectAllNamed[IPlugin, Named("core")]
    optional_plugins: InjectAllNamed[IPlugin, Named("optional")]

    def run_core(self) -> list[str]:
        return [p.execute() for p in self.core_plugins]

container.register(PluginManager)
manager = container.get(PluginManager)
manager.run_core()  # Only runs core plugins
```

## Advanced Usage

### Factory Functions with Dependencies

Factory functions can have dependencies that are automatically resolved from the container. Simply type-hint the parameters, and the container will inject them:

```python
from inversipy import Container, Scopes

container = Container()
container.register(Config, scope=Scopes.SINGLETON)

def create_database(config: Config) -> Database:
    """Factory function with dependency - config is automatically injected!"""
    return Database(config.db_url)

# The container automatically resolves the Config dependency
container.register_factory(Database, create_database, scope=Scopes.SINGLETON)

# Config is injected automatically when creating Database
db = container.get(Database)
```

Works with multiple dependencies too:

```python
def create_user_service(db: Database, logger: Logger, cache: Cache) -> UserService:
    """All three dependencies are automatically resolved and injected"""
    return UserService(db, logger, cache)

container.register_factory(UserService, create_user_service)
service = container.get(UserService)  # db, logger, and cache auto-injected
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
from inversipy import Container, Scopes
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

## FastAPI Integration

Inversipy provides seamless FastAPI integration with the `@inject` decorator:

```python
from typing import Annotated
from fastapi import FastAPI
from inversipy import Container
from inversipy.decorators import Inject
from inversipy.fastapi import inject

# Setup
app = FastAPI()
container = Container()
container.register(Database)
container.register(Logger)
app.state.container = container

# Use @inject to auto-resolve dependencies
@app.get("/users")
@inject
async def get_users(
    db: Annotated[Database, Inject],
    logger: Annotated[Logger, Inject],
    limit: int = 10
):
    logger.info(f"Fetching {limit} users")
    return db.query("SELECT * FROM users LIMIT ?", limit)
```

The `@inject` decorator:
- Identifies parameters marked with `Annotated[Type, Inject]`
- Resolves them from the container automatically
- Leaves normal FastAPI parameters (query params, body, etc.) unchanged
- Works with both sync and async route handlers

Install FastAPI support:
```bash
pip install inversipy fastapi
```
