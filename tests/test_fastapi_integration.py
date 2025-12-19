"""Tests for FastAPI integration."""

from typing import Annotated

import pytest

# Check if FastAPI is available
pytest.importorskip("fastapi", reason="FastAPI not installed")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from inversipy import Container
from inversipy.decorators import Inject
from inversipy.fastapi import inject


class Database:
    """Mock database service."""

    def query(self, sql: str) -> list[str]:
        return ["user1", "user2", "user3"]


class Logger:
    """Mock logger service."""

    def __init__(self):
        self.logs: list[str] = []

    def info(self, message: str) -> None:
        self.logs.append(message)


class TestFastAPIIntegration:
    """Test FastAPI @inject decorator."""

    def test_inject_with_single_dependency(self) -> None:
        """Test @inject with one injected dependency."""
        app = FastAPI()
        container = Container()
        container.register(Database)
        app.state.container = container

        @app.get("/users")
        @inject
        def get_users(db: Annotated[Database, Inject]):
            return {"users": db.query("SELECT * FROM users")}

        client = TestClient(app)
        response = client.get("/users")

        assert response.status_code == 200
        assert response.json() == {"users": ["user1", "user2", "user3"]}

    def test_inject_with_multiple_dependencies(self) -> None:
        """Test @inject with multiple injected dependencies."""
        app = FastAPI()
        container = Container()
        container.register(Database)
        container.register(Logger)
        app.state.container = container

        @app.get("/users")
        @inject
        def get_users(db: Annotated[Database, Inject], logger: Annotated[Logger, Inject]):
            logger.info("Fetching users")
            return {"users": db.query("SELECT * FROM users")}

        client = TestClient(app)
        response = client.get("/users")

        assert response.status_code == 200
        assert response.json() == {"users": ["user1", "user2", "user3"]}

    def test_inject_with_mixed_parameters(self) -> None:
        """Test @inject with both injected and normal parameters."""
        app = FastAPI()
        container = Container()
        container.register(Database)
        container.register(Logger)
        app.state.container = container

        @app.get("/users")
        @inject
        def get_users(
            db: Annotated[Database, Inject], logger: Annotated[Logger, Inject], limit: int = 10
        ):
            logger.info(f"Fetching {limit} users")
            return {"users": db.query("SELECT * FROM users"), "limit": limit}

        client = TestClient(app)

        # Test with default limit
        response = client.get("/users")
        assert response.status_code == 200
        assert response.json()["limit"] == 10

        # Test with custom limit
        response = client.get("/users?limit=5")
        assert response.status_code == 200
        assert response.json()["limit"] == 5

    def test_inject_async_route(self) -> None:
        """Test @inject with async route handler."""
        app = FastAPI()
        container = Container()
        container.register(Database)
        app.state.container = container

        @app.get("/users")
        @inject
        async def get_users(db: Annotated[Database, Inject]):
            return {"users": db.query("SELECT * FROM users")}

        client = TestClient(app)
        response = client.get("/users")

        assert response.status_code == 200
        assert response.json() == {"users": ["user1", "user2", "user3"]}

    def test_get_container_without_setup_raises(self) -> None:
        """Test that get_container raises if app.state.container wasn't set."""
        app = FastAPI()
        # Don't set app.state.container

        @app.get("/test")
        @inject
        def test_route(db: Annotated[Database, Inject]):
            return {"data": "test"}

        client = TestClient(app)

        with pytest.raises(RuntimeError) as exc_info:
            client.get("/test")

        assert "Container not configured in app.state" in str(exc_info.value)

    def test_inject_preserves_function_metadata(self) -> None:
        """Test that @inject preserves function name and docstring."""
        app = FastAPI()
        container = Container()
        container.register(Database)
        app.state.container = container

        @app.get("/users")
        @inject
        def get_users(db: Annotated[Database, Inject]):
            """Get all users from database."""
            return {"users": db.query("SELECT * FROM users")}

        # Check that wrapper preserves metadata
        assert get_users.__name__ == "get_users"
        assert get_users.__doc__ == "Get all users from database."
