"""
Unit tests for broker inspection API.

Tests verify that introspection methods provide accurate information about
namespaces, subscribers, and broker state.
"""

import gc
import json
from typing import Callable

import broker


def test_get_namespaces() -> None:
    """Test getting all registered namespaces."""
    broker.clear()

    def handler1(data: str) -> None:
        pass

    def handler2(value: int) -> None:
        pass

    broker.register_subscriber("system.io.file", handler1)
    broker.register_subscriber("app.startup", handler2)
    broker.register_subscriber("test.event", handler1)

    namespaces = broker.get_namespaces()

    assert namespaces == ["app.startup", "system.io.file", "test.event"]


def test_namespace_exists() -> None:
    """Test checking if namespace exists."""
    broker.clear()

    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler)

    assert broker.namespace_exists("test.event") is True
    assert broker.namespace_exists("nonexistent") is False


def test_get_subscriber_count() -> None:
    """Test counting subscribers for a namespace."""
    broker.clear()

    def handler1(data: str) -> None:
        pass

    def handler2(data: str) -> None:
        pass

    def handler3(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler1)
    broker.register_subscriber("test.event", handler2)
    broker.register_subscriber("test.event", handler3)

    assert broker.get_subscriber_count("test.event") == 3
    assert broker.get_subscriber_count("nonexistent") == 0


def test_get_live_subscriber_count() -> None:
    """Test counting only live subscribers."""
    broker.clear()

    handler1 = lambda data: None

    def handler2(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler1)
    broker.register_subscriber("test.event", handler2)

    assert broker.get_live_subscriber_count("test.event") == 2

    del handler1
    gc.collect()

    assert broker.get_live_subscriber_count("test.event") == 1


def test_is_subscribed() -> None:
    """Test checking if specific callback is subscribed."""
    broker.clear()

    def handler1(data: str) -> None:
        pass

    def handler2(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler1)

    assert broker.is_subscribed(handler1, "test.event") is True
    assert broker.is_subscribed(handler2, "test.event") is False
    assert broker.is_subscribed(handler1, "other.event") is False


def test_get_subscriptions() -> None:
    """Test getting all subscriptions for a callback."""
    broker.clear()

    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.one", handler)
    broker.register_subscriber("test.two", handler)
    broker.register_subscriber("test.three", handler)

    subscriptions = broker.get_subscriptions(handler)

    assert subscriptions == ["test.one", "test.three", "test.two"]


def test_get_subscribers() -> None:
    """Test getting all subscribers for a namespace."""
    broker.clear()

    def handler1(data: str) -> None:
        pass

    def handler2(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler1, priority=10)
    broker.register_subscriber("test.event", handler2, priority=5)

    subscribers = broker.get_subscribers("test.event")

    assert len(subscribers) == 2
    assert subscribers[0].priority == 10
    assert subscribers[1].priority == 5


def test_get_live_subscribers() -> None:
    """Test getting only live subscribers."""
    broker.clear()

    handler1 = lambda data: None

    def handler2(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler1)
    broker.register_subscriber("test.event", handler2)

    live_subs = broker.get_live_subscribers("test.event")
    assert len(live_subs) == 2

    del handler1
    gc.collect()

    live_subs = broker.get_live_subscribers("test.event")
    assert len(live_subs) == 1
    assert live_subs[0].callback == handler2


def test_get_matching_namespaces() -> None:
    """Test getting namespaces that match a pattern."""
    broker.clear()

    def handler(data: str) -> None:
        pass

    broker.register_subscriber("system.io.file", handler)
    broker.register_subscriber("system.io.network", handler)
    broker.register_subscriber("system.ui.render", handler)
    broker.register_subscriber("app.startup", handler)

    matches = broker.get_matching_namespaces("system.io.*")
    assert matches == ["system.io.file", "system.io.network"]

    matches = broker.get_matching_namespaces("app.startup")
    assert matches == ["app.startup"]

    matches = broker.get_matching_namespaces("system.*")
    assert "system.io.file" in matches
    assert "system.ui.render" in matches


def test_get_namespace_info() -> None:
    """Test getting detailed namespace information."""
    broker.clear()

    def sync_handler(data: str) -> None:
        pass

    async def async_handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", sync_handler, priority=10)
    broker.register_subscriber("test.event", async_handler, priority=5)

    info = broker.get_namespace_info("test.event")

    assert info["namespace"] == "test.event"
    assert info["subscriber_count"] == 2
    assert info["live_subscriber_count"] == 2
    assert info["expected_params"] == {"data"}
    assert info["has_async"] is True
    assert info["has_sync"] is True
    assert info["priorities"] == [10, 5]


