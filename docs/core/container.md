# Container

The `Container` is the central component that manages dependency registration and resolution.

## Registration

```python
from inversipy import Container, Scopes

container = Container()

# Register with automatic resolution (type = implementation)
container.register(MyService)

# Register with explicit implementation
container.register(IService, implementation=MyServiceImpl)

# Register with factory function
container.register_factory(MyService, lambda: MyService("config"))

# Register with pre-created instance
instance = MyService()
container.register_instance(MyService, instance)
```

All registration methods return `self` for chaining:

```python
container = Container()
container.register(Database, scope=Scopes.SINGLETON).register(UserRepository).register(UserService)
```

## Resolution

```python
# Resolve a dependency
service = container.get(MyService)

# Check if registered
if container.has(MyService):
    service = container.get(MyService)

# Try to get (returns None if not found)
service = container.try_get(MyService)
```

## Async Resolution

All resolution methods have async counterparts:

```python
service = await container.get_async(MyService)
service = await container.try_get_async(MyService)
```

## Factory Functions with Dependencies

Factory functions can have dependencies that are automatically resolved:

```python
container.register(Config, scope=Scopes.SINGLETON)

def create_database(config: Config) -> Database:
    return Database(config.db_url)

container.register_factory(Database, create_database, scope=Scopes.SINGLETON)

# Config is injected automatically
db = container.get(Database)
```

## Conditional Registration

```python
if is_production:
    container.register(ICache, implementation=RedisCache)
else:
    container.register(ICache, implementation=InMemoryCache)
```
