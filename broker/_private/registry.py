"""
Herein is the namespace table and staged emission buffer.

A reimport protection clause exists at the top of the file to prevent the
subscribers table from being lost on import.
"""

import sys
from typing import DefaultDict

from broker import namespaces
from broker import subscriber

# -----------------------------------------------------------------------------
_existing = sys.modules.get("broker._private.registry")
if _existing is not None and hasattr(_existing, "_REGISTRY_IMPORT_GUARD"):
    raise ImportError(
        "Module 'broker._private.registry' has already been imported and cannot be reloaded. "
        "Subscriber data would be lost. "
        "Restart your Python session to reimport."
    )

_REGISTRY_IMPORT_GUARD = True
# -----------------------------------------------------------------------------


NAMESPACE_REGISTRY: dict[str, namespaces.NamespaceEntry] = {}
"""
Global namespace registry.
Each namespace tracks its subscribers, transformers, and expected signature.
A namespace exists if it has at least one subscriber OR transformer.
"""


STAGED_REGISTRY: dict[str, list[dict]] = DefaultDict(list)
"""
A separate namespace table to temporarily hold emitted values until the user
calls broker.emit_staged(). 
"""


def matches(namespace: str, pattern: str) -> bool:
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


def ensure_namespace_exists(namespace: str) -> bool:
    """
    Ensure namespace entry exists in registry.
    Returns True if the namespace was added, False if it already existed.
    """
    if namespace not in NAMESPACE_REGISTRY:
        NAMESPACE_REGISTRY[namespace] = namespaces.NamespaceEntry([], [], None)
        return True

    return False


def get_sorted_subscribers(namespace: str) -> list[tuple[str, subscriber.Subscriber]]:
    """Get all live subscribers matching namespace, sorted by priority descending."""
    result = []
    for reg_namespace, entry in NAMESPACE_REGISTRY.items():
        if matches(namespace, reg_namespace):
            result.extend((reg_namespace, sub) for sub in entry.subscribers)

    result.sort(key=lambda x: x[1].priority, reverse=True)
    return result
