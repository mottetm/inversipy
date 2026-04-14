"""Helpers for concurrency-related tests."""

import threading
from collections.abc import Callable


class CountingResolver:
    """A nullary callable that counts invocations and signals entry.

    Usable as both a Lazy resolver and a binding factory: every call
    increments ``call_count``, sets ``in_resolver``, and (optionally) blocks
    on a user-supplied ``wait`` hook before returning a fresh ``object()``.
    """

    def __init__(self, wait: Callable[[], object] | None = None) -> None:
        self.call_count = 0
        self.in_resolver = threading.Event()
        self._wait = wait

    def __call__(self) -> object:
        self.call_count += 1
        self.in_resolver.set()
        if self._wait:
            self._wait()
        return object()
