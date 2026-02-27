"""Tests for error classes and message extraction."""

from __future__ import annotations

import pytest

from lnbot.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    LnBotError,
    NotFoundError,
    UnauthorizedError,
    _extract_message,
)


class TestLnBotError:
    def test_message(self):
        e = LnBotError("fail", 500, "{}")
        assert str(e) == "fail"

    def test_status_and_body(self):
        e = LnBotError("fail", 500, '{"error":"fail"}')
        assert e.status == 500
        assert e.body == '{"error":"fail"}'

    def test_repr(self):
        e = LnBotError("fail", 500, "{}")
        assert "LnBotError" in repr(e)
        assert "500" in repr(e)

    def test_is_exception(self):
        assert issubclass(LnBotError, Exception)


class TestTypedErrors:
    @pytest.mark.parametrize(
        "cls,status,fallback",
        [
            (BadRequestError, 400, "Bad Request"),
            (UnauthorizedError, 401, "Unauthorized"),
            (ForbiddenError, 403, "Forbidden"),
            (NotFoundError, 404, "Not Found"),
            (ConflictError, 409, "Conflict"),
        ],
    )
    def test_status_code(self, cls, status, fallback):
        e = cls('{"message":"oops"}')
        assert e.status == status
        assert isinstance(e, LnBotError)

    @pytest.mark.parametrize(
        "cls",
        [BadRequestError, UnauthorizedError, ForbiddenError, NotFoundError, ConflictError],
    )
    def test_extracts_message_from_json(self, cls):
        e = cls('{"message":"custom error"}')
        assert str(e) == "custom error"

    @pytest.mark.parametrize(
        "cls,fallback",
        [
            (BadRequestError, "Bad Request"),
            (UnauthorizedError, "Unauthorized"),
            (ForbiddenError, "Forbidden"),
            (NotFoundError, "Not Found"),
            (ConflictError, "Conflict"),
        ],
    )
    def test_fallback_on_invalid_json(self, cls, fallback):
        e = cls("not json")
        assert str(e) == fallback


class TestExtractMessage:
    def test_message_field(self):
        assert _extract_message('{"message":"invalid amount"}', "fallback") == "invalid amount"

    def test_error_field(self):
        assert _extract_message('{"error":"bad input"}', "fallback") == "bad input"

    def test_message_takes_precedence(self):
        assert _extract_message('{"message":"msg","error":"err"}', "fallback") == "msg"

    def test_invalid_json(self):
        assert _extract_message("not json", "fallback") == "fallback"

    def test_no_known_fields(self):
        assert _extract_message('{"detail":"something"}', "fallback") == "fallback"
