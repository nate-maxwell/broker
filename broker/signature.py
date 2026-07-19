"""
Internal utility functions for the event broker.

Not intended for direct use, but may be of some utility to users.
"""

import inspect
from typing import Any

from broker import subscriber
from broker.private import namespace as _namespace


class EmitArgumentError(Exception):
    """Raised when emit arguments don't match subscriber signatures."""


class SignatureMismatchError(Exception):
    """Raised when subscriber signatures don't match for a namespace."""


def get_callback_params(callback: subscriber.SUBSCRIBER_SIG) -> set[str]:
    """
    Extract parameter names from a callback function.

    Args:
        callback (CALLBACK): The callback function to inspect.
    Returns:
        set[str]: Explicit parameter names accepted by the callback.
    """
    sig = inspect.signature(callback)

    return {
        name
        for name, param in sig.parameters.items()
        if param.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    }


def callback_accepts_kwargs(callback: subscriber.SUBSCRIBER_SIG) -> bool:
    """Return whether a callback explicitly accepts arbitrary keyword args."""
    return any(
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in inspect.signature(callback).parameters.values()
    )


def get_callback_kwargs(
    callback: subscriber.SUBSCRIBER_SIG, kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Project an event payload to the arguments accepted by a callback."""
    if callback_accepts_kwargs(callback):
        return kwargs

    return {name: kwargs[name] for name in get_callback_params(callback)}


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
    for reg_namespace, entry in _namespace.NAMESPACE_REGISTRY.items():
        if not _namespace.matches(namespace, reg_namespace):
            continue

        expected_params = entry.signature

        if expected_params is None:
            continue

        missing_params = expected_params - provided_args
        if missing_params:
            raise EmitArgumentError(
                f"Argument mismatch when emitting to '{namespace}'. "
                f"Subscribers in '{reg_namespace}' require: "
                f"{sorted(expected_params)}, but the transformed payload is "
                f"missing: {sorted(missing_params)}"
            )
