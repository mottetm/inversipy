"""Modules example for inversipy.

This example demonstrates:
- Creating modules with public/private dependencies
- Using ModuleBuilder for fluent API
- Composing modules together
- Registering modules with containers
"""

from inversipy import Container, Module, ModuleBuilder, Scopes


# Database layer classes
class DatabaseConnection:
    """Internal database connection (should be private)."""

    def __init__(self) -> None:
        self.connected = True

    def execute(self, query: str) -> list[str]:
        """Execute a database query."""
        return [f"DB result: {query}"]


class QueryBuilder:
    """Internal query builder (should be private)."""

    def __init__(self) -> None:
        self.query_count = 0

    def build_select(self, table: str) -> str:
        """Build a SELECT query."""
        self.query_count += 1
        return f"SELECT * FROM {table}"


class Database:
    """Public database interface."""

    def __init__(self, connection: DatabaseConnection, query_builder: QueryBuilder) -> None:
        self.connection = connection
        self.query_builder = query_builder

    def query(self, table: str) -> list[str]:
        """Query a table."""
        sql = self.query_builder.build_select(table)
        return self.connection.execute(sql)


class UserRepository:
    """Public repository for user data."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def get_users(self) -> list[str]:
        """Fetch all users."""
        return self.db.query("users")


# Authentication layer classes
class TokenValidator:
    """Internal token validator (should be private)."""

    def validate(self, token: str) -> bool:
        """Validate a token."""
        return len(token) > 0


class AuthService:
    """Public authentication service."""

    def __init__(self, validator: TokenValidator) -> None:
        self.validator = validator

    def authenticate(self, token: str) -> bool:
        """Authenticate a user with a token."""
        return self.validator.validate(token)


# Application service that uses both modules
class AppService:
    """Application service that uses database and auth."""

    def __init__(self, db: Database, auth: AuthService) -> None:
        self.db = db
        self.auth = auth

    def get_authenticated_users(self, token: str) -> list[str]:
        """Get users if authenticated."""
        if self.auth.authenticate(token):
            return self.db.query("users")
        return []


def demonstrate_basic_module() -> None:
    """Demonstrate basic module with public/private dependencies."""
    print("\n=== Basic Module ===")
    print("Creating a module with public and private dependencies")

    # Create database module
    db_module = Module("Database")

    # Register private dependencies (default is private)
    db_module.register(DatabaseConnection, scope=Scopes.SINGLETON)
    db_module.register(QueryBuilder, scope=Scopes.SINGLETON)

    # Register public dependencies
    db_module.register(Database, scope=Scopes.SINGLETON, public=True)
    db_module.register(UserRepository, public=True)

    # Or use export to make dependencies public
    db_module.export(Database, UserRepository)

    # Register module in container
    container = Container()
    container.register_module(db_module)

    # Can access public dependencies
    database = container.get(Database)
    users = database.query("users")
    print(f"✓ Accessed public Database: {users}")

    user_repo = container.get(UserRepository)
    users = user_repo.get_users()
    print(f"✓ Accessed public UserRepository: {users}")

    # Cannot access private dependencies
    try:
        container.get(DatabaseConnection)
        print("✗ Should not be able to access private DatabaseConnection")
    except Exception:
        print("✓ Private DatabaseConnection is not accessible")


def demonstrate_module_builder() -> None:
    """Demonstrate using ModuleBuilder for fluent API."""
    print("\n=== Module Builder ===")
    print("Using ModuleBuilder for a fluent configuration API")

    # Create module using builder
    db_module = (
        ModuleBuilder("Database")
        .bind(DatabaseConnection, scope=Scopes.SINGLETON)  # Private
        .bind(QueryBuilder, scope=Scopes.SINGLETON)  # Private
        .bind_public(Database, scope=Scopes.SINGLETON)  # Public
        .bind_public(UserRepository)  # Public
        .build()
    )

    container = Container()
    container.register_module(db_module)

    # Access public dependencies
    database = container.get(Database)
    users = database.query("users")
    print(f"✓ ModuleBuilder works correctly: {users}")


def demonstrate_module_composition() -> None:
    """Demonstrate composing multiple modules."""
    print("\n=== Module Composition ===")
    print("Composing multiple modules together")

    # Create database module
    db_module = Module("Database")
    db_module.register(DatabaseConnection, scope=Scopes.SINGLETON)
    db_module.register(QueryBuilder, scope=Scopes.SINGLETON)
    db_module.register(Database, scope=Scopes.SINGLETON, public=True)

    # Create auth module
    auth_module = Module("Auth")
    auth_module.register(TokenValidator)  # Private
    auth_module.register(AuthService, public=True)  # Public

    # Create app module that composes both
    app_module = Module("App")
    app_module.register_module(db_module)
    app_module.register_module(auth_module)
    app_module.register(AppService, public=True)

    # Register app module in container
    container = Container()
    container.register_module(app_module)

    # Can access all public dependencies
    app_service = container.get(AppService)
    users = app_service.get_authenticated_users("valid-token")
    print(f"✓ Composed modules work together: {users}")

    # Can access public dependencies from nested modules
    database = container.get(Database)
    print(f"✓ Can access Database from composed db_module: {database.query('users')}")

    auth_service = container.get(AuthService)
    print(f"✓ Can access AuthService from composed auth_module: {auth_service.authenticate('token')}")


def demonstrate_dynamic_module_updates() -> None:
    """Demonstrate that modules remain live and can be updated."""
    print("\n=== Dynamic Module Updates ===")
    print("Modules are live providers - changes reflect in the container")

    db_module = Module("Database")
    db_module.register(DatabaseConnection, scope=Scopes.SINGLETON)
    db_module.register(Database, scope=Scopes.SINGLETON, public=True)

    container = Container()
    container.register_module(db_module)

    # Access initial public dependency
    database = container.get(Database)
    print(f"✓ Initial Database access: {database.query('users')}")

    # Add new public dependency to module after registration
    db_module.register(UserRepository, public=True)

    # New dependency is immediately available
    user_repo = container.get(UserRepository)
    print(f"✓ Dynamically added UserRepository: {user_repo.get_users()}")


def main() -> None:
    """Run all module examples."""
    demonstrate_basic_module()
    demonstrate_module_builder()
    demonstrate_module_composition()
    demonstrate_dynamic_module_updates()
    print("\n✓ All module examples completed successfully")


if __name__ == "__main__":
    main()
