"""Decorators example for inversipy.

This example demonstrates:
- Using @singleton and @transient decorators for registration
- Using @inject decorator for function injection
- Using Injectable base class for property injection
- Using Inject marker for annotated property injection
"""

from typing import Annotated

from inversipy import Container, Inject, Injectable, inject, singleton, transient


# Basic decorator registration
container = Container()


@singleton(container)
class Logger:
    """Logger service registered as singleton."""

    def __init__(self) -> None:
        self.logs: list[str] = []

    def log(self, message: str) -> None:
        """Log a message."""
        self.logs.append(message)
        print(f"[LOG] {message}")


@singleton(container)
class Database:
    """Database service registered as singleton."""

    def __init__(self, logger: Logger) -> None:
        self.logger = logger
        self.logger.log("Database initialized")

    def query(self, sql: str) -> list[str]:
        """Execute a query."""
        self.logger.log(f"Executing: {sql}")
        return [f"Result: {sql}"]


@transient(container)
class RequestHandler:
    """Request handler registered as transient."""

    def __init__(self, db: Database, logger: Logger) -> None:
        self.db = db
        self.logger = logger
        self.logger.log("RequestHandler created")

    def handle(self, request: str) -> list[str]:
        """Handle a request."""
        self.logger.log(f"Handling request: {request}")
        return self.db.query(f"SELECT * FROM {request}")


def demonstrate_decorator_registration() -> None:
    """Demonstrate decorator-based registration."""
    print("\n=== Decorator Registration ===")
    print("Using @singleton and @transient decorators")

    # Get instances - they're already registered via decorators
    handler1 = container.get(RequestHandler)
    result = handler1.handle("users")
    print(f"✓ Handler 1 result: {result}")

    handler2 = container.get(RequestHandler)
    print(f"✓ Handler 2 created (transient)")

    # Verify transient behavior
    assert handler1 is not handler2, "Handlers should be different (transient)"
    print("✓ Transient decorator works correctly")

    # Verify singleton behavior
    logger1 = container.get(Logger)
    logger2 = container.get(Logger)
    assert logger1 is logger2, "Loggers should be same (singleton)"
    print("✓ Singleton decorator works correctly")


# Function injection
@inject(container)
def process_request(handler: RequestHandler, logger: Logger, request_id: str = "default") -> list[str]:
    """Process a request with injected dependencies.

    Args:
        handler: Injected RequestHandler
        logger: Injected Logger
        request_id: Regular parameter (not injected)

    Returns:
        Query results
    """
    logger.log(f"Processing request {request_id}")
    return handler.handle("orders")


def demonstrate_function_injection() -> None:
    """Demonstrate @inject decorator for functions."""
    print("\n=== Function Injection ===")
    print("Using @inject to inject dependencies into functions")

    # Call without providing injected parameters
    result = process_request(request_id="REQ-001")
    print(f"✓ Function injection result: {result}")

    # Can also call with explicit arguments
    handler = container.get(RequestHandler)
    logger = container.get(Logger)
    result = process_request(handler, logger, "REQ-002")
    print(f"✓ Function with explicit args: {result}")


# Property injection with Injectable base class
class UserService(Injectable):
    """Service using Injectable base class for property injection."""

    # Properties marked with Annotated[Type, Inject] are automatically injected
    database: Annotated[Database, Inject]
    logger: Annotated[Logger, Inject]

    def get_users(self) -> list[str]:
        """Get all users."""
        self.logger.log("Fetching all users")
        return self.database.query("SELECT * FROM users")

    def get_user(self, user_id: int) -> str:
        """Get a specific user."""
        self.logger.log(f"Fetching user {user_id}")
        results = self.database.query(f"SELECT * FROM users WHERE id = {user_id}")
        return results[0] if results else "Not found"


class OrderService(Injectable):
    """Another service using Injectable."""

    database: Annotated[Database, Inject]
    logger: Annotated[Logger, Inject]

    # Can also have regular properties
    def __init__(self) -> None:
        self.order_count = 0

    def create_order(self, product: str) -> str:
        """Create an order."""
        self.order_count += 1
        self.logger.log(f"Creating order #{self.order_count} for {product}")
        self.database.query(f"INSERT INTO orders (product) VALUES ('{product}')")
        return f"Order #{self.order_count} created"


def demonstrate_property_injection() -> None:
    """Demonstrate Injectable base class for property injection."""
    print("\n=== Property Injection ===")
    print("Using Injectable base class with Annotated[Type, Inject]")

    # Register services using Injectable
    container.register(UserService)
    container.register(OrderService)

    # Get and use UserService
    user_service = container.get(UserService)
    users = user_service.get_users()
    print(f"✓ UserService result: {users}")

    user = user_service.get_user(42)
    print(f"✓ UserService get_user: {user}")

    # Get and use OrderService
    order_service = container.get(OrderService)
    order = order_service.create_order("Widget")
    print(f"✓ OrderService result: {order}")

    # Verify properties were injected
    assert user_service.database is not None, "Database should be injected"
    assert user_service.logger is not None, "Logger should be injected"
    print("✓ Property injection works correctly")

    # Verify singleton dependencies are shared
    assert user_service.database is order_service.database, "Should share database"
    print("✓ Injected singletons are shared correctly")


# Combining decorators
@singleton(container)
class CacheService(Injectable):
    """Service combining @singleton decorator with Injectable."""

    logger: Annotated[Logger, Inject]

    def __init__(self) -> None:
        self.cache: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        """Get a cached value."""
        value = self.cache.get(key)
        self.logger.log(f"Cache {'hit' if value else 'miss'} for key: {key}")
        return value

    def set(self, key: str, value: str) -> None:
        """Set a cached value."""
        self.cache[key] = value
        self.logger.log(f"Cache set: {key} = {value}")


def demonstrate_combined_decorators() -> None:
    """Demonstrate combining decorators."""
    print("\n=== Combined Decorators ===")
    print("Using @singleton with Injectable base class")

    cache = container.get(CacheService)
    cache.set("user:1", "John")
    value = cache.get("user:1")
    print(f"✓ Combined decorators result: {value}")

    # Verify singleton
    cache2 = container.get(CacheService)
    assert cache is cache2, "Should be singleton"
    assert cache2.get("user:1") == "John", "Should share state"
    print("✓ Combined decorators work correctly")


def main() -> None:
    """Run all decorator examples."""
    demonstrate_decorator_registration()
    demonstrate_function_injection()
    demonstrate_property_injection()
    demonstrate_combined_decorators()
    print("\n✓ All decorator examples completed successfully")


if __name__ == "__main__":
    main()
