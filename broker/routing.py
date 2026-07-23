"""
# Primary event routing logic

The business logic for sending payloads to their intended destinations.
"""

from typing import Any
from typing import Optional

from broker import signature
from broker import handlers
from broker import metrics
from broker import namespaces
from broker import subscriber
from broker import transformer
from broker.private import namespace as _namespace

__all__ = [
    # ---vars---
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
]

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

    Synchronous subscribers are called immediately in parent-to-child namespace
    order, then descending priority order within each namespace.
    Each namespace's transformers run immediately before its subscribers on an
    isolated copy of the emitted keyword mapping.
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
    _namespace.validate_namespace(namespace)
    metric_context = metrics._start_emit(namespace, "sync")
    try:
        if _is_paused():
            if metric_context is not None:
                metric_context.paused()
            return

        was_blocked = _emit_sync_namespaces(namespace, kwargs, metric_context)
        if was_blocked:
            if metric_context is not None:
                metric_context.blocked()
            return

        _emit_notify_event(
            source_namespace=namespace,
            notify_namespace=namespaces.BROKER_ON_EMIT,
            should_notify=notify_on_emit or notify_on_emit_all,
        )
        if metric_context is not None:
            metric_context.complete()
    except Exception:
        if metric_context is not None:
            metric_context.failed()
        raise
    finally:
        if metric_context is not None:
            metric_context.finish()


