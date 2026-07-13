"""
Pause context manager for the event broker.

Provides PausedContext, a context manager that suppresses all event emission
for the duration of a with block. Emission resumes automatically on exit,
even if an exception is raised.

Supports nesting — the broker tracks pause depth as an integer counter rather
than a bool, so inner contexts exiting do not prematurely unpause outer ones.

Accessed via broker.paused():

    with broker.paused():
        broker.emit('file.saved', filename='test.exr')  # suppressed
"""

from types import TracebackType
from typing import Optional

from broker import routing


class PausedContext(object):
    """Context manager that pauses event emission for the duration of the block."""

    def __call__(self) -> "PausedContext":
        return self

    def __enter__(self) -> "PausedContext":
        # noinspection PyProtectedMember
        routing._paused += 1
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        # noinspection PyProtectedMember
        routing._paused -= 1
        return None
