_paused: int

from broker._broker import Broker as _Broker

_instance = _Broker()
paused = _instance.paused


def __getattr__(name: str) -> object:
    return getattr(_instance, name)
