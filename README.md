# Broker

A lightweight message broker system for Python with support for sync/async events, transformers, and flexible event routing.

## Quick Start

```python
import broker

# Subscribe to events
@broker.subscribe("file.saved")
def on_file_saved(filename: str, size: int) -> None:
    print(f'Saved: {filename} ({size} bytes)')

# Emit events
broker.emit('file.saved', filename='document.txt', size=1024)
```

## Core Concepts

The broker comprises 5 components:

- **The Broker** - The central event system
- **Namespaces** - Dot-notation event channels (e.g., `system.io.file_opened`)
- **Subscribers** - Callbacks that receive events
- **Transformers** - Middleware that modifies or filters events before delivery
- **Emitters** - Code that produces events via `emit()` or `emit_async()`

## Subscribing to Events

```python
import broker

# Decorator style
@broker.subscribe("system.io.file")
def print_filename(filename: str) -> None:
    print(f'File accessed: {filename}')

# Or programmatic registration
broker.register_subscriber("system.io.file", print_filename)
```

More info can be found [here](./docs/Subscribers.md).

## Emitting Events

```python
import broker

# Subscribe to events
@broker.subscribe("file.saved")
def on_file_saved(filename: str, size: int) -> None:
    print(f'Saved: {filename} ({size} bytes)')

# Emit events
broker.emit('file.saved', filename='document.txt', size=1024)

# Asynchronously emit events
await broker.emit_async('file.saved', filename='document.txt', size=1024)
```

More info can be found [here](./docs/Emitting.md).

## Signature Validation

The broker validates that all subscribers and emitters use consistent argument signatures:

```python
@broker.subscribe('user.login')
def first_subscriber(username: str, user_id: int) -> None:
    pass

# This will raise an exception - signature mismatch
@broker.subscribe('user.login')
def wrong_signature(username: str, email: str) -> None:  # ❌ Different args
    pass

# This will also raise an exception
broker.emit('user.login', username='alice', email='[email protected]')  # ❌ Wrong args
```

The first subscriber sets the expected signature for that namespace.

## Transformers

Transformers intercept and modify event data before it reaches subscribers. They execute in priority order and are scoped to specific namespaces.

### Basic Transformer

```python
import datetime

def add_timestamp(namespace: str, kwargs: dict) -> dict:
    """Add timestamp to all events."""
    now = datetime.datetime.now().time().isoformat()[:-4]
    kwargs['timestamp'] = now
    return kwargs

broker.register_transformer('system.*', add_timestamp, priority=10)

@broker.subscribe('system.startup')
def on_startup(timestamp: str) -> None:
    print(f'Started at {timestamp}')

broker.emit('system.startup')  # timestamp added automatically
```

More info can be found [here](./docs/Transformers.md).

## Exception Handling

Configure how the broker handles errors in subscribers and transformers.

More info can be found [here](./docs/Handlers.md).

## Advanced Features

### Flexible Callbacks

Use `**kwargs` for flexible argument handling:

```python
def flexible_handler(**kwargs: object) -> None:
    print('Received:', kwargs)

broker.register_subscriber('flexible.event', flexible_handler)
broker.emit('flexible.event', foo='bar', count=42, active=True)
```

### Weak References

The broker will not maintain references to items, preventing them from being
culled by the garbage collector.
Deletion of items referenced by the broker can be subscribed to.

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

More info can be found [here](./docs/EventNotifies.md).

### Reimport Protection

The broker is a singleton with reimport safeguards. Reimporting raises
`ImportError` to prevent data loss:

```python
import broker
import importlib
importlib.reload(broker)  # Raises ImportError
```

This protects the global namespace/subscriber table from being accidentally cleared.

## API References
Can be found [here](./docs/APIReferences.md).
