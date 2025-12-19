"""Dependency injection patterns example for inversipy.

This example demonstrates:
- Pure class registration without decorators
- Using Injectable base class for property injection
- Using Container.run() for function injection
- Proper separation of concerns - classes remain container-agnostic
"""

from typing import Annotated

from inversipy import Container, Inject, Injectable, Scopes


# Pure classes - no coupling to container
class Logger:
    """Logger service - pure class."""

    def __init__(self) -> None:
        self.logs: list[str] = []

    def log(self, message: str) -> None:
        """Log a message."""
        self.logs.append(message)
        print(f"[LOG] {message}")


class Database:
    """Database service - pure class."""

    def __init__(self, logger: Logger) -> None:
        self.logger = logger
        self.logger.log("Database initialized")

    def query(self, sql: str) -> list[str]:
        """Execute a query."""
        self.logger.log(f"Executing: {sql}")
        return [f"Result: {sql}"]


class RequestHandler:
    """Request handler - pure class."""

    def __init__(self, db: Database, logger: Logger) -> None:
        self.db = db
        self.logger = logger
        self.logger.log("RequestHandler created")

    def handle(self, request: str) -> list[str]:
        """Handle a request."""
        self.logger.log(f"Handling request: {request}")
        return self.db.query(f"SELECT * FROM {request}")


def demonstrate_pure_registration() -> None:
    """Demonstrate pure registration without decorators."""
    print("\n=== Pure Registration ===")
    print("Classes remain pure - container stays in infrastructure layer")

    # Container configuration stays separate from implementation
    container = Container()
    container.register(Logger, scope=Scopes.SINGLETON)
    container.register(Database, scope=Scopes.SINGLETON)
    container.register(RequestHandler, scope=Scopes.TRANSIENT)

    # Get instances - they're registered via pure registration
    handler1 = container.get(RequestHandler)
    result = handler1.handle("users")
    print(f"✓ Handler 1 result: {result}")

    handler2 = container.get(RequestHandler)
    print(f"✓ Handler 2 created (transient)")

    # Verify transient behavior
    assert handler1 is not handler2, "Handlers should be different (transient)"
    print("✓ Transient scope works correctly")

    # Verify singleton behavior
    logger1 = container.get(Logger)
    logger2 = container.get(Logger)
    assert logger1 is logger2, "Loggers should be same (singleton)"
    print("✓ Singleton scope works correctly")


# Pure function for processing - no decorator needed
def process_request(handler: RequestHandler, logger: Logger, request_id: str = "default") -> list[str]:
    """Process a request with dependencies.

    Args:
        handler: RequestHandler dependency
        logger: Logger dependency
        request_id: Regular parameter (not injected)

    Returns:
        Query results
    """
    logger.log(f"Processing request {request_id}")
    return handler.handle("orders")


def demonstrate_function_injection() -> None:
    """Demonstrate Container.run() for function injection."""
    print("\n=== Function Injection ===")
    print("Using container.run() to inject dependencies into pure functions")

    container = Container()
    container.register(Logger, scope=Scopes.SINGLETON)
    container.register(Database, scope=Scopes.SINGLETON)
    container.register(RequestHandler, scope=Scopes.TRANSIENT)

    # Use container.run() - function stays pure
    result = container.run(process_request, request_id="REQ-001")
    print(f"✓ Function injection result: {result}")

    # Can also call with explicit arguments
    handler = container.get(RequestHandler)
    logger = container.get(Logger)
    result = process_request(handler, logger, "REQ-002")
    print(f"✓ Function with explicit args: {result}")


# Property injection with Injectable base class - classes stay pure
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
    """Another service using Injectable - still a pure class."""

    database: Annotated[Database, Inject]
    logger: Annotated[Logger, Inject]

    def __init__(self) -> None:
        """Custom init for additional properties."""
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

    container = Container()
    container.register(Logger, scope=Scopes.SINGLETON)
    container.register(Database, scope=Scopes.SINGLETON)

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

    # Classes remain pure - can be instantiated manually
    manual_db = Database(Logger())
    manual_logger = Logger()
    manual_service = UserService(database=manual_db, logger=manual_logger)
    print("✓ Classes can be instantiated manually (remain pure)")


class CacheService(Injectable):
    """Service using Injectable - pure class, registered as singleton."""

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


def demonstrate_combined_patterns() -> None:
    """Demonstrate combining patterns."""
    print("\n=== Combined Patterns ===")
    print("Combining Injectable with explicit scope registration")

    container = Container()
    container.register(Logger, scope=Scopes.SINGLETON)

    # Register Injectable class with specific scope
    container.register(CacheService, scope=Scopes.SINGLETON)

    cache = container.get(CacheService)
    cache.set("user:1", "John")
    value = cache.get("user:1")
    print(f"✓ Combined patterns result: {value}")

    # Verify singleton
    cache2 = container.get(CacheService)
    assert cache is cache2, "Should be singleton"
    assert cache2.get("user:1") == "John", "Should share state"
    print("✓ Combined patterns work correctly")


def main() -> None:
    """Run all examples."""
    demonstrate_pure_registration()
    demonstrate_function_injection()
    demonstrate_property_injection()
    demonstrate_combined_patterns()
    print("\n✓ All examples completed successfully")
    print("\nKey takeaways:")
    print("- Classes remain pure and container-agnostic")
    print("- Container.run() provides function injection without decorators")
    print("- Injectable base class enables property injection while keeping classes pure")
    print("- Container stays in infrastructure layer, not in implementation")


if __name__ == "__main__":
    main()
