"""Application exception hierarchy.

All errors raised by the application derive from a small number of base
exceptions so the API layer can translate them into controlled HTTP responses
without leaking internal details to the client.
"""
from __future__ import annotations


class GroundedError(Exception):
    """Base class for all application errors."""

    status_code = 500
    message = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.message
        super().__init__(self.message)


class ConfigurationError(GroundedError):
    """Raised when the application is not configured correctly.

    This is a server-side problem (missing env, bad provider value, ...).
    """

    status_code = 500
    message = "The server is not configured correctly."


class AuthenticationError(GroundedError):
    """Raised when a request cannot be authenticated."""

    status_code = 401
    message = "Authentication required."


class AuthorizationError(GroundedError):
    """Raised when an authenticated user cannot perform the action."""

    status_code = 403
    message = "You are not allowed to perform this action."


class ValidationError(GroundedError):
    """Raised when request input is invalid."""

    status_code = 422
    message = "Invalid request."


class NotFoundError(GroundedError):
    """Raised when a requested resource does not exist."""

    status_code = 404
    message = "Resource not found."


class ProviderError(GroundedError):
    """Raised when an upstream provider (LLM, vector store) fails.

    The internal provider message is never exposed to the client.
    """

    status_code = 502
    message = "An upstream service failed."
