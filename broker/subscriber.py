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
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Optional
from typing import Union

from broker import handlers


SUBSCRIBER_SIG = Union[Callable[..., Any], Callable[..., Coroutine[Any, Any, Any]]]
"""
The callback end point that event info is forwarded to. These are the actions
that 'subscribe' and will execute when an event is triggered. Can be sync or
async.

The broker cannot determine which value to send back to the caller.
If you want data back, create an event going the opposite direction.
"""

SUBSCRIPTION_EXCEPTION_HANDLER = Callable[[SUBSCRIBER_SIG, str, Exception], bool]
"""
Signature for exception handlers.

Exception handlers receive the failing callback, namespace, and exception, then
return True to stop delivery or False to continue to remaining subscribers.
"""

subscriptions_exception_handler: Optional[SUBSCRIPTION_EXCEPTION_HANDLER] = (
    handlers.stop_and_log_subscriber_exception
)
"""
Which handler to use when an exception is raised while passing messages to
subscribers.
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
    def callback(self) -> Optional[SUBSCRIBER_SIG]:
        """Get the live callback, or None if collected."""
        return self.weak_callback()


def set_subscriber_exception_handler(
    handler: Optional[SUBSCRIPTION_EXCEPTION_HANDLER],
) -> None:
    """
    Set the exception handler for subscriber errors.
    The handler is called when a subscriber raises an exception during emit.

    Args:
        Optional[SUBSCRIPTION_EXCEPTION_HANDLER]:
            Callable with signature (SUBSCRIBER, str, Exception) -> bool.
            Returns True to stop delivery, False to continue.
            Pass None to restore default behavior (re-raise exceptions).
    """
    global subscriptions_exception_handler
    subscriptions_exception_handler = handler
