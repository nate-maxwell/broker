"""
# Primary event routing logic

Herein is the event broker's routing system itself.

For a complete breakdown of broker functionality, read the project readme.
"""

from typing import Any
from typing import Optional

from broker import function
from broker import handlers
from broker import namespaces
from broker import subscriber
from broker import transformer
from broker.private import registry

__all__ = [
    # ---vars---
    "notify_on_all",
    "notify_on_subscribe",
    "notify_on_unsubscribe",
    "notify_on_collected",
    "notify_on_transformer_add",
    "notify_on_transformer_remove",
    "notify_on_transformer_collected",
    "notify_on_emit",
    "notify_on_emit_async",
    "notify_on_emit_all",
    "notify_on_new_namespace",
    "notify_on_del_namespace",
    # ---funcs---
    "emit",
    "emit_async",
    "stage",
    "emit_staged",
    "emit_staged_async",
    "clear",
    "clear_staged",
    "notify_new_namespace_created",
    "set_flag_states",
]

notify_on_all: bool = False

notify_on_subscribe: bool = False
notify_on_unsubscribe: bool = False
notify_on_collected: bool = False

notify_on_transformer_add: bool = False
notify_on_transformer_remove: bool = False
notify_on_transformer_collected: bool = False

notify_on_emit: bool = False
notify_on_emit_async: bool = False
notify_on_emit_all: bool = False

notify_on_new_namespace: bool = False
notify_on_del_namespace: bool = False

_paused: int = 0
"""
When greater than 0, the broker will not pass signals on to subscribers
through emit or emit_async. Primarily toggled through context managers.

This is tracked as an integer instead of a bool so that nested context
managers will not create an invalid state for outer context managers.
i.e. if a `with` block nested in another exists, the __exit__ may create
an invalid state that the outer `with` block will use before exiting.
"""


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
    if _paused > 0:
        return

    function.validate_emit_args(namespace, kwargs)

    transformed_kwargs = _apply_transformers(namespace, kwargs)
    if transformed_kwargs is None:
        return

    one_shots: list[tuple[str, subscriber.SUBSCRIBER]] = []

    for reg_namespace, sub in registry.get_sorted_subscribers(namespace):
        callback = sub.callback
        if callback is None or sub.is_async:
            continue

        try:
            callback(**transformed_kwargs)
        except Exception as e:
            if subscriber.subscriptions_exception_handler is None:
                raise
            if subscriber.subscriptions_exception_handler(callback, namespace, e):
                break

        if sub.is_one_shot:
            one_shots.append((reg_namespace, callback))

    for reg_namespace, callback in one_shots:
        subscriber.unregister_subscriber(reg_namespace, callback)

    if not namespace.startswith(namespaces.NOTIFY_NAMESPACE_ROOT) and (
        notify_on_emit or notify_on_emit_all
    ):
        emit(namespace=namespaces.BROKER_ON_EMIT, using=namespace)


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
    if _paused > 0:
        return

    function.validate_emit_args(namespace, kwargs)

    transformed_kwargs = _apply_transformers(namespace, kwargs)
    if transformed_kwargs is None:
        return  # Event blocked

    one_shots: list[tuple[str, subscriber.SUBSCRIBER]] = []

    for reg_namespace, sub in registry.get_sorted_subscribers(namespace):
        callback = sub.callback

        if callback is None:
            continue

        try:
            if sub.is_async:
                await callback(**transformed_kwargs)
            else:
                callback(**transformed_kwargs)
        except Exception as e:
            if subscriber.subscriptions_exception_handler is None:
                raise

            if subscriber.subscriptions_exception_handler(callback, namespace, e):
                break

        if sub.is_one_shot:
            one_shots.append((reg_namespace, callback))

    for reg_namespace, callback in one_shots:
        subscriber.unregister_subscriber(reg_namespace, callback)

    if not namespace.startswith(namespaces.NOTIFY_NAMESPACE_ROOT) and (
        notify_on_emit_async or notify_on_emit_all
    ):
        emit(namespace=namespaces.BROKER_ON_EMIT_ASYNC, using=namespace)


