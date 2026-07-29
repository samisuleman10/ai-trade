import ai_trade.market_data as market_data
from ai_trade.market_data import OHLCVBar, fx_contract


def test_fx_contract_fields():
    contract = fx_contract("eur")
    assert contract.symbol == "EUR"
    assert contract.secType == "CASH"
    assert contract.exchange == "IDEALPRO"
    assert contract.currency == "USD"


def test_fx_contract_non_usd_quote():
    contract = fx_contract("EUR", "gbp")
    assert contract.symbol == "EUR"
    assert contract.currency == "GBP"


def test_fetch_passes_what_to_show(monkeypatch):
    captured = {}

    def fake_connect(self, host, port, client_id):
        self.connected.set()

    def fake_run(self):
        return None

    def fake_req(self, req_id, contract, end, duration, bar_size, what_to_show,
                 use_rth, format_date, keep_up_to_date, chart_options):
        captured["what_to_show"] = what_to_show
        captured["use_rth"] = use_rth
        self.bars.append(OHLCVBar("2026-01-05T00:00:00Z", 1.1, 1.1, 1.1, 1.1, -1.0))
        self.complete.set()

    monkeypatch.setattr(market_data._HistoricalDataClient, "connect", fake_connect)
    monkeypatch.setattr(market_data._HistoricalDataClient, "run", fake_run)
    monkeypatch.setattr(market_data._HistoricalDataClient, "reqHistoricalData", fake_req)
    monkeypatch.setattr(market_data._HistoricalDataClient, "isConnected", lambda self: False)

    bars = market_data.fetch_historical_bars(
        contract=fx_contract("EUR"), duration="1 D", bar_size="15 mins",
        use_rth=False, what_to_show="MIDPOINT",
    )
    assert captured["what_to_show"] == "MIDPOINT"
    assert captured["use_rth"] == 0
    assert bars[0].volume == -1.0


def test_fetch_default_what_to_show_is_trades(monkeypatch):
    captured = {}

    def fake_connect(self, host, port, client_id):
        self.connected.set()

    def fake_req(self, req_id, contract, end, duration, bar_size, what_to_show,
                 use_rth, format_date, keep_up_to_date, chart_options):
        captured["what_to_show"] = what_to_show
        self.bars.append(OHLCVBar("2026-01-05T00:00:00Z", 1.1, 1.1, 1.1, 1.1, 10.0))
        self.complete.set()

    monkeypatch.setattr(market_data._HistoricalDataClient, "connect", fake_connect)
    monkeypatch.setattr(market_data._HistoricalDataClient, "run", lambda self: None)
    monkeypatch.setattr(market_data._HistoricalDataClient, "reqHistoricalData", fake_req)
    monkeypatch.setattr(market_data._HistoricalDataClient, "isConnected", lambda self: False)

    market_data.fetch_historical_bars(
        contract=market_data.spy_contract(), duration="1 D", bar_size="15 mins",
    )
    assert captured["what_to_show"] == "TRADES"
