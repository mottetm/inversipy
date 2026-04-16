"""Tests for named bindings / qualifiers feature."""

import pytest

from inversipy import (
    Container,
    DependencyNotFoundError,
    Inject,
    Injectable,
    Module,
    ModuleBuilder,
    Named,
    RegistrationError,
    Scopes,
)
from inversipy.decorators import extract_inject_info


# Test interfaces and implementations
class IDatabase:
    """Interface for database connections."""

    def query(self, sql: str) -> str:
        raise NotImplementedError


class PostgresDB(IDatabase):
    """PostgreSQL database implementation."""

    def query(self, sql: str) -> str:
        return f"PostgreSQL: {sql}"


class MySQLDB(IDatabase):
    """MySQL database implementation."""

    def query(self, sql: str) -> str:
        return f"MySQL: {sql}"


class SQLiteDB(IDatabase):
    """SQLite database implementation."""

    def query(self, sql: str) -> str:
        return f"SQLite: {sql}"


class ICache:
    """Interface for cache."""

    def get(self, key: str) -> str | None:
        raise NotImplementedError


class RedisCache(ICache):
    """Redis cache implementation."""

    def get(self, key: str) -> str | None:
        return f"redis:{key}"


class MemoryCache(ICache):
    """In-memory cache implementation."""

    def get(self, key: str) -> str | None:
        return f"memory:{key}"


