"""Currencies: rounding per currency and parsing the rates service."""

from decimal import Decimal

import httpx
import pytest

from storefront.currency import CURRENCIES, RatesError, fetch_rates, to_local


def test_pkr_rounds_to_whole_rupees_and_others_to_cents() -> None:
    assert to_local(Decimal("279.00"), Decimal("281.4"), "PKR") == Decimal("78511")
    assert to_local(Decimal("279.00"), Decimal("0.92"), "EUR") == Decimal("256.68")
    assert CURRENCIES["PKR"].decimals == 0 and CURRENCIES["USD"].symbol == "$"


def client(status: int, body: object) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body)))


def test_fetch_keeps_only_supported_currencies() -> None:
    body = {"result": "success", "rates": {"USD": 1, "PKR": 281.4, "EUR": 0.92, "JPY": 150}}
    assert fetch_rates(client(200, body)) == {
        "USD": Decimal("1"),
        "PKR": Decimal("281.4"),
        "EUR": Decimal("0.92"),
    }


@pytest.mark.parametrize(("status", "body"), [(500, {}), (200, {"result": "error"})])
def test_fetch_failures_raise(status: int, body: object) -> None:
    with pytest.raises(RatesError):
        fetch_rates(client(status, body))
