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

## Custom Scopes

Beyond the built-in scopes, you can define your own by subclassing `BindingStrategy` and wrapping it in a `CustomScope`:

```python
import threading
from inversipy import BindingStrategy, CustomScope, Container

class ThreadLocalStrategy(BindingStrategy):
    """One instance per thread."""

    def __init__(self):
        self._local = threading.local()

    def get(self, factory, is_async_factory):
        if not hasattr(self._local, "instance"):
            self._local.instance = factory()
        return self._local.instance

    async def get_async(self, factory):
        if not hasattr(self._local, "instance"):
            result = factory()
            if asyncio.iscoroutine(result):
                self._local.instance = await result
            else:
                self._local.instance = result
        return self._local.instance

# Create a reusable scope constant
THREAD_LOCAL = CustomScope("thread_local", ThreadLocalStrategy)

# Use it like any built-in scope
container = Container()
container.register(MyService, scope=THREAD_LOCAL)
```

`CustomScope` works anywhere a built-in `Scopes` value does via the `Scope` type alias (`Scopes | CustomScope`). Each binding gets its own strategy instance, so there's no shared state between different registrations using the same custom scope.

### Implementing a BindingStrategy

Your strategy must implement two methods:

- **`get(factory, is_async_factory)`** — Called during sync resolution (`container.get()`). If `is_async_factory` is `True`, raise a `ResolutionError`.
- **`get_async(factory)`** — Called during async resolution (`container.get_async()`). Must handle both sync and async factories (check with `asyncio.iscoroutine(result)`).
