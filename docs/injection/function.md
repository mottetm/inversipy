# Function Injection

Run functions with automatic dependency injection using `container.run()`.

## Basic Usage

```python
from inversipy import Container, Scopes

container = Container()
container.register(Database, scope=Scopes.SINGLETON)
container.register(RequestHandler)

def handle_request(handler: RequestHandler) -> dict:
    return {"status": "ok"}

result = container.run(handle_request)
```

## Providing Arguments

You can pass some arguments explicitly; the rest are resolved from the container:

```python
def process(handler: RequestHandler, user_id: int) -> dict:
    return handler.process(user_id)

result = container.run(process, user_id=42)
```

## Async Functions

```python
result = await container.run_async(async_handler)
```

!!! note
    `run_async()` resolves dependencies asynchronously but does not await the function itself.
    If the function is async, the return value is a coroutine that needs to be awaited.
