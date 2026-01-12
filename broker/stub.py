"""
Required for static type checkers to accept these names as members of the
broker module.

This module gets imported into the broker module so stubs are accessible
through the broker namespace.

The doc strings for each function exists in the stubs for intellisense
fetching, instead of within the broker class itself because the broker class
is a module replacement at runtime, so the namespaces during inspection are
different.
"""

import os
from typing import Any
from typing import Callable
from typing import Optional
from typing import Union

from broker import handlers
from broker import subscriber
from broker import transformer


# -----General Stubs-----------------------------------------------------------


def clear() -> None:
    """Clears the namespace and subscriber table."""


# noinspection PyUnusedLocal
def set_flag_states(
    on_subscribe: bool = False,
    on_unsubscribe: bool = False,
    on_subscriber_collected: bool = False,
    on_transform: bool = False,
    on_untransform: bool = False,
    on_transformer_collected: bool = False,
    on_emit: bool = False,
    on_emit_async: bool = False,
    on_emit_all: bool = False,
    on_new_namespace: bool = False,
    on_del_namespace: bool = False,
) -> None:
    """
    Set the notification flags on or off for each type of broker activity.
    The broker can be configured through any of the following:

    Args:
        on_subscribe:    	       if True, get notified whenever register_subscriber() is called;
        on_unsubscribe:  	       if True, get notified whenever unregister_subscriber() is called;
        on_subscriber_collected:   if True, get notified whenever a subscriber has been garbage collected;

        on_transform:    	       if True, get notified whenever register_transformer() is called;
        on_untransform:  	       if True, get notified whenever unregister_transformer() is called;
        on_transformer_collected:  if True, get notified whenever a transformer has been garbage collected;

        on_emit:			       if True, get notified whenever emit() is called;
        on_emit_async:		       if True, get notified whenever emit_async() is called;
        on_emit_all:		       if True, get notified whenever emit() or emit_async() is called.

        on_new_namespace: 	       if True, get notified whenever a new namespace is created;
        on_del_namespace:	       if True, get notified whenever a namespace is "deleted";
    """


def to_dict() -> dict:
    """Convert the broker structure to a dictionary."""


# noinspection PyUnusedLocal
def to_string() -> str:
    """Returns a string representation of the broker."""


# noinspection PyUnusedLocal
def export(filepath: Union[str, os.PathLike]) -> None:
    """Export broker structure to filepath."""


def get_namespaces() -> list[str]:
    """Get all registered namespaces."""


# noinspection PyUnusedLocal
def namespace_exists(namespace: str) -> bool:
    """Check if a namespace exists..."""


# noinspection PyUnresolvedReferences
# noinspection PyUnusedLocal
def get_matching_namespaces(pattern: str) -> list[str]:
    """
    Get all namespaces that match a pattern (including wildcards).

    Args:
        pattern (str): Pattern to match (e.g., 'system.*' or 'app.module.action').
    Returns:
        list[str]: List of matching namespace strings.
    Example:
        >>> broker.get_matching_namespaces('system.*')
        ['system.io.file', 'system.io.network']
    """


# noinspection PyUnresolvedReferences
# noinspection PyUnusedLocal
def get_namespace_info(namespace: str) -> Optional[dict[str, object]]:
    """
    Get detailed information about a namespace.

    Args:
        namespace (str): Namespace to get info for.
    Returns:
        Optional[dict[str, object]]: Dictionary with namespace details, or None
            if namespace doesn't exist.
    Example:
        >>> info = broker.get_namespace_info('test.event')
        >>> print(info)
        {
            'namespace': 'test.event',
            'subscriber_count': 3,
            'live_subscriber_count': 2,
            'expected_params': {'data', 'size'},
            'has_async': True,
            'has_sync': True,
            'priorities': [1, 5, 10]
        }
    """


# noinspection PyUnresolvedReferences
def get_all_namespace_info() -> dict[str, dict[str, object]]:
    """
    Get detailed information for all namespaces.

    Returns:
        dict[str, dict[str, object]]: Dictionary mapping namespace to info dict.
    Example:
        >>> all_info = broker.get_all_namespace_info()
        >>> for ns, info in all_info.items():
        ...     print(f"{ns}: {info['live_subscriber_count']} live subscribers")
    """


