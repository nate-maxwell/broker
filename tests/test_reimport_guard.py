import pytest


def test_reimport_guard() -> None:
    """
    Test that reimporting the broker module results in an ImportError,
    preventing developers form reimporting the module.
    """
    import importlib
    import broker._registry

    with pytest.raises(ImportError):
        importlib.reload(broker._registry)
