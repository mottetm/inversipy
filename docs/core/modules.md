# Modules

Modules organize dependencies with public/private access control. Dependencies are **private by default** - you must explicitly mark them as public.

## Creating Modules

```python
from inversipy import Module, Container, Scopes

db_module = Module("Database")

# Private dependencies (default)
db_module.register(DatabaseConnection, scope=Scopes.SINGLETON)
db_module.register(QueryBuilder)

# Public dependencies
db_module.register(Database, scope=Scopes.SINGLETON, public=True)
db_module.register(UserRepository, public=True)
```

Register the module with a container:

```python
container = Container()
container.register_module(db_module)

# Only public dependencies are accessible
database = container.get(Database)         # Works
user_repo = container.get(UserRepository)  # Works
# container.get(DatabaseConnection)        # DependencyNotFoundError
```

## Exporting Dependencies

You can also make dependencies public after registration:

```python
db_module.register(Database, scope=Scopes.SINGLETON)
db_module.export(Database)  # Now public
```

For named dependencies:

```python
db_module.export_named(IDatabase, "primary")
```

## Module Composition

Modules can register other modules:

```python
auth_module = Module("Auth")
auth_module.register(AuthService, public=True)

db_module = Module("Database")
db_module.register(Database, public=True)

app_module = Module("App")
app_module.register_module(auth_module)
app_module.register_module(db_module)
app_module.register(AppService, public=True)

container = Container()
container.register_module(app_module)

auth = container.get(AuthService)  # From auth_module
db = container.get(Database)       # From db_module
app = container.get(AppService)    # From app_module
```

!!! note "Non-Transitive Visibility"
    Child module dependencies are NOT automatically public through parent modules.
    To expose them, use `export()` explicitly.

## ModuleBuilder

A fluent API for building modules:

```python
from inversipy import ModuleBuilder, Scopes

module = (
    ModuleBuilder("Database")
    .bind(DatabaseConnection, scope=Scopes.SINGLETON)  # Private
    .bind(QueryBuilder)                                 # Private
    .bind_public(Database, scope=Scopes.SINGLETON)      # Public
    .bind_public(UserRepository)                        # Public
    .build()
)
```
