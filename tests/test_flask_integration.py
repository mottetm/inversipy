"""Tests for Flask integration."""

import pytest

pytest.importorskip("flask", reason="Flask not installed")

from flask import Flask

from inversipy import Container
from inversipy.decorators import Inject, InjectAll
from inversipy.flask import bind, get_container, inject
from inversipy.types import Named


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


class IPlugin:
    """Plugin interface."""

    name: str = "base"


class PluginA(IPlugin):
    name = "a"


class PluginB(IPlugin):
    name = "b"


class TestFlaskIntegration:
    """Test Flask @inject decorator."""

    def test_inject_with_single_dependency(self) -> None:
        app = Flask(__name__)
        container = Container()
        container.register(Database)
        bind(app, container)

        @app.route("/users")
        @inject
        def get_users(db: Inject[Database]):
            return {"users": db.query("SELECT * FROM users")}

        with app.test_client() as client:
            response = client.get("/users")
            assert response.status_code == 200
            assert response.get_json() == {"users": ["user1", "user2", "user3"]}

    def test_inject_with_multiple_dependencies(self) -> None:
        app = Flask(__name__)
        container = Container()
        container.register(Database)
        container.register(Logger)
        bind(app, container)

        @app.route("/users")
        @inject
        def get_users(db: Inject[Database], logger: Inject[Logger]):
            logger.info("Fetching users")
            return {"users": db.query("SELECT * FROM users")}

        with app.test_client() as client:
            response = client.get("/users")
            assert response.status_code == 200
            assert response.get_json() == {"users": ["user1", "user2", "user3"]}

    def test_inject_with_path_parameter(self) -> None:
        app = Flask(__name__)
        container = Container()
        container.register(Database)
        bind(app, container)

        @app.route("/users/<int:user_id>")
        @inject
        def get_user(user_id: int, db: Inject[Database]):
            return {"user_id": user_id, "users": db.query("SELECT 1")}

        with app.test_client() as client:
            response = client.get("/users/42")
            assert response.status_code == 200
            assert response.get_json()["user_id"] == 42

    def test_inject_with_named_dependency(self) -> None:
        app = Flask(__name__)
        container = Container()
        container.register(Database, name="primary")
        bind(app, container)

        @app.route("/data")
        @inject
        def get_data(db: Inject[Database, Named("primary")]):
            return {"data": db.query("SELECT 1")}

        with app.test_client() as client:
            response = client.get("/data")
            assert response.status_code == 200
            assert response.get_json() == {"data": ["user1", "user2", "user3"]}

    def test_inject_all(self) -> None:
        app = Flask(__name__)
        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)
        bind(app, container)

        @app.route("/plugins")
        @inject
        def get_plugins(plugins: InjectAll[IPlugin]):
            return {"plugins": [p.name for p in plugins]}

        with app.test_client() as client:
            response = client.get("/plugins")
            assert response.status_code == 200
            assert set(response.get_json()["plugins"]) == {"a", "b"}

    def test_get_container_without_setup_raises(self) -> None:
        app = Flask(__name__)

        with app.app_context():
            with pytest.raises(RuntimeError, match="Container not configured"):
                get_container()

    def test_inject_preserves_function_metadata(self) -> None:
        app = Flask(__name__)
        container = Container()
        container.register(Database)
        bind(app, container)

        @inject
        def get_users(db: Inject[Database]):
            """Get all users from database."""
            return {"users": db.query("SELECT * FROM users")}

        assert get_users.__name__ == "get_users"
        assert get_users.__doc__ == "Get all users from database."

    def test_no_inject_passthrough(self) -> None:
        """@inject on a function with no Inject params returns the original."""
        app = Flask(__name__)
        container = Container()
        bind(app, container)

        def plain_view():
            return {"ok": True}

        wrapped = inject(plain_view)
        assert wrapped is plain_view
