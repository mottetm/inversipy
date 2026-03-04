# Flask Integration

Inversipy provides Flask integration with the `@inject` decorator.

## Setup

```python
from flask import Flask
from inversipy import Container, Inject
from inversipy.flask import bind, inject

app = Flask(__name__)
container = Container()
container.register(Database)
container.register(Logger)
bind(app, container)
```

## Route Handlers

Use `@inject` to auto-resolve dependencies. Parameters marked with `Inject[T]` are resolved from the container; normal parameters (path params, etc.) are handled by Flask:

```python
@app.route("/users/<int:user_id>")
@inject
def get_user(
    user_id: int,
    db: Inject[Database],
    logger: Inject[Logger],
):
    logger.info(f"Fetching user {user_id}")
    return db.get_user(user_id)
```

The `@inject` decorator:

- Identifies parameters marked with `Inject[Type]` or `InjectAll[Type]`
- Resolves them from the container automatically
- Leaves normal Flask parameters (path params, etc.) unchanged
- Works with named dependencies via `Inject[Type, Named("x")]`

## Installation

```bash
pip install inversipy flask
```
