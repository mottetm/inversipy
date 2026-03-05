"""Tests for the inversipy pytest plugin."""

import pytest

pytest.importorskip("inversipy_pytest")

pytest_plugins = ["pytester"]


class TestPytestPlugin:
    """Test the pytest plugin using pytester."""

    def test_inject_resolves_dependency(self, pytester: pytest.Pytester) -> None:
        pytester.makeconftest(
            """
import pytest
from inversipy import Container

class Greeter:
    def greet(self, name):
        return f"Hello, {name}!"

@pytest.fixture
def container():
    c = Container()
    c.register(Greeter)
    return c

@pytest.fixture
def greeter_cls():
    return Greeter
"""
        )
        pytester.makepyfile(
            """
from inversipy_pytest import inject

def test_greet(container):
    from conftest import Greeter
    from inversipy.decorators import Inject

    greeter = container.get(Greeter)
    assert greeter.greet("Alice") == "Hello, Alice!"
"""
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_inject_decorator_resolves(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            conftest="""
import pytest
from inversipy import Container

class Greeter:
    def greet(self, name):
        return f"Hello, {name}!"

@pytest.fixture
def container():
    c = Container()
    c.register(Greeter)
    return c
""",
            test_inject="""
from conftest import Greeter
from inversipy.decorators import Inject
from inversipy_pytest import inject

@inject
def test_greet(greeter: Inject[Greeter]):
    assert greeter.greet("Alice") == "Hello, Alice!"
""",
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_inject_with_multiple_dependencies(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            conftest="""
import pytest
from inversipy import Container

class Database:
    def query(self):
        return ["row1"]

class Logger:
    def log(self, msg):
        pass

@pytest.fixture
def container():
    c = Container()
    c.register(Database)
    c.register(Logger)
    return c
""",
            test_multi="""
from conftest import Database, Logger
from inversipy.decorators import Inject
from inversipy_pytest import inject

@inject
def test_multi(db: Inject[Database], logger: Inject[Logger]):
    assert db.query() == ["row1"]
""",
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_inject_with_child_container_override(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            conftest="""
import pytest
from inversipy import Container

class IDatabase:
    def query(self):
        return "real"

class MockDatabase(IDatabase):
    def query(self):
        return "mock"

@pytest.fixture
def base_container():
    c = Container()
    c.register(IDatabase)
    return c

@pytest.fixture
def container(base_container):
    child = base_container.create_child()
    child.register(IDatabase, MockDatabase)
    return child
""",
            test_override="""
from conftest import IDatabase
from inversipy.decorators import Inject
from inversipy_pytest import inject

@inject
def test_override(db: Inject[IDatabase]):
    assert db.query() == "mock"
""",
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_inject_with_normal_fixtures(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            conftest="""
import pytest
from inversipy import Container

class Greeter:
    def greet(self, name):
        return f"Hello, {name}!"

@pytest.fixture
def container():
    c = Container()
    c.register(Greeter)
    return c

@pytest.fixture
def username():
    return "Bob"
""",
            test_mixed="""
from conftest import Greeter
from inversipy.decorators import Inject
from inversipy_pytest import inject

@inject
def test_mixed(username, greeter: Inject[Greeter]):
    assert greeter.greet(username) == "Hello, Bob!"
""",
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_default_container_fixture(self, pytester: pytest.Pytester) -> None:
        """The plugin provides a default empty container fixture."""
        pytester.makepyfile(
            """
def test_container_exists(container):
    from inversipy import Container
    assert isinstance(container, Container)
"""
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_no_inject_passthrough(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            """
from inversipy_pytest import inject

@inject
def test_plain():
    assert True
"""
        )
        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestInjectDecorator:
    """Direct (in-process) tests for the @inject decorator."""

    def test_passthrough_when_no_inject_params(self) -> None:
        from inversipy_pytest import inject

        def original():
            pass

        assert inject(original) is original

    def test_resolves_inject_param(self) -> None:
        from inversipy import Container
        from inversipy.decorators import Inject
        from inversipy_pytest import inject

        class Greeter:
            def greet(self) -> str:
                return "hi"

        container = Container()
        container.register(Greeter)

        @inject
        def my_test(g: Inject[Greeter]) -> str:
            return g.greet()

        assert my_test(container=container) == "hi"

    def test_resolves_inject_all_param(self) -> None:
        from inversipy import Container
        from inversipy.decorators import InjectAll
        from inversipy_pytest import inject

        class IPlugin:
            name: str = "base"

        class PluginA(IPlugin):
            name = "a"

        class PluginB(IPlugin):
            name = "b"

        container = Container()
        container.register(IPlugin, PluginA)
        container.register(IPlugin, PluginB)

        @inject
        def my_test(plugins: InjectAll[IPlugin]) -> list[str]:
            return [p.name for p in plugins]

        assert set(my_test(container=container)) == {"a", "b"}

    def test_mixed_fixtures_and_inject(self) -> None:
        import inspect

        from inversipy import Container
        from inversipy.decorators import Inject
        from inversipy_pytest import inject

        class Service:
            pass

        container = Container()
        container.register(Service)

        @inject
        def my_test(some_fixture: str, svc: Inject[Service]) -> tuple[str, Service]:
            return (some_fixture, svc)

        # Verify signature was rewritten: should have some_fixture + container
        sig = inspect.signature(my_test)
        assert "some_fixture" in sig.parameters
        assert "container" in sig.parameters
        assert "svc" not in sig.parameters

        result = my_test("hello", container=container)
        assert result[0] == "hello"
        assert isinstance(result[1], Service)

    def test_preserves_function_metadata(self) -> None:
        from inversipy.decorators import Inject
        from inversipy_pytest import inject

        class Dep:
            pass

        @inject
        def my_func(d: Inject[Dep]) -> None:
            """My docstring."""

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."
