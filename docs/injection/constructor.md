# Constructor Injection

The primary injection mechanism. The container analyzes `__init__` type hints and resolves dependencies automatically.

```python
from inversipy import Container

class Database:
    def query(self, sql: str) -> list:
        return []

class UserRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

container = Container()
container.register(Database)
container.register(UserRepository)

repo = container.get(UserRepository)  # Database injected automatically
```

Classes remain completely framework-agnostic. They can be instantiated manually:

```python
db = Database()
repo = UserRepository(db=db)
```
