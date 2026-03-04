# Click Integration

Inversipy provides Click integration with the `@inject` decorator, `@pass_container`, and `@with_modules`.

## Setup

```python
import click
from inversipy import Container
from inversipy.click import inject, pass_container
from inversipy.decorators import Inject

container = Container()
container.register(Database)
container.register(Logger)

@click.group()
@pass_container(container)
def cli():
    pass
```

## Commands

Use `@inject` to auto-resolve dependencies. Parameters marked with `Inject[T]` are resolved from the container; normal parameters are handled by Click:

```python
@cli.command()
@click.option("--limit", type=int, default=10)
@inject
def list_users(limit: int, db: Inject[Database], logger: Inject[Logger]):
    logger.info(f"Fetching {limit} users")
    for user in db.get_users()[:limit]:
        click.echo(user)
```

The `@inject` decorator:

- Identifies parameters marked with `Inject[Type]` or `InjectAll[Type]`
- Resolves them from the container stored in Click's context
- Leaves normal Click parameters (options, arguments) unchanged
- Rewrites the function signature so Click only sees CLI parameters

## Domain Modules

Use `@with_modules` on groups to register domain-specific modules:

```python
from inversipy.click import with_modules
from inversipy.module import Module

auth_module = Module("auth")
auth_module.register(AuthService, public=True)

@cli.group()
@with_modules(auth_module)
def auth():
    pass

@auth.command()
@click.argument("username")
@inject
def login(username: str, auth_svc: Inject[AuthService]):
    auth_svc.login(username)
```

Modules are registered on the shared container. Since Click only executes one command path per invocation, modules registered at a group level are only relevant to that group's subcommands.

## Installation

```bash
pip install inversipy click
```
