# Philosophy

## Design Principles

### Type Hints as Configuration

Dependencies are declared via Python type annotations — `Inject[T]`, `InjectAll[T]`, and `Named("x")`. There are no XML files, no YAML manifests, no external configuration. The container introspects type hints at resolution time to discover and wire dependencies automatically. The type system *is* the configuration language.

### Framework-Agnostic Classes

Classes never reference the container. A service declares its dependencies as constructor parameters or annotated fields and remains a plain Python object, fully usable without the DI framework. The optional `Injectable` base class uses `__init_subclass__` to generate constructors from annotations, but the resulting classes can still be instantiated manually — no container required.

### Explicit Visibility and Encapsulation

Module bindings are **private by default**. A dependency must be explicitly marked `public=True` or exported via `export()` to be visible outside its module. Internally, the container distinguishes external from internal resolution by inspecting the resolution stack: an empty stack means an external call (visibility enforced), a non-empty stack means an ongoing resolution chain (private access allowed). This gives modules real encapsulation without additional API complexity.

### Dual Sync/Async Support

Every resolution path — `get`/`get_async`, `run`/`run_async`, `get_all`/`get_all_async` — has both synchronous and asynchronous variants. The container detects async factories automatically and raises a clear error if one is used in a synchronous context, rather than silently producing a coroutine.

### Scope as Strategy

Lifecycle management follows the Strategy pattern. Three built-in strategies — Singleton (double-checked locking), Transient (fresh instance each time), and Request (one instance per context via `contextvars`) — implement the `BindingStrategy` interface. Each strategy encapsulates its own concurrency handling, making scope behavior pluggable without touching resolution logic.

### Safety by Design

Circular dependencies are caught at two layers: statically via DFS during `container.validate()`, and at runtime via the resolution stack (backed by context variables). After configuration, `container.freeze()` locks the container against further registration. Seven specific exception types (`DependencyNotFoundError`, `CircularDependencyError`, `ValidationError`, `InvalidScopeError`, `RegistrationError`, `ResolutionError`, `AmbiguousDependencyError`) enable precise error handling. Thread-safety is achieved through context variables — there is no global mutable state.

### Composition over Inheritance

Containers support parent–child nesting and module composition. The `ModuleProtocol` is a duck-typed interface: any object that implements its methods can serve as a module provider, without inheriting from a framework base class. This keeps the composition model open to third-party implementations.

---

## Comparison with the Ecosystem

### vs. dependency-injector

[dependency-injector](https://github.com/ets-labs/python-dependency-injector) is the most established Python DI library. It follows a **provider-centric** paradigm: dependencies are defined as provider objects (`Factory`, `Singleton`, `Callable`, etc.) declared as class attributes on a declarative container class. The container acts as a central blueprint where every dependency and its lifecycle are explicit and visible in one place.

This approach prioritizes transparency and central control. It also supports loading configuration from YAML, INI, JSON, and environment variables — something inversipy intentionally avoids in favor of code-only configuration. The tradeoff is coupling: consumer classes often reference the container directly via `Provide[Container.service]` markers, tying application code to the framework. Inversipy keeps classes completely unaware of the container, relying on type hints alone for dependency discovery.

### vs. lagom

[lagom](https://github.com/meadsteve/lagom) takes the opposite approach: **zero-configuration autowiring**. The container inspects `__init__` type hints and resolves dependencies automatically, with no explicit registration required for simple cases. Classes are entirely unaware of the framework — a principle inversipy shares.

Where the two diverge is in structure. Lagom deliberately minimizes controls: there is no module system, no private-by-default visibility, and limited validation or lifecycle management. It provides "just enough" help and trusts convention. Inversipy offers the same type-hint-driven autowiring but layers on explicit module encapsulation, pluggable scope strategies, and static validation — guardrails that become valuable as application complexity grows.

### vs. punq

[punq](https://github.com/bobthemighty/punq) values **simplicity and transparency** above all. No global state, no decorators, no magic — you create a container, register services explicitly, and resolve them. The entire library is small enough to read in one sitting. Classes use normal constructors with type hints, and composition happens through child containers that inherit parent registrations.

Inversipy shares punq's preference for explicit registration and its use of child containers for hierarchical composition. It extends the model with module-level encapsulation (private-by-default bindings), a formal scope strategy system, and dual-layer circular dependency detection — features that punq omits in the interest of staying minimal.

### vs. dishka

[dishka](https://github.com/reagento/dishka) is a modern framework that puts **lifecycle management at the center**. Its core abstraction is a scope hierarchy (APP → REQUEST → ACTION → STEP) with strict lifetime boundaries: dependencies are lazily created on first request and automatically finalized in reverse creation order when a scope exits. Providers are defined via `@provide`-decorated generator functions, which naturally express setup/teardown semantics.

Of all the frameworks in the ecosystem, dishka is the closest to inversipy in its emphasis on lifecycle and async-first design. The key differences lie in module design and extensibility. Dishka uses a components system for namespace isolation, but dependencies within a component are public by default. Inversipy inverts this: private by default, explicit export required. Dishka's scopes are a fixed hierarchy; inversipy's scopes are pluggable strategies, making it possible to introduce new lifecycle behaviors without modifying the container.

### vs. inject

[inject](https://github.com/ivankorobkov/python-inject) takes the **lightest possible touch**. A single global injector is configured at startup via a callback function. It does not steal constructors, does not try to manage the full object graph, and does not impose structure. Dependencies can be retrieved explicitly with `inject.instance(Type)` or injected into functions via decorators.

This minimalism makes inject easy to adopt in existing codebases, but it provides little structure for larger applications — no modules, no scope strategies, no validation, no hierarchy. Inversipy targets applications that need more architectural support while still keeping classes decoupled from the framework.

---

Inversipy combines the type-hint-driven autowiring found in lagom with the explicit registration and hierarchical composition of punq, then adds capabilities that are absent from the broader ecosystem: private-by-default module visibility for real encapsulation, a Strategy-based scope system that makes lifecycle behavior pluggable, and layered safety guarantees — static and runtime cycle detection, container freezing, and a rich error hierarchy.
