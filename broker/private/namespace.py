"""
Herein is the namespace table and staged emission buffer.

A reimport protection clause exists at the top of the file to prevent the
subscriber table from being lost on import.

Defines the NamespaceEntry dataclass that represents a unified namespace in the
broker's internal registry. Each namespace entry tracks both subscribers and
transformers registered to that namespace, along with the expected parameter
signature for validation.

A namespace exists in the registry when it has at least one subscriber OR
transformer registered, except very briefly when registering a transformer or
subscriber to a newly created namespace.
"""

import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from broker.subscriber import Subscriber
    from broker.transformer import Transformer

# -----------------------------------------------------------------------------
_ENV_REIMPORT_GUARD = "BROKER_REIMPORT_GUARD"
_ENV_GUARD_T = "true"
_ENV_GUARD_F = "false"
os.environ[_ENV_REIMPORT_GUARD] = _ENV_GUARD_T


def check_reimport_guard() -> None:
    if os.environ[_ENV_REIMPORT_GUARD] == _ENV_GUARD_F:
        return

    _existing = sys.modules.get("broker.private.namespace")
    if _existing is not None and hasattr(_existing, "_NAMESPACE_IMPORT_GUARD"):
        raise ImportError(
            "Module 'broker.private.namespace' has already been imported and cannot be reloaded. "
            "Subscriber data would be lost. "
            "Restart your Python session, or set 'BROKER_REIMPORT_GUARD' environ var to 'false', to reimport."
        )


check_reimport_guard()

_NAMESPACE_IMPORT_GUARD = True
# -----------------------------------------------------------------------------


@dataclass
class NamespaceEntry(object):
    """Entry for a namespace in the unified registry."""

    subscribers: list["Subscriber"]
    """All subscribers registered to the namespace."""

    transformers: list["Transformer"]
    """All transformers registered to the namespace."""

    signature: Optional[set[str]]
    """The kwargs to validate incoming data against in this namespace."""


NAMESPACE_REGISTRY: dict[str, NamespaceEntry] = {}
"""
Global namespace registry.
Each namespace tracks its subscribers, transformers, and expected signature.
A namespace exists if it has at least one subscriber OR transformer.
"""


STAGED_REGISTRY: dict[str, list[dict]] = defaultdict(list)
"""
A separate namespace table to temporarily hold emitted values until the user
calls broker.emit_staged(). 
"""


def validate_namespace(namespace: str) -> None:
    """Reject the wildcard syntax removed by hierarchical namespaces."""
    if "*" in namespace:
        raise DeprecationWarning(
            "Wildcard namespace syntax was deprecated in v2.0.0. "
            "Register the parent namespace instead."
        )


def matches(namespace: str, registered_namespace: str) -> bool:
    """
    Check whether an emitted namespace is the same as or below a registered
    namespace in the hierarchy.

    Args:
        namespace (str): The namespace where the event was emitted.
        registered_namespace (str): The subscriber or transformer namespace.
    Returns:
        bool: True if subscribers should receive the event.
    """
    return namespace == registered_namespace or namespace.startswith(
        registered_namespace + "."
    )


def ensure_namespace_exists(namespace: str) -> bool:
    """
    Ensure a namespace entry exists in registry.
    Returns True if the namespace was added, False if it already existed.
    """
    if namespace not in NAMESPACE_REGISTRY:
        NAMESPACE_REGISTRY[namespace] = NamespaceEntry([], [], None)
        return True

    return False


def get_sorted_subscribers(namespace: str) -> list[tuple[str, "Subscriber"]]:
    """Get all live subscribers matching namespace, sorted by priority descending."""
    result: list[tuple[str, "Subscriber"]] = []

    for reg_namespace, entry in NAMESPACE_REGISTRY.items():
        if matches(namespace, reg_namespace):
            result.extend((reg_namespace, sub) for sub in entry.subscribers)

    result.sort(key=lambda x: x[1].priority, reverse=True)
    return result
