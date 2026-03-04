# Collection Injection

Register multiple implementations and inject them as a collection using `InjectAll`.

## Registration

Multiple `register()` calls for the same interface **accumulate** (they don't overwrite):

```python
from inversipy import Container

class IPlugin:
    def execute(self) -> str:
        raise NotImplementedError

class PluginA(IPlugin):
    def execute(self) -> str:
        return "PluginA executed"

class PluginB(IPlugin):
    def execute(self) -> str:
        return "PluginB executed"

container = Container()
container.register(IPlugin, PluginA)
container.register(IPlugin, PluginB)
```

## Resolution

```python
# Get all implementations
plugins = container.get_all(IPlugin)  # [PluginA(), PluginB()]

# Single resolution fails when ambiguous
# container.get(IPlugin)  # raises AmbiguousDependencyError
```

## Property Injection

```python
from inversipy import Injectable, InjectAll

class PluginManager(Injectable):
    plugins: InjectAll[IPlugin]

    def run_all(self) -> list[str]:
        return [plugin.execute() for plugin in self.plugins]

container.register(PluginManager)
manager = container.get(PluginManager)
results = manager.run_all()  # ['PluginA executed', 'PluginB executed']
```

See also: [Named Dependencies](named.md) for grouping implementations by name.
