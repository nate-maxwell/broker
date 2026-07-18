"""Tests for hierarchical namespace contracts and event arguments."""

from typing import Any
from typing import Callable

import pytest

import broker


@pytest.fixture(autouse=True)
def clear_broker() -> None:
    broker.clear()


def test_child_expands_parent_contract_and_projects_parent_payload() -> None:
    parent_calls: list[tuple[str]] = []
    child_calls: list[tuple[str, int]] = []

    def parent(filename: str) -> None:
        parent_calls.append((filename,))

    def child(filename: str, size: int) -> None:
        child_calls.append((filename, size))

    broker.register_subscriber("system", parent)
    broker.register_subscriber("system.io.file", child)
    broker.emit("system.io.file", filename="test.txt", size=1024)

    assert parent_calls == [("test.txt",)]
    assert child_calls == [("test.txt", 1024)]


def test_child_contract_must_include_parent_contract() -> None:
    def parent(filename: str, size: int) -> None:
        pass

    def child(filename: str) -> None:
        pass

    broker.register_subscriber("system", parent)

    with pytest.raises(broker.SignatureMismatchError, match="child namespace"):
        broker.register_subscriber("system.io", child)

    assert not broker.namespace_exists("system.io")


def test_parent_can_be_registered_after_compatible_child() -> None:
    calls: list[str] = []

    def child(data: str, extra: int) -> None:
        pass

    def parent(data: str) -> None:
        calls.append(data)

    broker.register_subscriber("app.module.action", child)
    broker.register_subscriber("app", parent)
    broker.emit("app.module.action", data="test", extra=42)

    assert calls == ["test"]


def test_parent_registered_after_child_must_be_child_subset() -> None:
    def child(data: str) -> None:
        pass

    def parent(data: str, extra: int) -> None:
        pass

    broker.register_subscriber("app.module.action", child)

    with pytest.raises(broker.SignatureMismatchError, match="parent namespace"):
        broker.register_subscriber("app", parent)

    assert not broker.namespace_exists("app")


def test_parent_registered_after_flexible_child_expands_child_contract() -> None:
    def child(extra: int, **kwargs: Any) -> None:
        pass

    def parent(data: str) -> None:
        pass

    def fixed_child(data: str, extra: int) -> None:
        pass

    broker.register_subscriber("app.child", child)
    broker.register_subscriber("app", parent)
    broker.register_subscriber("app.child", fixed_child)

    assert broker.get_namespace_info("app.child")["expected_params"] == {
        "data",
        "extra",
    }


def test_three_level_contracts_can_expand_at_each_level() -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []

    def root(data: str) -> None:
        calls.append(("root", (data,)))

    def child(data: str, module: str) -> None:
        calls.append(("child", (data, module)))

    def grandchild(data: str, module: str, action: int) -> None:
        calls.append(("grandchild", (data, module, action)))

    broker.register_subscriber("root", root)
    broker.register_subscriber("root.child", child)
    broker.register_subscriber("root.child.grandchild", grandchild)
    broker.emit("root.child.grandchild", data="test", module="core", action=3)

    assert calls == [
        ("root", ("test",)),
        ("child", ("test", "core")),
        ("grandchild", ("test", "core", 3)),
    ]


def test_subscribers_at_same_namespace_keep_one_contract() -> None:
    def first(filename: str, size: int) -> None:
        pass

    def second(filename: str, mode: str) -> None:
        pass

    broker.register_subscriber("file.save", first)

    with pytest.raises(broker.SignatureMismatchError, match="parameter mismatch"):
        broker.register_subscriber("file.save", second)


def test_emit_requires_every_ancestor_contract_key() -> None:
    def root(data: str) -> None:
        pass

    def child(data: str, extra: int) -> None:
        pass

    broker.register_subscriber("app", root)
    broker.register_subscriber("app.module", child)

    with pytest.raises(broker.EmitArgumentError, match="extra"):
        broker.emit("app.module", data="test")


def test_extra_payload_keys_are_allowed_and_filtered() -> None:
    received: list[str] = []

    def handler(data: str) -> None:
        received.append(data)

    broker.register_subscriber("events", handler)
    broker.emit("events.click", data="test", child_only=42)

    assert received == ["test"]