# noinspection PyUnresolvedReferences
def get_statistics() -> dict[str, object]:
    """
    Get overall broker statistics.

    Returns:
        dict[str, object]: Dictionary with broker-wide statistics.

    Example:
        >>> stats = broker.get_statistics()
        >>> print(stats)
        {
            'total_namespaces': 10,
            'total_subscribers': 45,
            'total_live_subscribers': 42,
            'dead_references': 3,
            'namespaces_with_async': 5,
            'namespaces_with_sync': 8,
            'average_subscribers_per_namespace': 4.5
        }
        {
            "total_namespaces": 10,
            "total_subscribers": 45,
            "total_live_subscribers": 42,
            "dead_subscriber_references": 3,
            "total_transformers": 11,
            "total_live_transformers": 9,
            "dead_transformer_references": 2,
            "namespaces_with_async": ['system.io', ...],
            "namespaces_with_sync": ['app.status', ...],
            "namespaces_with_transformers": ['system.io'],
            "average_subscribers_per_namespace": 22,
            "average_transformers_per_namespace": 4,
        }
    """


# -----Emitter Stubs-----------------------------------------------------------


# noinspection PyUnusedLocal
def emit(namespace: str, **kwargs: Any) -> None:
    """
    Emit an event to all matching synchronous subscribers.

    Synchronous subscribers are called immediately in priority order.
    Asynchronous subscribers are NOT called - they are skipped entirely.

    Use emit_async() if you need to call async subscribers or await their
    completion.

    Args:
        namespace (str): Event namespace (e.g., 'system.io.file_open').
        **kwargs (Any): Arguments to pass to subscriber callbacks.
    Raises:
        EmitArgumentError: If provided kwargs don't match subscriber signatures.
    Note:
        -This method only calls synchronous callbacks. Async callbacks are
        skipped. Use emit_async() to call async callbacks.
        -Emits a notify event after args have been sent to subscribers.
        Notify emits the used namespace.
    """


# noinspection PyUnusedLocal
async def emit_async(namespace: str, **kwargs: Any) -> None:
    """
    Asynchronously emit an event to all matching subscribers.

    Both synchronous and asynchronous subscribers are called in priority order.
    - Synchronous subscribers are executed immediately.
    - Asynchronous subscribers are awaited sequentially.

    This method must be awaited. Execution blocks until all subscribers complete.
    Use emit() for fire-and-forget behavior with sync-only subscribers.

    Args:
        namespace (str): Event namespace (e.g., 'system.io.file_open').
        **kwargs (Any): Arguments to pass to subscriber callbacks.
    Raises:
        EmitArgumentError: If provided kwargs don't match subscriber
            signatures.
    Note:
        -This method calls both sync and async callbacks. Sync callbacks are
        executed normally, async callbacks are awaited.
        -Emits a notify event after args have been sent to subscribers.
        Notify emits the used namespace.
    """


# -----Subscriber Stubs--------------------------------------------------------


# noinspection PyUnusedLocal
def register_subscriber(
    namespace: str, callback: subscriber.CALLBACK, priority: int = 0
) -> None:
    """
    Register a callback function to a namespace.

    Args:
        namespace (str): Event namespace
            (e.g., 'system.io.file_open' or 'system.*').
        callback (CALLBACK): Function to call when events are emitted. Can be
            sync or async.
        priority (int): The priority used for callback execution order.
            Higher priorities are ran before lower priorities.
    Raises:
        SignatureMismatchError: If callback signature doesn't match existing
            subscribers.
    Notes:
        Emits a notify event when a namespace is created and when a
        subscriber is registered. Notify emits the used namespace.
    """


# noinspection PyUnusedLocal
def subscribe(
    namespace: str, priority: int = 0
) -> Callable[[subscriber.CALLBACK], subscriber.CALLBACK]:
    """
    Decorator to register a function or static method as a subscriber.

    To register an instance referencing class method (one using 'self'),
    use broker.register_subscriber('source', 'event_name', self.method).

    Usage:
        @subscribe('system.file.io', 5)
        def on_file_open(filepath: str) -> None:
            print(f'File opened: {filepath}')
    Args:
        namespace (str): The event namespace to subscribe to.
        priority (int): The execution priority. Defaults to 0.
    Returns:
        Callable: Decorator function that registers the subscriber.
    """


# noinspection PyUnusedLocal
def unregister_subscriber(namespace: str, callback: subscriber.CALLBACK) -> None:
    """
    Remove a callback from a namespace.

    Args:
        namespace (str): Event namespace.
        callback (CALLBACK): Function to remove.
    Notes:
        Emits a notify event when subscriber is unregistered and when a
        namespace is removed from consolidation. Notify emits the used
        namespace.
    """


