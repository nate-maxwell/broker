"""
Namespace registry data structures for the event broker.

Defines the NamespaceEntry dataclass that represents a unified namespace in the
broker's internal registry. Each namespace entry tracks both subscribers and
transformers registered to that namespace, along with the expected parameter
signature for validation.

A namespace exists in the registry when it has at least one subscriber OR
transformer registered, except very briefly when registering a transformer or
subscriber to a newly created namespace.
"""

from typing import Optional
from dataclasses import dataclass

from broker import subscriber
from broker import transformer


@dataclass
class NamespaceEntry(object):
    """Entry for a namespace in the unified registry."""

    subscribers: list[subscriber.Subscriber]
    """All subscribers registered to the namespace."""

    transformers: list[transformer.Transformer]
    """All transformers registered to the namespace."""

    signature: Optional[set[str]]
    """The kwargs to validate incoming data against in this namespace."""
