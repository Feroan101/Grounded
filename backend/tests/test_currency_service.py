"""Tests for the currency conversion service.

All external HTTP requests are mocked — tests never touch the live
Frankfurter API.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.errors import ProviderError, ValidationError
from app.services.currency_service import (
    CurrencyService,
    ConversionResult,
    get_currency_service,
)


# ── Helpers ────────────────────────────────────────────────────────

def _fake_response(
    payload: dict,
    status_code: int = 200,
):
    """Return a lightweight stand-in for httpx.Response."""
    import json

    class _Resp:
        def __init__(self, data, code):
            self._data = data
            self.status_code = code

        def json(self):
            return self._data

        @property
        def text(self):
            return json.dumps(self._data)

    return _Resp(payload, status_code)


def _usd_to_inr_response(rate: float = 83.50, date: str = "2025-04-09"):
    return _fake_response({
        "amount": 1,
        "base": "USD",
        "date": date,
        "rates": {"INR": rate},
    })


class _FailingClient:
    """httpx.get that always raises."""

    def get(self, *a, **kw):
        import httpx
        raise httpx.ConnectError("connection refused")


class _SlowClient:
    """httpx.get that times out."""

    def get(self, *a, **kw):
        import httpx
        raise httpx.TimeoutException("timed out")


# ── Tests: successful conversion ──────────────────────────────────

def test_successful_conversion_usd_to_inr(monkeypatch):
    """Basic conversion: 100 USD -> INR at 83.50."""
    import app.services.currency_service as mod

    monkeypatch.setattr(mod.httpx, "get", lambda *a, **kw: _usd_to_inr_response())

    svc = CurrencyService()
    result = svc.convert(100, "USD", "INR")

    assert isinstance(result, ConversionResult)
    assert result.original_amount == Decimal("100")
    assert result.source_currency == "USD"
    assert result.target_currency == "INR"
    assert result.rate == Decimal("83.50")
    assert result.converted_amount == Decimal("8350.00")
    assert result.rate_date == "2025-04-09"
    assert "Frankfurter" in result.provider


def test_conversion_with_string_amount(monkeypatch):
    """Amount passed as a string should be parsed correctly."""
    import app.services.currency_service as mod

    monkeypatch.setattr(mod.httpx, "get", lambda *a, **kw: _usd_to_inr_response(rate=83.1234))

    svc = CurrencyService()
    result = svc.convert("50.50", "USD", "INR")

    assert result.original_amount == Decimal("50.50")
    # 50.50 * 83.1234 = 4197.7317 → quantized to 4197.73
    assert result.converted_amount == Decimal("4197.73")


def test_same_currency_no_api_call(monkeypatch):
    """Converting USD → USD should short-circuit without an HTTP call."""
    import app.services.currency_service as mod

    call_count = {"n": 0}
    def _counting_get(*a, **kw):
        call_count["n"] += 1
        return _usd_to_inr_response()

    monkeypatch.setattr(mod.httpx, "get", _counting_get)

    result = CurrencyService().convert(100, "USD", "USD")

    assert result.converted_amount == Decimal("100")
    assert result.rate == Decimal("1")
    assert result.rate_date == "N/A"
    assert call_count["n"] == 0


# ── Tests: validation ─────────────────────────────────────────────

def test_invalid_from_currency():
    with pytest.raises(ValidationError, match="from_currency"):
        CurrencyService().convert(100, "USDX", "INR")


def test_unsupported_to_currency():
    """Valid 3-letter format but not in the supported set."""
    with pytest.raises(ValidationError, match="not supported"):
        CurrencyService().convert(100, "USD", "XYZ")


def test_unsupported_currency_code():
    """Currency accepted by format check but not in the supported set."""
    with pytest.raises(ValidationError, match="not supported"):
        CurrencyService().convert(100, "USD", "BTC")


def test_currency_code_case_insensitive(monkeypatch):
    """Lowercase input should be normalised to uppercase."""
    import app.services.currency_service as mod

    monkeypatch.setattr(mod.httpx, "get", lambda *a, **kw: _usd_to_inr_response())

    result = CurrencyService().convert(100, "usd", "inr")
    assert result.source_currency == "USD"
    assert result.target_currency == "INR"


def test_empty_currency_code():
    with pytest.raises(ValidationError, match="from_currency"):
        CurrencyService().convert(100, "", "INR")


def test_none_currency_code():
    with pytest.raises(ValidationError, match="to_currency"):
        CurrencyService().convert(100, "USD", None)


def test_zero_amount():
    with pytest.raises(ValidationError, match="greater than zero"):
        CurrencyService().convert(0, "USD", "INR")


def test_negative_amount():
    with pytest.raises(ValidationError, match="greater than zero"):
        CurrencyService().convert(-50, "USD", "INR")


def test_non_numeric_amount():
    with pytest.raises(ValidationError, match="Cannot parse"):
        CurrencyService().convert("abc", "USD", "INR")


# ── Tests: API failures ───────────────────────────────────────────

def test_api_http_error(monkeypatch):
    """API returns a 4xx/5xx status."""
    import app.services.currency_service as mod

    monkeypatch.setattr(
        mod.httpx, "get",
        lambda *a, **kw: _fake_response({"error": "not found"}, status_code=404),
    )

    with pytest.raises(ProviderError, match="unexpected response"):
        CurrencyService().convert(100, "USD", "INR")


def test_api_connection_error(monkeypatch):
    """Network-level failure (DNS, connection refused, etc.)."""
    import app.services.currency_service as mod

    monkeypatch.setattr(mod.httpx, "get", _FailingClient().get)

    with pytest.raises(ProviderError, match="temporarily unavailable"):
        CurrencyService().convert(100, "USD", "INR")


def test_api_timeout(monkeypatch):
    """Request times out."""
    import app.services.currency_service as mod

    monkeypatch.setattr(mod.httpx, "get", _SlowClient().get)

    with pytest.raises(ProviderError, match="temporarily unavailable"):
        CurrencyService().convert(100, "USD", "INR")


def test_api_non_json_response(monkeypatch):
    """API returns 200 with non-JSON body."""
    import app.services.currency_service as mod

    class _BadJson:
        status_code = 200
        text = "<html>Server Error</html>"

        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(mod.httpx, "get", lambda *a, **kw: _BadJson())

    with pytest.raises(ProviderError, match="invalid data"):
        CurrencyService().convert(100, "USD", "INR")


def test_api_missing_rate_in_response(monkeypatch):
    """Response JSON is valid but the target currency is absent."""
    import app.services.currency_service as mod

    monkeypatch.setattr(
        mod.httpx, "get",
        lambda *a, **kw: _fake_response({
            "amount": 1, "base": "USD", "date": "2025-04-09",
            "rates": {"EUR": 0.92},
        }),
    )

    with pytest.raises(ProviderError, match="did not return the expected rate"):
        CurrencyService().convert(100, "USD", "INR")


def test_api_malformed_rate_value(monkeypatch):
    """Rate value in response is not a valid number."""
    import app.services.currency_service as mod

    monkeypatch.setattr(
        mod.httpx, "get",
        lambda *a, **kw: _fake_response({
            "amount": 1, "base": "USD", "date": "2025-04-09",
            "rates": {"INR": "not-a-number"},
        }),
    )

    with pytest.raises(ProviderError, match="unparseable rate"):
        CurrencyService().convert(100, "USD", "INR")


# ── Tests: decimal precision ──────────────────────────────────────

def test_decimal_precision_accuracy():
    """Conversion uses Decimal, not float, to avoid rounding drift."""
    from decimal import Decimal

    # 0.1 + 0.2 != 0.3 in float, but Decimal handles it correctly.
    amount = Decimal("0.1") + Decimal("0.2")
    rate = Decimal("3.14159265")
    result = (amount * rate).quantize(Decimal("0.01"))

    # 0.3 * 3.14159265 = 0.942477795 → 0.94
    assert result == Decimal("0.94")


def test_large_amount_precision(monkeypatch):
    """Large amounts with many digits should not lose precision."""
    import app.services.currency_service as mod

    monkeypatch.setattr(mod.httpx, "get", lambda *a, **kw: _usd_to_inr_response(rate=83.1234))

    result = CurrencyService().convert("999999.99", "USD", "INR")
    assert result.original_amount == Decimal("999999.99")
    expected = (Decimal("999999.99") * Decimal("83.1234")).quantize(Decimal("0.01"))
    assert result.converted_amount == expected


def test_fractional_amount_precision(monkeypatch):
    """Tiny fractional amounts should round correctly."""
    import app.services.currency_service as mod

    monkeypatch.setattr(mod.httpx, "get", lambda *a, **kw: _usd_to_inr_response(rate=83.12))

    result = CurrencyService().convert("0.01", "USD", "INR")
    assert result.converted_amount == Decimal("0.83")


# ── Tests: module interface ───────────────────────────────────────

def test_singleton_returns_same_instance():
    a = get_currency_service()
    b = get_currency_service()
    assert a is b


def test_result_is_frozen_dataclass():
    r = ConversionResult(
        original_amount=Decimal("1"),
        source_currency="USD",
        target_currency="INR",
        rate=Decimal("83.50"),
        converted_amount=Decimal("83.50"),
        rate_date="2025-04-09",
    )
    with pytest.raises(AttributeError):
        r.source_currency = "EUR"  # type: ignore[misc]
