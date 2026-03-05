# inversipy

[![CI](https://github.com/mottetm/inversipy/actions/workflows/ci.yml/badge.svg)](https://github.com/mottetm/inversipy/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/inversipy)](https://pypi.org/project/inversipy/)
[![Python versions](https://img.shields.io/pypi/pyversions/inversipy)](https://pypi.org/project/inversipy/)
[![License](https://img.shields.io/pypi/l/inversipy)](https://pypi.org/project/inversipy/)
[![Coverage](https://codecov.io/gh/mottetm/inversipy/branch/main/graph/badge.svg)](https://codecov.io/gh/mottetm/inversipy)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://mottetm.github.io/inversipy/)

A powerful and type-safe dependency injection/IoC (Inversion of Control) library for Python 3.12+.

## Features

- **Type annotation-based** - Dependencies resolved using Python type hints
- **Pure classes** - No container coupling; classes remain framework-agnostic
- **Zero runtime dependencies** - Pure Python
- **Async-first** - First-class support for async dependencies and factories
- **Module system** - Organize dependencies with public/private access control
- **Multiple scopes** - Singleton, Transient, and Request
- **Named dependencies** - Multiple implementations with named disambiguation
- **Collection injection** - Register and inject multiple implementations with `InjectAll`
- **Optional dependencies** - `T | None` parameters resolve to `None` when unregistered
- **Container freezing** - Lock the container after configuration
- **Validation** - Catch configuration errors at startup
- **FastAPI integration** - `@inject` decorator for route handlers
- **Full type safety** - Strict MyPy support with `py.typed` marker

## Installation

```bash
pip install inversipy
```

## Quick Start

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

## Documentation

Full documentation is available at the [documentation site](https://mottetm.github.io/inversipy/).

- [Getting Started](https://mottetm.github.io/inversipy/getting-started/)
- [Core Concepts](https://mottetm.github.io/inversipy/core/container/)
- [Injection Patterns](https://mottetm.github.io/inversipy/injection/constructor/)
- [FastAPI Integration](https://mottetm.github.io/inversipy/integrations/fastapi/)
- [Testing](https://mottetm.github.io/inversipy/advanced/testing/)
- [Best Practices](https://mottetm.github.io/inversipy/best-practices/)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.

## Similar Projects

- [dependency-injector](https://python-dependency-injector.ets-labs.org/)
- [injector](https://github.com/alecthomas/injector)
- [lagom](https://github.com/meadsteve/lagom)
