"""
Introspection mixin for the event broker.

Provides BrokerIntrospectionMixin, a mixin class that adds read-only query
methods to the Broker. Covers subscriber and transformer inspection, namespace
queries, statistics, and serialization.

Intended to be composed into the Broker class only. Not for direct use.
"""

from __future__ import annotations

import json
import os
from typing import Callable
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union

from broker import subscriber
from broker import transformer
from broker._registry import NAMESPACE_REGISTRY
from broker._registry import STAGED_REGISTRY

if TYPE_CHECKING:
    from broker._broker import Broker


class BrokerIntrospectionMixin(object):
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
        fetched = NAMESPACE_REGISTRY.get(namespace, None)
        if fetched is None:
            return 0

        return len(fetched.subscribers)

    @staticmethod
    def get_live_subscriber_count(namespace: str) -> int:
        """
        Get the number of live (non-garbage-collected) subscribers.

        Args:
            namespace: Namespace to count live subscribers for.
        Returns:
            Number of subscribers with live callbacks.
        """
        if namespace not in NAMESPACE_REGISTRY:
            return 0
        return sum(
            1
            for sub in NAMESPACE_REGISTRY[namespace].subscribers
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
        if namespace not in NAMESPACE_REGISTRY:
            return False

        for sub in NAMESPACE_REGISTRY[namespace].subscribers:
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
        for namespace, entry in NAMESPACE_REGISTRY.items():
            for sub in entry.subscribers:
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
        return list(NAMESPACE_REGISTRY.get(namespace, {}).subscribers)

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
        if namespace not in NAMESPACE_REGISTRY:
            return []

        return [
            sub
            for sub in NAMESPACE_REGISTRY[namespace].subscribers
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
        fetched = NAMESPACE_REGISTRY.get(namespace, None)
        if fetched is None:
            return 0

        return len(fetched.transformers)

    @staticmethod
    def get_live_transformer_count(namespace: str) -> int:
        """
        Get the number of live (non-garbage-collected) transformers.

        Args:
            namespace: Namespace to count live transformers for.
        Returns:
            Number of transformers with live callbacks.
        """
        if namespace not in NAMESPACE_REGISTRY:
            return 0

        return sum(
            1
            for trans in NAMESPACE_REGISTRY[namespace].transformers
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
        if namespace not in NAMESPACE_REGISTRY:
            return False

        for trans in NAMESPACE_REGISTRY[namespace].transformers:
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
        for namespace, entry in NAMESPACE_REGISTRY.items():
            for trans in entry.transformers:
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
        return list(NAMESPACE_REGISTRY.get(namespace, {}).transformers)

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
        if namespace not in NAMESPACE_REGISTRY:
            return []

        return [
            trans
            for trans in NAMESPACE_REGISTRY[namespace].transformers
            if trans.callback is not None
        ]

    # -----Staging Introspection Methods---------------------------------------

    @staticmethod
    def get_staged_namespaces() -> list[str]:
        """Get all namespaces with staged events."""
        return sorted(STAGED_REGISTRY.keys())

    @staticmethod
    def get_staged_count(namespace: Optional[str] = None) -> int:
        """
        Get the number of staged events.

        Args:
            namespace (str): If provided, returns the count for that namespace
                only. If None, returns the total count across all namespaces.
        Returns:
            int: Number of staged events.
        """
        if namespace is not None:
            return len(STAGED_REGISTRY.get(namespace, []))
        return sum(len(events) for events in STAGED_REGISTRY.values())

    # -----General Introspection Methods-----------------------------

    def get_matching_namespaces(self: Broker, pattern: str) -> list[str]:
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
        for namespace in NAMESPACE_REGISTRY.keys():
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
        if namespace not in NAMESPACE_REGISTRY:
            return None

        subscribers = NAMESPACE_REGISTRY[namespace].subscribers
        live_subs = [sub for sub in subscribers if sub.callback is not None]

        transformers = NAMESPACE_REGISTRY[namespace].transformers
        live_trans = [trans for trans in transformers if trans.callback is not None]

        return {
            "namespace": namespace,
            "subscriber_count": len(subscribers),
            "live_subscriber_count": len(live_subs),
            "transformer_count": len(transformers),
            "live_transformer_count": len(live_trans),
            "expected_params": NAMESPACE_REGISTRY[namespace].signature,
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
            for namespace in NAMESPACE_REGISTRY.keys()
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
            len(entry.subscribers) for entry in NAMESPACE_REGISTRY.values()
        )
        total_live_subscribers = sum(
            sum(1 for sub in entry.subscribers if sub.callback is not None)
            for entry in NAMESPACE_REGISTRY.values()
        )

        total_transformers = sum(
            len(entry.transformers) for entry in NAMESPACE_REGISTRY.values()
        )
        total_live_transformers = sum(
            sum(1 for trans in entry.transformers if trans.callback is not None)
            for entry in NAMESPACE_REGISTRY.values()
        )

        namespaces_with_async = sum(
            1
            for entry in NAMESPACE_REGISTRY.values()
            if any(
                sub.is_async and sub.callback is not None for sub in entry.subscribers
            )
        )

        namespaces_with_sync = sum(
            1
            for entry in NAMESPACE_REGISTRY.values()
            if any(
                not sub.is_async and sub.callback is not None
                for sub in entry.subscribers
            )
        )

        namespaces_with_transformers = sum(
            1
            for entry in NAMESPACE_REGISTRY.values()
            if any(trans.callback is not None for trans in entry.transformers)
        )

        namespace_count = len(NAMESPACE_REGISTRY)

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
        keys = sorted(NAMESPACE_REGISTRY.keys())
        data = {}

        for namespace in keys:
            entry = NAMESPACE_REGISTRY[namespace]

            # Process subscribers
            subscribers_info = []
            for sub in entry.subscribers:
                info = self._get_callback_info(sub.callback)

                priority_str = (
                    f" [priority={sub.priority}]" if sub.priority != 0 else ""
                )
                async_str = " [async]" if sub.is_async else ""
                subscribers_info.append(f"{info}{priority_str}{async_str}")

            # Process transformers
            transformers_info = []
            for trans in entry.transformers:
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
        return sorted(NAMESPACE_REGISTRY.keys())

    @staticmethod
    def namespace_exists(namespace: str) -> bool:
        """Check if a namespace exists..."""
        return namespace in NAMESPACE_REGISTRY