class TestNamedBindingsBasic:
    """Basic registration and resolution tests."""

    def test_register_with_name(self) -> None:
        """Test registering a dependency with a name."""
        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")

        db = container.get(IDatabase, name="primary")
        assert isinstance(db, PostgresDB)

    def test_register_multiple_implementations(self) -> None:
        """Test registering multiple implementations of the same interface."""
        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")
        container.register(IDatabase, MySQLDB, name="replica")

        primary = container.get(IDatabase, name="primary")
        replica = container.get(IDatabase, name="replica")

        assert isinstance(primary, PostgresDB)
        assert isinstance(replica, MySQLDB)

    def test_named_and_unnamed_coexist(self) -> None:
        """Test that named and unnamed bindings can coexist."""
        container = Container()
        container.register(IDatabase, SQLiteDB)  # Unnamed
        container.register(IDatabase, PostgresDB, name="production")

        default = container.get(IDatabase)
        production = container.get(IDatabase, name="production")

        assert isinstance(default, SQLiteDB)
        assert isinstance(production, PostgresDB)

    def test_named_not_found_error(self) -> None:
        """Test error when named dependency is not found."""
        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")

        with pytest.raises(DependencyNotFoundError) as exc_info:
            container.get(IDatabase, name="nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_unnamed_does_not_find_named(self) -> None:
        """Test that unnamed get() doesn't find named bindings."""
        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")

        with pytest.raises(DependencyNotFoundError):
            container.get(IDatabase)  # Should not find the named binding


class TestNamedBindingsRegistrationMethods:
    """Test all registration methods with names."""

    def test_register_factory_with_name(self) -> None:
        """Test register_factory with a name."""
        container = Container()

        def create_db() -> IDatabase:
            return PostgresDB()

        container.register_factory(IDatabase, create_db, name="factory")
        db = container.get(IDatabase, name="factory")

        assert isinstance(db, PostgresDB)

    def test_register_instance_with_name(self) -> None:
        """Test register_instance with a name."""
        container = Container()
        instance = PostgresDB()

        container.register_instance(IDatabase, instance, name="singleton")
        db = container.get(IDatabase, name="singleton")

        assert db is instance


class TestNamedBindingsScopes:
    """Test scopes with named bindings."""

    def test_singleton_scope_per_name(self) -> None:
        """Test that singleton scope respects names separately."""
        container = Container()
        container.register(IDatabase, PostgresDB, scope=Scopes.SINGLETON, name="primary")
        container.register(IDatabase, MySQLDB, scope=Scopes.SINGLETON, name="replica")

        # Same name should return same instance
        primary1 = container.get(IDatabase, name="primary")
        primary2 = container.get(IDatabase, name="primary")
        assert primary1 is primary2

        # Different names should return different instances
        replica = container.get(IDatabase, name="replica")
        assert primary1 is not replica

    def test_transient_scope_with_names(self) -> None:
        """Test that transient scope creates new instances per get."""
        container = Container()
        container.register(IDatabase, PostgresDB, scope=Scopes.TRANSIENT, name="primary")

        db1 = container.get(IDatabase, name="primary")
        db2 = container.get(IDatabase, name="primary")

        assert db1 is not db2
        assert isinstance(db1, PostgresDB)
        assert isinstance(db2, PostgresDB)


class TestNamedBindingsHas:
    """Test has() method with names."""

    def test_has_with_name(self) -> None:
        """Test has() returns True for registered named dependency."""
        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")

        assert container.has(IDatabase, name="primary")
        assert not container.has(IDatabase, name="nonexistent")
        assert not container.has(IDatabase)  # Unnamed not registered

    def test_has_mixed_named_unnamed(self) -> None:
        """Test has() with both named and unnamed registrations."""
        container = Container()
        container.register(IDatabase, SQLiteDB)
        container.register(IDatabase, PostgresDB, name="production")

        assert container.has(IDatabase)
        assert container.has(IDatabase, name="production")
        assert not container.has(IDatabase, name="staging")


class TestNamedBindingsTryGet:
    """Test try_get() method with names."""

    def test_try_get_with_name(self) -> None:
        """Test try_get() with named dependencies."""
        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")

        db = container.try_get(IDatabase, name="primary")
        assert isinstance(db, PostgresDB)

        missing = container.try_get(IDatabase, name="nonexistent")
        assert missing is None


class TestNamedBindingsInjectableClass:
    """Test Injectable base class with named dependencies."""

    def test_injectable_with_named_dependencies(self) -> None:
        """Test Injectable class with Inject[T, Named(...)] annotations."""

        class UserService(Injectable):
            primary_db: Inject[IDatabase, Named("primary")]
            replica_db: Inject[IDatabase, Named("replica")]
            cache: Inject[ICache]

            def get_user(self, id: int) -> str:
                return self.primary_db.query(f"SELECT * FROM users WHERE id = {id}")

            def list_users(self) -> str:
                return self.replica_db.query("SELECT * FROM users")

        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")
        container.register(IDatabase, MySQLDB, name="replica")
        container.register(ICache, RedisCache)
        container.register(UserService)

        service = container.get(UserService)

        assert isinstance(service.primary_db, PostgresDB)
        assert isinstance(service.replica_db, MySQLDB)
        assert isinstance(service.cache, RedisCache)
        assert "PostgreSQL" in service.get_user(1)
        assert "MySQL" in service.list_users()

    def test_injectable_mixed_named_unnamed(self) -> None:
        """Test Injectable with mixed named and unnamed dependencies."""

        class MixedService(Injectable):
            default_db: Inject[IDatabase]
            special_db: Inject[IDatabase, Named("special")]

        container = Container()
        container.register(IDatabase, SQLiteDB)
        container.register(IDatabase, PostgresDB, name="special")
        container.register(MixedService)

        service = container.get(MixedService)

        assert isinstance(service.default_db, SQLiteDB)
        assert isinstance(service.special_db, PostgresDB)


class TestNamedBindingsModule:
    """Test Module with named dependencies."""

    def test_module_register_with_name(self) -> None:
        """Test Module.register() with name parameter."""
        module = Module("Database")
        module.register(IDatabase, PostgresDB, name="primary", public=True)
        module.register(IDatabase, MySQLDB, name="replica", public=True)

        container = Container()
        container.register_module(module)

        # Container should be able to resolve named dependencies from module
        primary = container.get(IDatabase, name="primary")
        replica = container.get(IDatabase, name="replica")

        assert isinstance(primary, PostgresDB)
        assert isinstance(replica, MySQLDB)

    def test_module_is_public_with_name(self) -> None:
        """Test Module.is_public() with named dependencies."""
        module = Module("Database")
        module.register(IDatabase, PostgresDB, name="primary", public=True)
        module.register(IDatabase, MySQLDB, name="replica", public=False)

        assert module.is_public(IDatabase, name="primary")
        assert not module.is_public(IDatabase, name="replica")

    def test_module_builder_with_name(self) -> None:
        """Test ModuleBuilder with named dependencies."""
        module = (
            ModuleBuilder("Database")
            .bind_public(IDatabase, PostgresDB, name="primary")
            .bind(IDatabase, MySQLDB, name="replica")  # Private
            .build()
        )

        assert module.is_public(IDatabase, name="primary")
        assert not module.is_public(IDatabase, name="replica")

    def test_export_named_makes_private_public(self) -> None:
        """Test export_named() can make a private named dependency public."""
        module = Module("Database")
        module.register(IDatabase, PostgresDB, name="primary", public=False)

        # Initially private
        assert not module.is_public(IDatabase, name="primary")

        # Export it
        module.export_named(IDatabase, "primary")

        # Now public
        assert module.is_public(IDatabase, name="primary")

    def test_export_named_raises_for_unregistered(self) -> None:
        """Test export_named() raises for unregistered dependencies."""
        module = Module("Database")

        with pytest.raises(RegistrationError, match="not registered"):
            module.export_named(IDatabase, "nonexistent")


class TestNamedBindingsParentChild:
    """Test parent-child container hierarchy with named dependencies."""

    def test_child_inherits_named_from_parent(self) -> None:
        """Test that child container inherits named bindings from parent."""
        parent = Container(name="Parent")
        parent.register(IDatabase, PostgresDB, name="primary")

        child = parent.create_child(name="Child")
        child.register(ICache, RedisCache)

        # Child should resolve from parent
        db = child.get(IDatabase, name="primary")
        assert isinstance(db, PostgresDB)

    def test_child_overrides_named_from_parent(self) -> None:
        """Test that child can override parent's named bindings."""
        parent = Container(name="Parent")
        parent.register(IDatabase, PostgresDB, name="primary")

        child = parent.create_child(name="Child")
        child.register(IDatabase, MySQLDB, name="primary")

        # Child's binding should take precedence
        db = child.get(IDatabase, name="primary")
        assert isinstance(db, MySQLDB)


class TestNamedBindingsExtractInfo:
    """Test extract_inject_info helper function."""

    def test_extract_unnamed_inject(self) -> None:
        """Test extracting info from Inject[T]."""
        hint = Inject[IDatabase]
        result = extract_inject_info(hint)

        assert result is not None
        actual_type, name = result
        assert actual_type is IDatabase
        assert name is None

    def test_extract_named_inject(self) -> None:
        """Test extracting info from Inject[T, Named(...)]."""
        hint = Inject[IDatabase, Named("primary")]
        result = extract_inject_info(hint)

        assert result is not None
        actual_type, name = result
        assert actual_type is IDatabase
        assert name == "primary"

    def test_extract_non_inject_returns_none(self) -> None:
        """Test that non-Inject type hints return None."""
        assert extract_inject_info(int) is None
        assert extract_inject_info(str) is None
        assert extract_inject_info(IDatabase) is None


class TestNamedBindingsConstructorInjection:
    """Test constructor injection with named dependencies."""

    def test_constructor_injection_named(self) -> None:
        """Test constructor parameter injection with named dependencies."""

        class UserRepository:
            def __init__(self, db: Inject[IDatabase, Named("primary")]) -> None:
                self.db = db

            def get_user(self, id: int) -> str:
                return self.db.query(f"SELECT * FROM users WHERE id = {id}")

        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")
        container.register(UserRepository)

        repo = container.get(UserRepository)
        assert isinstance(repo.db, PostgresDB)

    def test_constructor_injection_mixed(self) -> None:
        """Test constructor with mixed named and unnamed dependencies."""

        class DataService:
            def __init__(
                self,
                default_cache: Inject[ICache],
                special_db: Inject[IDatabase, Named("special")],
            ) -> None:
                self.cache = default_cache
                self.db = special_db

        container = Container()
        container.register(ICache, MemoryCache)
        container.register(IDatabase, PostgresDB, name="special")
        container.register(DataService)

        service = container.get(DataService)
        assert isinstance(service.cache, MemoryCache)
        assert isinstance(service.db, PostgresDB)


class TestNamedBindingsAsync:
    """Test async resolution with named dependencies."""

    @pytest.mark.asyncio
    async def test_get_async_with_name(self) -> None:
        """Test async resolution of named dependencies."""
        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")

        db = await container.get_async(IDatabase, name="primary")
        assert isinstance(db, PostgresDB)

    @pytest.mark.asyncio
    async def test_injectable_async_named(self) -> None:
        """Test async resolution of Injectable with named dependencies."""

        class AsyncService(Injectable):
            primary_db: Inject[IDatabase, Named("primary")]

        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")
        container.register(AsyncService)

        service = await container.get_async(AsyncService)
        assert isinstance(service.primary_db, PostgresDB)


class TestNamedBindingsFactoryWithNamedDeps:
    """Test factory functions that use named dependencies in their parameters."""

    def test_factory_with_named_dependency_parameter(self) -> None:
        """Test factory function that receives a named dependency."""

        class DataService:
            def __init__(self, db: IDatabase) -> None:
                self.db = db

        def create_data_service(
            db: Inject[IDatabase, Named("primary")],
        ) -> DataService:
            return DataService(db)

        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")
        container.register(DataService, factory=create_data_service)

        service = container.get(DataService)
        assert isinstance(service.db, PostgresDB)

    def test_factory_with_multiple_named_dependencies(self) -> None:
        """Test factory with multiple named dependencies."""

        class ReplicationService:
            def __init__(self, primary: IDatabase, replica: IDatabase) -> None:
                self.primary = primary
                self.replica = replica

        def create_replication_service(
            primary: Inject[IDatabase, Named("primary")],
            replica: Inject[IDatabase, Named("replica")],
        ) -> ReplicationService:
            return ReplicationService(primary, replica)

        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")
        container.register(IDatabase, MySQLDB, name="replica")
        container.register(ReplicationService, factory=create_replication_service)

        service = container.get(ReplicationService)
        assert isinstance(service.primary, PostgresDB)
        assert isinstance(service.replica, MySQLDB)

    def test_factory_with_mixed_named_and_unnamed_deps(self) -> None:
        """Test factory with both named and unnamed dependencies."""

        class CachedService:
            def __init__(self, cache: ICache, db: IDatabase) -> None:
                self.cache = cache
                self.db = db

        def create_cached_service(
            cache: Inject[ICache],
            primary_db: Inject[IDatabase, Named("primary")],
        ) -> CachedService:
            return CachedService(cache, primary_db)

        container = Container()
        container.register(ICache, RedisCache)
        container.register(IDatabase, PostgresDB, name="primary")
        container.register(CachedService, factory=create_cached_service)

        service = container.get(CachedService)
        assert isinstance(service.cache, RedisCache)
        assert isinstance(service.db, PostgresDB)


class TestNamedMarkerClass:
    """Test Named class behavior."""

    def test_named_equality(self) -> None:
        """Test Named equality comparison."""
        a = Named("primary")
        b = Named("primary")
        c = Named("replica")

        assert a == b
        assert a != c
        assert a != "primary"

    def test_named_hash(self) -> None:
        """Test Named can be used in sets/dicts."""
        names = {Named("primary"), Named("replica"), Named("primary")}
        assert len(names) == 2

    def test_named_repr(self) -> None:
        """Test Named repr."""
        assert repr(Named("primary")) == 'Named("primary")'

    def test_named_rejects_empty_string(self) -> None:
        """Test that Named rejects empty strings."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Named("")

    def test_named_rejects_whitespace_only(self) -> None:
        """Test that Named rejects whitespace-only strings."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Named("   ")

    def test_named_rejects_non_string(self) -> None:
        """Test that Named rejects non-string values with TypeError."""
        with pytest.raises(TypeError, match="must be a string"):
            Named(123)  # type: ignore[arg-type]

    def test_named_is_immutable(self) -> None:
        """Test that Named instances cannot be mutated after creation."""
        n = Named("primary")
        with pytest.raises(AttributeError):
            n.name = "changed"  # type: ignore[misc]

    def test_named_hash_stability_after_mutation_attempt(self) -> None:
        """Test that hash remains stable (mutation is blocked, hash doesn't change)."""
        n = Named("primary")
        original_hash = hash(n)
        with pytest.raises(AttributeError):
            n.name = "changed"  # type: ignore[misc]
        assert hash(n) == original_hash
        assert hash(n) == hash(("Named", "primary"))

    def test_named_delete_blocked(self) -> None:
        """Test that deleting name attribute is blocked."""
        n = Named("primary")
        with pytest.raises(AttributeError):
            del n.name  # type: ignore[misc]


class TestNamedBindingsErrorMessages:
    """Test error messages include name information."""

    def test_not_found_error_includes_name(self) -> None:
        """Test DependencyNotFoundError includes the name in message."""
        container = Container()

        with pytest.raises(DependencyNotFoundError) as exc_info:
            container.get(IDatabase, name="production")

        error = exc_info.value
        assert error.name == "production"
        assert "production" in str(error)
        assert "IDatabase" in str(error)


class TestNamedBindingsCircularDependency:
    """Test circular dependency detection with named bindings."""

    def test_circular_dependency_with_named_bindings(self) -> None:
        """Test that circular dependencies are detected with named bindings."""
        from inversipy.exceptions import CircularDependencyError

        class ServiceA:
            def __init__(self, b: Inject[IDatabase, Named("special")]) -> None:
                self.b = b

        class ServiceB:
            def __init__(self, a: ServiceA) -> None:
                self.a = a

        # Create a cycle: ServiceA -> IDatabase[special] -> ServiceB -> ServiceA
        container = Container()
        container.register(ServiceA)
        container.register(IDatabase, ServiceB, name="special")  # ServiceB implements IDatabase
        container.register(ServiceB)

        # This should raise CircularDependencyError when resolving
        with pytest.raises(CircularDependencyError):
            container.get(ServiceA)

    def test_validation_detects_missing_named_dependency(self) -> None:
        """Test that validation fails when named dependency is missing."""
        from inversipy.exceptions import ValidationError

        class ServiceWithNamedDep:
            def __init__(self, db: Inject[IDatabase, Named("primary")]) -> None:
                self.db = db

        container = Container()
        container.register(ServiceWithNamedDep)
        # NOT registering IDatabase with name="primary"

        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        error_msg = str(exc_info.value)
        assert "IDatabase" in error_msg
        assert "primary" in error_msg

    def test_validation_passes_with_named_dependency(self) -> None:
        """Test that validation passes when named dependency is registered."""

        class ServiceWithNamedDep:
            def __init__(self, db: Inject[IDatabase, Named("primary")]) -> None:
                self.db = db

        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")
        container.register(ServiceWithNamedDep)

        # Should not raise
        container.validate()

    def test_has_with_named_dependency_from_module(self) -> None:
        """Test that has() correctly checks modules for named dependencies."""
        module = Module("Database")
        module.register(IDatabase, PostgresDB, name="primary", public=True)

        container = Container()
        container.register_module(module)

        # has() should find named dependency from module
        assert container.has(IDatabase, name="primary")
        assert not container.has(IDatabase, name="replica")

    def test_validate_includes_named_bindings_in_graph(self) -> None:
        """Test that named bindings are included in cycle detection graph."""
        from inversipy.exceptions import ValidationError

        class ServiceWithDep:
            def __init__(self, db: IDatabase) -> None:
                self.db = db

        # Register implementation under a named binding
        # The implementation ServiceWithDep depends on IDatabase
        container = Container()
        container.register(IDatabase, ServiceWithDep, name="recursive")
        # This creates: IDatabase[name='recursive'] -> implementation needs IDatabase
        # Without the fix, this named binding would be skipped in cycle detection

        # This should raise validation error about missing IDatabase dependency
        with pytest.raises(ValidationError) as exc_info:
            container.validate()

        assert "IDatabase" in str(exc_info.value)


class TestNamedBindingsRun:
    """Test container.run() with named dependencies."""

    def test_run_with_named_dependency(self) -> None:
        """Test run() resolves Inject[T, Named(...)] correctly."""
        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")

        def my_func(db: Inject[IDatabase, Named("primary")]) -> str:
            return db.query("SELECT 1")

        result = container.run(my_func)
        assert "PostgreSQL" in result

    def test_run_with_multiple_named_dependencies(self) -> None:
        """Test run() with multiple named dependencies."""
        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")
        container.register(IDatabase, MySQLDB, name="replica")

        def my_func(
            primary: Inject[IDatabase, Named("primary")],
            replica: Inject[IDatabase, Named("replica")],
        ) -> tuple[str, str]:
            return (primary.query("SELECT 1"), replica.query("SELECT 2"))

        result = container.run(my_func)
        assert "PostgreSQL" in result[0]
        assert "MySQL" in result[1]

    def test_run_with_mixed_named_and_unnamed(self) -> None:
        """Test run() with both named and unnamed dependencies."""
        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")
        container.register(ICache, RedisCache)

        def my_func(
            db: Inject[IDatabase, Named("primary")],
            cache: Inject[ICache],
        ) -> tuple[str, str]:
            return (db.query("SELECT 1"), cache.get("key"))

        result = container.run(my_func)
        assert "PostgreSQL" in result[0]
        assert "redis" in result[1]  # RedisCache.get returns "redis:key"

    @pytest.mark.asyncio
    async def test_run_async_with_named_dependency(self) -> None:
        """Test run_async() resolves Inject[T, Named(...)] correctly."""
        container = Container()
        container.register(IDatabase, PostgresDB, name="primary")

        def my_func(db: Inject[IDatabase, Named("primary")]) -> str:
            return db.query("SELECT 1")

        result = await container.run_async(my_func)
        assert "PostgreSQL" in result


class TestModuleBuilderExportNamed:
    """Test ModuleBuilder.export_named() method."""

    def test_module_builder_export_named(self) -> None:
        """Test ModuleBuilder can export named dependencies."""
        module = (
            ModuleBuilder("Database")
            .bind(IDatabase, PostgresDB, name="primary")
            .export_named(IDatabase, "primary")
            .build()
        )

        assert module.is_public(IDatabase, name="primary")

    def test_module_builder_export_named_chaining(self) -> None:
        """Test ModuleBuilder.export_named() returns self for chaining."""
        module = (
            ModuleBuilder("Database")
            .bind(IDatabase, PostgresDB, name="primary")
            .bind(IDatabase, MySQLDB, name="replica")
            .export_named(IDatabase, "primary")
            .export_named(IDatabase, "replica")
            .build()
        )

        assert module.is_public(IDatabase, name="primary")
        assert module.is_public(IDatabase, name="replica")