def test_get_namespace_info_nonexistent() -> None:
    """Test getting info for nonexistent namespace returns None."""
    broker.clear()

    info = broker.get_namespace_info("nonexistent")
    assert info is None


def test_get_all_namespace_info() -> None:
    """Test getting info for all namespaces."""
    broker.clear()

    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.one", handler)
    broker.register_subscriber("test.two", handler)

    all_info = broker.get_all_namespace_info()

    assert len(all_info) == 2
    assert "test.one" in all_info
    assert "test.two" in all_info
    assert all_info["test.one"]["subscriber_count"] == 1


def test_get_statistics() -> None:
    """Test getting overall broker statistics."""
    broker.clear()

    def sync_handler(data: str) -> None:
        pass

    async def async_handler(data: str) -> None:
        pass

    broker.register_subscriber("test.one", sync_handler)
    broker.register_subscriber("test.one", async_handler)
    broker.register_subscriber("test.two", sync_handler)

    stats = broker.get_statistics()

    assert stats["total_namespaces"] == 2
    assert stats["total_subscribers"] == 3
    assert stats["total_live_subscribers"] == 3
    assert stats["dead_subscriber_references"] == 0
    assert stats["namespaces_with_async"] == 1
    assert stats["namespaces_with_sync"] == 2
    assert stats["average_subscribers_per_namespace"] == 1.5


def test_inspection_with_wildcard_subscribers() -> None:
    """Test inspection works correctly with wildcard subscriptions."""
    broker.clear()

    def wildcard_handler(data: str) -> None:
        pass

    def specific_handler(data: str) -> None:
        pass

    broker.register_subscriber("system.*", wildcard_handler)
    broker.register_subscriber("system.io.file", specific_handler)

    namespaces = broker.get_namespaces()
    assert "system.*" in namespaces
    assert "system.io.file" in namespaces

    assert broker.is_subscribed(wildcard_handler, "system.*")
    assert broker.is_subscribed(specific_handler, "system.io.file")


def test_inspection_after_unsubscribe() -> None:
    """Test inspection reflects unsubscribe operations."""
    broker.clear()

    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler)
    assert broker.namespace_exists("test.event")

    broker.unregister_subscriber("test.event", handler)
    assert broker.namespace_exists("test.event") is False
    assert broker.get_namespaces() == []


def _fill_broker() -> tuple[Callable, Callable, Callable]:
    def process_1() -> None:
        return

    process_2 = lambda value: None
    process_3 = lambda value: None

    broker.register_subscriber("system.io", process_1)
    broker.register_subscriber("system.io.export", process_2)
    broker.register_subscriber("application", process_2)
    broker.register_subscriber("application.start", process_3)

    return process_1, process_2, process_3


def test_to_string_output_structure() -> None:
    """Test that to_string produces correct structure and content."""
    broker.clear()
    refs = _fill_broker()
    json_str = broker.to_string()
    parsed = json.loads(json_str)

    assert "application" in parsed
    assert "application.start" in parsed
    assert "system.io" in parsed
    assert "system.io.export" in parsed

    assert any("process_1" in s for s in parsed["system.io"]["subscribers"])
    assert any("<lambda>" in s for s in parsed["application"]["subscribers"])
    assert any("<lambda>" in s for s in parsed["application.start"]["subscribers"])
    assert any("<lambda>" in s for s in parsed["system.io.export"]["subscribers"])


def test_to_dict_structure() -> None:
    """Test that to_dict returns correct structure."""
    broker.clear()
    refs = _fill_broker()  # store lambdas to var to keep from getting collected
    result = broker.to_dict()

    assert "application" in result
    assert "application.start" in result
    assert "system.io" in result
    assert "system.io.export" in result

    assert "subscribers" in result["application"]
    assert "subscribers" in result["application.start"]
    assert "subscribers" in result["system.io"]
    assert "subscribers" in result["system.io.export"]

    assert len(result["application"]["subscribers"]) == 1
    assert len(result["application.start"]["subscribers"]) == 1
    assert len(result["system.io"]["subscribers"]) == 1
    assert len(result["system.io.export"]["subscribers"]) == 1

    assert any("process_1" in sub for sub in result["system.io"]["subscribers"])
    assert any("<lambda>" in sub for sub in result["application"]["subscribers"])


def test_to_string_is_valid_json() -> None:
    """Test that to_string produces valid JSON."""
    broker.clear()
    refs = _fill_broker()  # store lambdas to var to keep from getting collected

    json_str = broker.to_string()
    parsed = json.loads(json_str)

    assert parsed == broker.to_dict()
