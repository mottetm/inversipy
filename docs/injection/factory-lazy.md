# Factory and Lazy Injection

`Factory[T]` and `Lazy[T]` provide deferred dependency resolution — the dependency is not resolved when the parent object is created, but later when explicitly called.

## Factory[T]

A callable wrapper that resolves `T` from the container on each call, respecting registered scopes.

```python
from inversipy import Container, Factory, Scopes

class Connection:
    pass

class ConnectionPool:
    def __init__(self, make_conn: Factory[Connection]) -> None:
        self.make_conn = make_conn

    def acquire(self) -> Connection:
        return self.make_conn()  # New Connection each time

container = Container()
container.register(Connection)
container.register(ConnectionPool)

pool = container.get(ConnectionPool)
conn1 = pool.acquire()
conn2 = pool.acquire()
assert conn1 is not conn2  # Transient scope: different instances
```

### With Singleton Scope

`Factory[T]` respects the scope of the underlying binding:

```python
container = Container()
container.register(Connection, scope=Scopes.SINGLETON)
container.register(ConnectionPool)

pool = container.get(ConnectionPool)
conn1 = pool.acquire()
conn2 = pool.acquire()
assert conn1 is conn2  # Singleton scope: same instance
```

## Lazy[T]

A callable wrapper that resolves `T` on the first call and caches the result. Subsequent calls return the cached instance.

```python
from inversipy import Container, Lazy

class ExpensiveService:
    pass

class Controller:
    def __init__(self, service: Lazy[ExpensiveService]) -> None:
        self.service = service

    def handle(self) -> ExpensiveService:
        return self.service()  # Resolved on first call, cached after

container = Container()
container.register(ExpensiveService)
container.register(Controller)

ctrl = container.get(Controller)
svc1 = ctrl.handle()
svc2 = ctrl.handle()
assert svc1 is svc2  # Same instance returned every time
```

## With Named Dependencies

Both `Factory` and `Lazy` work with `Inject` and `Named` qualifiers:

```python
from inversipy import Container, Factory, Lazy, Inject, Named

class IDatabase:
    pass

class PostgresDB(IDatabase):
    pass

class MySQLDB(IDatabase):
    pass

class Service:
    def __init__(
        self,
        pg_factory: Inject[Factory[IDatabase], Named("primary")],
        mysql: Inject[Lazy[IDatabase], Named("replica")],
    ) -> None:
        self.pg_factory = pg_factory
        self.mysql = mysql

container = Container()
container.register(IDatabase, PostgresDB, name="primary")
container.register(IDatabase, MySQLDB, name="replica")
container.register(Service)

svc = container.get(Service)
db = svc.pg_factory()    # Resolves PostgresDB
replica = svc.mysql()    # Resolves MySQLDB (cached)
```

## With Function Injection

```python
from inversipy import Container, Factory

class Worker:
    pass

def spawn_workers(make_worker: Factory[Worker], count: int) -> list[Worker]:
    return [make_worker() for _ in range(count)]

container = Container()
container.register(Worker)

workers = container.run(spawn_workers, count=3)
assert len(workers) == 3
```

## With Property Injection

```python
from inversipy import Container, Factory, Lazy, Inject, Injectable

class Logger:
    pass

class AppService(Injectable):
    logger_factory: Inject[Factory[Logger]]
    lazy_logger: Inject[Lazy[Logger]]

container = Container()
container.register(Logger)
container.register(AppService)

svc = container.get(AppService)
logger = svc.logger_factory()
cached = svc.lazy_logger()
```

## Deferred Errors

Resolution errors are deferred to call time. If the underlying type is not registered, the `Factory` or `Lazy` wrapper is still injected — the error occurs when you call it:

```python
class Unregistered:
    pass

class Consumer:
    def __init__(self, f: Factory[Unregistered]) -> None:
        self.f = f

container = Container()
container.register(Consumer)

consumer = container.get(Consumer)  # Succeeds
consumer.f()                        # Raises DependencyNotFoundError
```

## Caching Behaviour and Scopes

The declared scope of the dependency is correctly enforced for the wrapper itself. The container caches `Factory` and `Lazy` wrappers according to the dependency's scope — Singleton yields one shared wrapper, Transient creates a fresh wrapper each time it is injected, and Request produces one wrapper per request context.

Once a wrapper instance has been distributed to a consumer:

- **`Factory[T]`** calls `container.get(T)` on every invocation, so each call goes through the container's normal resolution (which may return a cached instance depending on the scope).
- **`Lazy[T]`** resolves `T` on the first call and always returns that same instance on subsequent calls — it never re-queries the container.

| Scope | `Factory[T]()` per call | `Lazy[T]()` per call |
|-------|------------------------|---------------------|
| Transient | New instance each time | First call's instance (cached by wrapper) |
| Singleton | Same instance (cached by container) | Same instance (cached by both) |
| Request | New instance each time (dependencies may be request-cached) | First call's instance (cached by per-request wrapper) |

## When to Use Which

| Type | Resolves | Caches | Use Case |
|------|----------|--------|----------|
| Direct (`T`) | At parent creation | N/A | Default — eager resolution |
| `Lazy[T]` | On first call | Yes | Expensive initialization, break circular startup |
| `Factory[T]` | On every call | No | Multiple instances on demand |
