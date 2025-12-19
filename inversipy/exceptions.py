"""Custom exceptions for the inversipy library."""

from typing import Any, Type


class InversipyError(Exception):
    """Base exception for all inversipy errors."""

    pass


class DependencyNotFoundError(InversipyError):
    """Raised when a dependency cannot be found in the container."""

    def __init__(self, dependency_type: Type[Any], container_name: str = "container") -> None:
        self.dependency_type = dependency_type
        self.container_name = container_name
        super().__init__(
            f"Dependency '{dependency_type.__name__}' not found in {container_name}"
        )


class CircularDependencyError(InversipyError):
    """Raised when a circular dependency is detected."""

    def __init__(self, dependency_chain: list[Type[Any]]) -> None:
        self.dependency_chain = dependency_chain
        chain_str = " -> ".join(dep.__name__ for dep in dependency_chain)
        super().__init__(f"Circular dependency detected: {chain_str}")


class ValidationError(InversipyError):
    """Raised when container validation fails."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        error_messages = "\n  - " + "\n  - ".join(errors)
        super().__init__(f"Container validation failed with {len(errors)} error(s):{error_messages}")


class InvalidScopeError(InversipyError):
    """Raised when an invalid scope is used."""

    pass


class RegistrationError(InversipyError):
    """Raised when there's an error during dependency registration."""

    pass


class ResolutionError(InversipyError):
    """Raised when there's an error during dependency resolution."""

    pass
