from typing import Optional
from typing import TypedDict

from broker import subscriber
from broker import transformer


class NamespaceEntry(TypedDict):
    """Entry for a namespace in the unified registry."""

    subscribers: list[subscriber.Subscriber]
    transformers: list[transformer.Transformer]
    signature: Optional[set[str]]
