import pytest


def test_reimport_guard() -> None:
    """
    Test that reimporting the broker module results in an ImportError,
    preventing developers form reimporting the module.
    """
    import importlib
    import broker._private.registry

    with pytest.raises(ImportError):
        importlib.reload(broker._private.registry)
