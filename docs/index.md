# inversipy

[![CI](https://github.com/mottetm/inversipy/actions/workflows/ci.yml/badge.svg)](https://github.com/mottetm/inversipy/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/inversipy)](https://pypi.org/project/inversipy/)
[![Python versions](https://img.shields.io/pypi/pyversions/inversipy)](https://pypi.org/project/inversipy/)
[![License](https://img.shields.io/pypi/l/inversipy)](https://pypi.org/project/inversipy/)
[![Coverage](https://codecov.io/gh/mottetm/inversipy/branch/main/graph/badge.svg)](https://codecov.io/gh/mottetm/inversipy)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://mottetm.github.io/inversipy/)

A powerful and type-safe dependency injection/IoC (Inversion of Control) library for Python 3.12+.

## Why inversipy?

- **Zero runtime dependencies** - Pure Python, nothing to install beyond the library itself
- **Type annotation-based** - Dependencies resolved using Python type hints
- **Pure classes** - No container coupling; classes remain framework-agnostic
- **Async-first** - First-class support for async dependencies and factories
- **Validated** - Catch configuration errors at startup, not at runtime

## Key Features

- [Container](core/container.md) with registration, resolution, and composition
- [Three scopes](core/scopes.md): Singleton, Transient, and Request
- [Module system](core/modules.md) with public/private access control
- [Property injection](injection/property.md) via `Injectable` base class
- [Named dependencies](injection/named.md) for multiple implementations
- [Collection injection](injection/collection.md) with `InjectAll`
- [Optional dependencies](injection/optional.md) with `T | None`
- [Container freezing](advanced/freezing.md) for runtime safety
- [FastAPI integration](integrations/fastapi.md)
- Full MyPy support with strict typing

## Quick Example

```python
from inversipy import Container, Scopes

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

# Create container and register dependencies
container = Container()
container.register(Database, scope=Scopes.SINGLETON)
container.register(UserRepository)
container.register(UserService)

# Validate and freeze
container.validate()
container.freeze()

# Resolve dependencies
service = container.get(UserService)
users = service.list_users()
```
