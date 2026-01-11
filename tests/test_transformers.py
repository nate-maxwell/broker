"""Unit tests for broker middleware/transformer system."""

# -----------------------------------------------------------------------------
# Many of the tests are attempting to verify data within the broker, but the
# broker uses a protective closure to make the subscriber table difficult to
# access.

# The work-around is to create functions that append results to a local table,
# list, or other collection and validate that the collection contains the
# expected items.
# -----------------------------------------------------------------------------


import pytest

import broker


def test_transformer_modifies_kwargs() -> None:
    """Test that transformers can modify event kwargs."""
    broker.clear()
    broker.clear_transformers()

    received_kwargs = []

    def add_field(namespace: str, kwargs: dict) -> dict:
        kwargs["added_field"] = "added_value"
        return kwargs

    def handler(**kwargs) -> None:
        received_kwargs.append(kwargs)

    broker.register_transformer("test.event", add_field)
    broker.register_subscriber("test.event", handler)

    broker.emit("test.event", original="data")

    assert len(received_kwargs) == 1
    assert received_kwargs[0]["original"] == "data"
    assert received_kwargs[0]["added_field"] == "added_value"


def test_transformer_can_block_event() -> None:
    """Test that returning None blocks event propagation."""
    broker.clear()
    broker.clear_transformers()

    calls = []

    def block_event(namespace: str, kwargs: dict) -> None:
        return None  # Block

    def handler(data: str) -> None:
        calls.append(data)

    broker.register_transformer("test.event", block_event)
    broker.register_subscriber("test.event", handler)

    broker.emit("test.event", data="blocked")

    # Handler should not be called
    assert len(calls) == 0


def test_transformer_priority_order() -> None:
    """Test that transformers execute in priority order."""
    broker.clear()
    broker.clear_transformers()

    execution_order = []

    def transformer_low(namespace: str, kwargs: dict) -> dict:
        execution_order.append("low")
        return kwargs

    def transformer_high(namespace: str, kwargs: dict) -> dict:
        execution_order.append("high")
        return kwargs

    def transformer_medium(namespace: str, kwargs: dict) -> dict:
        execution_order.append("medium")
        return kwargs

    def handler(data: str) -> None:
        pass

    broker.register_transformer("test.event", transformer_low, priority=1)
    broker.register_transformer("test.event", transformer_high, priority=10)
    broker.register_transformer("test.event", transformer_medium, priority=5)
    broker.register_subscriber("test.event", handler)

    broker.emit("test.event", data="test")

    assert execution_order == ["high", "medium", "low"]


def test_transformer_with_wildcard() -> None:
    """Test that transformers work with wildcard namespaces."""
    broker.clear()
    broker.clear_transformers()

    received = []

    def add_timestamp(namespace: str, kwargs: dict) -> dict:
        kwargs["timestamp"] = "now"
        return kwargs

    def handler(**kwargs) -> None:
        received.append(kwargs)

    broker.register_transformer("system.*", add_timestamp)
    broker.register_subscriber("system.io.file", handler)

    broker.emit("system.io.file", data="test")

    assert len(received) == 1
    assert received[0]["timestamp"] == "now"


def test_multiple_transformers_chain() -> None:
    """Test that multiple transformers chain together."""
    broker.clear()
    broker.clear_transformers()

    received = []

    def add_field1(namespace: str, kwargs: dict) -> dict:
        kwargs["field1"] = "value1"
        return kwargs

    def add_field2(namespace: str, kwargs: dict) -> dict:
        kwargs["field2"] = "value2"
        return kwargs

    def handler(**kwargs) -> None:
        received.append(kwargs)

    broker.register_transformer("test.event", add_field1, priority=10)
    broker.register_transformer("test.event", add_field2, priority=5)
    broker.register_subscriber("test.event", handler)

    broker.emit("test.event", original="data")

    assert len(received) == 1
    assert received[0]["original"] == "data"
    assert received[0]["field1"] == "value1"
    assert received[0]["field2"] == "value2"


