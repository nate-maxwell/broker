"""Custom Broker exceptions."""


class SignatureMismatchError(Exception):
    """Raised when callback signatures don't match for a namespace."""


class EmitArgumentError(Exception):
    """Raised when emit arguments don't match subscriber signatures."""
