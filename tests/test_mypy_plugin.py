"""Tests for the inversipy mypy plugin.

These tests verify that the mypy plugin correctly handles:
- Inject[T] resolving to type T
- Inject[T, Named("x")] resolving to type T
- Bare Inject[] (no args) producing an error
- InjectAll[T] preserving list[T] semantics
"""

import tempfile
import textwrap
from pathlib import Path

from mypy import api as mypy_api


def run_mypy(code: str) -> tuple[str, str, int]:
    """Run mypy on a code snippet with the inversipy plugin enabled.

    Args:
        code: Python source code to type-check

    Returns:
        (stdout, stderr, exit_code)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write source file
        src = Path(tmpdir) / "test_snippet.py"
        src.write_text(textwrap.dedent(code))

        # Write mypy config enabling the plugin
        ini = Path(tmpdir) / "mypy.ini"
        ini.write_text("[mypy]\nplugins = inversipy.mypy_plugin\n")

        return mypy_api.run(
            [
                str(src),
                "--config-file",
                str(ini),
                "--no-error-summary",
                "--hide-error-context",
            ]
        )


class TestInjectTypeResolution:
    """Tests that Inject[T, ...] resolves to T for type checking."""

    def test_inject_resolves_to_base_type(self) -> None:
        """Inject[T] should resolve to T, allowing attribute access on T."""
        stdout, stderr, exit_code = run_mypy(
            """
            from inversipy import Inject

            class Database:
                def query(self, sql: str) -> str:
                    return sql

            def use_db(db: Inject[Database]) -> str:
                return db.query("SELECT 1")
        """
        )
        assert exit_code == 0, f"mypy failed:\nstdout: {stdout}\nstderr: {stderr}"

    def test_inject_with_named_resolves_to_base_type(self) -> None:
        """Inject[T, Named("x")] should resolve to T."""
        stdout, stderr, exit_code = run_mypy(
            """
            from inversipy import Inject, Named

            class IDatabase:
                def query(self, sql: str) -> str:
                    raise NotImplementedError

            def use_db(db: Inject[IDatabase, Named("primary")]) -> str:
                return db.query("SELECT 1")
        """
        )
        assert exit_code == 0, f"mypy failed:\nstdout: {stdout}\nstderr: {stderr}"

    def test_inject_catches_wrong_attribute(self) -> None:
        """Inject[T] should still catch incorrect attribute access on T."""
        stdout, _, exit_code = run_mypy(
            """
            from inversipy import Inject

            class Database:
                def query(self, sql: str) -> str:
                    return sql

            def use_db(db: Inject[Database]) -> str:
                return db.nonexistent_method()
        """
        )
        assert exit_code != 0, "mypy should have caught invalid attribute access"
        assert "nonexistent_method" in stdout

    def test_inject_catches_wrong_attribute_with_named(self) -> None:
        """Inject[T, Named("x")] should still catch incorrect attribute access on T."""
        stdout, _, exit_code = run_mypy(
            """
            from inversipy import Inject, Named

            class Database:
                def query(self, sql: str) -> str:
                    return sql

            def use_db(db: Inject[Database, Named("primary")]) -> str:
                return db.nonexistent_method()
        """
        )
        assert exit_code != 0, "mypy should have caught invalid attribute access"
        assert "nonexistent_method" in stdout


class TestInjectNoArgs:
    """Tests that bare Inject[] (no type args) produces an error."""

    def test_inject_without_args_fails(self) -> None:
        """Inject without type arguments should produce a mypy error."""
        stdout, _, exit_code = run_mypy(
            """
            from inversipy import Inject

            def use_db(db: Inject) -> None:
                pass
        """
        )
        # Bare Inject (no subscript) should either error or at least not silently pass
        assert (
            exit_code != 0 or "error" in stdout.lower() or "Inject" in stdout
        ), f"Expected mypy to flag bare Inject usage, got: {stdout}"


class TestInjectAllType:
    """Tests that InjectAll[T] preserves list[T] semantics."""

    def test_inject_all_is_iterable(self) -> None:
        """InjectAll[T] should be iterable as list[T]."""
        stdout, stderr, exit_code = run_mypy(
            """
            from inversipy import InjectAll

            class IPlugin:
                def execute(self) -> None:
                    raise NotImplementedError

            def run_plugins(plugins: InjectAll[IPlugin]) -> None:
                for plugin in plugins:
                    plugin.execute()
        """
        )
        assert exit_code == 0, f"mypy failed:\nstdout: {stdout}\nstderr: {stderr}"

    def test_inject_all_catches_wrong_item_attribute(self) -> None:
        """InjectAll[T] items should be typed as T, catching invalid access."""
        stdout, _, exit_code = run_mypy(
            """
            from inversipy import InjectAll

            class IPlugin:
                def execute(self) -> None:
                    raise NotImplementedError

            def run_plugins(plugins: InjectAll[IPlugin]) -> None:
                for plugin in plugins:
                    plugin.nonexistent_method()
        """
        )
        assert exit_code != 0, "mypy should have caught invalid attribute access"
        assert "nonexistent_method" in stdout


class TestInjectablePropertyInjection:
    """Tests that Injectable with Inject annotations type-checks correctly."""

    def test_injectable_with_inject_attributes(self) -> None:
        """Injectable class with Inject[T] attributes should type-check."""
        stdout, stderr, exit_code = run_mypy(
            """
            from inversipy import Injectable, Inject

            class Logger:
                def log(self, msg: str) -> None:
                    pass

            class Database:
                def query(self, sql: str) -> str:
                    return sql

            class UserService(Injectable):
                database: Inject[Database]
                logger: Inject[Logger]

                def get_users(self) -> str:
                    self.logger.log("Getting users")
                    return self.database.query("SELECT * FROM users")
        """
        )
        assert exit_code == 0, f"mypy failed:\nstdout: {stdout}\nstderr: {stderr}"

    def test_injectable_with_named_inject(self) -> None:
        """Injectable class with Inject[T, Named("x")] should type-check."""
        stdout, stderr, exit_code = run_mypy(
            """
            from inversipy import Injectable, Inject, Named

            class IDatabase:
                def query(self, sql: str) -> str:
                    raise NotImplementedError

            class UserService(Injectable):
                primary_db: Inject[IDatabase, Named("primary")]
                replica_db: Inject[IDatabase, Named("replica")]

                def read(self) -> str:
                    return self.replica_db.query("SELECT 1")

                def write(self) -> str:
                    return self.primary_db.query("INSERT INTO t VALUES (1)")
        """
        )
        assert exit_code == 0, f"mypy failed:\nstdout: {stdout}\nstderr: {stderr}"


class TestPluginEntryPoint:
    """Tests for the plugin entry point function."""

    def test_plugin_returns_plugin_class(self) -> None:
        """The plugin() entry point should return InversipyPlugin."""
        from inversipy.mypy_plugin import InversipyPlugin, plugin

        result = plugin("1.0.0")
        assert result is InversipyPlugin
