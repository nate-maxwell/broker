## Exception Handling

### Subscriber Exception Handlers

Configure how the broker handles errors in subscriber callbacks:

```python
from broker import handlers

# Stop and Log (default) - logs error and stops delivery
broker.set_subscriber_exception_handler(
    handlers.stop_and_log_subscriber_exception
)

# Log and Continue - logs but continues to next subscriber
broker.set_subscriber_exception_handler(
    handlers.log_and_continue_subscriber_exception
)

# Silent - ignores all exceptions and continues
broker.set_subscriber_exception_handler(
    handlers.silent_subscriber_exception
)

# Collecting - captures exceptions for batch review
handlers.exceptions_caught.clear()
broker.set_subscriber_exception_handler(
    handlers.collect_subscriber_exception
)

broker.emit('event', data='test')

for error in handlers.exceptions_caught:
    print(f"Error in {error['namespace']}: {error['exception']}")
```

### Custom Handlers

Custom handlers can also be created.
They must support a callback, namespace, and exception argument and return a bool.
The return value dictates whether the system raises or passes the error.
```python
def custom_handler(callback: Callable, namespace: str, exception: Exception) -> bool:
    """Return True to stop delivery, False to continue."""
    if isinstance(exception, ValueError):
        return True  # Stop on ValueError
    return False  # Continue on other exceptions

broker.set_subscriber_exception_handler(custom_handler)
```

### Disabling Handlers

The broker handler can be set to None to return to raise all encountered
exceptions.
```python
# Disable (raise all exceptions)
broker.set_subscriber_exception_handler(None)
```

### Transformer Exception Handlers

Similar handlers for transformer errors:

```python
from broker import handlers

# Stop and log transformer errors (blocks event)
broker.set_transformer_exception_handler(
    handlers.stop_and_log_transformer_exception
)

# Log and continue with next transformer
broker.set_transformer_exception_handler(
    handlers.log_and_continue_transformer_exception
)

# Silent mode
broker.set_transformer_exception_handler(
    handlers.silent_transformer_exception
)

# Collecting mode
handlers.transformer_exceptions_caught.clear()
broker.set_transformer_exception_handler(
    handlers.collecting_transformer_exception
)

# Custom handler
def custom_transformer_handler(transformer, namespace, exception):
    print(f"Transformer error: {exception}")
    return False  # Continue with next transformer

broker.set_transformer_exception_handler(custom_transformer_handler)

# Disable (re-raise exceptions)
broker.set_transformer_exception_handler(None)
```
