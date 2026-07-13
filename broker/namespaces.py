"""
Namespace registry data structures for the event broker.

Defines the NamespaceEntry dataclass that represents a unified namespace in the
broker's internal registry. Each namespace entry tracks both subscribers and
transformers registered to that namespace, along with the expected parameter
signature for validation.

A namespace exists in the registry when it has at least one subscriber OR
transformer registered, except very briefly when registering a transformer or
subscriber to a newly created namespace.
"""

from broker import routing
from broker.private import registry


NOTIFY_NAMESPACE_ROOT = "broker.notify."

BROKER_ON_SUBSCRIBER_ADDED = f"{NOTIFY_NAMESPACE_ROOT}subscriber.added"
BROKER_ON_SUBSCRIBER_REMOVED = f"{NOTIFY_NAMESPACE_ROOT}subscriber.removed"
BROKER_ON_SUBSCRIBER_COLLECTED = f"{NOTIFY_NAMESPACE_ROOT}subscriber.collected"

BROKER_ON_TRANSFORMER_ADDED = f"{NOTIFY_NAMESPACE_ROOT}transformer.added"
BROKER_ON_TRANSFORMER_REMOVED = f"{NOTIFY_NAMESPACE_ROOT}transformer.removed"
BROKER_ON_TRANSFORMER_COLLECTED = f"{NOTIFY_NAMESPACE_ROOT}transformer.collected"

BROKER_ON_EMIT = f"{NOTIFY_NAMESPACE_ROOT}emit.sync"
BROKER_ON_EMIT_ASYNC = f"{NOTIFY_NAMESPACE_ROOT}emit.async"
BROKER_ON_EMIT_ALL = f"{NOTIFY_NAMESPACE_ROOT}emit.all"

BROKER_ON_NAMESPACE_CREATED = f"{NOTIFY_NAMESPACE_ROOT}namespace.created"
BROKER_ON_NAMESPACE_DELETED = f"{NOTIFY_NAMESPACE_ROOT}namespace.deleted"


def cleanup_namespace_if_empty(namespace: str) -> None:
    """Remove namespace from registry if it has no subscribers or transformers."""
    if namespace not in registry.NAMESPACE_REGISTRY:
        return

    entry = registry.NAMESPACE_REGISTRY[namespace]
    if not entry.subscribers and not entry.transformers:
        del registry.NAMESPACE_REGISTRY[namespace]
        if (
            not namespace.startswith(NOTIFY_NAMESPACE_ROOT)
            and routing.notify_on_del_namespace
        ):
            routing.emit(namespace=BROKER_ON_NAMESPACE_DELETED, using=namespace)
