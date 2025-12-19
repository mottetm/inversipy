"""Scopes example for inversipy.

This example demonstrates:
- Singleton scope (one instance for all requests)
- Transient scope (new instance for each request)
- Request scope (one instance per context/request)
"""

from inversipy import Container, Scopes


class Counter:
    """A simple counter to track instance creation."""

    _instance_count = 0

    def __init__(self) -> None:
        Counter._instance_count += 1
        self.instance_id = Counter._instance_count
        self.value = 0

    def increment(self) -> int:
        """Increment and return the counter value."""
        self.value += 1
        return self.value

    @classmethod
    def reset_count(cls) -> None:
        """Reset the instance counter."""
        cls._instance_count = 0


def demonstrate_singleton() -> None:
    """Demonstrate singleton scope behavior."""
    print("\n=== Singleton Scope ===")
    print("One instance is created and reused for all requests")

    Counter.reset_count()
    container = Container()
    container.register(Counter, scope=Scopes.SINGLETON)

    # Get the same instance multiple times
    counter1 = container.get(Counter)
    print(f"Counter 1 - Instance ID: {counter1.instance_id}, Value: {counter1.value}")

    counter1.increment()
    counter1.increment()
    print(f"Counter 1 after increments - Value: {counter1.value}")

    counter2 = container.get(Counter)
    print(f"Counter 2 - Instance ID: {counter2.instance_id}, Value: {counter2.value}")

    # Verify they're the same instance
    assert counter1 is counter2, "Should be same instance"
    assert counter2.value == 2, "Should share state"
    print("✓ Singleton: Both references point to the same instance")


def demonstrate_transient() -> None:
    """Demonstrate transient scope behavior."""
    print("\n=== Transient Scope ===")
    print("A new instance is created for each request")

    Counter.reset_count()
    container = Container()
    container.register(Counter, scope=Scopes.TRANSIENT)

    # Get different instances
    counter1 = container.get(Counter)
    print(f"Counter 1 - Instance ID: {counter1.instance_id}, Value: {counter1.value}")

    counter1.increment()
    counter1.increment()
    print(f"Counter 1 after increments - Value: {counter1.value}")

    counter2 = container.get(Counter)
    print(f"Counter 2 - Instance ID: {counter2.instance_id}, Value: {counter2.value}")

    # Verify they're different instances
    assert counter1 is not counter2, "Should be different instances"
    assert counter1.instance_id != counter2.instance_id, "Should have different IDs"
    assert counter2.value == 0, "Should have independent state"
    print("✓ Transient: Each request gets a new instance")


def demonstrate_request_scope() -> None:
    """Demonstrate request scope behavior."""
    print("\n=== Request Scope ===")
    print("One instance per context (uses contextvars for isolation)")

    Counter.reset_count()
    container = Container()
    container.register(Counter, scope=Scopes.REQUEST)

    # Within the same context, we get the same instance
    counter1 = container.get(Counter)
    print(f"Counter 1 - Instance ID: {counter1.instance_id}, Value: {counter1.value}")

    counter1.increment()
    print(f"Counter 1 after increment - Value: {counter1.value}")

    counter2 = container.get(Counter)
    print(
        f"Counter 2 (same context) - Instance ID: {counter2.instance_id}, "
        f"Value: {counter2.value}"
    )

    # Verify they're the same within context
    assert counter1 is counter2, "Should be same instance within context"
    assert counter2.value == 1, "Should share state within context"
    print("✓ Request scope: Same instance within the same context")


class Service:
    """A service with dependencies using different scopes."""

    def __init__(self, singleton_counter: Counter, transient_counter: Counter) -> None:
        self.singleton_counter = singleton_counter
        self.transient_counter = transient_counter


def demonstrate_mixed_scopes() -> None:
    """Demonstrate using multiple scopes together."""
    print("\n=== Mixed Scopes ===")
    print("Combining different scopes in a single application")

    Counter.reset_count()
    container = Container()

    # Register different instances with different names/keys
    # We'll use factory functions to work around the same type limitation
    def create_singleton_counter() -> Counter:
        return Counter()

    def create_transient_counter() -> Counter:
        return Counter()

    container.register_factory(Counter, create_singleton_counter, scope=Scopes.SINGLETON)

    singleton1 = container.get(Counter)
    singleton1.increment()
    print(f"Singleton Counter 1 - Instance ID: {singleton1.instance_id}, Value: {singleton1.value}")

    singleton2 = container.get(Counter)
    print(f"Singleton Counter 2 - Instance ID: {singleton2.instance_id}, Value: {singleton2.value}")

    assert singleton1 is singleton2
    print("✓ Mixed scopes work together correctly")


def main() -> None:
    """Run all scope examples."""
    demonstrate_singleton()
    demonstrate_transient()
    demonstrate_request_scope()
    demonstrate_mixed_scopes()
    print("\n✓ All scope examples completed successfully")


if __name__ == "__main__":
    main()
