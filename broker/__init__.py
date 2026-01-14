"""
# Primary Event Broker

Herein is the event broker system itself as a module class to create a
protective closure around the subscriber namespace table.

A reimport protection clause exists at the top of the file to prevent the
subscribers table from being lost on import.

Function stubs exist in the stubs file for static type checkers to validate
correct calls.

For a complete breakdown of broker functionality, read the project readme.
"""

# Remember to update doc strings in the stub.py file so static type checkers
# and intellisense can receive accurate feedback!

import sys

# -----------------------------------------------------------------------------
# Prevent module reload - subscribers table would be lost!
if "broker" in sys.modules:
    existing_module = sys.modules["broker"]
    if hasattr(existing_module, "_BROKER_IMPORT_GUARD"):
        raise ImportError(
            "Module 'broker' has already been imported and cannot be reloaded. "
            "Subscriber data would be lost. "
            "Restart your Python session to reimport."
        )
_BROKER_IMPORT_GUARD = True
# -----------------------------------------------------------------------------

import asyncio
import inspect
import json
import weakref
from types import ModuleType

from broker.stub import *
from broker import handlers
from broker import transformer
from broker import subscriber
from broker import namespaces


version_major = 1
version_minor = 7
version_patch = 0
__version__ = f"{version_major}.{version_minor}.{version_patch}"

_NAMESPACE_REGISTRY: dict[str, namespaces.NamespaceEntry] = {}
"""
Global namespace registry.
Each namespace tracks its subscribers, transformers, and expected signature.
A namespace exists if it has at least one subscriber OR transformer.
"""

# -----Notifies----------------------------------------------------------------
_NOTIFY_NAMESPACE_ROOT = "broker.notify."

BROKER_ON_SUBSCRIBER_ADDED = f"{_NOTIFY_NAMESPACE_ROOT}subscriber.added"
BROKER_ON_SUBSCRIBER_REMOVED = f"{_NOTIFY_NAMESPACE_ROOT}subscriber.removed"
BROKER_ON_SUBSCRIBER_COLLECTED = f"{_NOTIFY_NAMESPACE_ROOT}subscriber.collected"

BROKER_ON_TRANSFORMER_ADDED = f"{_NOTIFY_NAMESPACE_ROOT}transformer.added"
BROKER_ON_TRANSFORMER_REMOVED = f"{_NOTIFY_NAMESPACE_ROOT}transformer.removed"
BROKER_ON_TRANSFORMER_COLLECTED = f"{_NOTIFY_NAMESPACE_ROOT}transformer.collected"

BROKER_ON_EMIT = f"{_NOTIFY_NAMESPACE_ROOT}emit.sync"
BROKER_ON_EMIT_ASYNC = f"{_NOTIFY_NAMESPACE_ROOT}emit.async"
BROKER_ON_EMIT_ALL = f"{_NOTIFY_NAMESPACE_ROOT}emit.all"

BROKER_ON_NAMESPACE_CREATED = f"{_NOTIFY_NAMESPACE_ROOT}namespace.created"
BROKER_ON_NAMESPACE_DELETED = f"{_NOTIFY_NAMESPACE_ROOT}namespace.deleted"


# -----Exceptions--------------------------------------------------------------
class SignatureMismatchError(Exception):
    """Raised when callback signatures don't match for a namespace."""


class EmitArgumentError(Exception):
    """Raised when emit arguments don't match subscriber signatures."""


# -----------------------------------------------------------------------------


def _make_weak_ref(
    callback: subscriber.SUBSCRIBER,
    namespace: str,
    on_collected_callback: Callable[[str], None],
) -> Union[weakref.ref[Any], weakref.WeakMethod]:
    """Create appropriate weak reference for any callback type."""

    def cleanup(_: Union[weakref.ref[Any], weakref.WeakMethod]) -> None:
        # Arg needed to add for weakref creation.
        on_collected_callback(namespace)

    if hasattr(callback, "__self__"):
        return weakref.WeakMethod(callback, cleanup)
    else:
        return weakref.ref(callback, cleanup)


def _make_subscribe_decorator(broker_module: "Broker") -> Callable:
    """
    Create a subscribe decorator with access to the broker module.

    This exists as a function accepting the broker module as an argument so the
    function can call register_subscriber() on the broker without referring to
    it using a python namespace and thus creating a circular reference.
    """

    def subscribe_(
        namespace: str, priority: int = 0
    ) -> Callable[[subscriber.SUBSCRIBER], subscriber.SUBSCRIBER]:
        def decorator(func: subscriber.SUBSCRIBER) -> subscriber.SUBSCRIBER:
            broker_module.register_subscriber(namespace, func, priority)
            return func

        return decorator

    return subscribe_


