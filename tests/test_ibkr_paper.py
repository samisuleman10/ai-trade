from decimal import Decimal

import pytest

from ai_trade.ibkr_paper import BracketOrderRequest, PaperBroker, PaperExecutionError, build_bracket_orders


def request(**overrides) -> BracketOrderRequest:
    values = {
        "symbol": "SPY",
        "quantity": 10,
        "side": "BUY",
        "entry_type": "LMT",
        "limit_price": 600.0,
        "stop_price": 595.0,
        "target_price": 610.0,
    }
    values.update(overrides)
    return BracketOrderRequest(**values)


def test_paper_broker_rejects_live_port() -> None:
    with pytest.raises(PaperExecutionError, match="7497"):
        PaperBroker(expected_account="DU123456", port=7496)


def test_paper_broker_rejects_non_paper_account() -> None:
    with pytest.raises(PaperExecutionError, match="beginning with DU"):
        PaperBroker(expected_account="U123456")


def test_preview_never_connects_or_transmits() -> None:
    result = PaperBroker(expected_account="DU123456").place_bracket(request(), transmit=False)
    assert result["mode"] == "preview"


def test_build_bracket_transmits_only_final_child() -> None:
    orders = build_bracket_orders(request(), account="DU123456", parent_order_id=100, transmit=True)
    assert [order_id for order_id, _ in orders] == [100, 101, 102]
    assert [order.transmit for _, order in orders] == [False, False, True]
    assert orders[0][1].totalQuantity == Decimal(10)
    assert orders[1][1].parentId == 100
    assert orders[2][1].parentId == 100


def test_long_limit_bracket_requires_prices_in_order() -> None:
    with pytest.raises(PaperExecutionError, match="stop < entry < target"):
        request(stop_price=605.0).validate()