def test_kwargs_only_subscriber_does_not_prevent_concrete_contract() -> None:
    flexible_calls: list[dict[str, Any]] = []
    specific_calls: list[str] = []

    def flexible(**kwargs: Any) -> None:
        flexible_calls.append(kwargs)

    def specific(data: str) -> None:
        specific_calls.append(data)

    broker.register_subscriber("events", flexible)
    broker.register_subscriber("events", specific)
    broker.emit("events", data="test", transformed=True)

    assert broker.get_namespace_info("events")["expected_params"] == {"data"}
    assert flexible_calls == [{"data": "test", "transformed": True}]
    assert specific_calls == ["test"]


def test_named_kwargs_subscriber_can_accept_established_contract() -> None:
    received: list[tuple[str, dict[str, Any]]] = []

    def fixed(data: str, level: int) -> None:
        pass

    def flexible(data: str, **kwargs: Any) -> None:
        received.append((data, kwargs))

    broker.register_subscriber("events", fixed)
    broker.register_subscriber("events", flexible)
    broker.emit("events.child", data="test", level=2, child_only=True)

    assert received == [("test", {"level": 2, "child_only": True})]


def test_named_kwargs_child_inherits_parent_contract() -> None:
    def parent(data: str) -> None:
        pass

    def flexible_child(extra: int, **kwargs: Any) -> None:
        pass

    def fixed_child(data: str, extra: int) -> None:
        pass

    broker.register_subscriber("events", parent)
    broker.register_subscriber("events.child", flexible_child)
    broker.register_subscriber("events.child", fixed_child)

    assert broker.get_namespace_info("events.child")["expected_params"] == {
        "data",
        "extra",
    }


def test_named_kwargs_subscriber_cannot_require_unknown_contract_key() -> None:
    def fixed(data: str) -> None:
        pass

    def flexible(other: str, **kwargs: Any) -> None:
        pass

    broker.register_subscriber("events", fixed)

    with pytest.raises(broker.SignatureMismatchError, match="parameter mismatch"):
        broker.register_subscriber("events", flexible)


def test_parent_transformer_can_supply_required_child_key() -> None:
    received: list[tuple[str, int]] = []

    def parent(data: str) -> None:
        pass

    def child(data: str, sequence: int) -> None:
        received.append((data, sequence))

    def add_sequence(namespace: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        assert namespace == "events.child"
        return {**kwargs, "sequence": 1}

    broker.register_subscriber("events", parent)
    broker.register_subscriber("events.child", child)
    broker.register_transformer("events", add_sequence)
    broker.emit("events.child", data="test")

    assert received == [("test", 1)]


def test_validation_uses_payload_after_transformer_removes_key() -> None:
    def handler(data: str) -> None:
        pass

    def remove_data(namespace: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        kwargs.pop("data")
        return kwargs

    broker.register_subscriber("events", handler)
    broker.register_transformer("events", remove_data)

    with pytest.raises(broker.EmitArgumentError, match="data"):
        broker.emit("events.child", data="test")


def test_defaulted_callback_parameter_is_still_required() -> None:
    def handler(data: str = "default") -> None:
        pass

    broker.register_subscriber("events", handler)

    with pytest.raises(broker.EmitArgumentError, match="data"):
        broker.emit("events")


def test_hierarchy_uses_dot_boundaries() -> None:
    received: list[str] = []

    def handler(data: str) -> None:
        received.append(data)

    broker.register_subscriber("app", handler)
    broker.emit("application.start", data="not-related")

    assert received == []


def test_parent_event_does_not_flow_down_to_child() -> None:
    calls: list[str] = []

    def parent(data: str) -> None:
        calls.append("parent")

    def child(data: str, extra: int) -> None:
        calls.append("child")

    broker.register_subscriber("app", parent)
    broker.register_subscriber("app.child", child)
    broker.emit("app", data="test")

    assert calls == ["parent"]


def test_unrelated_namespace_contract_does_not_validate_emit() -> None:
    def system(filename: str) -> None:
        pass

    def app(data: str) -> None:
        pass

    broker.register_subscriber("system", system)
    broker.register_subscriber("app", app)
    broker.emit("app.action", data="test")


def test_wildcard_namespace_syntax_is_rejected() -> None:
    def subscriber(data: str) -> None:
        pass

    def transformer(namespace: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        return kwargs

    operations: list[Callable[[], object]] = [
        lambda: broker.register_subscriber("events.*", subscriber),
        lambda: broker.register_transformer("events.*", transformer),
        lambda: broker.emit("events.*", data="test"),
        lambda: broker.stage("events.*", data="test"),
        lambda: broker.get_matching_namespaces("events.*"),
    ]

    for operation in operations:
        with pytest.raises(
            DeprecationWarning,
            match="Wildcard namespace syntax was deprecated in v2.0.0. Register the parent namespace instead",
        ):
            operation()
