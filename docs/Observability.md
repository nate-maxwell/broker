# Observability

Broker provides side-effect-free delivery planning, immutable state snapshots,
and disabled-by-default runtime metrics.

## Explain an emission

`explain_emit()` uses the same namespace matching and priority ordering as
actual routing, but does not execute transformers or subscribers.

```python
plan = broker.explain_emit("user.login", mode="sync")

for step in plan.transformers:
    print(step.callback, step.priority, step.will_run)

for step in plan.subscribers:
    print(step.callback, step.registered_namespace, step.skip_reason)
```

The plan includes the effective required parameter names, broker pause state,
and whether each callback is live. In sync mode, async subscribers are present
in the plan with `will_run=False` and a skip reason.

The planner cannot predict changes or blocking caused by transformers because
executing them would make explanation stateful.

### `EmitPlan`

The top-level plan describes the emission and contains its ordered route.

| Field | Type | Meaning |
| --- | --- | --- |
| `namespace` | `str` | The exact namespace passed to `explain_emit()`. It does not need to be registered itself when a registered parent namespace matches it. |
| `mode` | `Literal["sync", "async"]` | The delivery API being modeled: `"sync"` represents `emit()` and `"async"` represents `emit_async()`. |
| `is_paused` | `bool` | Whether the broker was paused when the plan was captured. Eligible callbacks are marked as skipped while this is `True`. |
| `required_parameters` | `tuple[str, ...]` | The sorted parameter names required by all matching subscriber contracts. These describe the payload after transformation because transformers run before validation. |
| `transformers` | `tuple[TransformerDeliveryPlan, ...]` | Matching transformer steps in descending execution-priority order. |
| `subscribers` | `tuple[SubscriberDeliveryPlan, ...]` | Matching subscriber steps in descending execution-priority order, including callbacks that would be skipped. |

### `SubscriberDeliveryPlan`

Each subscriber step describes a registration that matches the emitted
namespace.

| Field | Type | Meaning |
| --- | --- | --- |
| `callback` | `str` | A display name for the callback, or `"<dead reference>"` when its weak reference is no longer live. The callback object itself is not retained. |
| `registered_namespace` | `str` | The namespace where the subscriber was registered. This may be a parent of the emitted namespace. |
| `priority` | `int` | Delivery priority; higher values execute before lower values. |
| `is_async` | `bool` | Whether the callback is asynchronous. Async subscribers are skipped in sync mode. |
| `is_one_shot` | `bool` | Whether the registration is configured to unregister itself after it fires. |
| `is_alive` | `bool` | Whether the weakly referenced callback was live when the plan was captured. |
| `will_run` | `bool` | Whether the callback is statically eligible for the selected mode and current pause state. An earlier transformer or exception policy can still prevent it from running. |
| `skip_reason` | `Optional[str]` | Why the callback is not eligible, or `None` when `will_run` is `True`. Current reasons cover a dead callback, a paused broker, and an async subscriber used with `emit()`. |

### `TransformerDeliveryPlan`

Each transformer step describes a registration that matches the emitted
namespace.

| Field | Type | Meaning |
| --- | --- | --- |
| `callback` | `str` | A display name for the callback, or `"<dead reference>"` when its weak reference is no longer live. The callback object itself is not retained. |
| `registered_namespace` | `str` | The namespace where the transformer was registered. This may be a parent of the emitted namespace. |
| `priority` | `int` | Transformation priority; higher values execute before lower values. |
| `is_alive` | `bool` | Whether the weakly referenced callback was live when the plan was captured. |
| `will_run` | `bool` | Whether the transformer is statically eligible to run. An earlier transformer can still block the event before this step is reached. |
| `skip_reason` | `Optional[str]` | Why the transformer is not eligible, or `None` when `will_run` is `True`. Current reasons cover a dead callback and a paused broker. |

## Structured snapshots

