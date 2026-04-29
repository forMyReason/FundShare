"""Typed errors for clearer user vs system failure handling."""


class DomainError(ValueError):
    """Business rule or user input violation (catch as ValueError for compatibility)."""
