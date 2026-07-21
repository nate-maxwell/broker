"""
Immutable views of the broker's registration and staging state.

Snapshots capture diagnostic state without retaining callback objects or
exposing staged payload values, making them safe to compare, inspect, and
serialize independently of later broker activity.
"""

from dataclasses import dataclass
from typing import Optional
from typing import TYPE_CHECKING

from broker.private.namespace import NAMESPACE_REGISTRY
from broker.private.namespace import STAGED_REGISTRY
from broker.introspection import _get_callback_info

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class SubscriberSnapshot(object):
    """Immutable description of one subscriber registration."""

    callback: str
    namespace: str
    priority: int
    is_async: bool
    is_one_shot: bool
    is_alive: bool


@dataclass(frozen=True)
class TransformerSnapshot(object):
    """Immutable description of one transformer registration."""

    callback: str
    namespace: str
    priority: int
    is_alive: bool


@dataclass(frozen=True)
class NamespaceSnapshot(object):
    """Immutable snapshot of one registered namespace."""

    namespace: str
    expected_parameters: Optional[tuple[str, ...]]
    subscribers: tuple[SubscriberSnapshot, ...]
    transformers: tuple[TransformerSnapshot, ...]


@dataclass(frozen=True)
class StagedEventsSnapshot(object):
    """Immutable count of staged events for one namespace."""

    namespace: str
    event_count: int


@dataclass(frozen=True)
class BrokerSnapshot(object):
    """Immutable structured snapshot of broker registration state."""

    namespaces: tuple[NamespaceSnapshot, ...]
    staged_events: tuple[StagedEventsSnapshot, ...]


def get_snapshot() -> BrokerSnapshot:
    """
    Capture immutable, structured broker registration and staging state.

    Callback objects and staged payload values are intentionally excluded so
    the snapshot neither extends callback lifetimes nor exposes event data.
    """
    namespace_snapshots = []
    for namespace in sorted(NAMESPACE_REGISTRY):
        entry = NAMESPACE_REGISTRY[namespace]

        subscriber_snapshots = []
        for sub in entry.subscribers:
            callback = sub.callback
            subscriber_snapshots.append(
                SubscriberSnapshot(
                    callback=_get_callback_info(callback),
                    namespace=sub.namespace,
                    priority=sub.priority,
                    is_async=sub.is_async,
                    is_one_shot=sub.is_one_shot,
                    is_alive=callback is not None,
                )
            )

        transformer_snapshots = []
        for trans in entry.transformers:
            callback = trans.callback
            transformer_snapshots.append(
                TransformerSnapshot(
                    callback=_get_callback_info(callback),
                    namespace=trans.namespace,
                    priority=trans.priority,
                    is_alive=callback is not None,
                )
            )

        namespace_snapshots.append(
            NamespaceSnapshot(
                namespace=namespace,
                expected_parameters=(
                    tuple(sorted(entry.signature))
                    if entry.signature is not None
                    else None
                ),
                subscribers=tuple(subscriber_snapshots),
                transformers=tuple(transformer_snapshots),
            )
        )

    staged_snapshots = tuple(
        StagedEventsSnapshot(namespace=namespace, event_count=len(events))
        for namespace, events in sorted(STAGED_REGISTRY.items())
    )
    return BrokerSnapshot(
        namespaces=tuple(namespace_snapshots), staged_events=staged_snapshots
    )
