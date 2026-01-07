# Broker

A simple message broker system for python.
Supports sync and async events.

## Namespaces

End-points can subscribe to namespaces using dot notation like
`system.io.file_opened` or wildcard namespace subscriptions for specific levels
downwards like `system.io.*`.
 
## Priorities

Subscriptions can add a priority integer that will dictate the subscriber
execution order:
```python
broker.subscribe('file.io.*', my_func, priority=10)
```

Higher priorities are executed first.

## Expressive Arguments

Events can be emitted with any keyword arguments:
```python
broker.emit('file.io.open_file', path=Path('D:/dir/file.txt'))
```

## Signature Validation

If a subscriber to a namespace with keyword arguments different from previous
subscribers, or an event is emitted using different keywords than subscribers
are expecting, an explicit exception is raised. First subscribers set the
expectation and following subscribers + emitters are validated.

## Exception Handling

The broker provides configurable exception handling for errors that occur during
subscriber callback execution. By default, exceptions are logged and stop
delivery to remaining subscribers.

### Exception Handler Types

**Stop on Exception (Default)**

```python
from broker import exceptions

# Default behavior - logs error and stops delivery
broker.set_exception_handler(exceptions.stop_on_exception_handler)
```

**Silent Handler** - Ignores exceptions and continues delivery:
```python
broker.set_exception_handler(exceptions.silent_exception_handler)
```

**Collecting Handler** - Captures all exceptions for batch processing:
```python
exceptions.exceptions_caught.clear()
broker.set_exception_handler(exceptions.collecting_exception_handler)

broker.emit('event', data='test')

# Review collected exceptions
for error in exceptions.exceptions_caught:
    print(f"Error in {error['namespace']}: {error['exception']}")
```

**Custom Handler** - Create your own exception policy:
```python
def custom_handler(callback, namespace, exception):
    # Log the error
    print(f"Error in {namespace}: {exception}")
    
    # Return True to stop delivery, False to continue
    if isinstance(exception, ValueError):
        return True  # Stop on ValueError
    return False  # Continue on other exceptions

broker.set_exception_handler(custom_handler)
```

**Disable Handler** - Re-raise all exceptions:
```python
broker.set_exception_handler(None)  # Exceptions propagate normally
```

Exception handlers work with both `emit()` and `emit_async()`, and apply to all
subscriber types including sync callbacks, async callbacks, instance methods,
and lambdas.

## Broker Event Notification

Actions within the broker itself can be subscribed to, including:
* Subscriber addition
* Subscriber removal
* Subscriber deletion from GC
* Synchronous event emitting
* Asynchronous event emitting
* All event emitting
* Namespace creation
* Namespace deletion

This is easily achieved using broker constants like so:
```python
@broker.subscribe(broker.BROKER_ON_SUBSCRIBER_ADDED)
def on_subscriber_added(using: str) -> None:
    print(f'New subscriber to namespace: {using}')

# --or--

broker.register_subscriber(broker.BROKER_ON_SUBSCRIBER_ADDED, on_subscriber_added)
```
* Note that this decorator does not work with instance bound class methods. It
works with regular functions or static methods.

# Example
```python
import broker

# Basic usage - register and emit
def on_file_saved(filename: str, size: int) -> None:
    print(f'File saved: {filename} ({size} bytes)')

broker.register_subscriber('file.save', on_file_saved)
broker.emit('file.save', filename='document.txt', size=1024)


# Wildcard subscriptions
def on_any_file_event(filename: str, size: int) -> None:
    print(f'File event: {filename}')

broker.register_subscriber('file.*', on_any_file_event)
broker.emit('file.save', filename='data.json', size=2048)
broker.emit('file.delete', filename='temp.txt', size=512)


# Priority-based execution (higher priority runs first)
def high_priority_handler(message: str) -> None:
    print('High priority:', message)

def low_priority_handler(message: str) -> None:
    print('Low priority:', message)

broker.register_subscriber('system.alert', high_priority_handler, priority=10)
broker.register_subscriber('system.alert', low_priority_handler, priority=1)
broker.emit('system.alert', message='Warning!')


# Async callbacks
import asyncio

async def async_handler(data: str) -> None:
    await asyncio.sleep(0.1)
    print(f'Async processed: {data}')

def sync_handler(data: str) -> None:
    print(f'Sync processed: {data}')

broker.register_subscriber('process.data', async_handler)
broker.register_subscriber('process.data', sync_handler)

# Use emit() for sync only
broker.emit('process.data', data='example')  # Only calls sync_handler

# Use emit_async() for both sync and async
await broker.emit_async('process.data', data='example')  # Calls both


# Flexible callbacks with **kwargs
def flexible_handler(**kwargs: object) -> None:
    print('Received:', kwargs)

broker.register_subscriber('flexible.event', flexible_handler)
broker.emit('flexible.event', foo='bar', count=42, active=True)


# Exception handling example
def might_fail(value: int) -> None:
    if value < 0:
        raise ValueError('Negative values not allowed')
    print(f'Processed: {value}')

def always_succeeds(value: int) -> None:
    print('Cleanup complete')

broker.register_subscriber('process', might_fail, priority=10)
broker.register_subscriber('process', always_succeeds, priority=5)

# With silent handler, both callbacks run even if first fails
from broker import exceptions
broker.set_exception_handler(exceptions.silent_exception_handler)

broker.emit('process', value=-1)  # Both callbacks execute


# Unregister subscribers
broker.unregister_subscriber('file.save', on_file_saved)
```
