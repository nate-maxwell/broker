import inspect
from typing import Callable

from broker import subscriber
from broker import transformer
from broker import exceptions
from broker import function
from broker import introspection
from broker import namespaces
from broker import routing
from broker.private import registry


__all__ = [
    "SignatureMismatchError",
    "register_subscriber",
    "subscribe",
    "unregister_subscriber",
    "unregister_subscriber_all",
    "register_transformer",
    "transform",
    "unregister_transformer",
    "unregister_transformer_all",
]


class SignatureMismatchError(Exception):
    """Raised when callback signatures don't match for a namespace."""


# -----Subscribers-------------------------------------------------------------


def register_subscriber(
    namespace: str,
    callback: subscriber.SUBSCRIBER_SIG,
    priority: int = 0,
    once: bool = False,
) -> None:
    """
    Register a callback function to a namespace.

    Args:
        namespace (str): Event namespace (e.g., 'system.io.file_open' or 'system.*').
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
        Emits a notify event when a namespace is created and when a subscriber
        is registered. Notify emits the used namespace.
    """
    weak_callback = function.make_weak_ref(
        callback=callback,
        namespace=namespace,
        on_collected_callback=_on_subscriber_collected,
    )
    sub = subscriber.Subscriber(
        weak_callback=weak_callback,
        priority=priority,
        is_async=inspect.iscoroutinefunction(callback),
        namespace=namespace,
        is_one_shot=once,
    )

    is_new_namespace = registry.ensure_namespace_exists(namespace)
    entry = registry.NAMESPACE_REGISTRY[namespace]
    _validate_and_set_subscriber_signature(
        namespace=namespace,
        entry=entry,
        callback_params=function.get_callback_params(callback),
    )

    entry.subscribers.append(sub)

    if is_new_namespace:
        routing.notify_new_namespace_created(namespace)

    if (
        not namespace.startswith(namespaces.NOTIFY_NAMESPACE_ROOT)
        and routing.notify_on_subscribe
    ):
        routing.emit(namespace=namespaces.BROKER_ON_SUBSCRIBER_ADDED, using=namespace)


def _validate_and_set_subscriber_signature(
    namespace: str,
    entry: registry.NamespaceEntry,
    callback_params: set[str] | None,
) -> None:
    if entry.signature is None:
        entry.signature = callback_params
        return

    existing_params = entry.signature
    if existing_params is None or callback_params is None:
        entry.signature = None
    elif existing_params != callback_params:
        raise exceptions.SignatureMismatchError(
            f"Subscriber parameter mismatch for namespace '{namespace}'. "
            f"Expected parameters: {sorted(existing_params)}, "
            f"but got: {sorted(callback_params)}"
        )


def subscribe(
    namespace: str, priority: int = 0, once: bool = False
) -> Callable[[subscriber.SUBSCRIBER_SIG], subscriber.SUBSCRIBER_SIG]:
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

    def decorator(func: subscriber.SUBSCRIBER_SIG) -> subscriber.SUBSCRIBER_SIG:
        register_subscriber(namespace, func, priority, once)
        return func

    return decorator


def unregister_subscriber(namespace: str, callback: subscriber.SUBSCRIBER_SIG) -> None:
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


def unregister_subscriber_all(callback: subscriber.SUBSCRIBER_SIG) -> None:
    """
    Removes a subscriber from all namespaces it is currently present in.

    Args:
        callback (Callable): The callable to unsubscribe.
    """
    subscriber_namespaces = introspection.get_subscriptions(callback)
    for namespace in subscriber_namespaces:
        unregister_subscriber(namespace, callback)


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


# -----Transformer-------------------------------------------------------------


def register_transformer(
    namespace: str,
    callback: transformer.TRANSFORMER_SIG,
    priority: int = 0,
) -> None:
    """
    Register a transformer for a namespace.

    Transformers intercept events before they reach subscribers and can:
    - Modify event arguments
    - Block event propagation
    - Log/validate events

    Args:
        namespace (str): Namespace pattern (supports wildcards like 'system.*').
        callback (TRANSFORMER): Function that receives (namespace, kwargs)
            and returns modified kwargs or None to block.
        priority (int): Execution order (higher = earlier, default 0).
    """
    weak_transformer = function.make_weak_ref(
        callback=callback,
        namespace=namespace,
        on_collected_callback=_on_transformer_collected,
    )

    transformer_obj = transformer.Transformer(
        weak_callback=weak_transformer, namespace=namespace, priority=priority
    )

    is_new_namespace = registry.ensure_namespace_exists(namespace)
    entry = registry.NAMESPACE_REGISTRY[namespace]
    entry.transformers.append(transformer_obj)
    entry.transformers.sort(key=lambda t: t.priority, reverse=True)

    if is_new_namespace:
        routing.notify_new_namespace_created(namespace)

    if (
        not namespace.startswith(namespaces.NOTIFY_NAMESPACE_ROOT)
        and routing.notify_on_transformer_add
    ):
        routing.emit(namespace=namespaces.BROKER_ON_TRANSFORMER_ADDED, using=namespace)


def transform(
    namespace: str, priority: int = 0
) -> Callable[[transformer.TRANSFORMER_SIG], transformer.TRANSFORMER_SIG]:
    """
    Decorator to register a function or static method as a transformer.

    To register an instance referencing class method (one using 'self'),
    use broker.register_transformer('source', 'event_name', self.method).

    Args:
        namespace (str): The event namespace to transform data for.
        priority (int): The execution priority. Defaults to 0.
    """

    def decorator(func: transformer.TRANSFORMER_SIG) -> transformer.TRANSFORMER_SIG:
        register_transformer(namespace, func, priority)
        return func

    return decorator


def unregister_transformer(
    namespace: str, callback: transformer.TRANSFORMER_SIG
) -> None:
    """
    Remove a transformer from a namespace.

    Args:
        namespace (str): The namespace the transformer is registered to.
        callback (TRANSFORMER): The transformer function to remove.
    """
    if namespace not in registry.NAMESPACE_REGISTRY:
        return

    entry = registry.NAMESPACE_REGISTRY[namespace]
    items = getattr(entry, "transformers")
    setattr(entry, "transformers", [i for i in items if i.callback != callback])

    if (
        not namespace.startswith(namespaces.NOTIFY_NAMESPACE_ROOT)
        and routing.notify_on_transformer_remove
    ):
        routing.emit(
            namespace=namespaces.BROKER_ON_TRANSFORMER_REMOVED, using=namespace
        )

    namespaces.cleanup_namespace_if_empty(namespace)


def unregister_transformer_all(callback: transformer.TRANSFORMER_SIG) -> None:
    """
    Removes a transformer from all namespaces it is currently present in.

    Args:
        callback (TRANSFORMER): The callable to unsubscribe.
    """
    transformer_namespaces = introspection.get_transformations(callback)
    for namespace in transformer_namespaces:
        unregister_transformer(namespace, callback)


def _on_transformer_collected(namespace: str) -> None:
    """Called when a transformer is garbage collected."""
    if namespace in registry.NAMESPACE_REGISTRY:
        entry = registry.NAMESPACE_REGISTRY[namespace]
        items = getattr(entry, "transformers")
        setattr(entry, "transformers", [i for i in items if i.callback is not None])

        namespaces.cleanup_namespace_if_empty(namespace)

    if routing.notify_on_transformer_collected and not namespace.startswith(
        namespaces.NOTIFY_NAMESPACE_ROOT
    ):
        routing.emit(
            namespace=namespaces.BROKER_ON_TRANSFORMER_COLLECTED, using=namespace
        )
