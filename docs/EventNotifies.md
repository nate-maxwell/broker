## Broker Event Notifications

Subscribe to internal broker events to monitor subscription changes, emissions, and namespace lifecycle:

```python
# Enable specific notifications
broker.set_flag_states(on_subscribe=True, on_emit=True)

@broker.subscribe(broker.BROKER_ON_SUBSCRIBER_ADDED)
def on_subscriber_added(using: str) -> None:
    print(f'New subscriber to: {using}')

@broker.subscribe(broker.BROKER_ON_EMIT)
def on_emit(namespace: str, kwargs: dict) -> None:
    print(f'Event emitted: {namespace}')
```

### Available Notifications

**Subscriber Events**
- `BROKER_ON_SUBSCRIBER_ADDED` - New subscriber registered
- `BROKER_ON_SUBSCRIBER_REMOVED` - Subscriber unregistered
- `BROKER_ON_SUBSCRIBER_COLLECTED` - Subscriber garbage collected

**Transformer Events**
- `BROKER_ON_TRANSFORMER_ADDED` - New transformer registered
- `BROKER_ON_TRANSFORMER_REMOVED` - Transformer unregistered
- `BROKER_ON_TRANSFORMER_COLLECTED` - Transformer garbage collected

**Emission Events**
- `BROKER_ON_EMIT` - Event emitted via `emit()`
- `BROKER_ON_EMIT_ASYNC` - Event emitted via `emit_async()`
- `BROKER_ON_EMIT_ALL` - Any emission (sync or async)

**Namespace Events**
- `BROKER_ON_NAMESPACE_CREATED` - New namespace created
- `BROKER_ON_NAMESPACE_DELETED` - Namespace removed
