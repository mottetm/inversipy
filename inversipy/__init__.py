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

from .container import Binding, Container
from .decorators import (
    Inject,
    InjectAll,
    InjectAllNamed,
    Injectable,
    extract_inject_all_info,
    extract_inject_all_type,
    extract_inject_info,
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
from .types import DependencyKey, Factory, ModuleProtocol, Named

__version__ = "0.1.0"

__all__ = [
    # Core classes
    "Container",
    "Binding",
    "Module",
    "ModuleBuilder",
    # Scopes
    "Scopes",
    # Types
    "Factory",
    "DependencyKey",
    "ModuleProtocol",
    "Named",
    # Dependency injection utilities
    "Inject",
    "InjectAll",
    "InjectAllNamed",
    "Injectable",
    "extract_inject_info",
    "extract_inject_all_type",
    "extract_inject_all_info",
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
