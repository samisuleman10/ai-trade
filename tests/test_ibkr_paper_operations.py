import pytest

from ai_trade.ibkr_paper import PaperExecutionError
from ai_trade.ibkr_paper_operations import PaperAccountOperations, PaperOrderRequest


def test_operations_reject_live_port() -> None:
    with pytest.raises(PaperExecutionError, match="7497"):
        PaperAccountOperations(expected_account="DU123", port=7496)


def test_operations_reject_live_account_identifier() -> None:
    with pytest.raises(PaperExecutionError, match="beginning with DU"):
        PaperAccountOperations(expected_account="U123")


def test_place_preview_does_not_connect() -> None:
    broker = PaperAccountOperations(expected_account="DU123")
    result = broker.place_order(
        PaperOrderRequest("SPY", "BUY", 1, "LMT", 500.0),
        transmit=False,
    )
    assert result["mode"] == "preview"


def test_cancel_and_cancel_all_default_to_preview() -> None:
    broker = PaperAccountOperations(expected_account="DU123")
    assert broker.cancel_order(10)["mode"] == "preview_cancel"
    assert broker.cancel_all()["mode"] == "preview_cancel_all"


def test_invalid_limit_order_is_rejected_before_connection() -> None:
    with pytest.raises(PaperExecutionError, match="limit_price"):
        PaperOrderRequest("SPY", "BUY", 1, "LMT").validate()
