"""
Unit tests for broker inspection API.

Tests verify that introspection methods provide accurate information about
namespaces, subscribers, transformers, and broker state.
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


def test_get_transformer_count() -> None:
    """Test counting transformers for a namespace."""
    broker.clear()

    def transformer1(namespace: str, kwargs: dict) -> dict:
        return kwargs

    def transformer2(namespace: str, kwargs: dict) -> dict:
        return kwargs

    def transformer3(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer1)
    broker.register_transformer("test.event", transformer2)
    broker.register_transformer("test.event", transformer3)

    assert broker.get_transformer_count("test.event") == 3
    assert broker.get_transformer_count("nonexistent") == 0


def test_get_transformers() -> None:
    """Test getting all transformers for a namespace."""
    broker.clear()

    def transformer1(namespace: str, kwargs: dict) -> dict:
        return kwargs

    def transformer2(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer1, priority=10)
    broker.register_transformer("test.event", transformer2, priority=5)

    transformers = broker.get_transformers("test.event")

    assert len(transformers) == 2
    assert transformers[0].priority == 10
    assert transformers[1].priority == 5


def test_get_live_transformers() -> None:
    """Test getting only live transformers."""
    broker.clear()

    transformer1 = lambda namespace, kwargs: kwargs

    def transformer2(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer1)
    broker.register_transformer("test.event", transformer2)

    live_transformers = broker.get_live_transformers("test.event")
    assert len(live_transformers) == 2

    del transformer1
    gc.collect()

    live_transformers = broker.get_live_transformers("test.event")
    assert len(live_transformers) == 1
    assert live_transformers[0].callback == transformer2


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


def test_get_namespace_info_with_transformers() -> None:
    """Test that namespace info includes transformer data."""
    broker.clear()

    def handler(data: str) -> None:
        pass

    def transformer1(namespace: str, kwargs: dict) -> dict:
        return kwargs

    def transformer2(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_subscriber("test.event", handler)
    broker.register_transformer("test.event", transformer1, priority=10)
    broker.register_transformer("test.event", transformer2, priority=5)

    info = broker.get_namespace_info("test.event")

    assert info["transformer_count"] == 2
    assert info["live_transformer_count"] == 2
    assert info["transformer_priorities"] == [10, 5]


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


def test_get_statistics_with_transformers() -> None:
    """Test that statistics include transformer data."""
    broker.clear()

    def handler(data: str) -> None:
        pass

    def transformer1(namespace: str, kwargs: dict) -> dict:
        return kwargs

    def transformer2(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_subscriber("test.one", handler)
    broker.register_subscriber("test.two", handler)
    broker.register_transformer("test.one", transformer1)
    broker.register_transformer("test.two", transformer2)

    stats = broker.get_statistics()

    assert stats["total_transformers"] == 2
    assert stats["total_live_transformers"] == 2
    assert stats["dead_transformer_references"] == 0
    assert stats["namespaces_with_transformers"] == 2
    assert stats["average_transformers_per_namespace"] == 1.0


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


def test_inspection_with_wildcard_transformers() -> None:
    """Test inspection works correctly with wildcard transformer registrations."""
    broker.clear()

    def wildcard_transformer(namespace: str, kwargs: dict) -> dict:
        return kwargs

    def specific_transformer(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("system.*", wildcard_transformer)
    broker.register_transformer("system.io.file", specific_transformer)

    namespaces = broker.get_namespaces()
    assert "system.*" in namespaces
    assert "system.io.file" in namespaces

    assert broker.is_transformed(wildcard_transformer, "system.*")
    assert broker.is_transformed(specific_transformer, "system.io.file")


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


def test_inspection_after_untransform() -> None:
    """Test inspection reflects unregister transformer operations."""
    broker.clear()

    def transformer(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer)
    assert broker.namespace_exists("test.event")

    broker.unregister_transformer("test.event", transformer)
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


def _fill_broker_with_transformers() -> tuple[Callable, Callable]:
    def transform_1(namespace: str, kwargs: dict) -> dict:
        return kwargs

    transform_2 = lambda namespace, kwargs: kwargs

    broker.register_transformer("system.io", transform_1, priority=10)
    broker.register_transformer("application", transform_2, priority=5)

    return transform_1, transform_2


def test_to_string_output_structure() -> None:
    """Test that to_string produces correct structure and content."""
    broker.clear()
    refs = _fill_broker()  # store lambdas to var so they don't get collected
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
    refs = _fill_broker()  # store lambdas to var so they don't get collected
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


def test_to_dict_with_transformers() -> None:
    """Test that to_dict includes transformer information."""
    broker.clear()
    sub_refs = _fill_broker()  # store lambdas to var so they don't get collected
    trans_refs = _fill_broker_with_transformers()
    result = broker.to_dict()

    # Check transformers are included
    assert "transformers" in result["system.io"]
    assert "transformers" in result["application"]

    # Check transformer content
    assert len(result["system.io"]["transformers"]) == 1
    assert len(result["application"]["transformers"]) == 1

    # Check priority is shown
    assert "[priority=10]" in result["system.io"]["transformers"][0]
    assert "[priority=5]" in result["application"]["transformers"][0]

    # Check transformer names
    assert "transform_1" in result["system.io"]["transformers"][0]
    assert "<lambda>" in result["application"]["transformers"][0]


def test_to_string_is_valid_json() -> None:
    """Test that to_string produces valid JSON."""
    broker.clear()
    refs = _fill_broker()  # store lambdas to var to keep from getting collected

    json_str = broker.to_string()
    parsed = json.loads(json_str)

    assert parsed == broker.to_dict()


def test_to_dict_namespaces_without_transformers() -> None:
    """Test that namespaces without transformers don't include empty transformers key."""
    broker.clear()

    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler)
    result = broker.to_dict()

    # Should have subscribers but no transformers key
    assert "subscribers" in result["test.event"]
    assert "transformers" not in result["test.event"]


def test_to_dict_namespaces_without_subscribers() -> None:
    """Test that namespaces with only transformers don't include empty subscribers key."""
    broker.clear()

    def transformer(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_transformer("test.event", transformer)
    result = broker.to_dict()

    # Should have transformers but no subscribers key
    assert "transformers" in result["test.event"]
    assert "subscribers" not in result["test.event"]
