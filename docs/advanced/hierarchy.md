# Parent-Child Containers

Create container hierarchies where children inherit parent dependencies.

## Basic Usage

```python
from inversipy import Container, Scopes

parent = Container(name="Parent")
parent.register(Database, scope=Scopes.SINGLETON)
parent.register(Config, scope=Scopes.SINGLETON)

child = parent.create_child(name="RequestContainer")
child.register(RequestContext)
child.register(RequestHandler)

# Child can access parent dependencies
db = child.get(Database)         # Resolved from parent
handler = child.get(RequestHandler)  # Resolved from child

# Parent is not affected by child registrations
assert not parent.has(RequestHandler)
```

## Use Cases

- **Request-scoped containers**: Create a child per request with request-specific services
- **Test isolation**: Create a child container that overrides production services with mocks
- **Plugin systems**: Each plugin gets its own child container while sharing core services
