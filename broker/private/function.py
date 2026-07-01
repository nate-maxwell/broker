"""
Internal utility functions for the event broker.

Provides three low-level utilities used during subscriber registration and
event emission:

Not intended for direct use outside of broker/private/.
"""

import inspect
import weakref
from typing import Any
from typing import Callable
from typing import Optional
from typing import Union

from broker import exceptions
from broker import subscriber
from broker.private import registry


def make_weak_ref(
    callback: subscriber.SUBSCRIBER,
    namespace: str,
    on_collected_callback: Callable[[str], None],
) -> Union[weakref.ref[Any], weakref.WeakMethod]:
    """Create the appropriate weak reference for any callback type."""

    def cleanup(_: Union[weakref.ref[Any], weakref.WeakMethod]) -> None:
        # Arg needed to add for weakref creation.
        on_collected_callback(namespace)

    if hasattr(callback, "__self__"):
        return weakref.WeakMethod(callback, cleanup)
    else:
        return weakref.ref(callback, cleanup)


def get_callback_params(callback: subscriber.SUBSCRIBER) -> Optional[set[str]]:
    """
    Extract parameter names from a callback function.

    Args:
        callback (CALLBACK): The callback function to inspect.
    Returns:
        Optional[set[str]]: Set of parameter names, or None if callback
            accepts **kwargs.
    """
    sig = inspect.signature(callback)

    # **kwargs is not tracked
    for param in sig.parameters.values():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return None

    return {
        name
        for name, param in sig.parameters.items()
        if param.kind != inspect.Parameter.VAR_POSITIONAL  # exclude *args
    }


def validate_emit_args(namespace: str, kwargs: dict[str, Any]) -> None:
    """
    Validate that emit arguments match subscriber signatures.

    Args:
        namespace (str): The namespace being emitted to.
        kwargs (dict[str, Any]): The keyword arguments being emitted.
    Raises:
        EmitArgumentError: If provided kwargs don't match subscriber signatures.
    """
    provided_args = set(kwargs.keys())

    # Check all namespaces that match the emitted namespace
    for reg_namespace, entry in registry.NAMESPACE_REGISTRY.items():
        if not registry.matches(namespace, reg_namespace):
            continue

        expected_params = entry.signature

        if expected_params is None:
            continue

        if provided_args != expected_params:
            raise exceptions.EmitArgumentError(
                f"Argument mismatch when emitting to '{namespace}'. "
                f"Subscribers in '{reg_namespace}' expect: {sorted(expected_params)}, "
                f"but got: {sorted(provided_args)}"
            )
