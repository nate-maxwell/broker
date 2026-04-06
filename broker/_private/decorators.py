from typing import Callable
from typing import TYPE_CHECKING

from broker.subscriber import SUBSCRIBER
from broker.transformer import TRANSFORMER

if TYPE_CHECKING:
    from broker._private.broker import Broker


def make_subscribe_decorator(broker: "Broker") -> Callable:
    """
    Create a subscribe decorator with access to the broker module.

    This exists as a function accepting the broker module as an argument so the
    function can call register_subscriber() on the broker without referring to
    it using a python namespace and thus creating a circular reference.
    """

    def subscribe_(
        namespace: str, priority: int = 0, once: bool = False
    ) -> Callable[[SUBSCRIBER], SUBSCRIBER]:

        def decorator(func: SUBSCRIBER) -> SUBSCRIBER:
            broker.register_subscriber(namespace, func, priority, once)
            return func

        return decorator

    return subscribe_


def make_transformer_decorator(broker: "Broker") -> Callable:
    """
    Create a transform decorator with access to the broker module.

    This exists as a function accepting the broker module as an argument so the
    function can call register_subscriber() on the broker without referring to
    it using a python namespace and thus creating a circular reference.
    """

    def transform_(
        namespace: str, priority: int = 0
    ) -> Callable[[TRANSFORMER], TRANSFORMER]:

        def decorator(func: TRANSFORMER) -> TRANSFORMER:
            broker.register_transformer(namespace, func, priority)
            return func

        return decorator

    return transform_
