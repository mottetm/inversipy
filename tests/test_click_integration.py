"""Tests for Click integration."""

import pytest

# Check if Click is available
pytest.importorskip("click", reason="Click not installed")

import click
from click.testing import CliRunner

from inversipy import Container
from inversipy.click import CONTAINER_KEY, inject, pass_container, with_modules
from inversipy.decorators import Inject, InjectAll, Named
from inversipy.module import Module


class Database:
    """Mock database service."""

    def query(self, sql: str) -> list[str]:
        return ["user1", "user2", "user3"]


class Logger:
    """Mock logger service."""

    def __init__(self) -> None:
        self.logs: list[str] = []

    def info(self, message: str) -> None:
        self.logs.append(message)


class IPlugin:
    """Plugin interface."""

    name: str = "base"


class PluginA(IPlugin):
    name = "plugin_a"


class PluginB(IPlugin):
    name = "plugin_b"


class AuthService:
    """Mock auth service for module tests."""

    def login(self, user: str) -> str:
        return f"logged in as {user}"


class TestClickInject:
    """Test Click @inject decorator."""

    def test_inject_with_single_dependency(self) -> None:
        container = Container()
        container.register(Database)

        @click.command()
        @inject
        def cmd(db: Inject[Database]):
            click.echo(db.query("SELECT 1")[0])

        @click.group()
        @pass_container(container)
        def cli():
            pass

        cli.add_command(cmd)

        runner = CliRunner()
        result = runner.invoke(cli, ["cmd"])
        assert result.exit_code == 0
        assert "user1" in result.output

    def test_inject_with_multiple_dependencies(self) -> None:
        container = Container()
        container.register(Database)
        container.register(Logger)

        @click.command()
        @inject
        def cmd(db: Inject[Database], logger: Inject[Logger]):
            logger.info("test")
            click.echo(f"users={len(db.query(''))},logs={len(logger.logs)}")

        @click.group()
        @pass_container(container)
        def cli():
            pass

        cli.add_command(cmd)

        runner = CliRunner()
        result = runner.invoke(cli, ["cmd"])
        assert result.exit_code == 0
        assert "users=3,logs=1" in result.output

    def test_inject_with_mixed_parameters(self) -> None:
        container = Container()
        container.register(Database)

        @click.command()
        @click.option("--limit", type=int, default=10)
        @inject
        def cmd(limit: int, db: Inject[Database]):
            users = db.query("")[:limit]
            click.echo(f"count={len(users)}")

        @click.group()
        @pass_container(container)
        def cli():
            pass

        cli.add_command(cmd)

        runner = CliRunner()

        result = runner.invoke(cli, ["cmd"])
        assert result.exit_code == 0
        assert "count=3" in result.output

        result = runner.invoke(cli, ["cmd", "--limit", "1"])
        assert result.exit_code == 0
        assert "count=1" in result.output

    def test_inject_with_click_argument(self) -> None:
        container = Container()
        container.register(Database)

        @click.command()
        @click.argument("name")
        @inject
        def greet(name: str, db: Inject[Database]):
            click.echo(f"Hello {name}, {len(db.query(''))} users")

        @click.group()
        @pass_container(container)
        def cli():
            pass

        cli.add_command(greet)

        runner = CliRunner()
        result = runner.invoke(cli, ["greet", "Alice"])
        assert result.exit_code == 0
        assert "Hello Alice, 3 users" in result.output

    def test_inject_all(self) -> None:
        container = Container()
        container.register(IPlugin, implementation=PluginA)
        container.register(IPlugin, implementation=PluginB)

        @click.command()
        @inject
        def cmd(plugins: InjectAll[IPlugin]):
            names = [p.name for p in plugins]
            click.echo(",".join(names))

        @click.group()
        @pass_container(container)
        def cli():
            pass

        cli.add_command(cmd)

        runner = CliRunner()
        result = runner.invoke(cli, ["cmd"])
        assert result.exit_code == 0
        assert "plugin_a" in result.output
        assert "plugin_b" in result.output

    def test_inject_with_named_dependency(self) -> None:
        container = Container()
        db1 = Database()
        db2 = Database()
        container.register_instance(Database, db1, name="primary")
        container.register_instance(Database, db2, name="secondary")

        @click.command()
        @inject
        def cmd(db: Inject[Database, Named("primary")]):
            click.echo(f"got db: {db is db1}")

        @click.group()
        @pass_container(container)
        def cli():
            pass

        cli.add_command(cmd)

        runner = CliRunner()
        result = runner.invoke(cli, ["cmd"])
        assert result.exit_code == 0
        assert "got db: True" in result.output

    def test_inject_missing_container_raises(self) -> None:
        @click.command()
        @inject
        def cmd(db: Inject[Database]):
            click.echo("should not reach")

        runner = CliRunner()
        result = runner.invoke(cmd, [])
        assert result.exit_code != 0
        assert isinstance(result.exception, RuntimeError)
        assert "Container not found" in str(result.exception)

    def test_inject_preserves_function_metadata(self) -> None:
        @inject
        def my_command(db: Inject[Database]):
            """My docstring."""
            pass

        assert my_command.__name__ == "my_command"
        assert my_command.__doc__ == "My docstring."

    def test_inject_preserves_click_params(self) -> None:
        @click.option("--name", type=str)
        @inject
        def cmd(name: str, db: Inject[Database]):
            pass

        assert hasattr(cmd, "__click_params__")
        param_names = [p.name for p in cmd.__click_params__]
        assert "name" in param_names


