"""Flask integration example for inversipy.

This example demonstrates:
- Setting up a container with Flask
- Using @inject decorator for route handlers
- Dependency injection with path parameters

Note: This example requires Flask to be installed:
    pip install flask

To run this example:
    flask --app examples.flask_example run
"""

try:
    from flask import Flask

    from inversipy import Container, Scopes
    from inversipy.decorators import Inject
    from inversipy.flask import bind, inject

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("Flask not available. Install with: pip install flask")


if FLASK_AVAILABLE:

    class Logger:
        """Logger service for request logging."""

        def __init__(self) -> None:
            self.logs: list[str] = []

        def log(self, message: str) -> None:
            self.logs.append(message)
            print(f"[LOG] {message}")

    class Database:
        """Database service for data access."""

        def __init__(self, logger: Logger) -> None:
            self.logger = logger
            self.data = {
                "users": [
                    {"id": 1, "name": "Alice", "email": "alice@example.com"},
                    {"id": 2, "name": "Bob", "email": "bob@example.com"},
                    {"id": 3, "name": "Charlie", "email": "charlie@example.com"},
                ]
            }
            self.logger.log("Database initialized")

        def get_users(self) -> list[dict[str, str | int]]:
            self.logger.log("Fetching all users")
            return self.data["users"]

        def get_user_by_id(self, user_id: int) -> dict[str, str | int] | None:
            self.logger.log(f"Fetching user {user_id}")
            for user in self.data["users"]:
                if user["id"] == user_id:
                    return user
            return None

    class UserService:
        """Service layer for user operations."""

        def __init__(self, db: Database, logger: Logger) -> None:
            self.db = db
            self.logger = logger

        def list_users(self) -> list[dict[str, str | int]]:
            return self.db.get_users()

        def find_user(self, user_id: int) -> dict[str, str | int] | None:
            return self.db.get_user_by_id(user_id)

    # Setup Flask app
    app = Flask(__name__)

    # Setup container
    container = Container()
    container.register(Logger, scope=Scopes.SINGLETON)
    container.register(Database, scope=Scopes.SINGLETON)
    container.register(UserService)

    # Bind container to app
    bind(app, container)

    @app.route("/")
    def root() -> dict[str, str]:
        return {"message": "Inversipy Flask Example"}

    @app.route("/users")
    @inject
    def get_users(service: Inject[UserService]) -> dict[str, list[dict[str, str | int]]]:
        return {"users": service.list_users()}

    @app.route("/users/<int:user_id>")
    @inject
    def get_user(user_id: int, service: Inject[UserService]) -> dict[str, object]:
        user = service.find_user(user_id)
        if user is None:
            return {"error": "User not found"}
        return {"user": user}


def main() -> None:
    if not FLASK_AVAILABLE:
        print("This example requires Flask.")
        print("Install with: pip install flask")
        return

    print("\n=== Flask Integration Example ===")
    print("\nTo run this example:")
    print("  flask --app examples.flask_example run")


if __name__ == "__main__":
    main()
