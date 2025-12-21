"""Mypy plugin for Inject[T, Named("x")] support.

This plugin enables mypy to properly type-check the Inject type alias with
variadic type parameters including Named qualifiers.

Usage:
    Add to your mypy.ini or pyproject.toml:

    [mypy]
    plugins = inversipy.mypy_plugin

    Or in pyproject.toml:

    [tool.mypy]
    plugins = ["inversipy.mypy_plugin"]
"""

from __future__ import annotations

from collections.abc import Callable

from mypy.plugin import AnalyzeTypeContext, Plugin
from mypy.types import Type


class InversipyPlugin(Plugin):
    """Mypy plugin to support Inject[T, Named("x")] syntax.

    The Inject type alias is defined as:
        type Inject[T, *Ts] = Annotated[T, _inject_marker, *Ts]

    Mypy validates type arguments before expanding type aliases, and rejects
    Named("x") as an invalid type argument (since it's a call expression).
    This plugin intercepts the type analysis and properly handles the Inject
    type alias to extract just the first type argument (T) for type checking.
    """

    def get_type_analyze_hook(self, fullname: str) -> Callable[[AnalyzeTypeContext], Type] | None:
        """Return a hook for analyzing type expressions.

        Args:
            fullname: Fully qualified name of the type being analyzed

        Returns:
            A callback function if this is an Inject type, None otherwise
        """
        if fullname == "inversipy.decorators.Inject" or fullname.endswith(".Inject"):
            return inject_type_callback
        return None


def inject_type_callback(ctx: AnalyzeTypeContext) -> Type:
    """Transform Inject[T, ...] to T for type checking.

    This callback is invoked when mypy encounters an Inject type alias.
    It extracts the first type argument (the actual dependency type) and
    returns it so that attribute access and method calls work correctly.

    For example:
        db: Inject[IDatabase, Named("primary")]

    Is treated as type IDatabase for type checking, so self.db.query()
    will properly type-check against IDatabase's methods.

    Args:
        ctx: The type analysis context from mypy

    Returns:
        The analyzed first type argument (T)
    """
    args = ctx.type.args

    if not args:
        ctx.api.fail("Inject requires at least one type argument", ctx.context)
        return ctx.api.named_type("builtins.object", [])

    # The first argument is the actual type (T)
    # Additional arguments (like Named("x")) are qualifiers for runtime
    first_arg = args[0]

    # Analyze and return the first type argument
    return ctx.api.analyze_type(first_arg)


def plugin(version: str) -> type[Plugin]:
    """Entry point for the mypy plugin.

    Args:
        version: The mypy version string

    Returns:
        The plugin class
    """
    return InversipyPlugin
