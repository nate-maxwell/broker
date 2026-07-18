## Subscribing to Events

### Basic Subscription

```python
import broker

# Decorator style
@broker.subscribe("system.io.file")
def print_filename(filename: str) -> None:
    print(f'File accessed: {filename}')

# Or programmatic registration
broker.register_subscriber("system.io.file", print_filename)
```

### Hierarchical Subscriptions

Events bubble through their parent namespaces. A child must include its
parent's required arguments, but may add its own:

```python
@broker.subscribe("file")
def on_file_event(filename: str) -> None:
    print(f'File event: {filename}')

@broker.subscribe("file.saved")
def on_file_saved(filename: str, size: int) -> None:
    print(f'Saved {filename} ({size} bytes)')

broker.emit('file.saved', filename='data.json', size=2048)

# Output: File event: data.json
# Output: Saved data.json (2048 bytes)
```

Both callbacks run. The parent callback receives only `filename`.

As of version 2.0.0, namespace strings containing `*` are no longer supported.

### Priorities

Control execution order with priority values (higher = earlier):

```python
@broker.subscribe('system.alert', priority=10)
def critical_handler(message: str) -> None:
    print('CRITICAL:', message)

@broker.subscribe('system.alert', priority=1)
def log_handler(message: str) -> None:
    print('Logged:', message)

broker.emit('system.alert', message='Disk full')
# Output:
# CRITICAL: Disk full
# Logged: Disk full
```

### Unsubscribing

```python
broker.unregister_subscriber('file.saved', on_file_saved)
```

To remove a callback from every namespace it is registered to at once, use
`unregister_subscriber_all`:
```python
broker.unregister_subscriber_all(my_handler)
```

### One-Shot Subscribers

A subscriber can be set to automatically unregister itself after firing once
using the `once` parameter. This is useful for "wait for X, then stop" patterns
without manual cleanup.
```python
# Decorator style
@broker.subscribe('app.ready', once=True)
def on_first_ready(status: str) -> None:
    print(f'App came up: {status}')

# Programmatic style
broker.register_subscriber('app.ready', on_first_ready, once=True)
```

The subscriber fires on the first matching emit and is then removed. Subsequent
emits to the same namespace will not trigger it:
```python
broker.emit('app.ready', status='ok')   # Prints: App came up: ok
broker.emit('app.ready', status='ok')   # No output - already unregistered
```

If a subscriber added to a namespace using `once` is removed and was the only
subscriber in that namespace, the namespace is cleaned up just like when removing
from subscribers manually.
