"""Tests for delivery plans, structured snapshots, and runtime metrics."""

import json
from dataclasses import asdict

import pytest

import broker


@pytest.fixture(autouse=True)
def reset_broker_observability():
    broker.set_flag_states()
    broker.set_subscriber_exception_handler(
        broker.handlers.stop_and_log_subscriber_exception
    )
    broker.set_transformer_exception_handler(
        broker.handlers.stop_and_log_transformer_exception
    )
    broker.disable_runtime_metrics()
    broker.reset_runtime_metrics()
    broker.clear()
    broker.clear_staged()
    yield
    broker.set_flag_states()
    broker.set_subscriber_exception_handler(
        broker.handlers.stop_and_log_subscriber_exception
    )
    broker.set_transformer_exception_handler(
        broker.handlers.stop_and_log_transformer_exception
    )
    broker.disable_runtime_metrics()
    broker.reset_runtime_metrics()
    broker.clear()
    broker.clear_staged()


def test_explain_emit_uses_runtime_order_without_calling_callbacks() -> None:
    calls: list[str] = []

    def parent_transformer(namespace: str, kwargs: dict) -> dict:
        calls.append(namespace)
        return kwargs

    def child_transformer(namespace: str, kwargs: dict) -> dict:
        calls.append(namespace)
        return kwargs

    def parent_handler(data: str) -> None:
        calls.append(data)

    async def child_handler(data: str) -> None:
        calls.append(data)

    broker.register_transformer("app", parent_transformer, priority=5)
    broker.register_transformer("app.created", child_transformer, priority=10)
    broker.register_subscriber("app", parent_handler, priority=5, once=True)
    broker.register_subscriber("app.created", child_handler, priority=10)

    plan = broker.explain_emit("app.created", mode="sync")

    assert calls == []
    assert plan.required_parameters == ("data",)
    assert [item.registered_namespace for item in plan.transformers] == [
        "app.created",
        "app",
    ]
    assert [item.registered_namespace for item in plan.subscribers] == [
        "app.created",
        "app",
    ]
    assert plan.subscribers[0].will_run is False
    assert plan.subscribers[0].skip_reason == "async subscriber is skipped by emit()"
    assert plan.subscribers[1].is_one_shot is True
    assert plan.subscribers[1].will_run is True

    async_plan = broker.explain_emit("app.created", mode="async")
    assert all(item.will_run for item in async_plan.subscribers)


def test_explain_emit_reports_paused_routes() -> None:
    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test", handler)
    with broker.PausedContext():
        plan = broker.explain_emit("test.child")

    assert plan.is_paused is True
    assert plan.subscribers[0].will_run is False
    assert plan.subscribers[0].skip_reason == "broker is paused"


def test_explain_emit_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="mode must be"):
        broker.explain_emit("test", mode="parallel")  # type: ignore[arg-type]


def test_structured_snapshot_is_immutable_and_json_compatible() -> None:
    def handler(data: str) -> None:
        pass

    def transformer(namespace: str, kwargs: dict) -> dict:
        return kwargs

    broker.register_subscriber("test.event", handler, priority=7, once=True)
    broker.register_transformer("test", transformer, priority=3)
    broker.stage("test.event", data="secret")

    snapshot = broker.get_snapshot()
    namespace = next(
        item for item in snapshot.namespaces if item.namespace == "test.event"
    )

    assert namespace.expected_parameters == ("data",)
    assert namespace.subscribers[0].priority == 7
    assert namespace.subscribers[0].is_one_shot is True
    assert snapshot.staged_events[0].event_count == 1
    assert "secret" not in json.dumps(asdict(snapshot))

    broker.clear()
    broker.clear_staged()
    assert len(snapshot.namespaces) == 2
    assert snapshot.staged_events[0].event_count == 1


def test_runtime_metrics_are_disabled_by_default() -> None:
    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler)
    broker.emit("test.event", data="value")

    metrics = broker.get_runtime_metrics()
    assert metrics.enabled is False
    assert metrics.emissions_attempted == 0
    assert metrics.subscriber_calls == 0


@pytest.mark.asyncio
async def test_runtime_metrics_cover_sync_async_and_namespace_details() -> None:
    def transformer(namespace: str, kwargs: dict) -> dict:
        return kwargs

    def sync_handler(data: str) -> None:
        pass

    async def async_handler(data: str) -> None:
        pass

    broker.register_transformer("test", transformer)
    broker.register_subscriber("test.event", sync_handler)
    broker.register_subscriber("test.event", async_handler)
    broker.enable_runtime_metrics()

    broker.emit("test.event", data="sync")
    await broker.emit_async("test.event", data="async")

    metrics = broker.get_runtime_metrics()
    assert metrics.enabled is True
    assert metrics.emissions_attempted == 2
    assert metrics.sync_emissions == 1
    assert metrics.async_emissions == 1
    assert metrics.emissions_completed == 2
    assert metrics.transformer_calls == 2
    assert metrics.subscriber_calls == 3
    assert metrics.async_subscribers_skipped == 1
    assert metrics.total_duration_seconds > 0
    assert len(metrics.by_namespace) == 1
    assert metrics.by_namespace[0].namespace == "test.event"
    assert metrics.by_namespace[0].subscriber_calls == 3


def test_runtime_metrics_record_blocked_paused_and_failed_emissions() -> None:
    def blocker(namespace: str, kwargs: dict) -> None:
        return None

    def handler(data: str) -> None:
        pass

    broker.register_transformer("blocked", blocker)
    broker.register_subscriber("failed", handler)
    broker.enable_runtime_metrics()

    broker.emit("blocked.event")
    with broker.PausedContext():
        broker.emit("paused.event")
    with pytest.raises(broker.EmitArgumentError):
        broker.emit("failed", wrong="value")

    metrics = broker.get_runtime_metrics()
    assert metrics.emissions_attempted == 3
    assert metrics.emissions_blocked == 1
    assert metrics.emissions_paused == 1
    assert metrics.emissions_failed == 1
    assert metrics.emissions_completed == 0


def test_runtime_metrics_record_handled_callback_errors() -> None:
    def failing_transformer(namespace: str, kwargs: dict) -> dict:
        raise RuntimeError("transformer failed")

    def failing_subscriber(data: str) -> None:
        raise RuntimeError("subscriber failed")

    broker.set_transformer_exception_handler(lambda callback, namespace, exc: False)
    broker.set_subscriber_exception_handler(lambda callback, namespace, exc: False)
    broker.register_transformer("test", failing_transformer)
    broker.register_subscriber("test", failing_subscriber)
    broker.enable_runtime_metrics()

    broker.emit("test", data="value")

    metrics = broker.get_runtime_metrics()
    assert metrics.transformer_calls == 1
    assert metrics.transformer_errors == 1
    assert metrics.subscriber_calls == 1
    assert metrics.subscriber_errors == 1
    assert metrics.emissions_completed == 1
    assert metrics.emissions_failed == 0


def test_reset_runtime_metrics_preserves_enabled_state() -> None:
    broker.enable_runtime_metrics()
    broker.emit("test")
    broker.reset_runtime_metrics()

    metrics = broker.get_runtime_metrics()
    assert metrics.enabled is True
    assert metrics.emissions_attempted == 0
