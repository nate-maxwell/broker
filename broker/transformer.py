"""
Transformer system for event broker.

Transformers are like diet middleware...

Allows users to register transformers that intercept and modify event data
before it reaches subscribers. Transformers execute in priority order.
"""

from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import Optional


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

    callback: TRANSFORMER
    """The transformer function to call."""

    priority: int
    """Execution order - higher priorities run first."""

    namespace: str
    """The namespace pattern this transformer applies to."""