class TestPassContainer:
    """Test pass_container decorator."""

    def test_pass_container_stores_in_context(self) -> None:
        container = Container()
        container.register(Database)

        @click.group()
        @pass_container(container)
        def cli():
            pass

        @cli.command()
        @click.pass_context
        def check(ctx):
            assert CONTAINER_KEY in ctx.obj
            assert ctx.obj[CONTAINER_KEY] is container
            click.echo("ok")

        runner = CliRunner()
        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 0
        assert "ok" in result.output

    def test_pass_container_custom_key(self) -> None:
        container = Container()

        @click.group()
        @pass_container(container, key="my_container")
        def cli():
            pass

        @cli.command()
        @click.pass_context
        def check(ctx):
            assert "my_container" in ctx.obj
            click.echo("ok")

        runner = CliRunner()
        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 0
        assert "ok" in result.output

    def test_container_propagates_to_subcommands(self) -> None:
        container = Container()
        container.register(Database)

        @click.group()
        @pass_container(container)
        def cli():
            pass

        @cli.group()
        def sub():
            pass

        @sub.command()
        @inject
        def cmd(db: Inject[Database]):
            click.echo(f"users={len(db.query(''))}")

        runner = CliRunner()
        result = runner.invoke(cli, ["sub", "cmd"])
        assert result.exit_code == 0
        assert "users=3" in result.output


class TestWithModules:
    """Test with_modules decorator."""

    def test_with_modules_registers_on_container(self) -> None:
        container = Container()

        auth_module = Module("auth")
        auth_module.register(AuthService, public=True)

        @click.group()
        @pass_container(container)
        def cli():
            pass

        @cli.group()
        @with_modules(auth_module)
        def auth():
            pass

        @auth.command()
        @inject
        def login(svc: Inject[AuthService]):
            click.echo(svc.login("alice"))

        runner = CliRunner()
        result = runner.invoke(cli, ["auth", "login"])
        assert result.exit_code == 0
        assert "logged in as alice" in result.output

    def test_with_modules_missing_container_raises(self) -> None:
        auth_module = Module("auth")

        @click.group()
        def cli():
            pass

        @cli.group()
        @with_modules(auth_module)
        def auth():
            pass

        @auth.command()
        def noop():
            click.echo("noop")

        runner = CliRunner()
        result = runner.invoke(cli, ["auth", "noop"])
        assert result.exit_code != 0
        assert isinstance(result.exception, RuntimeError)
        assert "Container not found" in str(result.exception)

    def test_with_modules_multiple_modules(self) -> None:
        container = Container()

        auth_module = Module("auth")
        auth_module.register(AuthService, public=True)

        log_module = Module("logging")
        log_module.register(Logger, public=True)

        @click.group()
        @pass_container(container)
        def cli():
            pass

        @cli.group()
        @with_modules(auth_module, log_module)
        def admin():
            pass

        @admin.command()
        @inject
        def cmd(svc: Inject[AuthService], logger: Inject[Logger]):
            logger.info("admin action")
            click.echo(f"{svc.login('admin')},logs={len(logger.logs)}")

        runner = CliRunner()
        result = runner.invoke(cli, ["admin", "cmd"])
        assert result.exit_code == 0
        assert "logged in as admin" in result.output
        assert "logs=1" in result.output

    def test_with_modules_combined_with_base_container_deps(self) -> None:
        container = Container()
        container.register(Database)

        auth_module = Module("auth")
        auth_module.register(AuthService, public=True)

        @click.group()
        @pass_container(container)
        def cli():
            pass

        @cli.group()
        @with_modules(auth_module)
        def auth():
            pass

        @auth.command()
        @inject
        def cmd(db: Inject[Database], svc: Inject[AuthService]):
            click.echo(f"users={len(db.query(''))},{svc.login('bob')}")

        runner = CliRunner()
        result = runner.invoke(cli, ["auth", "cmd"])
        assert result.exit_code == 0
        assert "users=3" in result.output
        assert "logged in as bob" in result.output


class TestDecoratorOrdering:
    """Test that both decorator orderings work."""

    def test_inject_below_click_option(self) -> None:
        """@click.option above @inject (standard ordering)."""
        container = Container()
        container.register(Database)

        @click.command()
        @click.option("--name", default="world")
        @inject
        def cmd(name: str, db: Inject[Database]):
            click.echo(f"Hello {name}, {len(db.query(''))} users")

        @click.group()
        @pass_container(container)
        def cli():
            pass

        cli.add_command(cmd)

        runner = CliRunner()
        result = runner.invoke(cli, ["cmd", "--name", "Alice"])
        assert result.exit_code == 0
        assert "Hello Alice" in result.output

    def test_inject_above_click_option(self) -> None:
        """@inject above @click.option (reversed ordering)."""
        container = Container()
        container.register(Database)

        @click.command()
        @inject
        @click.option("--name", default="world")
        def cmd(name: str, db: Inject[Database]):
            click.echo(f"Hello {name}, {len(db.query(''))} users")

        @click.group()
        @pass_container(container)
        def cli():
            pass

        cli.add_command(cmd)

        runner = CliRunner()
        result = runner.invoke(cli, ["cmd", "--name", "Bob"])
        assert result.exit_code == 0
        assert "Hello Bob" in result.output