def test_unregister_transformer() -> None:
    """Test removing a transformer."""
    broker.clear()
    broker.clear_transformers()

    received = []

    def transformer(namespace: str, kwargs: dict) -> dict:
        kwargs["transformed"] = True
        return kwargs

    def handler(**kwargs) -> None:
        received.append(kwargs)

    broker.register_transformer("test.event", transformer)
    broker.register_subscriber("test.event", handler)

    broker.emit("test.event", data="test")
    assert received[0].get("transformed") is True

    # Unregister transformer
    broker.unregister_transformer("test.event", transformer)
    received.clear()

    broker.emit("test.event", data="test")
    assert "transformed" not in received[0]


def test_transformer_doesnt_modify_original_kwargs() -> None:
    """Test that transformers work on a copy, not the original."""
    broker.clear()
    broker.clear_transformers()

    def transformer(namespace: str, kwargs: dict) -> dict:
        kwargs["added"] = "value"
        return kwargs

    def handler(**kwargs) -> None:
        pass

    broker.register_transformer("test.event", transformer)
    broker.register_subscriber("test.event", handler)

    original_kwargs = {"original": "data"}
    broker.emit("test.event", **original_kwargs)

    # Original dict should not be modified
    assert "added" not in original_kwargs


@pytest.mark.asyncio
async def test_transformer_with_async_emit() -> None:
    """Test that transformers work with emit_async."""
    broker.clear()
    broker.clear_transformers()

    received = []

    def transformer(namespace: str, kwargs: dict) -> dict:
        kwargs["transformed"] = True
        return kwargs

    async def async_handler(**kwargs) -> None:
        received.append(kwargs)

    broker.register_transformer("test.event", transformer)
    broker.register_subscriber("test.event", async_handler)

    await broker.emit_async("test.event", data="test")

    assert len(received) == 1
    assert received[0]["transformed"] is True


def test_transformer_error_raises() -> None:
    """Test that transformer errors are raised."""
    broker.clear()
    broker.clear_transformers()

    def failing_transformer(namespace: str, kwargs: dict) -> dict:
        raise ValueError("Transformer failed")

    def handler(data: str) -> None:
        pass

    broker.register_transformer("test.event", failing_transformer)
    broker.register_subscriber("test.event", handler)

    with pytest.raises(RuntimeError, match="Transformer .* failed"):
        broker.emit("test.event", data="test")


def test_get_transformers() -> None:
    """Test getting transformers for a namespace."""
    broker.clear()
    broker.clear_transformers()

    def transformer1(namespace: str, kwargs: dict) -> dict:
        return kwargs

    def transformer2(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer1)
    broker.register_transformer("test.event", transformer2)

    transformers = broker.get_transformers("test.event")

    assert len(transformers) == 2
    assert any(t.callback == transformer1 for t in transformers)
    assert any(t.callback == transformer2 for t in transformers)


def test_get_all_transformer_namespaces() -> None:
    """Test getting all transformer namespaces."""
    broker.clear()
    broker.clear_transformers()

    def transformer(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.one", transformer)
    broker.register_transformer("test.two", transformer)
    broker.register_transformer("system.*", transformer)

    namespaces = broker.get_all_transformer_namespaces()

    assert namespaces == ["system.*", "test.one", "test.two"]


def test_transformer_receives_namespace() -> None:
    """Test that transformer receives the actual event namespace."""
    broker.clear()
    broker.clear_transformers()

    received_namespace = []

    def transformer(namespace: str, kwargs: dict) -> dict:
        received_namespace.append(namespace)
        return kwargs

    def handler(data: str) -> None:
        pass

    broker.register_transformer("system.*", transformer)
    broker.register_subscriber("system.io.file", handler)

    broker.emit("system.io.file", data="test")

    assert received_namespace[0] == "system.io.file"
