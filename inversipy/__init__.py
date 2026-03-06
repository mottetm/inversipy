"""Inversipy - A powerful and type-safe dependency injection/IoC library for Python.

Inversipy provides a flexible dependency injection container with support for:
- Type annotation-based dependency resolution
- Container validation
- Modules with public/private dependencies
- Parent-child container hierarchy
- Multiple scopes (Singleton, Transient, Request)
- Function injection via container.run()
- Property injection via Injectable base class
- Pure classes with no container coupling
- Named dependencies for multiple implementations of the same interface
"""

from importlib.metadata import PackageNotFoundError, version

from .container import Container
from .decorators import (
    Inject,
    Injectable,
    InjectAll,
)
from .exceptions import (
    AmbiguousDependencyError,
    CircularDependencyError,
    DependencyNotFoundError,
    InvalidScopeError,
    InversipyError,
    RegistrationError,
    ResolutionError,
    ValidationError,
)
from .module import Module, ModuleBuilder
from .scopes import Scopes
from .types import Factory, Named

try:
    __version__ = version("inversipy")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    # Core classes
    "Container",
    "Module",
    "ModuleBuilder",
    # Scopes
    "Scopes",
    # Types
    "Factory",
    "Named",
    # Dependency injection utilities
    "Inject",
    "InjectAll",
    "Injectable",
    # Exceptions
    "InversipyError",
    "DependencyNotFoundError",
    "AmbiguousDependencyError",
    "CircularDependencyError",
    "ValidationError",
    "InvalidScopeError",
    "RegistrationError",
    "ResolutionError",
]
