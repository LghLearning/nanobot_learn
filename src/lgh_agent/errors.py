from __future__ import annotations


class LghAgentError(Exception):
    """Base class for expected, user-facing application errors."""


class ConfigError(LghAgentError):
    """Raised when required configuration is missing or invalid."""


class ProviderConnectionError(LghAgentError):
    """Raised when the model provider cannot be reached."""


class ProviderHTTPError(LghAgentError):
    """Raised when the model provider returns a non-success HTTP status."""


class ProviderResponseError(LghAgentError):
    """Raised when the model provider response shape is invalid."""
