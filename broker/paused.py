"""lorem ipsum dolor sit amet"""

from types import TracebackType
from typing import Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from broker._broker import Broker


class PausedContext(object):
    """Context manager that pauses event emission for the duration of the block."""

    def __init__(self, broker: "Broker") -> None:
        self._broker = broker

    def __call__(self) -> "PausedContext":
        return self

    def __enter__(self) -> "PausedContext":
        # noinspection PyProtectedMember
        self._broker._paused += 1
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        # noinspection PyProtectedMember
        self._broker._paused -= 1
        return None
