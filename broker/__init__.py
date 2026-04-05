# Primary user interface for the broker package.
#
# The broker's implementation lives in broker/_private/ and is not intended
# to be imported directly. This file is the sole public interface — all
# functionality is accessible through the broker module namespace:
#
#     import broker
#
#     broker.emit('file.saved', filename='test.exr')
#     broker.register_subscriber('file.saved', my_handler)
#
# All public functions, types, and constants are documented in __init__.pyi
# for static analysis tools and IDE intellisense.

# noinspection PyProtectedMember
from broker._private.broker import Broker as _Broker

_instance = _Broker()
paused = _instance.paused


def __getattr__(name: str) -> object:
    return getattr(_instance, name)
