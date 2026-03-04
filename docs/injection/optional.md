# Optional Dependencies

Parameters annotated with `T | None` or `Optional[T]` are treated as soft dependencies. If the dependency is not registered, `None` is injected instead of raising an error.

## Constructor Injection

```python
from inversipy import Container

class Cache:
    def get(self, key: str) -> str:
        return f"cached:{key}"

class UserService:
    def __init__(self, cache: Cache | None) -> None:
        self.cache = cache

container = Container()
container.register(UserService)

service = container.get(UserService)
assert service.cache is None  # Cache not registered, so None
```

When the dependency is registered, it resolves normally:

```python
container.register(Cache)
service = container.get(UserService)
assert isinstance(service.cache, Cache)
```

## In Factory Functions

```python
def create_service(logger: Logger, cache: Cache | None) -> MyService:
    return MyService(logger, cache)

container.register_factory(MyService, create_service)
```

## In `container.run()`

```python
def my_func(logger: Logger, cache: Cache | None) -> str:
    return f"cache={cache}"

result = container.run(my_func)  # cache=None
```

## Async Resolution

Works identically with `get_async()` and `run_async()`.

!!! note
    Non-optional parameters that can't be resolved still raise `ResolutionError` as expected.