async def emit_async(namespace: str, **kwargs: Any) -> None:
    """
    Asynchronously emit an event to all matching subscribers.

    Both synchronous and asynchronous subscribers are called in parent-to-child
    namespace order, then descending priority order within each namespace.
    Each namespace's transformers run immediately before its subscribers on an
    isolated copy of the emitted keyword mapping.
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
    _namespace.validate_namespace(namespace)
    metric_context = metrics._start_emit(namespace, "async")
    try:
        if _is_paused():
            if metric_context is not None:
                metric_context.paused()
            return

        was_blocked = await _emit_async_namespaces(namespace, kwargs, metric_context)
        if was_blocked:
            if metric_context is not None:
                metric_context.blocked()
            return

        _emit_notify_event(
            source_namespace=namespace,
            notify_namespace=namespaces.BROKER_ON_EMIT_ASYNC,
            should_notify=notify_on_emit_async or notify_on_emit_all,
        )
        if metric_context is not None:
            metric_context.complete()
    except Exception:
        if metric_context is not None:
            metric_context.failed()
        raise
    finally:
        if metric_context is not None:
            metric_context.finish()


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
    _namespace.validate_namespace(namespace)
    _namespace.STAGED_REGISTRY[namespace].append(kwargs)


def emit_staged(flush: bool = True) -> None:
    """
    Emits staged events through broker.emit()

    Args:
        flush (bool): Whether to empty the current staging registry after
            emitting. Defaults to True.
    """
    if _is_paused():
        return

    namespaces_ = list(_namespace.STAGED_REGISTRY.keys())
    staged = {ns: list(_namespace.STAGED_REGISTRY[ns]) for ns in namespaces_}

    if flush:
        _namespace.STAGED_REGISTRY.clear()

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
    if _is_paused():
        return

    namespaces_ = list(_namespace.STAGED_REGISTRY.keys())
    staged = {ns: list(_namespace.STAGED_REGISTRY[ns]) for ns in namespaces_}

    if flush:
        _namespace.STAGED_REGISTRY.clear()

    for namespace, events in staged.items():
        for kwargs in events:
            await emit_async(namespace, **kwargs)


def clear() -> None:
    _namespace.NAMESPACE_REGISTRY.clear()


def clear_staged() -> None:
    _namespace.STAGED_REGISTRY.clear()


def notify_new_namespace_created(namespace: str) -> None:
    if (
        not namespace.startswith(namespaces.NOTIFY_NAMESPACE_ROOT)
        and notify_on_new_namespace
    ):
        emit(namespace=namespaces.BROKER_ON_NAMESPACE_CREATED, using=namespace)


def _is_paused() -> bool:
    return _paused > 0


def _prepare_namespace_delivery(
    emitted_namespace: str,
    registered_namespace: str,
    expected_params: Optional[set[str]],
    transformers: list[transformer.Transformer],
    kwargs: dict[str, Any],
    metric_context: Optional[metrics._EmitMetricsContext],
) -> Optional[dict[str, Any]]:
    """Transform and validate an isolated payload for one namespace."""
    transformed_kwargs = _apply_transformers(
        emitted_namespace, transformers, kwargs, metric_context
    )
    if transformed_kwargs is None:
        return None

    signature._validate_namespace_emit_args(
        emitted_namespace,
        registered_namespace,
        expected_params,
        transformed_kwargs,
    )
    return transformed_kwargs


def _flush_one_shots(one_shots: list[tuple[str, subscriber.SUBSCRIBER_SIG]]) -> None:
    # duplicate to subscriber.unregister_subscriber to avoid a circular import.
    for reg_namespace, callback in one_shots:
        if reg_namespace not in _namespace.NAMESPACE_REGISTRY:
            return

        entry = _namespace.NAMESPACE_REGISTRY[reg_namespace]
        items = entry.subscribers
        entry.subscribers = [i for i in items if i.callback != callback]
        if not entry.subscribers:
            entry.signature = None

        if (
            not reg_namespace.startswith(namespaces.NOTIFY_NAMESPACE_ROOT)
            and notify_on_unsubscribe
        ):
            emit(namespace=namespaces.BROKER_ON_SUBSCRIBER_REMOVED, using=reg_namespace)

        namespaces.cleanup_namespace_if_empty(reg_namespace)


def _emit_sync_namespaces(
    namespace: str,
    kwargs: dict[str, Any],
    metric_context: Optional[metrics._EmitMetricsContext],
) -> bool:
    """
    Deliver isolated namespace phases from parent to child.

    Each phase transforms a fresh copy of the emitted payload, validates it,
    then invokes that namespace's subscribers. A blocked phase does not affect
    later namespaces.
    """
    one_shots: list[tuple[str, subscriber.SUBSCRIBER_SIG]] = []
    routes = _get_namespace_routes(namespace)
    blocked_routes = 0
    unblocked_routes = 0

    for reg_namespace, transformers, subscribers, expected_params in routes:
        transformed_kwargs = _prepare_namespace_delivery(
            emitted_namespace=namespace,
            registered_namespace=reg_namespace,
            expected_params=expected_params,
            transformers=transformers,
            kwargs=kwargs,
            metric_context=metric_context,
        )
        if transformed_kwargs is None:
            blocked_routes += 1
            continue

        unblocked_routes += 1
        for sub in subscribers:
            if not _deliver_sync_subscriber(
                namespace=namespace,
                transformed_kwargs=transformed_kwargs,
                reg_namespace=reg_namespace,
                sub=sub,
                one_shots=one_shots,
                metric_context=metric_context,
            ):
                _flush_one_shots(one_shots)
                return False

    _flush_one_shots(one_shots)
    return blocked_routes > 0 and unblocked_routes == 0


async def _emit_async_namespaces(
    namespace: str,
    kwargs: dict[str, Any],
    metric_context: Optional[metrics._EmitMetricsContext],
) -> bool:
    """Deliver isolated namespace phases asynchronously from parent to child."""
    one_shots: list[tuple[str, subscriber.SUBSCRIBER_SIG]] = []
    routes = _get_namespace_routes(namespace)
    blocked_routes = 0
    unblocked_routes = 0

    for reg_namespace, transformers, subscribers, expected_params in routes:
        transformed_kwargs = _prepare_namespace_delivery(
            emitted_namespace=namespace,
            registered_namespace=reg_namespace,
            expected_params=expected_params,
            transformers=transformers,
            kwargs=kwargs,
            metric_context=metric_context,
        )
        if transformed_kwargs is None:
            blocked_routes += 1
            continue

        unblocked_routes += 1
        for sub in subscribers:
            if not await _deliver_async_subscriber(
                namespace=namespace,
                transformed_kwargs=transformed_kwargs,
                reg_namespace=reg_namespace,
                sub=sub,
                one_shots=one_shots,
                metric_context=metric_context,
            ):
                _flush_one_shots(one_shots)
                return False

    _flush_one_shots(one_shots)
    return blocked_routes > 0 and unblocked_routes == 0


def _get_namespace_routes(
    namespace: str,
) -> list[
    tuple[
        str,
        list[transformer.Transformer],
        list[subscriber.Subscriber],
        Optional[set[str]],
    ]
]:
    """Snapshot matching namespace routes before callback execution begins."""
    routes = []
    for reg_namespace in _namespace.get_matching_registered_namespaces(namespace):
        entry = _namespace.NAMESPACE_REGISTRY[reg_namespace]
        routes.append(
            (
                reg_namespace,
                sorted(
                    entry.transformers,
                    key=lambda item: item.priority,
                    reverse=True,
                ),
                sorted(
                    entry.subscribers,
                    key=lambda item: item.priority,
                    reverse=True,
                ),
                entry.signature.copy() if entry.signature is not None else None,
            )
        )

    return routes


def _deliver_sync_subscriber(
    namespace: str,
    transformed_kwargs: dict[str, Any],
    reg_namespace: str,
    sub: subscriber.Subscriber,
    one_shots: list[tuple[str, subscriber.SUBSCRIBER_SIG]],
    metric_context: Optional[metrics._EmitMetricsContext],
) -> bool:
    callback = sub.callback
    if callback is None:
        return True
    if sub.is_async:
        if metric_context is not None:
            metric_context.async_subscriber_skipped()
        return True

    try:
        callback_kwargs = signature.get_callback_kwargs(callback, transformed_kwargs)
        if metric_context is not None:
            metric_context.subscriber_call()
        callback(**callback_kwargs)
    except Exception as exc:
        if metric_context is not None:
            metric_context.subscriber_error()
        if subscriber.subscriptions_exception_handler is None:
            raise

        if subscriber.subscriptions_exception_handler(callback, namespace, exc):
            return False

    if sub.is_one_shot:
        one_shots.append((reg_namespace, callback))

    return True


async def _deliver_async_subscriber(
    namespace: str,
    transformed_kwargs: dict[str, Any],
    reg_namespace: str,
    sub: subscriber.Subscriber,
    one_shots: list[tuple[str, subscriber.SUBSCRIBER_SIG]],
    metric_context: Optional[metrics._EmitMetricsContext],
) -> bool:
    callback = sub.callback

    if callback is None:
        return True

    try:
        callback_kwargs = signature.get_callback_kwargs(callback, transformed_kwargs)
        if metric_context is not None:
            metric_context.subscriber_call()
        if sub.is_async:
            await callback(**callback_kwargs)
        else:
            callback(**callback_kwargs)
    except Exception as exc:
        if metric_context is not None:
            metric_context.subscriber_error()
        if subscriber.subscriptions_exception_handler is None:
            raise

        if subscriber.subscriptions_exception_handler(callback, namespace, exc):
            return False

    if sub.is_one_shot:
        one_shots.append((reg_namespace, callback))

    return True


def _emit_notify_event(
    source_namespace: str, notify_namespace: str, should_notify: bool
) -> None:
    """
    Emit a broker notification for a non-notify source namespace when enabled.

    Notification events are skipped for namespaces under the broker notify
    root to avoid recursive notification loops.
    """
    if source_namespace.startswith(namespaces.NOTIFY_NAMESPACE_ROOT):
        return

    if should_notify:
        emit(namespace=notify_namespace, using=source_namespace)


def _apply_transformers(
    namespace: str,
    transformers: list[transformer.Transformer],
    kwargs: dict[str, Any],
    metric_context: Optional[metrics._EmitMetricsContext],
) -> Optional[dict[str, Any]]:
    """
    Apply one registered namespace's transformers to a payload copy.

    Transformers execute in descending priority order. If any returns None,
    delivery is blocked for this namespace only.

    Args:
        namespace (str): The event namespace being emitted.
        kwargs (dict[str, Any]): The event arguments.
    Returns:
        Modified kwargs dict, or None if event was blocked
    """
    current_kwargs = kwargs.copy()

    for transformer_obj in transformers:
        callback = transformer_obj.callback
        if callback is None:
            continue

        try:
            if metric_context is not None:
                metric_context.transformer_call()
            result = callback(namespace, current_kwargs)
            if result is None:
                return None

            current_kwargs = result

        except Exception as e:
            if metric_context is not None:
                metric_context.transformer_error()
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