`get_snapshot()` returns a frozen `BrokerSnapshot`. Its nested namespace,
subscriber, transformer, and staged-event records are frozen as well.

```python
from dataclasses import asdict

snapshot = broker.get_snapshot()

for namespace in snapshot.namespaces:
    print(namespace.namespace, namespace.expected_parameters)

serializable = asdict(snapshot)
```

Snapshots contain staged-event counts, but deliberately exclude staged payload
values and callback objects. They therefore do not expose event data or keep
weakly referenced callbacks alive.

### `BrokerSnapshot`

| Field | Type | Meaning |
| --- | --- | --- |
| `namespaces` | `tuple[NamespaceSnapshot, ...]` | Registered namespace snapshots, sorted by namespace. |
| `staged_events` | `tuple[StagedEventsSnapshot, ...]` | Counts for namespaces that currently contain staged events, sorted by namespace. |

### `NamespaceSnapshot`

| Field | Type | Meaning |
| --- | --- | --- |
| `namespace` | `str` | The registered namespace represented by this record. |
| `expected_parameters` | `Optional[tuple[str, ...]]` | The sorted parameter names required by the namespace's subscriber contract. `None` means the namespace has no subscriber contract, such as a transformer-only namespace. |
| `subscribers` | `tuple[SubscriberSnapshot, ...]` | Subscriber registrations belonging directly to this namespace. |
| `transformers` | `tuple[TransformerSnapshot, ...]` | Transformer registrations belonging directly to this namespace. |

### `SubscriberSnapshot`

| Field | Type | Meaning |
| --- | --- | --- |
| `callback` | `str` | A display name for the callback, or `"<dead reference>"`. No callback object is retained. |
| `namespace` | `str` | The namespace where the subscriber is registered. |
| `priority` | `int` | The subscriber's delivery priority. |
| `is_async` | `bool` | Whether the subscriber callback is asynchronous. |
| `is_one_shot` | `bool` | Whether the registration is configured to unregister itself after it fires. |
| `is_alive` | `bool` | Whether the weakly referenced callback was live when the snapshot was captured. |

### `TransformerSnapshot`

| Field | Type | Meaning |
| --- | --- | --- |
| `callback` | `str` | A display name for the callback, or `"<dead reference>"`. No callback object is retained. |
| `namespace` | `str` | The namespace where the transformer is registered. |
| `priority` | `int` | The transformer's execution priority. |
| `is_alive` | `bool` | Whether the weakly referenced callback was live when the snapshot was captured. |

### `StagedEventsSnapshot`

| Field | Type | Meaning |
| --- | --- | --- |
| `namespace` | `str` | The namespace associated with the staged events. |
| `event_count` | `int` | The number of staged events for that namespace. Payload values are not captured. |

## Runtime metrics

Collection is disabled by default. Enabling metrics does not reset counters,
and disabling metrics does not discard them.

```python
broker.enable_runtime_metrics()

broker.emit("user.login", username="alice")
metrics = broker.get_runtime_metrics()

print(metrics.emissions_attempted)
print(metrics.subscriber_calls)
print(metrics.total_duration_seconds)

for namespace in metrics.by_namespace:
    print(namespace.namespace, namespace.emissions_completed)

broker.disable_runtime_metrics()
broker.reset_runtime_metrics()
```

An emission is counted as attempted after its namespace is validated. Paused,
transformer-blocked, and failed emissions have separate counters. An emission
is completed only when delivery and any configured emit notification finish
without an unhandled exception. Exceptions consumed by subscriber or
transformer exception handlers increment their error counter while preserving
the handler's existing continue-or-stop behavior.

`subscriber_calls` and `transformer_calls` count callback invocations.
`async_subscribers_skipped` counts live async subscribers skipped by `emit()`.
Durations cover the complete attempted operation, including paused, blocked,
and failed attempts. Broker notification namespaces are counted like any other
emission and can be distinguished in `by_namespace`.
