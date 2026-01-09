"""
Unit test to ensure argument validation works across different namespace levels.

When a callback subscribes to a different level of a namespace hierarchy
(e.g., 'system.*' wildcard vs 'system.io.file' specific), the emit arguments
should still be validated against all matching subscribers.
"""

from typing import Any

import pytest

import broker


def test_wildcard_and_specific_same_signature() -> None:
    """Test that wildcard and specific namespaces with same signature work together."""
    broker.clear()
    wildcard_called: list[str] = []
    specific_called: list[str] = []

    def wildcard_handler(filename: str, size: int) -> None:
        wildcard_called.append(filename)

    def specific_handler(filename: str, size: int) -> None:
        specific_called.append(filename)

    broker.register_subscriber("system.*", wildcard_handler)
    broker.register_subscriber("system.io.file", specific_handler)

    broker.emit("system.io.file", filename="test.txt", size=1024)

    assert len(wildcard_called) == 1
    assert len(specific_called) == 1


def test_wildcard_then_specific_different_signature_raises() -> None:
    """
    Test that different signatures between wildcard and specific raise
    validation error.
    """
    broker.clear()

    def wildcard_handler(filename: str, size: int) -> None:
        pass

    def specific_handler(filename: str, content: str) -> None:
        pass

    broker.register_subscriber("system.*", wildcard_handler)
    broker.register_subscriber("system.io.file", specific_handler)

    # Should raise because wildcard expects (filename, size) but we're
    # giving (filename, content)
    with pytest.raises(broker.EmitArgumentError) as exc_info:
        broker.emit("system.io.file", filename="test.txt", content="data")

    assert "system.*" in str(exc_info.value)
    assert "filename" in str(exc_info.value)


def test_specific_then_wildcard_different_signature_raises() -> None:
    """
    Test validation error when specific namespace exists before wildcard with
    different signature.
    """
    broker.clear()

    def specific_handler(filename: str, size: int) -> None:
        pass

    def wildcard_handler(filename: str, content: str) -> None:
        pass

    broker.register_subscriber("system.io.file", specific_handler)
    broker.register_subscriber("system.*", wildcard_handler)

    # Should raise because specific expects (filename, size)
    with pytest.raises(broker.EmitArgumentError) as exc_info:
        broker.emit("system.io.file", filename="test.txt", content="data")

    assert "system.io.file" in str(exc_info.value)


def test_multiple_wildcard_levels_same_signature() -> None:
    """Test multiple wildcard levels with same signature work together."""
    broker.clear()
    level1_called: list[bool] = []
    level2_called: list[bool] = []
    specific_called: list[bool] = []

    def handler(data: str) -> None:
        pass

    def level1_handler(data: str) -> None:
        level1_called.append(True)

    def level2_handler(data: str) -> None:
        level2_called.append(True)

    def specific_handler(data: str) -> None:
        specific_called.append(True)

    broker.register_subscriber("app.*", level1_handler)
    broker.register_subscriber("app.module.*", level2_handler)
    broker.register_subscriber("app.module.action", specific_handler)

    broker.emit("app.module.action", data="test")

    assert len(level1_called) == 1
    assert len(level2_called) == 1
    assert len(specific_called) == 1


def test_multiple_wildcard_levels_different_signatures_raises() -> None:
    """
    Test that different signatures at different wildcard levels raise
    validation error.
    """
    broker.clear()

    def level1_handler(data: str) -> None:
        pass

    def level2_handler(data: str, extra: int) -> None:
        pass

    broker.register_subscriber("app.*", level1_handler)
    broker.register_subscriber("app.module.*", level2_handler)

    with pytest.raises(broker.EmitArgumentError) as exc_info:
        broker.emit("app.module.action", data="test", extra=42)

    assert "app.*" in str(exc_info.value)


def test_kwargs_wildcard_accepts_any_specific_signature() -> None:
    """Test that wildcard with **kwargs accepts any specific namespace signature."""
    broker.clear()
    wildcard_called: list[dict] = []
    specific_called: list[str] = []

    def wildcard_handler(**kwargs: Any) -> None:
        wildcard_called.append(kwargs)

    def specific_handler(filename: str, size: int) -> None:
        specific_called.append(filename)

    broker.register_subscriber("system.*", wildcard_handler)
    broker.register_subscriber("system.io.file", specific_handler)

    broker.emit("system.io.file", filename="test.txt", size=1024)

    assert len(wildcard_called) == 1
    assert wildcard_called[0] == {"filename": "test.txt", "size": 1024}
    assert len(specific_called) == 1


