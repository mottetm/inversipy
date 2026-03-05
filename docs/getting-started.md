# Getting Started

## Installation

```bash
pip install inversipy
```

For development:

```bash
git clone https://github.com/mottetm/inversipy.git
cd inversipy
uv sync
```

## Your First Container

```python
from inversipy import Container, Scopes

# Define your services as plain classes
class Database:
    def query(self, sql: str) -> list:
        return ["result"]

class UserRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_users(self) -> list:
        return self.db.query("SELECT * FROM users")

class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def list_users(self) -> list:
        return self.repo.get_users()
```

Create a container, register your services, and resolve:

```python
container = Container()
container.register(Database, scope=Scopes.SINGLETON)
container.register(UserRepository)
container.register(UserService)

# Optional but recommended: validate all dependencies
container.validate()

# Resolve a service - all dependencies are injected automatically
service = container.get(UserService)
users = service.list_users()
```

The container analyzes type hints on `__init__` methods to determine what to inject. No decorators, no configuration files, no special base classes needed.

## What's Next?

- [Container](core/container.md) - Registration and resolution APIs
- [Scopes](core/scopes.md) - Singleton, Transient, and Request lifecycles
- [Modules](core/modules.md) - Organize dependencies with access control
- [FastAPI Integration](integrations/fastapi.md) - Use with web frameworks