def _make_transformer_decorator(broker_module: "Broker") -> Callable:
    """
    Create a transform decorator with access to the broker module.

    This exists as a function accepting the broker module as an argument so the
    function can call register_subscriber() on the broker without referring to
    it using a python namespace and thus creating a circular reference.
    """

    def transform_(
        namespace: str, priority: int = 0
    ) -> Callable[[transformer.TRANSFORMER], transformer.TRANSFORMER]:
        def decorator(func: transformer.TRANSFORMER) -> transformer.TRANSFORMER:
            broker_module.register_transformer(namespace, func, priority)
            return func

        return decorator

    return transform_


class Broker(ModuleType):
    """
    Primary event coordinator.
    Supports hierarchical namespace through dot notation, with * for wildcards.

    Supports both synchronous and asynchronous subscribers.
    Use emit() for fire-and-forget behavior.
    Use emit_async() to await all subscribers.

    To manage subscribers use
    register_subscriber() and unregister_subscriber(),
    or decorate with @subscribe.

    To manage transformers use
    register_transformer() and unregister_transformer(),
    or decorate with @transform.
    """

    # -----Runtime Closures----------------------------------------------------
    # ---Constants---
    __version__ = __version__
    _BROKER_IMPORT_GUARD = _BROKER_IMPORT_GUARD
    # Explicitly refuse to make closure for _NAMESPACE_REGISTRY so it stays
    # protected!

    # ---Exceptions---
    SignatureMismatchError = SignatureMismatchError
    EmitArgumentError = EmitArgumentError

    # ---Default Namespaces---
    BROKER_ON_SUBSCRIBER_ADDED = BROKER_ON_SUBSCRIBER_ADDED
    BROKER_ON_SUBSCRIBER_REMOVED = BROKER_ON_SUBSCRIBER_REMOVED
    BROKER_ON_SUBSCRIBER_COLLECTED = BROKER_ON_SUBSCRIBER_COLLECTED
    BROKER_ON_TRANSFORMER_ADDED = BROKER_ON_TRANSFORMER_ADDED
    BROKER_ON_TRANSFORMER_REMOVED = BROKER_ON_TRANSFORMER_REMOVED
    BROKER_ON_TRANSFORMER_COLLECTED = BROKER_ON_TRANSFORMER_COLLECTED
    BROKER_ON_EMIT = BROKER_ON_EMIT
    BROKER_ON_EMIT_ASYNC = BROKER_ON_EMIT_ASYNC
    BROKER_ON_EMIT_ALL = BROKER_ON_EMIT_ALL
    BROKER_ON_NAMESPACE_CREATED = BROKER_ON_NAMESPACE_CREATED
    BROKER_ON_NAMESPACE_DELETED = BROKER_ON_NAMESPACE_DELETED

    # ---Modules---
    handlers = handlers
    subscriber = subscriber
    transformer = transformer
    # -------------------------------------------------------------------------

    def __init__(self, name: str) -> None:
        super().__init__(name)
        assert self._BROKER_IMPORT_GUARD is True

        self._install_decorators()

        # -----Exception Handlers-----
        self._subscriptions_exception_handler: Optional[
            handlers.SUBSCRIPTION_EXCEPTION_HANDLER
        ] = handlers.stop_and_log_subscriber_exception

        self._transformer_exception_handler: Optional[
            handlers.TRANSFORMER_EXCEPTION_HANDLER
        ] = handlers.stop_and_log_transformer_exception

        # -----Notifies-----
        self.notify_on_all: bool = False

        self.notify_on_subscribe: bool = False
        self.notify_on_unsubscribe: bool = False
        self.notify_on_collected: bool = False

        self.notify_on_transformer_add: bool = False
        self.notify_on_transformer_remove: bool = False
        self.notify_on_transformer_collected: bool = False

        self.notify_on_emit: bool = False
        self.notify_on_emit_async: bool = False
        self.notify_on_emit_all: bool = False

        self.notify_on_new_namespace: bool = False
        self.notify_on_del_namespace: bool = False

    def _install_decorators(self) -> None:
        """Create decorator bindings."""

        self.subscribe = _make_subscribe_decorator(self)
        """
        Decorator to register a function or static method as a subscriber.

        To register an instance referencing class method (one using 'self'),
        use broker.register_subscriber('source', 'event_name', self.method).

        Args:
            namespace (str): The event namespace to subscribe to.
            priority (int): The execution priority. Defaults to 0.
        """

        self.transform = _make_transformer_decorator(self)
        """
        Decorator to register a function or static method as a transformer.

        To register an instance referencing class method (one using 'self'),
        use broker.register_transformer('source', 'event_name', self.method).

        Args:
            namespace (str): The event namespace to transform data for.
            priority (int): The execution priority. Defaults to 0.
        """

    @staticmethod
    def clear() -> None:
        _NAMESPACE_REGISTRY.clear()

    # -----Subscriber Management-----------------------------------------------

    @staticmethod
    def _get_callback_params(callback: subscriber.SUBSCRIBER) -> Optional[set[str]]:
        """
        Extract parameter names from a callback function.

        Args:
            callback (CALLBACK): The callback function to inspect.
        Returns:
            Optional[set[str]]: Set of parameter names, or None if callback
                accepts **kwargs.
        """
        sig = inspect.signature(callback)

        # **kwargs is not tracked
        for param in sig.parameters.values():
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                return None

        return {
            name
            for name, param in sig.parameters.items()
            if param.kind != inspect.Parameter.VAR_POSITIONAL  # exclude *args
        }

    def _on_subscriber_collected(self, namespace: str) -> None:
        """Called when a subscriber is garbage collected."""
        if namespace in _NAMESPACE_REGISTRY:
            entry = _NAMESPACE_REGISTRY[namespace]
            entry["subscribers"] = [
                sub for sub in entry["subscribers"] if sub.callback is not None
            ]

            if self._cleanup_namespace_if_empty(namespace):
                if (
                    not namespace.startswith(_NOTIFY_NAMESPACE_ROOT)
                    and self.notify_on_del_namespace
                ):
                    self.emit(namespace=BROKER_ON_NAMESPACE_DELETED, using=namespace)

        if self.notify_on_collected and not namespace.startswith(
            _NOTIFY_NAMESPACE_ROOT
        ):
            self.emit(namespace=BROKER_ON_SUBSCRIBER_COLLECTED, using=namespace)

    def register_subscriber(
        self, namespace: str, callback: subscriber.SUBSCRIBER, priority: int = 0
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
        Raises:
            SignatureMismatchError: If callback signature doesn't match existing
                subscribers.
        Notes:
            Emits a notify event when a namespace is created and when a
            subscriber is registered. Notify emits the used namespace.
        """
        callback_params = self._get_callback_params(callback)
        is_async = asyncio.iscoroutinefunction(callback)

        weak_callback = _make_weak_ref(
            callback=callback,
            namespace=namespace,
            on_collected_callback=self._on_subscriber_collected,
        )

        sub = subscriber.Subscriber(
            weak_callback=weak_callback,
            priority=priority,
            is_async=is_async,
            namespace=namespace,
        )

        is_new_namespace = self._ensure_namespace_exists(namespace)
        entry = _NAMESPACE_REGISTRY[namespace]

        # Validate/set signature
        if entry["signature"] is None:
            entry["signature"] = callback_params
        else:
            existing_params = entry["signature"]
            if existing_params is None or callback_params is None:
                entry["signature"] = None
            elif existing_params != callback_params:
                raise SignatureMismatchError(
                    f"Subscriber parameter mismatch for namespace '{namespace}'. "
                    f"Expected parameters: {sorted(existing_params)}, "
                    f"but got: {sorted(callback_params)}"
                )

        entry["subscribers"].append(sub)

        if (
            is_new_namespace
            and not namespace.startswith(_NOTIFY_NAMESPACE_ROOT)
            and self.notify_on_new_namespace
        ):
            self.emit(namespace=BROKER_ON_NAMESPACE_CREATED, using=namespace)

        if (
            not namespace.startswith(_NOTIFY_NAMESPACE_ROOT)
            and self.notify_on_subscribe
        ):
            self.emit(namespace=BROKER_ON_SUBSCRIBER_ADDED, using=namespace)

    def unregister_subscriber(
        self, namespace: str, callback: subscriber.SUBSCRIBER
    ) -> None:
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
        if namespace not in _NAMESPACE_REGISTRY:
            return

        entry = _NAMESPACE_REGISTRY[namespace]
        entry["subscribers"] = [
            sub for sub in entry["subscribers"] if sub.callback != callback
        ]

        if (
            not namespace.startswith(_NOTIFY_NAMESPACE_ROOT)
            and self.notify_on_unsubscribe
        ):
            self.emit(namespace=BROKER_ON_SUBSCRIBER_REMOVED, using=namespace)

        self._cleanup_namespace_if_empty(namespace)

    def _validate_emit_args(self, namespace: str, kwargs: dict[str, Any]) -> None:
        """
        Validate that emit arguments match subscriber signatures.

        Args:
            namespace (str): The namespace being emitted to.
            kwargs (dict[str, Any]): The keyword arguments being emitted.
        Raises:
            EmitArgumentError: If provided kwargs don't match subscriber signatures.
        """
        provided_args = set(kwargs.keys())

        # Check all namespaces that match the emitted namespace
        for reg_namespace, entry in _NAMESPACE_REGISTRY.items():
            if not self._matches(namespace, reg_namespace):
                continue

            expected_params = entry["signature"]

            if expected_params is None:
                continue

            if provided_args != expected_params:
                raise EmitArgumentError(
                    f"Argument mismatch when emitting to '{namespace}'. "
                    f"Subscribers in '{reg_namespace}' expect: {sorted(expected_params)}, "
                    f"but got: {sorted(provided_args)}"
                )

    def set_subscriber_exception_handler(
        self, handler: Optional[handlers.SUBSCRIPTION_EXCEPTION_HANDLER]
    ) -> None:
        """
        Set the exception handler for subscriber errors.
        The handler is called when a subscriber raises an exception during emit.

        Args:
            Optional[handlers.SUBSCRIPTION_EXCEPTION_HANDLER]:
                Callable with signature (SUBSCRIBER, str, Exception) -> bool.
                Returns True to stop delivery, False to continue.
                Pass None to restore default behavior (re-raise exceptions).
        """
        self._subscriptions_exception_handler = handler

    # -----Emitter Handling----------------------------------------------------

    def emit(self, namespace: str, **kwargs: Any) -> None:
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
        self._validate_emit_args(namespace, kwargs)

        transformed_kwargs = self.apply_transformers(namespace, kwargs)
        if transformed_kwargs is None:
            return  # Event blocked

        for reg_namespace, entry in _NAMESPACE_REGISTRY.items():
            if not self._matches(namespace, reg_namespace):
                continue

            sorted_subscribers = sorted(
                entry["subscribers"], key=lambda s: s.priority, reverse=True
            )
            for sub in sorted_subscribers:
                callback = sub.callback
                if callback is None:
                    continue

                if sub.is_async:
                    continue

                try:
                    callback(**transformed_kwargs)
                except Exception as e:
                    if self._subscriptions_exception_handler is None:
                        raise

                    stop = self._subscriptions_exception_handler(callback, namespace, e)
                    if stop:
                        break

        if not namespace.startswith(_NOTIFY_NAMESPACE_ROOT) and (
            self.notify_on_emit or self.notify_on_emit_all
        ):
            self.emit(namespace=BROKER_ON_EMIT, using=namespace)

    async def emit_async(self, namespace: str, **kwargs: Any) -> None:
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
        self._validate_emit_args(namespace, kwargs)

        transformed_kwargs = self.apply_transformers(namespace, kwargs)
        if transformed_kwargs is None:
            return  # Event blocked

        for reg_namespace, entry in _NAMESPACE_REGISTRY.items():
            if not self._matches(namespace, reg_namespace):
                continue

            sorted_subscribers = sorted(
                entry["subscribers"], key=lambda s: s.priority, reverse=True
            )
            for sub in sorted_subscribers:
                callback = sub.callback

                if callback is None:
                    continue

                try:
                    if sub.is_async:
                        await callback(**transformed_kwargs)
                    else:
                        callback(**transformed_kwargs)
                except Exception as e:
                    if self._subscriptions_exception_handler is None:
                        raise

                    stop = self._subscriptions_exception_handler(callback, namespace, e)
                    if stop:
                        break

        if not namespace.startswith(_NOTIFY_NAMESPACE_ROOT) and (
            self.notify_on_emit_async or self.notify_on_emit_all
        ):
            self.emit(namespace=BROKER_ON_EMIT_ASYNC, using=namespace)

    # -----Transformers--------------------------------------------------------

    def _on_transformer_collected(self, namespace: str) -> None:
        """Called when a transformer is garbage collected."""
        if namespace in _NAMESPACE_REGISTRY:
            entry = _NAMESPACE_REGISTRY[namespace]
            entry["transformers"] = [
                t for t in entry["transformers"] if t.callback is not None
            ]

            if self._cleanup_namespace_if_empty(namespace):
                if (
                    not namespace.startswith(_NOTIFY_NAMESPACE_ROOT)
                    and self.notify_on_del_namespace
                ):
                    self.emit(namespace=BROKER_ON_NAMESPACE_DELETED, using=namespace)

        if self.notify_on_transformer_collected and not namespace.startswith(
            _NOTIFY_NAMESPACE_ROOT
        ):
            self.emit(namespace=BROKER_ON_TRANSFORMER_COLLECTED, using=namespace)

    def register_transformer(
        self,
        namespace: str,
        callback: transformer.TRANSFORMER,
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
        weak_transformer = _make_weak_ref(
            callback=callback,
            namespace=namespace,
            on_collected_callback=self._on_transformer_collected,
        )

        transformer_obj = transformer.Transformer(
            weak_callback=weak_transformer, namespace=namespace, priority=priority
        )

        is_new_namespace = self._ensure_namespace_exists(namespace)
        entry = _NAMESPACE_REGISTRY[namespace]
        entry["transformers"].append(transformer_obj)
        entry["transformers"].sort(key=lambda t: t.priority, reverse=True)

        if (
            is_new_namespace
            and not namespace.startswith(_NOTIFY_NAMESPACE_ROOT)
            and self.notify_on_new_namespace
        ):
            self.emit(namespace=BROKER_ON_NAMESPACE_CREATED, using=namespace)

        if (
            not namespace.startswith(_NOTIFY_NAMESPACE_ROOT)
            and self.notify_on_transformer_add
        ):
            self.emit(namespace=BROKER_ON_TRANSFORMER_ADDED, using=namespace)

    def unregister_transformer(
        self, namespace: str, callback: transformer.TRANSFORMER
    ) -> None:
        """
        Remove a transformer from a namespace.

        Args:
            namespace (str): The namespace the transformer is registered to.
            callback (TRANSFORMER): The transformer function to remove.
        """
        if namespace not in _NAMESPACE_REGISTRY:
            return

        entry = _NAMESPACE_REGISTRY[namespace]
        entry["transformers"] = [
            t for t in entry["transformers"] if t.callback != callback
        ]

        if (
            not namespace.startswith(_NOTIFY_NAMESPACE_ROOT)
            and self.notify_on_transformer_remove
        ):
            self.emit(namespace=BROKER_ON_TRANSFORMER_REMOVED, using=namespace)

        self._cleanup_namespace_if_empty(namespace)

    def set_transformer_exception_handler(
        self,
        handler: Optional[transformer.TRANSFORMER_EXCEPTION_HANDLER],
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
        self._transformer_exception_handler = handler

    def apply_transformers(
        self, namespace: str, kwargs: dict[str, Any]
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

        for reg_namespace, entry in _NAMESPACE_REGISTRY.items():
            if self._matches(namespace, reg_namespace):
                matching_transformers.extend(entry["transformers"])

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
                if self._transformer_exception_handler is not None:
                    stop = self._transformer_exception_handler(callback, namespace, e)
                    if stop:
                        return None
                else:
                    transformer_name = handlers.get_callable_name(callback)
                    raise RuntimeError(
                        f"Transformer '{transformer_name}' failed for namespace '{namespace}': {e}"
                    ) from e

        return current_kwargs

    def clear_transformers(self) -> None:
        """Clear all registered transformers."""
        for entry in _NAMESPACE_REGISTRY.values():
            entry["transformers"].clear()
        empty_ns = [
            ns
            for ns, entry in _NAMESPACE_REGISTRY.items()
            if not entry["subscribers"] and not entry["transformers"]
        ]
        for ns in empty_ns:
            del _NAMESPACE_REGISTRY[ns]
            if self.notify_on_del_namespace:
                self.emit(namespace=BROKER_ON_NAMESPACE_DELETED, using=ns)

    @staticmethod
    def get_all_transformer_namespaces() -> list[str]:
        """Get all namespaces that have transformers."""
        return sorted(
            [ns for ns, entry in _NAMESPACE_REGISTRY.items() if entry["transformers"]]
        )

    # -----Notifies + Helpers--------------------------------------------------

    def set_flag_states(
        self,
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
        self.notify_on_subscribe = on_subscribe
        self.notify_on_unsubscribe = on_unsubscribe
        self.notify_on_collected = on_subscriber_collected

        self.notify_on_transformer_add = on_transform
        self.notify_on_transformer_remove = on_untransform
        self.notify_on_transformer_collected = on_transformer_collected

        self.notify_on_emit = on_emit
        self.notify_on_emit_async = on_emit_async
        self.notify_on_emit_all = on_emit_all

        self.notify_on_new_namespace = on_new_namespace
        self.notify_on_del_namespace = on_del_namespace

    @staticmethod
    def _matches(namespace: str, pattern: str) -> bool:
        """
        Check if an event namespace matches a pattern, typically another item's
        namespace.

        Args:
            namespace (str): The namespace where event was emitted.
            pattern (str): The namespace to check against.
        Returns:
            bool: True if subscriber should receive the event.
        """
        if namespace == pattern:
            return True

        # Wildcard match - subscriber wants all events under a root
        if pattern.endswith(".*"):
            # Although not strictly necessary to remove . and *, doing so adds
            # slightly more validity to the check.
            root = pattern[:-2]
            return namespace.startswith(root + ".")

        return False

    def _cleanup_namespace_if_empty(self, namespace: str) -> None:
        """Remove namespace from registry if it has no subscribers or transformers."""
        if namespace not in _NAMESPACE_REGISTRY:
            return

        entry = _NAMESPACE_REGISTRY[namespace]
        if not entry["subscribers"] and not entry["transformers"]:
            del _NAMESPACE_REGISTRY[namespace]
            if (
                not namespace.startswith(_NOTIFY_NAMESPACE_ROOT)
                and self.notify_on_del_namespace
            ):
                self.emit(namespace=BROKER_ON_NAMESPACE_DELETED, using=namespace)

    @staticmethod
    def _ensure_namespace_exists(namespace: str) -> bool:
        """
        Ensure namespace entry exists in registry.
        Returns True if the namespace was added, False if it already existed.
        """
        if namespace not in _NAMESPACE_REGISTRY:
            _NAMESPACE_REGISTRY[namespace] = {
                "subscribers": [],
                "transformers": [],
                "signature": None,
            }
            return True

        return False

    # -----Introspection API---------------------------------------------------

    # -----Subscriber Introspection Methods--------------------------

    @staticmethod
    def get_subscriber_count(namespace: str) -> int:
        """
        Get the number of subscribers for a namespace.

        Args:
            namespace (str): Namespace to count subscribers for.
        Returns:
            int: Number of subscribers (including dead weak references).
        """
        return len(_NAMESPACE_REGISTRY.get(namespace, {}).get("subscribers", []))

    @staticmethod
    def get_live_subscriber_count(namespace: str) -> int:
        """
        Get the number of live (non-garbage-collected) subscribers.

        Args:
            namespace: Namespace to count live subscribers for.
        Returns:
            Number of subscribers with live callbacks.
        """
        if namespace not in _NAMESPACE_REGISTRY:
            return 0
        return sum(
            1
            for sub in _NAMESPACE_REGISTRY[namespace]["subscribers"]
            if sub.callback is not None
        )

    @staticmethod
    def is_subscribed(callback: subscriber.SUBSCRIBER, namespace: str) -> bool:
        """
        Check if a specific callback is subscribed to a namespace.

        Args:
            callback (Callable): The callback function to check.
            namespace (str): The namespace to check.

        Returns:
            bool: True if callback is subscribed to namespace, False otherwise.
        """
        if namespace not in _NAMESPACE_REGISTRY:
            return False

        for sub in _NAMESPACE_REGISTRY[namespace]["subscribers"]:
            if sub.callback == callback:
                return True

        return False

    @staticmethod
    def get_subscriptions(callback: subscriber.SUBSCRIBER) -> list[str]:
        """
        Get all namespaces that a callback is subscribed to.

        Args:
            callback (Callable): The callback to find subscriptions for.
        Returns:
            list[str]: List of namespace strings the callback is subscribed to.
        Example:
            >>> import broker
            ...
            >>> def my_handler(data: str): pass
            >>> broker.register_subscriber('test.one', my_handler)
            >>> broker.register_subscriber('test.two', my_handler)
            >>> broker.get_subscriptions(my_handler)
            ['test.one', 'test.two']
        """
        subscriptions = []
        for namespace, entry in _NAMESPACE_REGISTRY.items():
            for sub in entry["subscribers"]:
                if sub.callback == callback:
                    subscriptions.append(namespace)
                    break

        return sorted(subscriptions)

    @staticmethod
    def get_subscribers(namespace: str) -> list[subscriber.Subscriber]:
        """
        Get all subscribers for a namespace.

        Args:
            namespace (str): Namespace to get subscribers for.
        Returns:
            list[subscriber.Subscriber]: List of Subscriber objects. May include
                dead references.
        """
        return list(_NAMESPACE_REGISTRY.get(namespace, {}).get("subscribers", []))

    @staticmethod
    def get_live_subscribers(namespace: str) -> list[subscriber.Subscriber]:
        """
        Get all live (non-garbage-collected) subscribers for a namespace.

        Args:
            namespace (str): Namespace to get live subscribers for.
        Returns:
            list[subscriber.Subscriber]: List of Subscriber objects with live
                callbacks only.
        """
        if namespace not in _NAMESPACE_REGISTRY:
            return []

        return [
            sub
            for sub in _NAMESPACE_REGISTRY[namespace]["subscribers"]
            if sub.callback is not None
        ]

    # -----Transformer Introspection Methods-------------------------

    @staticmethod
    def get_transformer_count(namespace: str) -> int:
        """
        Get the number of transformers for a namespace.

        Args:
            namespace (str): Namespace to count transformers for.
        Returns:
            int: Number of transformers (including dead weak references).
        """
        return len(_NAMESPACE_REGISTRY.get(namespace, {}).get("transformers", []))

    @staticmethod
    def get_live_transformer_count(namespace: str) -> int:
        """
        Get the number of live (non-garbage-collected) transformers.

        Args:
            namespace: Namespace to count live transformers for.
        Returns:
            Number of transformers with live callbacks.
        """
        if namespace not in _NAMESPACE_REGISTRY:
            return 0

        return sum(
            1
            for trans in _NAMESPACE_REGISTRY[namespace]["transformers"]
            if trans.callback is not None
        )

    @staticmethod
    def is_transformed(callback: transformer.TRANSFORMER, namespace: str) -> bool:
        """
        Check if a specific callback is registered as a transformer for a namespace.

        Args:
            callback (Callable): The transformer function to check.
            namespace (str): The namespace to check.

        Returns:
            bool: True if callback is registered as transformer for namespace, False otherwise.
        """
        if namespace not in _NAMESPACE_REGISTRY:
            return False

        for trans in _NAMESPACE_REGISTRY[namespace]["transformers"]:
            if trans.callback == callback:
                return True

        return False

    @staticmethod
    def get_transformations(callback: transformer.TRANSFORMER) -> list[str]:
        """
        Get all namespaces that a callback is registered as a transformer for.

        Args:
            callback (Callable): The transformer callback to find registrations for.
        Returns:
            list[str]: List of namespace strings the callback transforms.
        Example:
            >>> import broker
            ...
            >>> def my_transformer(namespace_: str, kwargs: dict) -> dict:
            ...     return kwargs
            ...
            >>> broker.register_transformer('test.one', my_transformer)
            >>> broker.register_transformer('test.two', my_transformer)
            >>> broker.get_transformations(my_transformer)
            ['test.one', 'test.two']
        """
        transformations = []
        for namespace, entry in _NAMESPACE_REGISTRY.items():
            for trans in entry["transformers"]:
                if trans.callback == callback:
                    transformations.append(namespace)
                    break

        return sorted(transformations)

    @staticmethod
    def get_transformers(namespace: str) -> list[transformer.Transformer]:
        """
        Get all transformers for a namespace.

        Args:
            namespace (str): Namespace to get transformers for.
        Returns:
            list[transformer.Transformer]: List of Transformer objects. May include
                dead references.
        """
        return list(_NAMESPACE_REGISTRY.get(namespace, {}).get("transformers", []))

    @staticmethod
    def get_live_transformers(namespace: str) -> list[transformer.Transformer]:
        """
        Get all live (non-garbage-collected) transformers for a namespace.

        Args:
            namespace (str): Namespace to get live transformers for.
        Returns:
            list[transformer.Transformer]: List of Transformer objects with live
                callbacks only.
        """
        if namespace not in _NAMESPACE_REGISTRY:
            return []

        return [
            trans
            for trans in _NAMESPACE_REGISTRY[namespace]["transformers"]
            if trans.callback is not None
        ]

    # -----General Introspection Methods-----------------------------

    def get_matching_namespaces(self, pattern: str) -> list[str]:
        """
        Get all namespaces that match a pattern (including wildcards).

        Args:
            pattern (str): Pattern to match (e.g., 'system.*' or 'app.module.action').
        Returns:
            list[str]: List of matching namespace strings.
        Example:
            broker.get_matching_namespaces('system.*')
            ['system.io.file', 'system.io.network']
        """
        matching = []
        for namespace in _NAMESPACE_REGISTRY.keys():
            # Pattern 'system.io.*' should match namespace 'system.io.file'
            # OR namespace 'system.*' should match pattern 'system.io.file'
            if self._matches(namespace, pattern) or self._matches(pattern, namespace):
                matching.append(namespace)

        return sorted(matching)

    @staticmethod
    def get_namespace_info(namespace: str) -> Optional[dict[str, object]]:
        """
        Get detailed information about a namespace.

        Args:
            namespace (str): Namespace to get info for.
        Returns:
            Optional[dict[str, object]]: Dictionary with namespace details, or None
                if namespace doesn't exist.
        Example:
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
        if namespace not in _NAMESPACE_REGISTRY:
            return None

        subscribers = _NAMESPACE_REGISTRY[namespace]["subscribers"]
        live_subs = [sub for sub in subscribers if sub.callback is not None]

        transformers = _NAMESPACE_REGISTRY[namespace]["transformers"]
        live_trans = [trans for trans in transformers if trans.callback is not None]

        return {
            "namespace": namespace,
            "subscriber_count": len(subscribers),
            "live_subscriber_count": len(live_subs),
            "transformer_count": len(transformers),
            "live_transformer_count": len(live_trans),
            "expected_params": _NAMESPACE_REGISTRY[namespace]["signature"],
            "has_async": any(sub.is_async for sub in live_subs),
            "has_sync": any(not sub.is_async for sub in live_subs),
            "priorities": sorted(set(sub.priority for sub in live_subs), reverse=True),
            "transformer_priorities": sorted(
                set(trans.priority for trans in live_trans), reverse=True
            ),
        }

    def get_all_namespace_info(self) -> dict[str, dict[str, object]]:
        """
        Get detailed information for all namespaces.

        Returns:
            dict[str, dict[str, object]]: Dictionary mapping namespace to info dict.
        """
        return {
            namespace: self.get_namespace_info(namespace)
            for namespace in _NAMESPACE_REGISTRY.keys()
        }

    @staticmethod
    def get_statistics() -> dict[str, object]:
        """
        Get overall broker statistics.

        Returns:
            dict[str, object]: Dictionary with broker-wide statistics.

        Example:
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
        total_subscribers = sum(
            len(entry["subscribers"]) for entry in _NAMESPACE_REGISTRY.values()
        )
        total_live_subscribers = sum(
            sum(1 for sub in entry["subscribers"] if sub.callback is not None)
            for entry in _NAMESPACE_REGISTRY.values()
        )

        total_transformers = sum(
            len(entry["transformers"]) for entry in _NAMESPACE_REGISTRY.values()
        )
        total_live_transformers = sum(
            sum(1 for trans in entry["transformers"] if trans.callback is not None)
            for entry in _NAMESPACE_REGISTRY.values()
        )

        namespaces_with_async = sum(
            1
            for entry in _NAMESPACE_REGISTRY.values()
            if any(
                sub.is_async and sub.callback is not None
                for sub in entry["subscribers"]
            )
        )

        namespaces_with_sync = sum(
            1
            for entry in _NAMESPACE_REGISTRY.values()
            if any(
                not sub.is_async and sub.callback is not None
                for sub in entry["subscribers"]
            )
        )

        namespaces_with_transformers = sum(
            1
            for entry in _NAMESPACE_REGISTRY.values()
            if any(trans.callback is not None for trans in entry["transformers"])
        )

        namespace_count = len(_NAMESPACE_REGISTRY)

        return {
            "total_namespaces": namespace_count,
            "total_subscribers": total_subscribers,
            "total_live_subscribers": total_live_subscribers,
            "dead_subscriber_references": total_subscribers - total_live_subscribers,
            "total_transformers": total_transformers,
            "total_live_transformers": total_live_transformers,
            "dead_transformer_references": total_transformers - total_live_transformers,
            "namespaces_with_async": namespaces_with_async,
            "namespaces_with_sync": namespaces_with_sync,
            "namespaces_with_transformers": namespaces_with_transformers,
            "average_subscribers_per_namespace": (
                total_live_subscribers / namespace_count if namespace_count > 0 else 0
            ),
            "average_transformers_per_namespace": (
                total_live_transformers / namespace_count if namespace_count > 0 else 0
            ),
        }

    @staticmethod
    def _get_callback_info(callback: Callable) -> str:
        """Returns metadata on a callable as a string."""
        if callback is None:
            info = "<dead reference>"

        elif hasattr(callback, "__self__"):
            obj = callback.__self__
            class_name = obj.__class__.__name__
            method_name = callback.__name__
            info = f"{class_name}.{method_name}"

        elif hasattr(callback, "__qualname__"):
            # Regular function, static method, or class method
            module = getattr(callback, "__module__", "<unknown>")
            qualname = callback.__qualname__
            info = f"{module}.{qualname}"

        else:
            # Fallback for unusual callables
            info = str(callback)

        return info

    def to_dict(self) -> dict:
        """Convert the broker structure to a dictionary."""
        keys = sorted(_NAMESPACE_REGISTRY.keys())
        data = {}

        for namespace in keys:
            entry = _NAMESPACE_REGISTRY[namespace]

            # Process subscribers
            subscribers_info = []
            for sub in entry["subscribers"]:
                info = self._get_callback_info(sub.callback)

                priority_str = (
                    f" [priority={sub.priority}]" if sub.priority != 0 else ""
                )
                async_str = " [async]" if sub.is_async else ""
                subscribers_info.append(f"{info}{priority_str}{async_str}")

            # Process transformers
            transformers_info = []
            for trans in entry["transformers"]:
                info = self._get_callback_info(trans.callback)

                priority_str = (
                    f" [priority={trans.priority}]" if trans.priority != 0 else ""
                )
                transformers_info.append(f"{info}{priority_str}")

            # Build namespace entry
            namespace_data = {}
            if subscribers_info:
                namespace_data["subscribers"] = subscribers_info
            if transformers_info:
                namespace_data["transformers"] = transformers_info

            data[namespace] = namespace_data

        return data

    def to_string(self) -> str:
        """Returns a string representation of the broker."""
        return json.dumps(self.to_dict(), indent=4)

    def export(self, filepath: Union[str, os.PathLike]) -> None:
        """Export broker structure to filepath."""
        with open(filepath, "w") as outfile:
            json.dump(self.to_dict(), outfile, indent=4)

    @staticmethod
    def get_namespaces() -> list[str]:
        """Get all registered namespaces."""
        return sorted(_NAMESPACE_REGISTRY.keys())

    @staticmethod
    def namespace_exists(namespace: str) -> bool:
        """Check if a namespace exists..."""
        return namespace in _NAMESPACE_REGISTRY


# This is here to protect the _NAMESPACE_REGISTRY, creating a protective closure.
custom_module = Broker(sys.modules[__name__].__name__)
sys.modules[__name__] = custom_module
