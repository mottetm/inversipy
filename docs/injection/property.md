# Property Injection

The `Injectable` base class provides declarative property-based injection using `Inject[T]` and `InjectAll[T]`.

## Basic Usage

```python
from inversipy import Container, Injectable, Inject

container = Container()
container.register(Database)
container.register(Logger)

class UserService(Injectable):
    database: Inject[Database]
    logger: Inject[Logger]

    def get_users(self) -> list:
        self.logger.info("Fetching users")
        return self.database.query("SELECT * FROM users")

container.register(UserService)
service = container.get(UserService)
```

`Injectable` automatically:

- Scans for `Inject[Type]` annotations
- Generates a constructor accepting these as parameters
- Keeps classes pure - they can be instantiated manually

## Manual Instantiation

Classes using `Injectable` remain container-agnostic:

```python
my_db = Database()
my_logger = Logger()
service = UserService(database=my_db, logger=my_logger)
```

## With Named Dependencies

```python
from inversipy import Injectable, Inject, Named

class DataService(Injectable):
    primary_db: Inject[IDatabase, Named("primary")]
    backup_db: Inject[IDatabase, Named("backup")]
```

## With Collection Injection

```python
from inversipy import Injectable, InjectAll

class PluginManager(Injectable):
    plugins: InjectAll[IPlugin]

    def run_all(self) -> list[str]:
        return [plugin.execute() for plugin in self.plugins]
```
