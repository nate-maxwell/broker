"""
Subscriber data structures and type definitions for the event broker.

Defines the Subscriber dataclass which wraps callback functions with metadata
including priority, async status, and namespace. Uses weak references to allow
callbacks to be garbage collected, preventing the broker from keeping objects
alive indefinitely. Also defines the CALLBACK type alias used throughout the
broker system for type hints.
"""

import weakref
from dataclasses import dataclass
from types import ModuleType
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Optional
from typing import Union

SUBSCRIBER = Union[Callable[..., Any], Callable[..., Coroutine[Any, Any, Any]]]
"""
The callback end point that event info is forwarded to. These are the actions
that 'subscribe' and will execute when an event is triggered. Can be sync or
async.

The broker cannot determine which value to send back to the caller.
If you want data back, create an event going the opposite direction.
"""


@dataclass(frozen=True)
class Subscriber(object):
    """A subscriber with a callback and priority."""

    weak_callback: Union[weakref.ref[Any], weakref.WeakMethod]
    """
    The end point that data is forwarded to. i.e. what gets ran.
    This is a weak reference so the callback isn't kept alive by the broker.
    Broker can notify when item is garbage collected or deleted.
    """

    priority: int
    """
    Where in the execution order the callback should take place.
    Higher numbers are executed before lower numbers.
    """

    is_async: bool
    """If the item is asynchronous or not..."""

    namespace: str
    """The namespace the subscriber is listening to."""

    is_one_shot: bool
    """Whether to unregister self after firing."""

    @property
    def callback(self) -> Optional[SUBSCRIBER]:
        """Get the live callback, or None if collected."""
        return self.weak_callback()


def _make_subscribe_decorator(broker_module: ModuleType) -> Callable:
    """
    Create a subscribe decorator with access to the broker module.

    This exists as a function accepting the broker module as an argument so the
    function can call register_subscriber() on the broker without referring to
    it using a python namespace and thus creating a circular reference.
    """

    def subscribe_(
        namespace: str, priority: int = 0, once: bool = False
    ) -> Callable[[SUBSCRIBER], SUBSCRIBER]:

        def decorator(func: SUBSCRIBER) -> SUBSCRIBER:
            broker_module.register_subscriber(namespace, func, priority, once)
            return func

        return decorator

    return subscribe_
