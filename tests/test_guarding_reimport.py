import pytest


def test_reimport_guard() -> None:
    """
    Test that reimporting the broker module results in an ImportError,
    preventing developers form reimporting the module.
    """
    import importlib
    import broker

    with pytest.raises(
        # Explicit exception type is not exported so it is not added as the
        # expected_exception arg.
        match="Module 'broker' has already been imported and cannot be reloaded",
    ):
        importlib.reload(broker)
