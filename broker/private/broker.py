"""
# Primary Event Broker

Herein is the event broker system itself.

Function stubs exist in the stub file for static type checkers to validate
correct calls.

For a complete breakdown of broker functionality, read the project readme.
"""

# Remember to update functions in the stub file so static type checkers
# and IntelliSense can receive accurate feedback!

import inspect
from typing import Any
from typing import Optional

from broker import exceptions
from broker import handlers
from broker import subscriber
from broker import transformer
from broker.private import decorators
from broker.private import function
from broker.private import registry
from broker.private.introspection import BrokerIntrospectionMixin
from broker.paused import PausedContext


class Broker(BrokerIntrospectionMixin):
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

    # -----Class Values--------------------------------------------------------
    # ---Default Namespaces---
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

    # ---Version---
    version_major = 1
    version_minor = 11
    version_patch = 13
    __version__ = f"{version_major}.{version_minor}.{version_patch}"
    """Current broker version in {major}.{minor}.{patch} format."""

    # -----Runtime Closures----------------------------------------------------
    # ---Exceptions---
    SignatureMismatchError = exceptions.SignatureMismatchError
    EmitArgumentError = exceptions.EmitArgumentError

    # ---Modules---
    handlers = handlers
    subscriber = subscriber
    transformer = transformer
    # -------------------------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()

        self._install_decorators()

        # -----Exception Handlers-----
        self._subscriptions_exception_handler: Optional[
            handlers.SUBSCRIPTION_EXCEPTION_HANDLER
        ] = handlers.stop_and_log_subscriber_exception

        self._transformer_exception_handler: Optional[
            handlers.TRANSFORMER_EXCEPTION_HANDLER
        ] = handlers.stop_and_log_transformer_exception

        # ---Control Flow---
        self._paused: int = 0
        """
        When greater than 0, the broker will not pass signals on to subscribers
        through emit or emit_async. Primarily toggled through context managers.
        
        This is tracked as an integer instead of a bool so that nested context
        managers will not create an invalid state for outer context managers.
        i.e. if a `with` block nested in another exists, the __exit__ may create
        an invalid state that the outer `with` block will use before exiting.
        """

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

        # -----Component Mechanisms-----
        self.paused = PausedContext(self)

    def _install_decorators(self) -> None:
        """Create decorator bindings."""
        self.subscribe = decorators.make_subscribe_decorator(self)
        """Decorator to register a function or static method as a subscriber."""

        self.transform = decorators.make_transformer_decorator(self)
        """Decorator to register a function or static method as a transformer."""

    @staticmethod
    def clear() -> None:
        registry.NAMESPACE_REGISTRY.clear()

    @staticmethod
    def clear_staged() -> None:
        registry.STAGED_REGISTRY.clear()

    # -----Subscriber Management-----------------------------------------------

    def register_subscriber(
        self,
        namespace: str,
        callback: subscriber.SUBSCRIBER,
        priority: int = 0,
        once: bool = False,
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
            once: (bool): Whether the subscriber should unregister itself after
                firing. Defaults to False.
        Raises:
            SignatureMismatchError: If callback signature doesn't match existing
                subscribers.
        Notes:
            Emits a notify event when a namespace is created and when a
            subscriber is registered. Notify emits the used namespace.
        """
        callback_params = function.get_callback_params(callback)
        is_async = inspect.iscoroutinefunction(callback)

        weak_callback = function.make_weak_ref(
            callback=callback,
            namespace=namespace,
            on_collected_callback=self._on_subscriber_collected,
        )

        sub = subscriber.Subscriber(
            weak_callback=weak_callback,
            priority=priority,
            is_async=is_async,
            namespace=namespace,
            is_one_shot=once,
        )

        is_new_namespace = registry.ensure_namespace_exists(namespace)
        entry = registry.NAMESPACE_REGISTRY[namespace]

        # Validate/set signature
        if entry.signature is None:
            entry.signature = callback_params
        else:
            existing_params = entry.signature
            if existing_params is None or callback_params is None:
                entry.signature = None
            elif existing_params != callback_params:
                raise self.SignatureMismatchError(
                    f"Subscriber parameter mismatch for namespace '{namespace}'. "
                    f"Expected parameters: {sorted(existing_params)}, "
                    f"but got: {sorted(callback_params)}"
                )

        entry.subscribers.append(sub)

        if is_new_namespace:
            self._notify_new_namespace_created(namespace)

        if (
            not namespace.startswith(self._NOTIFY_NAMESPACE_ROOT)
            and self.notify_on_subscribe
        ):
            self.emit(namespace=self.BROKER_ON_SUBSCRIBER_ADDED, using=namespace)

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
        if namespace not in registry.NAMESPACE_REGISTRY:
            return

        entry = registry.NAMESPACE_REGISTRY[namespace]
        items = getattr(entry, "subscribers")
        setattr(entry, "subscribers", [i for i in items if i.callback != callback])

        if (
            not namespace.startswith(self._NOTIFY_NAMESPACE_ROOT)
            and self.notify_on_unsubscribe
        ):
            self.emit(namespace=self.BROKER_ON_SUBSCRIBER_REMOVED, using=namespace)

        self._cleanup_namespace_if_empty(namespace)

    def unregister_subscriber_all(self, callback: subscriber.SUBSCRIBER) -> None:
        """
        Removes a subscriber from all namespaces it is currently present in.

        Args:
            callback (Callable): The callable to unsubscribe.
        """
        subscriber_namespaces = self.get_subscriptions(callback)
        for namespace in subscriber_namespaces:
            self.unregister_subscriber(namespace, callback)

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
        if self._paused > 0:
            return

        function.validate_emit_args(namespace, kwargs)

        transformed_kwargs = self.apply_transformers(namespace, kwargs)
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
                if self._subscriptions_exception_handler is None:
                    raise
                if self._subscriptions_exception_handler(callback, namespace, e):
                    break

            if sub.is_one_shot:
                one_shots.append((reg_namespace, callback))

        for reg_namespace, callback in one_shots:
            self.unregister_subscriber(reg_namespace, callback)

        if not namespace.startswith(self._NOTIFY_NAMESPACE_ROOT) and (
            self.notify_on_emit or self.notify_on_emit_all
        ):
            self.emit(namespace=self.BROKER_ON_EMIT, using=namespace)

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
        if self._paused > 0:
            return

        function.validate_emit_args(namespace, kwargs)

        transformed_kwargs = self.apply_transformers(namespace, kwargs)
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
                if self._subscriptions_exception_handler is None:
                    raise

                if self._subscriptions_exception_handler(callback, namespace, e):
                    break

            if sub.is_one_shot:
                one_shots.append((reg_namespace, callback))

        for reg_namespace, callback in one_shots:
            self.unregister_subscriber(reg_namespace, callback)

        if not namespace.startswith(self._NOTIFY_NAMESPACE_ROOT) and (
            self.notify_on_emit_async or self.notify_on_emit_all
        ):
            self.emit(namespace=self.BROKER_ON_EMIT_ASYNC, using=namespace)

    # -----Staged Handling-----------------------------------------------------

    @staticmethod
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

    def emit_staged(self, flush: bool = True) -> None:
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
                self.emit(namespace, **kwargs)

    async def emit_staged_async(self, flush: bool = True) -> None:
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
                await self.emit_async(namespace, **kwargs)

    # -----Transformers--------------------------------------------------------

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
        weak_transformer = function.make_weak_ref(
            callback=callback,
            namespace=namespace,
            on_collected_callback=self._on_transformer_collected,
        )

        transformer_obj = transformer.Transformer(
            weak_callback=weak_transformer, namespace=namespace, priority=priority
        )

        is_new_namespace = registry.ensure_namespace_exists(namespace)
        entry = registry.NAMESPACE_REGISTRY[namespace]
        entry.transformers.append(transformer_obj)
        entry.transformers.sort(key=lambda t: t.priority, reverse=True)

        if is_new_namespace:
            self._notify_new_namespace_created(namespace)

        if (
            not namespace.startswith(self._NOTIFY_NAMESPACE_ROOT)
            and self.notify_on_transformer_add
        ):
            self.emit(namespace=self.BROKER_ON_TRANSFORMER_ADDED, using=namespace)

    def unregister_transformer(
        self, namespace: str, callback: transformer.TRANSFORMER
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
            not namespace.startswith(self._NOTIFY_NAMESPACE_ROOT)
            and self.notify_on_transformer_remove
        ):
            self.emit(namespace=self.BROKER_ON_TRANSFORMER_REMOVED, using=namespace)

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
        for ns, entry in registry.NAMESPACE_REGISTRY.items():
            entry.transformers.clear()
            self._cleanup_namespace_if_empty(ns)

    # -----Notify Flags--------------------------------------------------------

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

    # -----Helpers-------------------------------------------------------------

    def _notify_new_namespace_created(self, namespace: str) -> None:
        if (
            not namespace.startswith(self._NOTIFY_NAMESPACE_ROOT)
            and self.notify_on_new_namespace
        ):
            self.emit(namespace=self.BROKER_ON_NAMESPACE_CREATED, using=namespace)

    def _cleanup_namespace_if_empty(self, namespace: str) -> None:
        """Remove namespace from registry if it has no subscribers or transformers."""
        if namespace not in registry.NAMESPACE_REGISTRY:
            return

        entry = registry.NAMESPACE_REGISTRY[namespace]
        if not entry.subscribers and not entry.transformers:
            del registry.NAMESPACE_REGISTRY[namespace]
            if (
                not namespace.startswith(self._NOTIFY_NAMESPACE_ROOT)
                and self.notify_on_del_namespace
            ):
                self.emit(namespace=self.BROKER_ON_NAMESPACE_DELETED, using=namespace)

    def _on_subscriber_collected(self, namespace: str) -> None:
        """Called when a subscriber is garbage collected."""
        if namespace in registry.NAMESPACE_REGISTRY:
            entry = registry.NAMESPACE_REGISTRY[namespace]
            items = getattr(entry, "subscribers")
            setattr(entry, "subscribers", [i for i in items if i.callback is not None])

            self._cleanup_namespace_if_empty(namespace)

        if self.notify_on_collected and not namespace.startswith(
            self._NOTIFY_NAMESPACE_ROOT
        ):
            self.emit(namespace=self.BROKER_ON_SUBSCRIBER_COLLECTED, using=namespace)

    def _on_transformer_collected(self, namespace: str) -> None:
        """Called when a transformer is garbage collected."""
        if namespace in registry.NAMESPACE_REGISTRY:
            entry = registry.NAMESPACE_REGISTRY[namespace]
            items = getattr(entry, "transformers")
            setattr(entry, "transformers", [i for i in items if i.callback is not None])

            self._cleanup_namespace_if_empty(namespace)

        if self.notify_on_transformer_collected and not namespace.startswith(
            self._NOTIFY_NAMESPACE_ROOT
        ):
            self.emit(namespace=self.BROKER_ON_TRANSFORMER_COLLECTED, using=namespace)
