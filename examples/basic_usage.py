"""Basic usage example for inversipy.

This example demonstrates:
- Creating a container
- Registering dependencies
- Resolving dependencies with automatic constructor injection
- Using container validation
"""

from inversipy import Container, Scopes


# Define service classes
class Database:
    """Simulates a database connection."""

    def __init__(self) -> None:
        self.connected = True

    def query(self, sql: str) -> list[str]:
        """Execute a query and return results."""
        return [f"Result for: {sql}"]


class UserRepository:
    """Repository for user data access."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def get_users(self) -> list[str]:
        """Fetch all users from the database."""
        return self.db.query("SELECT * FROM users")

    def get_user_by_id(self, user_id: int) -> str:
        """Fetch a specific user by ID."""
        results = self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
        return results[0] if results else "User not found"


class UserService:
    """Service layer for user operations."""

    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def list_users(self) -> list[str]:
        """List all users."""
        return self.repo.get_users()

    def find_user(self, user_id: int) -> str:
        """Find a user by ID."""
        return self.repo.get_user_by_id(user_id)


def main() -> None:
    """Run the basic usage example."""
    # Create a container
    container = Container()

    # Register dependencies - the container will automatically resolve dependencies
    # Database has no dependencies, so it can be created directly
    container.register(Database, scope=Scopes.SINGLETON)

    # UserRepository depends on Database - will be injected automatically
    container.register(UserRepository, scope=Scopes.SINGLETON)

    # UserService depends on UserRepository - will be injected automatically
    container.register(UserService, scope=Scopes.SINGLETON)

    # Validate the container (optional but recommended)
    # This checks that all dependencies can be resolved
    container.validate()
    print("✓ Container validation passed")

    # Resolve the UserService - all dependencies are automatically injected
    service = container.get(UserService)

    # Use the service
    users = service.list_users()
    print(f"✓ Users: {users}")

    user = service.find_user(1)
    print(f"✓ User 1: {user}")

    # Verify singleton behavior - same instance is returned
    service2 = container.get(UserService)
    assert service is service2, "Singleton scope should return same instance"
    print("✓ Singleton scope verified")


if __name__ == "__main__":
    main()
