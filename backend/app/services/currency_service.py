"""Currency conversion service.

Provides a thin wrapper around the Frankfurter exchange-rate API
for converting amounts between ISO-4217 currency codes.

This is *not* a financial tool — it returns the latest published
Frankfurter rate and should not be treated as live forex data.

Tool interface (for future agent wiring):

    convert_currency(amount, from_currency, to_currency) -> ConversionResult
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import httpx

from app.errors import ProviderError, ValidationError

logger = logging.getLogger(__name__)

# ── Frankfurter API ────────────────────────────────────────────────
_BASE_URL = "https://api.frankfurter.dev/v2"
_RATE_PATH = _BASE_URL + "/rate/{base}/{quote}"

_TIMEOUT_SECONDS = 10

# Known ISO-4217 codes accepted by the Frankfurter API.
# Kept small; the API itself will reject unsupported codes cleanly.
_SUPPORTED_CURRENCIES: frozenset[str] = frozenset({
    "AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR",
    "GBP", "HKD", "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW",
    "MXN", "MYR", "NOK", "NZD", "PHP", "PLN", "RON", "SEK", "SGD",
    "THB", "TRY", "USD", "ZAR",
})


# ── Result model ───────────────────────────────────────────────────

@dataclass(frozen=True)
class ConversionResult:
    """Structured output returned by the conversion tool."""
    original_amount: Decimal
    source_currency: str
    target_currency: str
    rate: Decimal
    converted_amount: Decimal
    rate_date: str
    provider: str = "Frankfurter API (https://frankfurter.dev)"


# ── Service ────────────────────────────────────────────────────────

class CurrencyService:
    """Exchange-rate conversion backed by the Frankfurter API."""

    def convert(
        self,
        amount: float | int | str | Decimal,
        from_currency: str,
        to_currency: str,
    ) -> ConversionResult:
        """Convert *amount* from *from_currency* to *to_currency*.

        Parameters
        ----------
        amount:
            The amount to convert (int, float, string, or Decimal).
        from_currency:
            ISO-4217 base currency code, e.g. ``"USD"``.
        to_currency:
            ISO-4217 quote currency code, e.g. ``"INR"``.

        Returns
        -------
        ConversionResult
            Frozen dataclass with all conversion details.

        Raises
        ------
        ValidationError
            If currency codes are invalid or the amount is not a
            valid number.
        ProviderError
            If the Frankfurter API is unreachable or returns an
            unexpected response.
        """
        base = self._normalise_code(from_currency, "from_currency")
        quote = self._normalise_code(to_currency, "to_currency")
        dec_amount = self._parse_amount(amount)

        if base == quote:
            return ConversionResult(
                original_amount=dec_amount,
                source_currency=base,
                target_currency=quote,
                rate=Decimal("1"),
                converted_amount=dec_amount,
                rate_date="N/A",
            )

        rate, rate_date = self._fetch_rate(base, quote)
        converted = (dec_amount * rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        return ConversionResult(
            original_amount=dec_amount,
            source_currency=base,
            target_currency=quote,
            rate=rate,
            converted_amount=converted,
            rate_date=rate_date,
        )

    # ── Private helpers ────────────────────────────────────────────

    @staticmethod
    def _normalise_code(value: str | None, field_name: str) -> str:
        if not value or not isinstance(value, str):
            raise ValidationError(
                f"{field_name} must be a non-empty ISO-4217 currency code."
            )
        code = value.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValidationError(
                f"{field_name} must be a 3-letter ISO-4217 code, got '{value}'."
            )
        if code not in _SUPPORTED_CURRENCIES:
            raise ValidationError(
                f"Currency '{code}' is not supported. "
                f"Supported codes: {', '.join(sorted(_SUPPORTED_CURRENCIES))}."
            )
        return code

    @staticmethod
    def _parse_amount(value: float | int | str | Decimal) -> Decimal:
        try:
            dec = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValidationError(
                f"Cannot parse '{value}' as a numeric amount."
            )
        if dec <= 0:
            raise ValidationError("Amount must be greater than zero.")
        return dec

    @staticmethod
    def _fetch_rate(base: str, quote: str) -> tuple[Decimal, str]:
        """Fetch a single base→quote rate from Frankfurter.

        Returns ``(rate, date)`` where *rate* is a ``Decimal``.

        Raises ProviderError on HTTP or parse failures.
        """
        url = _RATE_PATH.format(base=base, quote=quote)
        try:
            resp = httpx.get(url, timeout=_TIMEOUT_SECONDS)
        except httpx.HTTPError as exc:
            logger.warning("Frankfurter API request failed: %s", exc)
            raise ProviderError(
                "The exchange-rate service is temporarily unavailable."
            ) from exc

        if resp.status_code != 200:
            logger.warning(
                "Frankfurter API returned status %d: %s",
                resp.status_code,
                resp.text[:200],
            )
            raise ProviderError(
                "The exchange-rate service returned an unexpected response."
            )

        try:
            data = resp.json()
        except ValueError as exc:
            logger.warning("Frankfurter API returned non-JSON: %s", resp.text[:200])
            raise ProviderError(
                "The exchange-rate service returned invalid data."
            ) from exc

        # Frankfurter v2 response: {"amount":1,"base":"USD","date":"…","rates":{"INR":…}}
        rates = data.get("rates")
        if not isinstance(rates, dict) or quote not in rates:
            logger.warning(
                "Frankfurter response missing rate for %s: %s", quote, data
            )
            raise ProviderError(
                "The exchange-rate service did not return the expected rate."
            )

        try:
            rate = Decimal(str(rates[quote]))
        except (InvalidOperation, ValueError) as exc:
            logger.warning("Cannot parse rate value: %s", rates[quote])
            raise ProviderError(
                "The exchange-rate service returned an unparseable rate."
            ) from exc

        rate_date = data.get("date", "unknown")
        return rate, str(rate_date)


# ── Module singleton ───────────────────────────────────────────────

_currency_service = CurrencyService()


def get_currency_service() -> CurrencyService:
    return _currency_service
