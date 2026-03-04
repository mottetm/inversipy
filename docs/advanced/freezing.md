# Container Freezing

Freeze a container to prevent accidental registration during runtime.

## Usage

```python
from inversipy import Container, RegistrationError

container = Container()
container.register(Database)
container.register(UserService)
container.validate()
container.freeze()

# Resolution still works
service = container.get(UserService)

# Registration is blocked
try:
    container.register(AnotherService)
except RegistrationError:
    print("Cannot register: container is frozen")
```

## What's Blocked

After `freeze()`, these methods raise `RegistrationError`:

- `register()`
- `register_factory()`
- `register_instance()`
- `register_module()`

## Cascading Behavior

Freezing cascades to all dependency providers that could affect resolution:

- **Modules**: All registered modules are frozen, preventing mutations that
  could cause ambiguous resolution errors.
- **Parent containers**: The parent container (if any) is also frozen, since
  the container delegates unresolved dependencies to its parent.
- **Child containers**: Freezing does **not** cascade to child containers.
  Children have independent lifecycles and their own freeze state.

```python
module = Module("auth")
module.register(AuthService, public=True)

parent = Container()
parent.register(Database)

child = parent.create_child()
child.register_module(module)
child.freeze()

# Both the module and parent are now frozen
module.frozen   # True
parent.frozen   # True
child.frozen    # True
```

## Checking Freeze State

```python
container.frozen  # True or False
```

## Method Chaining

```python
container = Container()
container.register(Database).register(UserService).freeze()
```
