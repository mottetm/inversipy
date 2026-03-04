"""FastAPI integration example for inversipy.

This example demonstrates:
- Setting up a container with FastAPI
- Using @inject decorator for route handlers
- Request-scoped dependencies
- Dependency injection in async routes

Note: This example requires FastAPI to be installed:
    pip install fastapi

To run this example:
    uvicorn examples.fastapi_example:app --reload
"""

try:
    from fastapi import FastAPI

    from inversipy import Container, Scopes
    from inversipy.decorators import Inject
    from inversipy.fastapi import bind, inject

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available. Install with: pip install fastapi")


if FASTAPI_AVAILABLE:

    # Domain services
    class Logger:
        """Logger service for request logging."""

        def __init__(self) -> None:
            self.logs: list[str] = []

        def log(self, message: str) -> None:
            """Log a message."""
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
            """Get all users."""
            self.logger.log("Fetching all users")
            return self.data["users"]

        def get_user_by_id(self, user_id: int) -> dict[str, str | int] | None:
            """Get a user by ID."""
            self.logger.log(f"Fetching user {user_id}")
            for user in self.data["users"]:
                if user["id"] == user_id:
                    return user
            return None

    class RequestContext:
        """Request-scoped context for tracking request metadata."""

        def __init__(self) -> None:
            self.request_count = 0
            self.request_id = ""

        def set_request_id(self, request_id: str) -> None:
            """Set the current request ID."""
            self.request_id = request_id

        def increment(self) -> int:
            """Increment and return request count."""
            self.request_count += 1
            return self.request_count

    class UserService:
        """Service layer for user operations."""

        def __init__(self, db: Database, logger: Logger, context: RequestContext) -> None:
            self.db = db
            self.logger = logger
            self.context = context

        def list_users(self) -> list[dict[str, str | int]]:
            """List all users."""
            count = self.context.increment()
            self.logger.log(f"Request #{count}: Listing users")
            return self.db.get_users()

        def find_user(self, user_id: int) -> dict[str, str | int] | None:
            """Find a user by ID."""
            count = self.context.increment()
            self.logger.log(f"Request #{count}: Finding user {user_id}")
            return self.db.get_user_by_id(user_id)

    # Setup FastAPI app
    app = FastAPI(title="Inversipy FastAPI Example")

    # Setup container
    container = Container()
    container.register(Logger, scope=Scopes.SINGLETON)
    container.register(Database, scope=Scopes.SINGLETON)
    container.register(RequestContext, scope=Scopes.REQUEST)
    container.register(UserService, scope=Scopes.REQUEST)

    # Bind container to app
    bind(app, container)

    # Routes using @inject decorator
    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint."""
        return {"message": "Inversipy FastAPI Example", "docs": "/docs"}

    @app.get("/users")
    @inject
    async def get_users(
        service: Inject[UserService],
        limit: int = 10,
    ) -> dict[str, list[dict[str, str | int]]]:
        """Get all users with injected UserService.

        Args:
            service: Injected UserService (from container)
            limit: Query parameter (from FastAPI)

        Returns:
            Dictionary with users list
        """
        users = service.list_users()
        return {"users": users[:limit]}

    @app.get("/users/{user_id}")
    @inject
    async def get_user(
        user_id: int,
        service: Inject[UserService],
    ) -> dict[str, dict[str, str | int] | str]:
        """Get a specific user.

        Args:
            user_id: Path parameter (from FastAPI)
            service: Injected UserService (from container)

        Returns:
            Dictionary with user data or error message
        """
        user = service.find_user(user_id)
        if user is None:
            return {"error": "User not found"}
        return {"user": user}

    @app.get("/stats")
    @inject
    async def get_stats(
        logger: Inject[Logger],
        db: Inject[Database],
    ) -> dict[str, int]:
        """Get statistics about the application.

        Args:
            logger: Injected Logger (singleton)
            db: Injected Database (singleton)

        Returns:
            Statistics dictionary
        """
        return {
            "total_users": len(db.get_users()),
            "total_logs": len(logger.logs),
        }

    # Example showing multiple injections
    @app.post("/users/{user_id}/activity")
    @inject
    async def log_activity(
        user_id: int,
        service: Inject[UserService],
        logger: Inject[Logger],
        context: Inject[RequestContext],
        activity: str = "viewed",
    ) -> dict[str, str]:
        """Log user activity.

        Args:
            user_id: Path parameter
            service: Injected UserService
            logger: Injected Logger
            context: Injected RequestContext
            activity: Query parameter

        Returns:
            Success message
        """
        user = service.find_user(user_id)
        if user is None:
            return {"error": "User not found"}

        logger.log(f"User {user_id} {activity} (request count: {context.request_count})")
        return {"message": f"Activity logged for user {user_id}"}


def main() -> None:
    """Main function to demonstrate the example."""
    if not FASTAPI_AVAILABLE:
        print("This example requires FastAPI.")
        print("Install with: pip install fastapi uvicorn")
        return

    print("\n=== FastAPI Integration Example ===")
    print("\nTo run this example:")
    print("  uvicorn examples.fastapi_example:app --reload")
    print("\nThen visit:")
    print("  http://localhost:8000/docs - Interactive API documentation")
    print("  http://localhost:8000/users - Get all users")
    print("  http://localhost:8000/users/1 - Get user by ID")
    print("  http://localhost:8000/stats - Get statistics")
    print("\n✓ FastAPI app is configured and ready")


if __name__ == "__main__":
    main()
