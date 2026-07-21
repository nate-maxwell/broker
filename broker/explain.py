"""
Side-effect-free analysis of the route an event would take through the broker.

Explanations reflect namespace matching, execution priority, delivery mode,
and pause state without invoking callbacks or changing broker state. Because
transformers are not executed, their payload changes and blocking decisions
remain intentionally outside the prediction.
"""

from dataclasses import dataclass
from typing import Literal
from typing import Optional

from broker import routing
from broker.introspection import _get_callback_info
from broker.private.namespace import NAMESPACE_REGISTRY
from broker.private.namespace import get_sorted_subscribers
from broker.private.namespace import get_sorted_transformers
from broker.private.namespace import matches
from broker.private.namespace import validate_namespace


@dataclass(frozen=True)
class TransformerDeliveryPlan(object):
    """One transformer step in an explained emission."""

    callback: str
    registered_namespace: str
    priority: int
    is_alive: bool
    will_run: bool
    skip_reason: Optional[str]


@dataclass(frozen=True)
class SubscriberDeliveryPlan(object):
    """One subscriber step in an explained emission."""

    callback: str
    registered_namespace: str
    priority: int
    is_async: bool
    is_one_shot: bool
    is_alive: bool
    will_run: bool
    skip_reason: Optional[str]


@dataclass(frozen=True)
class EmitPlan(object):
    """Side-effect-free description of the static route for an emission."""

    namespace: str
    mode: Literal["sync", "async"]
    is_paused: bool
    required_parameters: tuple[str, ...]
    transformers: tuple[TransformerDeliveryPlan, ...]
    subscribers: tuple[SubscriberDeliveryPlan, ...]


def explain_emit(
    namespace: str, *, mode: Literal["sync", "async"] = "sync"
) -> EmitPlan:
    """
    Explain the static delivery route for an emission without invoking callbacks.

    The returned steps use the same matching and priority ordering as routing.
    Transformers are not executed, so this function cannot predict payload
    changes or whether a transformer will block the event.

    Args:
        namespace: Namespace that would be emitted.
        mode: ``"sync"`` for emit() or ``"async"`` for emit_async().
    Raises:
        ValueError: If mode is not ``"sync"`` or ``"async"``.
    """
    validate_namespace(namespace)
    if mode not in ("sync", "async"):
        raise ValueError("mode must be 'sync' or 'async'")

    is_paused = routing._is_paused()
    required_parameters: set[str] = set()
    for registered_namespace, entry in NAMESPACE_REGISTRY.items():
        if matches(namespace, registered_namespace) and entry.signature is not None:
            required_parameters.update(entry.signature)

    transformer_steps = []
    for registered_namespace, trans in get_sorted_transformers(namespace):
        transformer_callback = trans.callback
        skip_reason = _delivery_skip_reason(transformer_callback is not None, is_paused)
        transformer_steps.append(
            TransformerDeliveryPlan(
                callback=_get_callback_info(transformer_callback),
                registered_namespace=registered_namespace,
                priority=trans.priority,
                is_alive=transformer_callback is not None,
                will_run=skip_reason is None,
                skip_reason=skip_reason,
            )
        )

    subscriber_steps = []
    for registered_namespace, sub in get_sorted_subscribers(namespace):
        subscriber_callback = sub.callback
        skip_reason = _delivery_skip_reason(subscriber_callback is not None, is_paused)
        if skip_reason is None and mode == "sync" and sub.is_async:
            skip_reason = "async subscriber is skipped by emit()"

        subscriber_steps.append(
            SubscriberDeliveryPlan(
                callback=_get_callback_info(subscriber_callback),
                registered_namespace=registered_namespace,
                priority=sub.priority,
                is_async=sub.is_async,
                is_one_shot=sub.is_one_shot,
                is_alive=subscriber_callback is not None,
                will_run=skip_reason is None,
                skip_reason=skip_reason,
            )
        )

    return EmitPlan(
        namespace=namespace,
        mode=mode,
        is_paused=is_paused,
        required_parameters=tuple(sorted(required_parameters)),
        transformers=tuple(transformer_steps),
        subscribers=tuple(subscriber_steps),
    )


def _delivery_skip_reason(is_alive: bool, is_paused: bool) -> Optional[str]:
    if not is_alive:
        return "callback reference is no longer alive"
    if is_paused:
        return "broker is paused"
    return None