# noinspection PyUnusedLocal
def set_subscriber_exception_handler(
    handler: Optional[handlers.SUBSCRIPTION_EXCEPTION_HANDLER],
) -> None:
    """
    Set the exception handler for subscriber errors.
    The handler is called when a subscriber raises an exception during emit.

    Args:
        handler: Callable with signature (CALLBACK, str, Exception) -> bool.
                 Returns True to stop delivery, False to continue.
                 Pass None to restore default behavior (re-raise exceptions).
    Example:
        def my_handler(callback: Callable, namespace: str, exc: Exception) -> bool:
            print(f"Error in {namespace}: {exc}")
            return False  # Continue

        broker.set_subscriber_exception_handler(my_handler)

        # Or use the built-in default handler
        import broker
        broker.set_subscriber_exception_handler(broker.default_exception_handler)
    """


# noinspection PyUnusedLocal
def get_subscriber_count(namespace: str) -> int:
    """
    Get the number of subscribers for a namespace.

    Args:
        namespace (str): Namespace to count subscribers for.
    Returns:
        int: Number of subscribers (including dead weak references).
    """


# noinspection PyUnusedLocal
def get_live_subscriber_count(namespace: str) -> int:
    """
    Get the number of live (non-garbage-collected) subscribers.

    Args:
        namespace: Namespace to count live subscribers for.
    Returns:
        Number of subscribers with live callbacks.
    """


# noinspection PyUnusedLocal
def is_subscribed(callback: subscriber.CALLBACK, namespace: str) -> bool:
    """
    Check if a specific callback is subscribed to a namespace.

    Args:
        callback (Callable): The callback function to check.
        namespace (str): The namespace to check.

    Returns:
        bool: True if callback is subscribed to namespace, False otherwise.
    """


# noinspection PyUnresolvedReferences
# noinspection PyUnusedLocal
def get_subscriptions(callback: subscriber.CALLBACK) -> list[str]:
    """
    Get all namespaces that a callback is subscribed to.

    Args:
        callback (Callable): The callback to find subscriptions for.
    Returns:
        list[str]: List of namespace strings the callback is subscribed to.
    Example:
        >>> def my_handler(data: str): pass
        >>> broker.register_subscriber('test.one', my_handler)
        >>> broker.register_subscriber('test.two', my_handler)
        >>> broker.get_subscriptions(my_handler)
        ['test.one', 'test.two']
    """


# noinspection PyUnusedLocal
def get_subscribers(namespace: str) -> list[subscriber.Subscriber]:
    """
    Get all subscribers for a namespace.

    Args:
        namespace (str): Namespace to get subscribers for.
    Returns:
        list[subscriber.Subscriber]: List of Subscriber objects. May include
            dead references.
    """


# noinspection PyUnusedLocal
def get_live_subscribers(namespace: str) -> list[subscriber.Subscriber]:
    """
    Get all live (non-garbage-collected) subscribers for a namespace.

    Args:
        namespace (str): Namespace to get live subscribers for.
    Returns:
        list[subscriber.Subscriber]: List of Subscriber objects with live
            callbacks only.
    """


# -----Transformer Stubs-------------------------------------------------------


# noinspection PyUnusedLocal
def register_transformer(
    namespace: str, transformer_: transformer.TRANSFORMER, priority: int = 0
) -> None:
    """
    Register a transformer for a namespace.

    Transformers intercept events before they reach subscribers and can:
    - Modify event arguments
    - Block event propagation
    - Log/validate events

    Args:
        namespace (str): Namespace pattern (supports wildcards like 'system.*').
        transformer_ (TRANSFORMER): Function that receives (namespace, kwargs)
            and returns modified kwargs or None to block.
        priority (int): Execution order (higher = earlier, default 0).
    Example:
        def add_timestamp(namespace: str, kwargs: dict[str, Any]) -> dict:
            kwargs['timestamp'] = time.time()

            return kwargs

        broker.register_transformer('system.*', add_timestamp, priority=10)
    """


