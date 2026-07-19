import importlib

import pytest


def test_reimport_guard() -> None:
    """
    Test that the guard rejects a second import once the module is loaded.
    """
    import broker

    registry = importlib.import_module("broker.private.namespace")

    with pytest.raises(ImportError):
        registry.check_reimport_guard()


def test_reimport_guard_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import broker

    registry = importlib.import_module("broker.private.namespace")
    monkeypatch.setenv("BROKER_REIMPORT_GUARD", "false")

    registry.check_reimport_guard()
