import sys

# -------Reimport Safeguard----------------------------------------------------
_existing = sys.modules.get("broker")
if _existing is not None and hasattr(_existing, "_BROKER_IMPORT_GUARD"):
    raise ImportError(
        "Module 'broker' has already been imported and cannot be reloaded. "
        "Subscriber data would be lost. "
        "Restart your Python session to reimport."
    )
# -----------------------------------------------------------------------------

from broker import _broker

_broker.__path__ = __path__
_broker.__package__ = __package__
_broker._BROKER_IMPORT_GUARD = True
sys.modules[__name__] = _broker

from broker.stub import *
