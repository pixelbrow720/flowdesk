"""Structured API errors.

Pure module (no FastAPI import) so gating/auth logic stays unit-testable without
a web stack. The FastAPI layer (``main.py``) converts these into JSON responses
of the form ``{"error": <message>, "code": <CODE>}`` via an exception handler.
"""
from __future__ import annotations

__all__ = [
    "ApiError",
    "Unauthenticated",
    "Forbidden",
    "NotFound",
    "ServiceUnavailable",
]


class ApiError(Exception):
    """Base class for structured API errors.

    Attributes:
        status_code: HTTP status to emit.
        code: stable machine-readable error code (the ``code`` field).
        message: human-readable message (the ``error`` field).
    """

    status_code: int = 500
    code: str = "INTERNAL"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message or self.__class__.__doc__ or self.code
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)

    def to_payload(self) -> dict[str, str]:
        """Render the structured error body."""
        return {"error": self.message, "code": self.code}


class Unauthenticated(ApiError):
    """No valid session present (not signed in)."""

    status_code = 401
    code = "UNAUTHENTICATED"


class Forbidden(ApiError):
    """Authenticated but missing the DESK role."""

    status_code = 403
    code = "FORBIDDEN"


class NotFound(ApiError):
    """Requested resource does not exist."""

    status_code = 404
    code = "NOT_FOUND"


class ServiceUnavailable(ApiError):
    """A backing dependency (Redis/Timescale) is not configured/available."""

    status_code = 503
    code = "SERVICE_UNAVAILABLE"
