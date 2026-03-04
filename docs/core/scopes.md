# Scopes

Scopes control the lifecycle of dependencies.

## Singleton

Creates one instance and reuses it for all requests:

```python
from inversipy import Container, Scopes

container = Container()
container.register(Database, scope=Scopes.SINGLETON)

db1 = container.get(Database)
db2 = container.get(Database)
assert db1 is db2  # Same instance
```

Use for: database connections, caches, configuration, loggers.

## Transient

Creates a new instance for each request (the default):

```python
container.register(RequestHandler, scope=Scopes.TRANSIENT)

handler1 = container.get(RequestHandler)
handler2 = container.get(RequestHandler)
assert handler1 is not handler2  # Different instances
```

Use for: stateful services, request handlers, commands.

## Request

Creates one instance per request/context using Python's `contextvars`. Automatically isolates instances per async task or thread:

```python
container.register(RequestService, scope=Scopes.REQUEST)

# Within the same context, you get the same instance
service1 = container.get(RequestService)
service2 = container.get(RequestService)
assert service1 is service2

# Different async tasks or threads get different instances automatically
```

Use for: per-request state in web applications.

The `contextvars`-based implementation provides:

- **Zero configuration** - automatic isolation per request/task/thread
- **Thread-safe** - each thread gets its own context
- **Async-aware** - works seamlessly with asyncio
- **Framework agnostic** - works with FastAPI, Flask, Starlette, etc.