def stage(namespace: str, **kwargs: Any) -> None:
    """
    Stage an entry for emitting later.

    Entries will only be emitted upon calling broker.emit_staged()or
    broker.emit_staged_async().

    Signature validation will only occur when emitted, not on staging.

    Args:
        namespace (str): The namespace to pass the event to.
        **kwargs: The arguments to pass through the namespace.
    """
    registry.STAGED_REGISTRY[namespace].append(kwargs)


def emit_staged(flush: bool = True) -> None:
    """
    Emits staged events through broker.emit()

    Args:
        flush (bool): Whether to empty the current staging registry after
            emitting. Defaults to True.
    """
    namespaces_ = list(registry.STAGED_REGISTRY.keys())
    staged = {ns: list(registry.STAGED_REGISTRY[ns]) for ns in namespaces_}

    if flush:
        registry.STAGED_REGISTRY.clear()

    for namespace, events in staged.items():
        for kwargs in events:
            emit(namespace, **kwargs)


async def emit_staged_async(flush: bool = True) -> None:
    """
    Emits staged events through broker.emit_async()

    Args:
        flush (bool): Whether to empty the current staging registry after
            emitting. Defaults to True.
    """
    namespaces_ = list(registry.STAGED_REGISTRY.keys())
    staged = {ns: list(registry.STAGED_REGISTRY[ns]) for ns in namespaces_}

    if flush:
        registry.STAGED_REGISTRY.clear()

    for namespace, events in staged.items():
        for kwargs in events:
            await emit_async(namespace, **kwargs)


def clear() -> None:
    registry.NAMESPACE_REGISTRY.clear()


def clear_staged() -> None:
    registry.STAGED_REGISTRY.clear()


def notify_new_namespace_created(namespace: str) -> None:
    if (
        not namespace.startswith(namespaces.NOTIFY_NAMESPACE_ROOT)
        and notify_on_new_namespace
    ):
        emit(namespace=namespaces.BROKER_ON_NAMESPACE_CREATED, using=namespace)


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
    global notify_on_subscribe
    global notify_on_unsubscribe
    global notify_on_collected
    global notify_on_transformer_add
    global notify_on_transformer_remove
    global notify_on_transformer_collected
    global notify_on_emit
    global notify_on_emit_async
    global notify_on_emit_all
    global notify_on_new_namespace
    global notify_on_del_namespace

    notify_on_subscribe = on_subscribe
    notify_on_unsubscribe = on_unsubscribe
    notify_on_collected = on_subscriber_collected

    notify_on_transformer_add = on_transform
    notify_on_transformer_remove = on_untransform
    notify_on_transformer_collected = on_transformer_collected

    notify_on_emit = on_emit
    notify_on_emit_async = on_emit_async
    notify_on_emit_all = on_emit_all

    notify_on_new_namespace = on_new_namespace
    notify_on_del_namespace = on_del_namespace


def _apply_transformers(
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
    matching_transformers = []

    for reg_namespace, entry in registry.NAMESPACE_REGISTRY.items():
        if registry.matches(namespace, reg_namespace):
            matching_transformers.extend(entry.transformers)

    matching_transformers.sort(key=lambda t: t.priority, reverse=True)
    current_kwargs = kwargs.copy()

    for transformer_obj in matching_transformers:
        callback = transformer_obj.callback
        if callback is None:
            continue

        try:
            result = callback(namespace, current_kwargs)
            if result is None:
                return None

            current_kwargs = result

        except Exception as e:
            if transformer.transformer_exception_handler is not None:
                stop = transformer.transformer_exception_handler(callback, namespace, e)
                if stop:
                    return None
            else:
                transformer_name = handlers.get_callable_name(callback)
                raise RuntimeError(
                    f"Transformer '{transformer_name}' failed for namespace '{namespace}': {e}"
                ) from e

    return current_kwargs
