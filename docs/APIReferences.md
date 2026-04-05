## API Reference

### Core Functions

- `subscribe(namespace: str, priority: int = 0)` - Decorator for registering subscribers
- `register_subscriber(namespace: str, callback: Callable, priority: int = 0)` - Register a subscriber programmatically
- `unregister_subscriber(namespace: str, callback: Callable)` - Remove a subscriber
- `set_subscriber_exception_handler(handler: Callable | None)` - Configure subscriber error handling

- `stage(namespace: str, **kwargs: Any)` - Stage an entry for emitting later
- `emit_staged(flush: bool = True)` - Emits staged events through `broker.emit()`
- `emit_staged_async(flush: bool = True)` - Emits staged events through `broker.emit_async()`
- `paused()` - Context manager that suppresses all emission for the duration of the block

- `register_transformer(namespace: str, transformer: Callable, priority: int = 0)` - Add event transformer
- `set_transformer_exception_handler(handler: Callable | None)` - Configure transformer error handling
- `clear_transformers()` - Clear all registered transformers

- `emit(namespace: str, **kwargs)` - Emit event to synchronous subscribers
- `emit_async(namespace: str, **kwargs)` - Emit event to all subscribers (async)

- `clear()` - Clears the subscriber table
- `clear_staged()` - Clears the staging table

### Introspection Functions

- `set_flag_states(**flags)` - Enable broker event notifications

- `to_dict()` - Serializes the broker structure to a dictionary
- `to_string()` - Returns a string representation of the broker
- `export(filepath: Union[str, os.PathLike])` - Exports broker structure to filepath

- `get_namespaces()` - Returns all registered namespaces
- `namespace_exists(namespace: str)` - Checks if a namespace exists...
- `get_matching_namespaces(pattern: str)` - Get all namespaces that match a pattern (including wildcards)
- `get_namespace_info(namespace: str)` - Get detailed information about a namespace
- `get_all_namespace_info()` - Get detailed information about all namespaces
- `get_statistics()` - Get overall broker statistics

- `get_subscriber_count(namespace: str)` - Get the number of subscribers for a namespace
- `get_live_subscriber_count(namespace: str)` - Get the number of live (non-garbage-collected) subscribers
- `is_subscribed(callback: subscriber.SUBSCRIBER, namespace: str)` - Check if a specific callback is a subscriber to a namespace
- `get_subscriptions(callback: subscriber.SUBSCRIBER)` - Get all namespaces that a callback is subscribed to
- `get_subscribers(namespace: str)` - Get all subscribers for a namespace
- `get_live_subscribers(namespace: str)` - Get all live (non-garbage-collected) subscribers for a namespace

- `get_all_transformer_namespaces()` - Get all namespaces that have transformers
- `get_transformer_count(namespace: str)` - Get the number of transformers for a namespace
- `get_live_transformer_count(namespace: str)` - Get the number of live (non-garbage-collected) transformers for a namespace
- `is_transformed(callback: transformer.TRANSFORMER, namespace: str)` - Check if a specific callback is registered as a transformer for a namespace
- `get_transformations(callback: transformer.TRANSFORMER)` - Get all namespaces that a callback is registered as a transformer for
- `get_transformers(namespace: str)` - Get all transformers for a namespace
- `get_live_transformers(namespace: str)` - Get all live (non-garbage-collected) transformers for a namespace

- `get_staged_namespaces()` - Get all namespaces with staged events
- `get_staged_count(namespace: Optional[str] = None)` - Get the number of staged events

### Notify Namespaces

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