# noinspection PyUnusedLocal
def transform(
    namespace: str, priority: int = 0
) -> Callable[[transformer.TRANSFORMER], transformer.TRANSFORMER]:
    """
    Decorator to register a function or static method as a transformer.

    To register an instance referencing class method (one using 'self'),
    use broker.register_transformer('source', 'event_name', self.method).

    Usage:
        @transform('system.file.io', 5)
        def add_timestamp(namespace: str, kwargs: dict) -> dict:
            kwargs['timestamp'] = time.time()
            return kwargs
    Args:
        namespace (str): The event namespace to transform data for.
        priority (int): The execution priority. Defaults to 0.
    Returns:
        Callable: Decorator function that registers the transformer.
    """


# noinspection PyUnusedLocal
def unregister_transformer(
    namespace: str, transformer_: transformer.TRANSFORMER
) -> None:
    """
    Remove a transformer from a namespace.

    Args:
        namespace (str): The namespace the transformer is registered to.
        transformer_ (TRANSFORMER): The transformer function to remove.
    """


def set_transformer_exception_handler(
    handler: Optional[transformer.TRANSFORMER_EXCEPTION_HANDLER],
) -> None:
    """
    Set the exception handler for transformer errors.
    The handler is called when a transformer raises an exception during emit.

    Args:
        handler: Callable with signature (TRANSFORMER, str, Exception) -> bool.
                 Returns True to stop delivery, False to continue.
                 Pass None to restore default behavior (re-raise exceptions).
    Example:
        def custom_handler(
        transformer: TRANSFORMER, namespace: str, exception: Exception
        ) -> bool:
            print(f"Transformer error: {exception}")

            return False

        broker.set_transformer_exception_handler(my_handler)

        # Or use the built-in default handler
        import broker
        broker.set_transformer_exception_handler(broker.default_exception_handler)
    """


# noinspection PyUnusedLocal
def apply_transformers(
    namespace: str, kwargs: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """
    Apply all matching transformers to event kwargs.

    Transformers execute in priority order. If any transformer returns None,
    propagation stops and the event is blocked.

    Args:
        namespace (str): The event namespace being emitted.
        kwargs (dict[str, Any]): The event arguments.
    Returns:
        Modified kwargs dict, or None if event was blocked
    """


def clear_transformers() -> None:
    """Clear all registered transformers."""


def get_all_transformer_namespaces() -> list[str]:
    """Get all namespaces that have transformers."""


# noinspection PyUnusedLocal
def get_transformer_count(namespace: str) -> int:
    """
    Get the number of transformers for a namespace.

    Args:
        namespace (str): Namespace to count transformers for.
    Returns:
        int: Number of transformers (including dead weak references).
    """


# noinspection PyUnusedLocal
def get_live_transformer_count(namespace: str) -> int:
    """
    Get the number of live (non-garbage-collected) transformers.

    Args:
        namespace: Namespace to count live transformers for.
    Returns:
        Number of transformers with live callbacks.
    """


# noinspection PyUnusedLocal
def is_transformed(callback: transformer.TRANSFORMER, namespace: str) -> bool:
    """
    Check if a specific callback is registered as a transformer for a namespace.

    Args:
        callback (Callable): The transformer function to check.
        namespace (str): The namespace to check.

    Returns:
        bool: True if callback is registered as transformer for namespace, False otherwise.
    """


# noinspection PyUnresolvedReferences
# noinspection PyUnusedLocal
def get_transformations(callback: transformer.TRANSFORMER) -> list[str]:
    """
    Get all namespaces that a callback is registered as a transformer for.

    Args:
        callback (Callable): The transformer callback to find registrations for.
    Returns:
        list[str]: List of namespace strings the callback transforms.
    Example:
        >>> def my_transformer(namespace: str, kwargs: dict) -> dict:
        ...     return kwargs
        >>> broker.register_transformer('test.one', my_transformer)
        >>> broker.register_transformer('test.two', my_transformer)
        >>> broker.get_transformations(my_transformer)
        ['test.one', 'test.two']
    """


# noinspection PyUnusedLocal
def get_transformers(namespace: str) -> list[transformer.Transformer]:
    """
    Get all transformers for a namespace.

    Args:
        namespace (str): Namespace to get transformers for.
    Returns:
        list[transformer.Transformer]: List of Transformer objects. May include
            dead references.
    """


# noinspection PyUnusedLocal
def get_live_transformers(namespace: str) -> list[transformer.Transformer]:
    """
    Get all live (non-garbage-collected) transformers for a namespace.

    Args:
        namespace (str): Namespace to get live transformers for.
    Returns:
        list[transformer.Transformer]: List of Transformer objects with live
            callbacks only.
    """
