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

from broker import handlers
from broker import namespaces
from broker.private import namespace as _namespace


TRANSFORMER_SIG = Callable[[str, dict[str, Any]], Optional[dict[str, Any]]]
"""
A transformer function that receives (namespace, kwargs) and returns:
  - Modified kwargs dict to continue the chain
  - None to block delivery to the transformer's registered namespace
"""

TRANSFORMER_EXCEPTION_HANDLER = Callable[[TRANSFORMER_SIG, str, Exception], bool]
"""
Signature for transformer exception handlers.

Exception handlers receive the failing transformer, namespace, and exception,
then return True to stop execution or False to continue.
"""


transformer_exception_handler: Optional[TRANSFORMER_EXCEPTION_HANDLER] = (
    handlers.stop_and_log_transformer_exception
)
"""
Which handler to use when an exception is raised while passing messages to
transformer.
"""


@dataclass(frozen=True)
class Transformer(object):
    """
    A transformer with callback and priority.
    Transformers alter an isolated payload copy before it reaches subscribers
    registered to the same namespace. They can append metadata, validate and
    filter out bad messages, or completely change the local payload.
    """

    weak_callback: Union[weakref.ref[Any], weakref.WeakMethod[Any]]
    """
    The end point that data is forwarded to. i.e. what gets ran.
    This is a weak reference so the callback isn't kept alive by the broker.
    Broker can notify when item is garbage collected or deleted.
    """

    priority: int
    """Execution order - higher priorities run first."""

    namespace: str
    """The exact namespace delivery phase this transformer applies to."""

    @property
    def callback(self) -> Optional[TRANSFORMER_SIG]:
        """Get the live callback, or None if collected."""
        return self.weak_callback()


def set_transformer_exception_handler(
    handler: Optional[TRANSFORMER_EXCEPTION_HANDLER],
) -> None:
    """
    Set the exception handler for transformer errors.
    The handler is called when a transformer raises an exception during emit.

    Args:
        Optional[transformer.TRANSFORMER_EXCEPTION_HANDLER]:
            Callable with signature (TRANSFORMER, str, Exception) -> bool.
            Returns True to stop delivery, False to continue.
            Pass None to restore default behavior (re-raise exceptions).
    """
    global transformer_exception_handler
    transformer_exception_handler = handler


def clear_transformers() -> None:
    """Clear all registered transformers."""
    for namespace, entry in _namespace.NAMESPACE_REGISTRY.items():
        entry.transformers.clear()
        namespaces.cleanup_namespace_if_empty(namespace)
