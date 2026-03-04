# FastAPI Integration

Inversipy provides seamless FastAPI integration with the `@inject` decorator.

## Setup

```python
from fastapi import FastAPI
from inversipy import Container, Inject
from inversipy.fastapi import inject

app = FastAPI()
container = Container()
container.register(Database)
container.register(Logger)
app.state.container = container
```

## Route Handlers

Use `@inject` to auto-resolve dependencies. Parameters marked with `Inject[T]` are resolved from the container; normal parameters are handled by FastAPI:

```python
@app.get("/users")
@inject
async def get_users(
    db: Inject[Database],
    logger: Inject[Logger],
    limit: int = 10,
):
    logger.info(f"Fetching {limit} users")
    return db.query("SELECT * FROM users LIMIT ?", limit)
```

The `@inject` decorator:

- Identifies parameters marked with `Inject[Type]`
- Resolves them from the container automatically
- Leaves normal FastAPI parameters (query params, path params, body, etc.) unchanged
- Works with both sync and async route handlers

## Installation

```bash
pip install inversipy fastapi
```
