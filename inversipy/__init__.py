"""Inversipy - A powerful and type-safe dependency injection/IoC library for Python.

Inversipy provides a flexible dependency injection container with support for:
- Type annotation-based dependency resolution
- Container validation
- Modules with public/private dependencies
- Parent-child container hierarchy
- Multiple scopes (Singleton, Transient, Request, AsyncSingleton)
- Decorator-based registration
"""

from .container import Container
from .module import Module, ModuleBuilder, Binding
from .scopes import (
    SingletonScope,
    TransientScope,
    RequestScope,
    AsyncSingletonScope,
    SINGLETON,
    TRANSIENT,
    REQUEST,
)
from .types import Scope, AsyncScope, Factory, DependencyKey
from .decorators import injectable, singleton, transient, inject, Inject
from .exceptions import (
    InversipyError,
    DependencyNotFoundError,
    CircularDependencyError,
    ValidationError,
    InvalidScopeError,
    RegistrationError,
    ResolutionError,
)

__version__ = "0.1.0"

__all__ = [
    # Core classes
    "Container",
    "Binding",
    "Module",
    "ModuleBuilder",
    # Scopes
    "Scope",
    "AsyncScope",
    "SingletonScope",
    "TransientScope",
    "RequestScope",
    "AsyncSingletonScope",
    "SINGLETON",
    "TRANSIENT",
    "REQUEST",
    # Types
    "Factory",
    "DependencyKey",
    # Decorators
    "injectable",
    "singleton",
    "transient",
    "inject",
    "Inject",
    # Exceptions
    "InversipyError",
    "DependencyNotFoundError",
    "CircularDependencyError",
    "ValidationError",
    "InvalidScopeError",
    "RegistrationError",
    "ResolutionError",
]
