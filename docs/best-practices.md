# Best Practices

1. **Validate early** - Call `container.validate()` at application startup to catch configuration errors before runtime.

2. **Freeze after configuration** - Call `container.freeze()` after all registrations to prevent accidental modifications.

3. **Use scopes appropriately**:
    - `SINGLETON` for expensive resources (database connections, caches)
    - `TRANSIENT` for stateful services (request handlers, commands)
    - `REQUEST` for request-scoped resources (in web applications)

4. **Organize with modules** - Group related dependencies into modules with clear public interfaces.

5. **Prefer constructor injection** - Use type-annotated constructors for dependency injection. It's the simplest and most portable approach.

6. **Use interfaces** - Register interfaces and bind to implementations for better testability.

7. **Child containers for isolation** - Use child containers for request-scoped or test-specific dependencies.

8. **Use `T | None` for soft dependencies** - Mark optional dependencies with `T | None` to avoid hard failures when a service is unavailable.
