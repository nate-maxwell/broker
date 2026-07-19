"""
# Primary registration logic

The business logic for validating, adding, and removing subscribers and
transformers with the primary namespace _namespace.
"""

import inspect
import weakref
from typing import Any
from typing import Callable
from typing import TypeAlias
from typing import Union

from broker import signature
from broker import introspection
from broker import namespaces
from broker import routing
from broker import subscriber
from broker import transformer
from broker.private import namespace as _namespace

__all__ = [
    "register_subscriber",
    "subscribe",
    "unregister_subscriber",
    "unregister_subscriber_all",
    "register_transformer",
    "transform",
    "unregister_transformer",
    "unregister_transformer_all",
]

_NamespaceContract: TypeAlias = tuple[str, _namespace.NamespaceEntry, set[str]]


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
        namespace (str): Event namespace (e.g., 'system.io.file_open').
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
    _namespace.validate_namespace(namespace)
    callback_params = signature.get_callback_params(callback)
    accepts_kwargs = signature.callback_accepts_kwargs(callback)
    existing_entry = _namespace.NAMESPACE_REGISTRY.get(namespace)
    subscriber_signature, descendant_signature_updates = (
        _get_validated_subscriber_signature(
            namespace=namespace,
            existing_signature=(
                existing_entry.signature if existing_entry is not None else None
            ),
            callback_params=callback_params,
            accepts_kwargs=accepts_kwargs,
        )
    )

    weak_callback = _make_weak_ref(
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

    is_new_namespace = _namespace.ensure_namespace_exists(namespace)
    namespace_entry = _namespace.NAMESPACE_REGISTRY[namespace]
    namespace_entry.signature = subscriber_signature
    namespace_entry.subscribers.append(sub)
    for (
        descendant_namespace,
        descendant_signature,
    ) in descendant_signature_updates.items():
        _namespace.NAMESPACE_REGISTRY[descendant_namespace].signature = (
            descendant_signature
        )

    if is_new_namespace:
        routing.notify_new_namespace_created(namespace)

    if (
        not namespace.startswith(namespaces.NOTIFY_NAMESPACE_ROOT)
        and routing.notify_on_subscribe
    ):
        routing.emit(namespace=namespaces.BROKER_ON_SUBSCRIBER_ADDED, using=namespace)


def _get_validated_subscriber_signature(
    namespace: str,
    existing_signature: set[str] | None,
    callback_params: set[str],
    accepts_kwargs: bool,
) -> tuple[set[str] | None, dict[str, set[str]]]:
    """Validate a subscriber without mutating the namespace _namespace."""
    if existing_signature is not None:
        _validate_existing_signature(
            namespace=namespace,
            existing_signature=existing_signature,
            callback_params=callback_params,
            accepts_kwargs=accepts_kwargs,
        )
        return existing_signature, {}

    # A callback with only **kwargs accepts any future contract but does not
    # establish one itself.
    if accepts_kwargs and not callback_params:
        return None, {}

    related_contracts = _get_related_namespace_contracts(namespace)
    ancestor_contracts = _get_ancestor_contracts(namespace, related_contracts)
    subscriber_signature = _build_subscriber_signature(
        namespace=namespace,
        callback_params=callback_params,
        accepts_kwargs=accepts_kwargs,
        ancestor_contracts=ancestor_contracts,
    )
    descendant_updates = _get_descendant_signature_updates(
        namespace=namespace,
        subscriber_signature=subscriber_signature,
        related_contracts=related_contracts,
    )
    return subscriber_signature, descendant_updates


def _validate_existing_signature(
    namespace: str,
    existing_signature: set[str],
    callback_params: set[str],
    accepts_kwargs: bool,
) -> None:
    """Ensure a callback can satisfy an established namespace contract."""
    is_compatible = (
        callback_params <= existing_signature
        if accepts_kwargs
        else callback_params == existing_signature
    )
    if is_compatible:
        return

    raise signature.SignatureMismatchError(
        f"Subscriber parameter mismatch for namespace '{namespace}'. "
        f"Expected parameters: {sorted(existing_signature)}, "
        f"but got: {sorted(callback_params)}"
    )


def _get_related_namespace_contracts(namespace: str) -> list[_NamespaceContract]:
    """Collect concrete contracts above or below a namespace candidate."""
    contracts: list[_NamespaceContract] = []
    for registered_namespace, entry in _namespace.NAMESPACE_REGISTRY.items():
        registered_signature = entry.signature
        if registered_signature is None or registered_namespace == namespace:
            continue

        if _namespace.matches(namespace, registered_namespace) or _namespace.matches(
            registered_namespace, namespace
        ):
            contracts.append((registered_namespace, entry, registered_signature))

    return contracts


def _get_ancestor_contracts(
    namespace: str, related_contracts: list[_NamespaceContract]
) -> list[_NamespaceContract]:
    """Return concrete contracts inherited by a namespace candidate."""
    return [
        contract
        for contract in related_contracts
        if _namespace.matches(namespace, contract[0])
    ]


def _build_subscriber_signature(
    namespace: str,
    callback_params: set[str],
    accepts_kwargs: bool,
    ancestor_contracts: list[_NamespaceContract],
) -> set[str]:
    """Build a new namespace contract from callback and ancestor requirements."""
    inherited_params = set().union(
        *(ancestor_signature for _, _, ancestor_signature in ancestor_contracts)
    )

    if accepts_kwargs:
        return callback_params | inherited_params

    for registered_namespace, _, ancestor_signature in ancestor_contracts:
        if not ancestor_signature <= callback_params:
            raise signature.SignatureMismatchError(
                f"Subscriber parameters for child namespace '{namespace}' "
                f"must include parent namespace '{registered_namespace}' "
                f"parameters: {sorted(ancestor_signature)}"
            )

    return callback_params


def _get_descendant_signature_updates(
    namespace: str,
    subscriber_signature: set[str],
    related_contracts: list[_NamespaceContract],
) -> dict[str, set[str]]:
    """
    Validate descendants and return safe flexible-contract expansions.

    This makes parent registration order-independent. If a child namespace,
    "app.child" is already created, and a parent namespace, "app" is created,
    every child namespace is checked to make sure
    - the child contract already includes the new parent requirements
    - if it lacks a requirement, then all the current subscribers accept **kwargs
    - if any subscriber cannot accept the newly inherited parent argument, it
      raises signature.SignatureMismatchError.
    """
    updates: dict[str, set[str]] = {}
    for registered_namespace, entry, descendant_signature in related_contracts:
        if not _namespace.matches(registered_namespace, namespace):
            continue

        if subscriber_signature <= descendant_signature:
            continue

        if _all_subscribers_accept_kwargs(entry):
            updates[registered_namespace] = descendant_signature | subscriber_signature
            continue

        raise signature.SignatureMismatchError(
            f"Subscriber parameters for parent namespace '{namespace}' "
            f"must be present in child namespace "
            f"'{registered_namespace}': {sorted(descendant_signature)}"
        )

    return updates


def _all_subscribers_accept_kwargs(entry: _namespace.NamespaceEntry) -> bool:
    """Return whether every live subscriber can accept an expanded contract."""
    callbacks = [sub.callback for sub in entry.subscribers]
    live_callbacks = [callback for callback in callbacks if callback is not None]
    return bool(live_callbacks) and all(
        signature.callback_accepts_kwargs(callback) for callback in live_callbacks
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
    _namespace.validate_namespace(namespace)
    if namespace not in _namespace.NAMESPACE_REGISTRY:
        return

    entry = _namespace.NAMESPACE_REGISTRY[namespace]
    items = entry.subscribers
    entry.subscribers = [i for i in items if i.callback != callback]
    if not entry.subscribers:
        entry.signature = None

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
    if namespace in _namespace.NAMESPACE_REGISTRY:
        entry = _namespace.NAMESPACE_REGISTRY[namespace]
        items = entry.subscribers
        entry.subscribers = [i for i in items if i.callback is not None]
        if not entry.subscribers:
            entry.signature = None

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
        namespace (str): Namespace whose events and descendants are transformed.
        callback (TRANSFORMER): Function that receives (namespace, kwargs)
            and returns modified kwargs or None to block.
        priority (int): Execution order (higher = earlier, default 0).
    """
    _namespace.validate_namespace(namespace)
    weak_transformer = _make_weak_ref(
        callback=callback,
        namespace=namespace,
        on_collected_callback=_on_transformer_collected,
    )

    transformer_obj = transformer.Transformer(
        weak_callback=weak_transformer, namespace=namespace, priority=priority
    )

    is_new_namespace = _namespace.ensure_namespace_exists(namespace)
    entry = _namespace.NAMESPACE_REGISTRY[namespace]
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
    _namespace.validate_namespace(namespace)
    if namespace not in _namespace.NAMESPACE_REGISTRY:
        return

    entry = _namespace.NAMESPACE_REGISTRY[namespace]
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
    if namespace in _namespace.NAMESPACE_REGISTRY:
        entry = _namespace.NAMESPACE_REGISTRY[namespace]
        items = getattr(entry, "transformers")
        setattr(entry, "transformers", [i for i in items if i.callback is not None])

        namespaces.cleanup_namespace_if_empty(namespace)

    if routing.notify_on_transformer_collected and not namespace.startswith(
        namespaces.NOTIFY_NAMESPACE_ROOT
    ):
        routing.emit(
            namespace=namespaces.BROKER_ON_TRANSFORMER_COLLECTED, using=namespace
        )


def _make_weak_ref(
    callback: subscriber.SUBSCRIBER_SIG,
    namespace: str,
    on_collected_callback: Callable[[str], None],
) -> Union[weakref.ref[Any], weakref.WeakMethod[Any]]:
    """Create the appropriate weak reference for any callback type."""

    def cleanup(_: Union[weakref.ref[Any], weakref.WeakMethod[Any]]) -> None:
        # Arg needed to add for weakref creation.
        on_collected_callback(namespace)

    if hasattr(callback, "__self__"):
        return weakref.WeakMethod(callback, cleanup)
    else:
        return weakref.ref(callback, cleanup)
