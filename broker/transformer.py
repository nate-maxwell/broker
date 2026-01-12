"""
Transformer system for event broker.

Transformers are like diet middleware...

Allows users to register transformers that intercept and modify event data
before it reaches subscribers. Transformers execute in priority order.
"""

import weakref
from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import Optional
from typing import Union


TRANSFORMER = Callable[[str, dict[str, Any]], Optional[dict[str, Any]]]
"""
A transformer function that receives (namespace, kwargs) and returns:
  - Modified kwargs dict to continue the chain
  - None to stop propagation (event is blocked)
"""

TRANSFORMER_EXCEPTION_HANDLER = Callable[[TRANSFORMER, str, Exception], bool]
"""
Signature for transformer exception handlers.

Exception handlers receive the failing transformer, namespace, and exception,
then return True to stop execution or False to continue.
"""


@dataclass(frozen=True)
class Transformer(object):
    """
    A transformer with callback and priority.
    Transformers alter the data emitted before it reaches the subscribers.
    """

    weak_callback: Union[weakref.ref[Any], weakref.WeakMethod]
    """
    The end point that data is forwarded to. i.e. what gets ran.
    This is a weak reference so the callback isn't kept alive by the broker.
    Broker can notify when item is garbage collected or deleted.
    """

    priority: int
    """Execution order - higher priorities run first."""

    namespace: str
    """The namespace pattern this transformer applies to."""

    @property
    def callback(self) -> Optional[TRANSFORMER]:
        """Get the live callback, or None if collected."""
        return self.weak_callback()
