"""
Transformer system for event broker.

Transformers are like diet middleware...

Allows users to register transformers that intercept and modify event data
before it reaches subscribers. Transformers execute in priority order.
"""

import weakref
from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import Optional
from typing import Union

from broker import function
from broker import handlers
from broker import introspection
from broker import namespaces
from broker import routing
from broker.private import registry

__all__ = [
    "TRANSFORMER",
    "transformer_exception_handler",
    "Transformer",
    "register_transformer",
    "transform",
    "unregister_transformer",
    "unregister_transformer_all",
    "set_transformer_exception_handler",
    "clear_transformers",
]

TRANSFORMER = Callable[[str, dict[str, Any]], Optional[dict[str, Any]]]
"""
A transformer function that receives (namespace, kwargs) and returns:
  - Modified kwargs dict to continue the chain
  - None to stop propagation (event is blocked)
"""

TRANSFORMER_EXCEPTION_HANDLER = Callable[[TRANSFORMER, str, Exception], bool]
"""
Signature for transformer exception handlers.

Exception handlers receive the failing transformer, namespace, and exception,
then return True to stop execution or False to continue.
"""


transformer_exception_handler: Optional[TRANSFORMER_EXCEPTION_HANDLER] = (
    handlers.stop_and_log_transformer_exception
)
"""
Which handler to use when an exception is raised while passing messages to
transformer.
"""


@dataclass(frozen=True)
class Transformer(object):
    """
    A transformer with callback and priority.
    Transformers alter the data emitted before it reaches the subscribers, like
    middleware. They can append metadata, validate and filter out bad messages,
    or completely change the payload.
    """

    weak_callback: Union[weakref.ref[Any], weakref.WeakMethod]
    """
    The end point that data is forwarded to. i.e. what gets ran.
    This is a weak reference so the callback isn't kept alive by the broker.
    Broker can notify when item is garbage collected or deleted.
    """

    priority: int
    """Execution order - higher priorities run first."""

    namespace: str
    """The namespace pattern this transformer applies to."""

    @property
    def callback(self) -> Optional[TRANSFORMER]:
        """Get the live callback, or None if collected."""
        return self.weak_callback()


def register_transformer(
    namespace: str,
    callback: TRANSFORMER,
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

    transformer_obj = Transformer(
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
) -> Callable[[TRANSFORMER], TRANSFORMER]:
    """
    Decorator to register a function or static method as a transformer.

    To register an instance referencing class method (one using 'self'),
    use broker.register_transformer('source', 'event_name', self.method).

    Args:
        namespace (str): The event namespace to transform data for.
        priority (int): The execution priority. Defaults to 0.
    """

    def decorator(func: TRANSFORMER) -> TRANSFORMER:
        register_transformer(namespace, func, priority)
        return func

    return decorator


def unregister_transformer(namespace: str, callback: TRANSFORMER) -> None:
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


def unregister_transformer_all(callback: TRANSFORMER) -> None:
    """
    Removes a transformer from all namespaces it is currently present in.

    Args:
        callback (TRANSFORMER): The callable to unsubscribe.
    """
    transformer_namespaces = introspection.get_transformations(callback)
    for namespace in transformer_namespaces:
        unregister_transformer(namespace, callback)


def set_transformer_exception_handler(
    handler: Optional[TRANSFORMER_EXCEPTION_HANDLER],
) -> None:
    """
    Set the exception handler for transformer errors.
    The handler is called when a transformer raises an exception during emit.

    Args:
        Optional[transformer.TRANSFORMER_EXCEPTION_HANDLER]:
            Callable with signature (TRANSFORMER, str, Exception) -> bool.
            Returns True to stop delivery, False to continue.
            Pass None to restore default behavior (re-raise exceptions).
    """
    global transformer_exception_handler
    transformer_exception_handler = handler


def clear_transformers() -> None:
    """Clear all registered transformers."""
    for namespace, entry in registry.NAMESPACE_REGISTRY.items():
        entry.transformers.clear()
        namespaces.cleanup_namespace_if_empty(namespace)


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
