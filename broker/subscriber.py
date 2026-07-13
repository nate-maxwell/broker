"""
Subscriber data structures and type definitions for the event broker.

Defines the Subscriber dataclass which wraps callback functions with metadata
including priority, async status, and namespace. Uses weak references to allow
callbacks to be garbage collected, preventing the broker from keeping objects
alive indefinitely. Also defines the CALLBACK type alias used throughout the
broker system for type hints.
"""

import inspect
import weakref
from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Optional
from typing import Union

from broker import exceptions
from broker import function
from broker import handlers
from broker import introspection
from broker import namespaces
from broker import routing
from broker.private import registry

__all__ = [
    "SUBSCRIBER",
    "subscriptions_exception_handler",
    "Subscriber",
    "register_subscriber",
    "subscribe",
    "unregister_subscriber",
    "unregister_subscriber_all",
    "set_subscriber_exception_handler",
]

SUBSCRIBER = Union[Callable[..., Any], Callable[..., Coroutine[Any, Any, Any]]]
"""
The callback end point that event info is forwarded to. These are the actions
that 'subscribe' and will execute when an event is triggered. Can be sync or
async.

The broker cannot determine which value to send back to the caller.
If you want data back, create an event going the opposite direction.
"""

SUBSCRIPTION_EXCEPTION_HANDLER = Callable[[SUBSCRIBER, str, Exception], bool]
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
    def callback(self) -> Optional[SUBSCRIBER]:
        """Get the live callback, or None if collected."""
        return self.weak_callback()


def register_subscriber(
    namespace: str,
    callback: SUBSCRIBER,
    priority: int = 0,
    once: bool = False,
) -> None:
    """
    Register a callback function to a namespace.

    Args:
        namespace (str): Event namespace
            (e.g., 'system.io.file_open' or 'system.*').
        callback (Callable): Function to call when events are emitted. Can be
            sync or async.
        priority (int): The priority used for callback execution order.
            Higher priorities are ran before lower priorities.
        once: (bool): Whether the subscriber should unregister itself after
            firing. Defaults to False.
    Raises:
        SignatureMismatchError: If callback signature doesn't match existing
            subscribers.
    Notes:
        Emits a notify event when a namespace is created and when a
        subscriber is registered. Notify emits the used namespace.
    """
    callback_params = function.get_callback_params(callback)
    is_async = inspect.iscoroutinefunction(callback)

    weak_callback = function.make_weak_ref(
        callback=callback,
        namespace=namespace,
        on_collected_callback=_on_subscriber_collected,
    )

    sub = Subscriber(
        weak_callback=weak_callback,
        priority=priority,
        is_async=is_async,
        namespace=namespace,
        is_one_shot=once,
    )

    is_new_namespace = registry.ensure_namespace_exists(namespace)
    entry = registry.NAMESPACE_REGISTRY[namespace]

    # Validate/set signature
    if entry.signature is None:
        entry.signature = callback_params
    else:
        existing_params = entry.signature
        if existing_params is None or callback_params is None:
            entry.signature = None
        elif existing_params != callback_params:
            raise exceptions.SignatureMismatchError(
                f"Subscriber parameter mismatch for namespace '{namespace}'. "
                f"Expected parameters: {sorted(existing_params)}, "
                f"but got: {sorted(callback_params)}"
            )

    entry.subscribers.append(sub)

    if is_new_namespace:
        routing.notify_new_namespace_created(namespace)

    if (
        not namespace.startswith(namespaces.NOTIFY_NAMESPACE_ROOT)
        and routing.notify_on_subscribe
    ):
        routing.emit(namespace=namespaces.BROKER_ON_SUBSCRIBER_ADDED, using=namespace)


def subscribe(
    namespace: str, priority: int = 0, once: bool = False
) -> Callable[[SUBSCRIBER], SUBSCRIBER]:
    """
    Decorator to register a function or static method as a subscriber.

    To register an instance referencing class method (one using 'self'),
    use broker.register_subscriber('source', 'event_name', self.method).

    Args:
        namespace (str): The event namespace to subscribe to.
        priority (int): The execution priority. Defaults to 0.
        once: (bool): Whether the subscriber should unregister itself after
            firing. Defaults to False.
    """

    def decorator(func: SUBSCRIBER) -> SUBSCRIBER:
        register_subscriber(namespace, func, priority, once)
        return func

    return decorator


def unregister_subscriber(namespace: str, callback: SUBSCRIBER) -> None:
    """
    Remove a callback from a namespace.

    Args:
        namespace (str): Event namespace.
        callback (Callable): Function to remove.
    Notes:
        Emits a notify event when subscriber is unregistered and when a
        namespace is removed from consolidation. Notify emits the used
        namespace.
    """
    if namespace not in registry.NAMESPACE_REGISTRY:
        return

    entry = registry.NAMESPACE_REGISTRY[namespace]
    items = entry.subscribers
    entry.subscribers = [i for i in items if i.callback != callback]

    if (
        not namespace.startswith(namespaces.NOTIFY_NAMESPACE_ROOT)
        and routing.notify_on_unsubscribe
    ):
        routing.emit(namespace=namespaces.BROKER_ON_SUBSCRIBER_REMOVED, using=namespace)

    namespaces.cleanup_namespace_if_empty(namespace)


def unregister_subscriber_all(callback: SUBSCRIBER) -> None:
    """
    Removes a subscriber from all namespaces it is currently present in.

    Args:
        callback (Callable): The callable to unsubscribe.
    """
    subscriber_namespaces = introspection.get_subscriptions(callback)
    for namespace in subscriber_namespaces:
        unregister_subscriber(namespace, callback)


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


def _on_subscriber_collected(namespace: str) -> None:
    """Called when a subscriber is garbage collected."""
    if namespace in registry.NAMESPACE_REGISTRY:
        entry = registry.NAMESPACE_REGISTRY[namespace]
        items = entry.subscribers
        entry.subscribers = [i for i in items if i.callback is not None]

        namespaces.cleanup_namespace_if_empty(namespace)

    if routing.notify_on_collected and not namespace.startswith(
        namespaces.NOTIFY_NAMESPACE_ROOT
    ):
        routing.emit(
            namespace=namespaces.BROKER_ON_SUBSCRIBER_COLLECTED, using=namespace
        )
