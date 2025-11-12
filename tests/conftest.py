"""Pytest configuration and fixtures for inversipy tests."""
import pytest
from inversipy import Scopes


@pytest.fixture(autouse=True)
def reset_scopes():
    """Reset all scopes after each test to prevent state leakage."""
    yield
    # Reset all scopes after the test completes
    for scope in Scopes:
        scope.reset()