def test_specific_kwargs_accepts_any_wildcard_signature() -> None:
    """Test that specific with **kwargs accepts any wildcard signature."""
    broker.clear()
    wildcard_called: list[str] = []
    specific_called: list[dict] = []

    def wildcard_handler(data: str) -> None:
        wildcard_called.append(data)

    def specific_handler(**kwargs: Any) -> None:
        specific_called.append(kwargs)

    broker.register_subscriber("system.*", wildcard_handler)
    broker.register_subscriber("system.io.file", specific_handler)

    broker.emit("system.io.file", data="test")

    assert len(wildcard_called) == 1
    assert len(specific_called) == 1


def test_missing_required_arg_for_wildcard_raises() -> None:
    """Test that missing a required argument for wildcard subscriber raises error."""
    broker.clear()

    def wildcard_handler(filename: str, size: int) -> None:
        pass

    def specific_handler(filename: str) -> None:
        pass

    broker.register_subscriber("system.*", wildcard_handler)
    broker.register_subscriber("system.io.file", specific_handler)

    # Missing 'size' that wildcard expects
    with pytest.raises(broker.EmitArgumentError) as exc_info:
        broker.emit("system.io.file", filename="test.txt")

    assert "system.*" in str(exc_info.value)
    assert "size" in str(exc_info.value)


def test_extra_arg_for_wildcard_raises() -> None:
    """Test that providing extra argument not expected by wildcard raises error."""
    broker.clear()

    def wildcard_handler(filename: str) -> None:
        pass

    def specific_handler(filename: str, extra: str) -> None:
        pass

    broker.register_subscriber("system.*", wildcard_handler)
    broker.register_subscriber("system.io.file", specific_handler)

    # 'extra' not expected by wildcard
    with pytest.raises(broker.EmitArgumentError) as exc_info:
        broker.emit("system.io.file", filename="test.txt", extra="data")

    assert "system.*" in str(exc_info.value)


def test_three_level_namespace_validation() -> None:
    """Test validation across three namespace levels (root.*, root.child.*, root.child.grandchild)."""
    broker.clear()

    def root_handler(data: str, level: int) -> None:
        pass

    def child_handler(data: str, level: int) -> None:
        pass

    def grandchild_handler(data: str, level: int) -> None:
        pass

    broker.register_subscriber("root.*", root_handler)
    broker.register_subscriber("root.child.*", child_handler)
    broker.register_subscriber("root.child.grandchild", grandchild_handler)

    # Should work fine - all have same signature
    broker.emit("root.child.grandchild", data="test", level=3)

    # Should fail - missing 'level'
    with pytest.raises(broker.EmitArgumentError):
        broker.emit("root.child.grandchild", data="test")


def test_wildcard_only_validates_when_matched() -> None:
    """Test that wildcard only validates when it actually matches the emitted namespace."""
    broker.clear()

    def system_handler(filename: str, size: int) -> None:
        pass

    def app_handler(data: str) -> None:
        pass

    broker.register_subscriber("system.*", system_handler)
    broker.register_subscriber("app.action", app_handler)

    # Should NOT raise - system.* doesn't match app.action
    broker.emit("app.action", data="test")

    # Should raise - system.* matches and expects different args
    with pytest.raises(broker.EmitArgumentError):
        broker.emit("system.io.file", data="test")


def test_exact_namespace_not_affected_by_unrelated_wildcard() -> None:
    """Test that exact namespace validation is not affected by unrelated wildcards."""
    broker.clear()

    def exact_handler(value: int) -> None:
        pass

    def unrelated_wildcard(data: str) -> None:
        pass

    broker.register_subscriber("config.setting", exact_handler)
    broker.register_subscriber("system.*", unrelated_wildcard)

    # Should work - system.* doesn't match config.setting
    broker.emit("config.setting", value=42)


def test_parent_wildcard_validates_child_emit() -> None:
    """Test that parent wildcard validates arguments when child namespace is emitted."""
    broker.clear()

    def parent_handler(x: int, y: int) -> None:
        pass

    broker.register_subscriber("math.*", parent_handler)

    # Should work
    broker.emit("math.add", x=1, y=2)

    # Should fail - wrong args
    with pytest.raises(broker.EmitArgumentError):
        broker.emit("math.multiply", a=3, b=4)


def test_child_subscription_validates_against_existing_parent() -> None:
    """Test that subscribing to child validates against existing parent wildcard."""
    broker.clear()

    def parent_handler(data: str) -> None:
        pass

    broker.register_subscriber("events.*", parent_handler)

    # This should work - same signature as parent
    def child_handler(data: str) -> None:
        pass

    broker.register_subscriber("events.click", child_handler)
    broker.emit("events.click", data="test")

    # This should fail at emit time due to parent wildcard
    def bad_child_handler(value: int) -> None:
        pass

    broker.register_subscriber("events.hover", bad_child_handler)

    with pytest.raises(broker.EmitArgumentError):
        broker.emit("events.hover", value=10)
