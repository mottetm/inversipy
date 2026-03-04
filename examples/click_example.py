"""Click integration example for inversipy.

This example demonstrates:
- Setting up a container with Click using pass_container
- Using @inject decorator for CLI commands
- Using @with_modules for domain-specific module registration
- Mixing Click options/arguments with injected services

Note: This example requires Click to be installed:
    pip install click

To run this example:
    python examples/click_example.py --help
    python examples/click_example.py greet --name Alice
    python examples/click_example.py admin create-user admin_user
"""

try:
    import click

    from inversipy import Container
    from inversipy.click import inject, pass_container, with_modules
    from inversipy.decorators import Inject
    from inversipy.module import Module

    CLICK_AVAILABLE = True
except ImportError:
    CLICK_AVAILABLE = False
    print("Click not available. Install with: pip install click")


if CLICK_AVAILABLE:

    # Domain services
    class Logger:
        """Logger service."""

        def __init__(self) -> None:
            self.logs: list[str] = []

        def log(self, message: str) -> None:
            self.logs.append(message)
            click.echo(f"[LOG] {message}")

    class Database:
        """Database service."""

        def __init__(self) -> None:
            self.users = ["Alice", "Bob", "Charlie"]

        def get_users(self) -> list[str]:
            return self.users

        def add_user(self, name: str) -> None:
            self.users.append(name)

    class AuthService:
        """Auth service provided by the auth module."""

        def check_admin(self, user: str) -> bool:
            return user in ("admin", "root")

    # Setup container with base services
    container = Container()
    container.register(Logger)
    container.register(Database)

    # Auth module for admin commands
    auth_module = Module("auth")
    auth_module.register(AuthService, public=True)

    # CLI definition
    @click.group()
    @pass_container(container)
    def cli() -> None:
        """Inversipy Click integration example."""
        pass

    @cli.command()
    @click.option("--name", default="World", help="Name to greet.")
    @inject
    def greet(name: str, logger: Inject[Logger]) -> None:
        """Greet someone with injected logging."""
        logger.log(f"Greeting {name}")
        click.echo(f"Hello, {name}!")

    @cli.command()
    @inject
    def list_users(db: Inject[Database], logger: Inject[Logger]) -> None:
        """List all users from the injected database."""
        logger.log("Listing users")
        for user in db.get_users():
            click.echo(f"  - {user}")

    # Admin group with auth module
    @cli.group()
    @with_modules(auth_module)
    def admin() -> None:
        """Admin commands (with auth module)."""
        pass

    @admin.command()
    @click.argument("username")
    @inject
    def create_user(
        username: str,
        db: Inject[Database],
        auth: Inject[AuthService],
        logger: Inject[Logger],
    ) -> None:
        """Create a new user (admin only)."""
        logger.log(f"Creating user: {username}")
        db.add_user(username)
        click.echo(f"User '{username}' created. Total users: {len(db.get_users())}")


def main() -> None:
    if not CLICK_AVAILABLE:
        print("This example requires Click.")
        print("Install with: pip install click")
        return

    cli()


if __name__ == "__main__":
    main()
