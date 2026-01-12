from typing import Optional
from typing import TypedDict

from broker import subscriber
from broker import transformer


class NamespaceEntry(TypedDict):
    """Entry for a namespace in the unified registry."""

    subscribers: list[subscriber.Subscriber]
    """All subscribers registered to the namespace."""

    transformers: list[transformer.Transformer]
    """All transformers registered to the namespace."""

    signature: Optional[set[str]]
    """The kwargs to validate incoming data against in this namespace."""
