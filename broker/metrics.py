"""Opt-in runtime metrics for broker event delivery."""

from dataclasses import dataclass
from threading import Lock
from time import perf_counter
from typing import Literal
from typing import Optional


__all__ = [
    "NamespaceRuntimeMetrics",
    "RuntimeMetrics",
    "disable_runtime_metrics",
    "enable_runtime_metrics",
    "get_runtime_metrics",
    "reset_runtime_metrics",
    "runtime_metrics_enabled",
]


@dataclass(frozen=True)
class NamespaceRuntimeMetrics(object):
    """Immutable runtime counters for one emitted namespace."""

    namespace: str
    emissions_attempted: int
    sync_emissions: int
    async_emissions: int
    emissions_completed: int
    emissions_blocked: int
    emissions_paused: int
    emissions_failed: int
    transformer_calls: int
    transformer_errors: int
    subscriber_calls: int
    subscriber_errors: int
    async_subscribers_skipped: int
    total_duration_seconds: float


@dataclass(frozen=True)
class RuntimeMetrics(object):
    """Immutable broker-wide runtime counters and per-namespace details."""

    enabled: bool
    emissions_attempted: int
    sync_emissions: int
    async_emissions: int
    emissions_completed: int
    emissions_blocked: int
    emissions_paused: int
    emissions_failed: int
    transformer_calls: int
    transformer_errors: int
    subscriber_calls: int
    subscriber_errors: int
    async_subscribers_skipped: int
    total_duration_seconds: float
    by_namespace: tuple[NamespaceRuntimeMetrics, ...]


@dataclass
class _MutableRuntimeMetrics(object):
    emissions_attempted: int = 0
    sync_emissions: int = 0
    async_emissions: int = 0
    emissions_completed: int = 0
    emissions_blocked: int = 0
    emissions_paused: int = 0
    emissions_failed: int = 0
    transformer_calls: int = 0
    transformer_errors: int = 0
    subscriber_calls: int = 0
    subscriber_errors: int = 0
    async_subscribers_skipped: int = 0
    total_duration_seconds: float = 0.0


_enabled = False
_totals = _MutableRuntimeMetrics()
_by_namespace: dict[str, _MutableRuntimeMetrics] = {}
_lock = Lock()


def enable_runtime_metrics() -> None:
    """Enable collection without resetting counters already collected."""
    global _enabled
    with _lock:
        _enabled = True


def disable_runtime_metrics() -> None:
    """Disable collection without discarding counters already collected."""
    global _enabled
    with _lock:
        _enabled = False


def runtime_metrics_enabled() -> bool:
    """Return whether runtime metrics collection is currently enabled."""
    with _lock:
        return _enabled


def reset_runtime_metrics() -> None:
    """Reset all counters while preserving the current enabled state."""
    global _totals
    with _lock:
        _totals = _MutableRuntimeMetrics()
        _by_namespace.clear()


def _namespace_snapshot(
    namespace: str, source: _MutableRuntimeMetrics
) -> NamespaceRuntimeMetrics:
    return NamespaceRuntimeMetrics(
        namespace=namespace,
        emissions_attempted=source.emissions_attempted,
        sync_emissions=source.sync_emissions,
        async_emissions=source.async_emissions,
        emissions_completed=source.emissions_completed,
        emissions_blocked=source.emissions_blocked,
        emissions_paused=source.emissions_paused,
        emissions_failed=source.emissions_failed,
        transformer_calls=source.transformer_calls,
        transformer_errors=source.transformer_errors,
        subscriber_calls=source.subscriber_calls,
        subscriber_errors=source.subscriber_errors,
        async_subscribers_skipped=source.async_subscribers_skipped,
        total_duration_seconds=source.total_duration_seconds,
    )


def get_runtime_metrics() -> RuntimeMetrics:
    """Return a stable snapshot of all runtime metrics."""
    with _lock:
        by_namespace = tuple(
            _namespace_snapshot(namespace, counters)
            for namespace, counters in sorted(_by_namespace.items())
        )
        return RuntimeMetrics(
            enabled=_enabled,
            emissions_attempted=_totals.emissions_attempted,
            sync_emissions=_totals.sync_emissions,
            async_emissions=_totals.async_emissions,
            emissions_completed=_totals.emissions_completed,
            emissions_blocked=_totals.emissions_blocked,
            emissions_paused=_totals.emissions_paused,
            emissions_failed=_totals.emissions_failed,
            transformer_calls=_totals.transformer_calls,
            transformer_errors=_totals.transformer_errors,
            subscriber_calls=_totals.subscriber_calls,
            subscriber_errors=_totals.subscriber_errors,
            async_subscribers_skipped=_totals.async_subscribers_skipped,
            total_duration_seconds=_totals.total_duration_seconds,
            by_namespace=by_namespace,
        )


def _increment(namespace: str, field: str, amount: int = 1) -> None:
    """Atomically increment a global and per-namespace metric counter."""
    with _lock:
        namespace_metrics = _by_namespace.setdefault(
            namespace, _MutableRuntimeMetrics()
        )
        setattr(_totals, field, getattr(_totals, field) + amount)
        setattr(
            namespace_metrics,
            field,
            getattr(namespace_metrics, field) + amount,
        )


def _add_duration(namespace: str, duration: float) -> None:
    """Atomically add elapsed time to global and per-namespace totals."""
    with _lock:
        namespace_metrics = _by_namespace.setdefault(
            namespace, _MutableRuntimeMetrics()
        )
        _totals.total_duration_seconds += duration
        namespace_metrics.total_duration_seconds += duration


class _EmitMetricsContext(object):
    """Tracks one emission that began while collection was enabled."""

    def __init__(self, namespace: str) -> None:
        self.namespace = namespace
        self.started_at = perf_counter()

    def paused(self) -> None:
        _increment(self.namespace, "emissions_paused")

    def blocked(self) -> None:
        _increment(self.namespace, "emissions_blocked")

    def complete(self) -> None:
        _increment(self.namespace, "emissions_completed")

    def failed(self) -> None:
        _increment(self.namespace, "emissions_failed")

    def transformer_call(self) -> None:
        _increment(self.namespace, "transformer_calls")

    def transformer_error(self) -> None:
        _increment(self.namespace, "transformer_errors")

    def subscriber_call(self) -> None:
        _increment(self.namespace, "subscriber_calls")

    def subscriber_error(self) -> None:
        _increment(self.namespace, "subscriber_errors")

    def async_subscriber_skipped(self) -> None:
        _increment(self.namespace, "async_subscribers_skipped")

    def finish(self) -> None:
        _add_duration(self.namespace, perf_counter() - self.started_at)


def _start_emit(
    namespace: str, mode: Literal["sync", "async"]
) -> Optional[_EmitMetricsContext]:
    # Keep disabled collection to a single boolean branch on the hot path.
    # A context that starts enabled remains internally consistent if metrics
    # are disabled while that emission is in flight.
    if not _enabled:
        return None

    _increment(namespace, "emissions_attempted")
    _increment(namespace, "sync_emissions" if mode == "sync" else "async_emissions")
    return _EmitMetricsContext(namespace)
