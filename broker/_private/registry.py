"""
Herein is the namespace table and staged emission buffer.

A reimport protection clause exists at the top of the file to prevent the
subscribers table from being lost on import.
"""

import sys

from broker import namespaces
from typing import DefaultDict

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
