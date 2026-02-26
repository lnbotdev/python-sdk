from __future__ import annotations

import json


class LnBotError(Exception):
    """Base exception for all LnBot API errors."""

    def __init__(self, message: str, status: int, body: str) -> None:
        super().__init__(message)
        self.status = status
        self.body = body

    def __repr__(self) -> str:
        return f"{type(self).__name__}(status={self.status}, body={self.body!r})"


class BadRequestError(LnBotError):
    """Raised for 400 Bad Request responses."""

    def __init__(self, body: str) -> None:
        super().__init__(_extract_message(body, "Bad Request"), 400, body)


class UnauthorizedError(LnBotError):
    """Raised for 401 Unauthorized responses."""

    def __init__(self, body: str) -> None:
        super().__init__(_extract_message(body, "Unauthorized"), 401, body)


class ForbiddenError(LnBotError):
    """Raised for 403 Forbidden responses."""

    def __init__(self, body: str) -> None:
        super().__init__(_extract_message(body, "Forbidden"), 403, body)


class NotFoundError(LnBotError):
    """Raised for 404 Not Found responses."""

    def __init__(self, body: str) -> None:
        super().__init__(_extract_message(body, "Not Found"), 404, body)


class ConflictError(LnBotError):
    """Raised for 409 Conflict responses."""

    def __init__(self, body: str) -> None:
        super().__init__(_extract_message(body, "Conflict"), 409, body)


def _extract_message(body: str, fallback: str) -> str:
    """Try to pull a human-readable message from a JSON error body."""
    try:
        data = json.loads(body)
        return data.get("message") or data.get("error") or fallback
    except (json.JSONDecodeError, TypeError, AttributeError):
        return fallback
