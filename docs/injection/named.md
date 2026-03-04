# Named Dependencies

Register multiple implementations of the same interface using named dependencies.

## Registration

```python
from inversipy import Container

class IDatabase:
    pass

class PostgresDB(IDatabase):
    pass

class SQLiteDB(IDatabase):
    pass

container = Container()
container.register(IDatabase, PostgresDB, name="primary")
container.register(IDatabase, SQLiteDB, name="backup")
```

## Resolution

```python
primary_db = container.get(IDatabase, name="primary")
backup_db = container.get(IDatabase, name="backup")
```

## With Property Injection

```python
from inversipy import Injectable, Inject, Named

class DataService(Injectable):
    primary_db: Inject[IDatabase, Named("primary")]
    backup_db: Inject[IDatabase, Named("backup")]
```

## Named Collections

Combine named dependencies with collection injection:

```python
from inversipy import Container, InjectAll, Named, Injectable

container = Container()
container.register(IPlugin, PluginA, name="core")
container.register(IPlugin, PluginB, name="core")
container.register(IPlugin, PluginC, name="optional")

# Get all in a named group
core_plugins = container.get_all(IPlugin, name="core")       # [PluginA(), PluginB()]
optional_plugins = container.get_all(IPlugin, name="optional")  # [PluginC()]
```

With property injection:

```python
class PluginManager(Injectable):
    core_plugins: InjectAll[IPlugin, Named("core")]
    optional_plugins: InjectAll[IPlugin, Named("optional")]
```
