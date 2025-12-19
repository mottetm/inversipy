"""Test suite for examples.

This test suite ensures that:
1. All examples can be imported without errors
2. All examples run successfully
3. Examples pass type checking
"""

import importlib
import sys
from pathlib import Path

import pytest

# Add examples directory to path
examples_dir = Path(__file__).parent.parent / "examples"
sys.path.insert(0, str(examples_dir.parent))


class TestExamplesImport:
    """Test that all examples can be imported."""

    def test_import_basic_usage(self) -> None:
        """Test importing basic_usage example."""
        from examples import basic_usage

        assert hasattr(basic_usage, "main")
        assert hasattr(basic_usage, "Database")
        assert hasattr(basic_usage, "UserRepository")
        assert hasattr(basic_usage, "UserService")

    def test_import_scopes_example(self) -> None:
        """Test importing scopes_example."""
        from examples import scopes_example

        assert hasattr(scopes_example, "main")
        assert hasattr(scopes_example, "Counter")
        assert hasattr(scopes_example, "demonstrate_singleton")
        assert hasattr(scopes_example, "demonstrate_transient")

    def test_import_modules_example(self) -> None:
        """Test importing modules_example."""
        from examples import modules_example

        assert hasattr(modules_example, "main")
        assert hasattr(modules_example, "Database")
        assert hasattr(modules_example, "DatabaseConnection")
        assert hasattr(modules_example, "demonstrate_basic_module")


    def test_import_fastapi_example(self) -> None:
        """Test importing fastapi_example."""
        from examples import fastapi_example

        assert hasattr(fastapi_example, "main")
        # FastAPI imports are optional
        if fastapi_example.FASTAPI_AVAILABLE:
            assert hasattr(fastapi_example, "app")


class TestExamplesExecution:
    """Test that all examples execute successfully."""

    def test_run_basic_usage(self) -> None:
        """Test running basic_usage example."""
        from examples import basic_usage

        # Should run without errors
        basic_usage.main()

    def test_run_scopes_example(self) -> None:
        """Test running scopes_example."""
        from examples import scopes_example

        # Should run without errors
        scopes_example.main()

    def test_run_modules_example(self) -> None:
        """Test running modules_example."""
        from examples import modules_example

        # Should run without errors
        modules_example.main()


    def test_run_fastapi_example(self) -> None:
        """Test running fastapi_example main function."""
        from examples import fastapi_example

        # Should run without errors
        fastapi_example.main()


class TestExampleBehavior:
    """Test specific behaviors in examples."""

    def test_basic_usage_container_validation(self) -> None:
        """Test that basic_usage validates container correctly."""
        from inversipy import Container, Scopes
        from examples.basic_usage import Database, UserRepository, UserService

        container = Container()
        container.register(Database, scope=Scopes.SINGLETON)
        container.register(UserRepository, scope=Scopes.SINGLETON)
        container.register(UserService, scope=Scopes.SINGLETON)

        # Should validate without errors
        container.validate()

        # Should resolve correctly
        service = container.get(UserService)
        assert service is not None
        assert isinstance(service, UserService)

    def test_scopes_singleton_behavior(self) -> None:
        """Test singleton behavior from scopes example."""
        from inversipy import Container, Scopes
        from examples.scopes_example import Counter

        Counter.reset_count()
        container = Container()
        container.register(Counter, scope=Scopes.SINGLETON)

        counter1 = container.get(Counter)
        counter2 = container.get(Counter)

        assert counter1 is counter2, "Singleton should return same instance"

    def test_scopes_transient_behavior(self) -> None:
        """Test transient behavior from scopes example."""
        from inversipy import Container, Scopes
        from examples.scopes_example import Counter

        Counter.reset_count()
        container = Container()
        container.register(Counter, scope=Scopes.TRANSIENT)

        counter1 = container.get(Counter)
        counter2 = container.get(Counter)

        assert counter1 is not counter2, "Transient should return different instances"

    def test_modules_public_private_access(self) -> None:
        """Test module public/private access control."""
        from inversipy import Container, Module, Scopes
        from inversipy.exceptions import DependencyNotFoundError
        from examples.modules_example import Database, DatabaseConnection

        module = Module("Database")
        module.register(DatabaseConnection, scope=Scopes.SINGLETON)  # Private
        module.register(Database, scope=Scopes.SINGLETON, public=True)  # Public

        container = Container()
        container.register_module(module)

        # Should be able to get public dependency
        database = container.get(Database)
        assert database is not None

        # Should not be able to get private dependency
        with pytest.raises(DependencyNotFoundError):
            container.get(DatabaseConnection)


    @pytest.mark.skipif(
        not importlib.util.find_spec("fastapi"),
        reason="FastAPI not installed",
    )
    def test_fastapi_app_creation(self) -> None:
        """Test FastAPI app is created correctly."""
        from examples import fastapi_example

        if fastapi_example.FASTAPI_AVAILABLE:
            assert fastapi_example.app is not None
            assert hasattr(fastapi_example.app, "state")
            assert hasattr(fastapi_example.app.state, "container")


class TestExamplesDocumentation:
    """Test that examples are well-documented."""

    def test_all_examples_have_docstrings(self) -> None:
        """Test that all example modules have docstrings."""
        from examples import (
            basic_usage,
            fastapi_example,
            modules_example,
            scopes_example,
        )

        for module in [
            basic_usage,
            scopes_example,
            modules_example,
            fastapi_example,
        ]:
            assert module.__doc__ is not None, f"{module.__name__} missing docstring"
            assert len(module.__doc__) > 50, f"{module.__name__} docstring too short"

    def test_all_examples_have_main_function(self) -> None:
        """Test that all examples have a main() function."""
        from examples import (
            basic_usage,
            fastapi_example,
            modules_example,
            scopes_example,
        )

        for module in [
            basic_usage,
            scopes_example,
            modules_example,
            fastapi_example,
        ]:
            assert hasattr(module, "main"), f"{module.__name__} missing main() function"
            assert callable(module.main), f"{module.__name__}.main is not callable"


class TestExamplesTypeChecking:
    """Test that examples are properly typed."""

    def test_examples_have_type_annotations(self) -> None:
        """Test that key functions in examples have type annotations."""
        from examples import basic_usage

        # Check that main functions have return type annotations
        assert basic_usage.main.__annotations__.get("return") is not None

        # Check that classes have typed __init__ methods
        assert basic_usage.Database.__init__.__annotations__.get("return") is not None
