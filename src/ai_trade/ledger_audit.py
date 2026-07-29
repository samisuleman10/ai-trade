"""Per-trade correctness checks that apply to every strategy's ledger.

``strategy_04_audit`` verifies that a trade obeyed Strategy 04's *written
rules*, which needs signal evidence -- zone geometry, the ATR reference,
the penetration fraction -- that only Strategy 04 records. Nothing in that
module can run against Strategy 01, 02 or 03.

This module checks a different and narrower thing: that the recorded ledger
row is *internally consistent with itself*. Every strategy in this
repository executes through ``backtest_strategy_01.run_backtest`` and emits
the same ``fixed_trades.csv`` columns, so these checks need no signal
evidence at all and run on every result directory that exists today.

A failing check means the ledger disagrees with its own arithmetic -- the
backtest is wrong, not that the trade was unprofitable.

Every function here is pure: no file reads, no printing, no clock. Reading
the ledger and resolving the contract multiplier is
``ledger_audit_datasets``' job.

``CheckResult`` is defined here and imported by ``strategy_04_audit``, so
the two audits do not merely have the same shape, they emit the same type.
Both feed one ``trade_audit`` dataset per run, and a Strategy 04 run's
entry is the concatenation of both check lists.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Sequence

UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# Money is recorded to the cent, so a discrepancy worth reporting is far
# larger than this; the headroom is for float accumulation, not for
# rounding away a real difference. Measured across all 4,948 recorded
# trades, the largest observed deviation is nine orders of magnitude below
# this bound.
MONEY_TOLERANCE = 1e-4

# result_r is recorded to three decimals in some producers, so its bound is
# looser than the money bound by necessity: a value written as -1.079 cannot
# be reproduced more precisely than 5e-4 from the fields beside it.
RESULT_R_TOLERANCE = 1e-3


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    passed: bool
    expected: str
    actual: str


@dataclass(frozen=True)
class LedgerRow:
    """One row of ``fixed_trades.csv`` (or ``rrms_trades.csv``).

    These are exactly the columns ``backtest_strategy_01.Trade`` writes,
    minus ``rrms_tier``, which no check below examines. Numbers are already
    parsed: this module never sees a CSV string.
    """

    decision_timestamp: str
    entry_timestamp: str
    exit_timestamp: str
    side: str
    quantity: int
    entry_price: float
    stop_price: float
    target_price: float
    exit_price: float
    exit_reason: str
    gross_pnl: float
    costs: float
    net_pnl: float
    result_r: float
    equity_after: float


def _check(check_id: str, passed: bool, expected: object, actual: object) -> CheckResult:
    return CheckResult(check_id, passed, str(expected), str(actual))


def _close(left: float, right: float, tolerance: float) -> bool:
    return abs(left - right) <= tolerance


def _parse(timestamp: str) -> Optional[datetime]:
    """Parse a recorded UTC timestamp, or ``None`` if it is not one.

    Returning ``None`` rather than raising keeps a malformed timestamp a
    failed check on one trade instead of an exception that abandons the
    whole run's audit.
    """

    try:
        return datetime.strptime(timestamp, UTC_FORMAT).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def check_net_pnl(row: LedgerRow) -> CheckResult:
    """Net P&L is gross P&L less the costs recorded beside it.

    ``run_backtest`` computes ``net_pnl = gross_pnl - costs`` and writes all
    three, so this is the ledger being asked whether it agrees with itself.
    It catches the specific and expensive error of reporting gross results
    as net: commissions and slippage are the difference between a strategy
    that is worth trading and one that is not.
    """

    expected = row.gross_pnl - row.costs
    return _check(
        "net_pnl",
        _close(expected, row.net_pnl, MONEY_TOLERANCE),
        expected,
        row.net_pnl,
    )


def check_equity_chain(row: LedgerRow, previous: Optional[LedgerRow]) -> CheckResult:
    """Each row's closing equity is the previous row's plus this row's P&L.

    The equity column is what every drawdown, every equity curve and every
    ending-balance headline is built from. A single row whose P&L never
    reached the balance -- or was applied twice -- shifts the whole curve
    from that point on while each row still looks correct in isolation.

    The first row has no predecessor inside the ledger, so there is nothing
    to compare it against here. It passes, and says why: the alternative
    would be to compare it against a starting equity this module does not
    have (it lives in ``fixed_summary.json``), and inventing one would be
    worse than declining to check.
    """

    if previous is None:
        return _check(
            "equity_chain",
            True,
            "no predecessor: first ledger row",
            row.equity_after,
        )
    expected = previous.equity_after + row.net_pnl
    return _check(
        "equity_chain",
        _close(expected, row.equity_after, MONEY_TOLERANCE),
        expected,
        row.equity_after,
    )


def check_result_r(row: LedgerRow, contract_multiplier: Optional[float]) -> CheckResult:
    """R is net P&L divided by the risk the position was actually sized to.

    ``result_r`` is the headline number on every dashboard row and in every
    summary statistic. ``run_backtest`` computes it as
    ``net_pnl / planned_risk`` with
    ``planned_risk = quantity * |entry_price - stop_price| * contract_multiplier``,
    so a mismatch means the ledger disagrees with itself.

    The multiplier is not optional decoration. Gold futures (MGC) move ten
    dollars per point, and every one of the 35 MGC trades in this repository
    fails this check by exactly 10x when it is omitted -- 35 false
    accusations against a correct backtest. It is passed in rather than
    read here because reading it means opening ``backtest_report.json``,
    and this module does no I/O.

    ``contract_multiplier=None`` means the run's multiplier could not be
    established at all. That is reported as a FAILED check whose expected
    value says "inconclusive", never as a pass: an unverifiable claim and a
    verified one must not look the same in the published dataset.

    Risk is a distance, so the absolute value is deliberate: a short's stop
    sits above its entry. A zero planned risk (a stop at the entry, or a
    zero quantity) makes R undefined and fails -- that is a defect in the
    ledger, not a trade to wave through.
    """

    if contract_multiplier is None:
        return _check(
            "result_r",
            False,
            "inconclusive: this run records no contract multiplier, so planned risk cannot be derived",
            row.result_r,
        )

    planned_risk = abs(row.entry_price - row.stop_price) * row.quantity * contract_multiplier
    if planned_risk <= 0:
        return _check(
            "result_r",
            False,
            "a positive planned risk (quantity x |entry - stop| x multiplier)",
            planned_risk,
        )
    expected = row.net_pnl / planned_risk
    return _check(
        "result_r",
        _close(expected, row.result_r, RESULT_R_TOLERANCE),
        expected,
        row.result_r,
    )


def check_exit_after_entry(row: LedgerRow) -> CheckResult:
    """A trade cannot close before it opens.

    Equality is allowed: ``_exit_trade`` can resolve a stop or a target
    inside the entry bar itself, which records the same timestamp on both
    ends. Only a strictly earlier exit is impossible, and it is the
    signature of an off-by-one in bar indexing -- an exit read from a bar
    before the entry, which is the ledger reporting a fill the strategy
    could not have received.
    """

    entry_at = _parse(row.entry_timestamp)
    exit_at = _parse(row.exit_timestamp)
    if entry_at is None or exit_at is None:
        return _check(
            "exit_after_entry",
            False,
            "two timestamps in " + UTC_FORMAT,
            "%s -> %s" % (row.entry_timestamp, row.exit_timestamp),
        )
    return _check(
        "exit_after_entry",
        exit_at >= entry_at,
        "exit at or after " + row.entry_timestamp,
        row.exit_timestamp,
    )


def check_quantity(row: LedgerRow) -> CheckResult:
    """Position size is a positive count; direction lives in ``side``.

    ``run_backtest`` skips any signal that sizes to fewer than one unit, so
    a recorded zero means a trade was written with no position behind it --
    its P&L came from somewhere other than its size. A negative quantity is
    worse: direction is already carried by ``side``, so a signed size
    double-counts it and flips the sign of the P&L a reader would derive.
    """

    return _check("quantity", row.quantity > 0, "a positive quantity", row.quantity)


def check_level_sides(row: LedgerRow) -> CheckResult:
    """The stop and the target sit on the correct sides of the entry.

    A long risks a fall and targets a rise (``stop < entry < target``); a
    short is the mirror. Swapping them is not a rounding error, it is a
    trade whose recorded risk is its reward: every R, every win rate and
    every profit factor derived from that row is inverted, and nothing else
    in the ledger would show it.

    The comparisons are strict. A stop or target exactly at the entry is a
    zero-distance trade the engine cannot size (``risk_per_unit <= 0`` is
    skipped upstream), so admitting equality here would admit a row that
    makes R undefined.
    """

    if row.side == "long":
        passed = row.stop_price < row.entry_price < row.target_price
        expected = "stop < entry < target"
    elif row.side == "short":
        passed = row.target_price < row.entry_price < row.stop_price
        expected = "target < entry < stop"
    else:
        return _check("level_sides", False, "side to be 'long' or 'short'", row.side)

    return _check(
        "level_sides",
        passed,
        expected,
        "stop=%s entry=%s target=%s" % (row.stop_price, row.entry_price, row.target_price),
    )


def audit_ledger_row(
    row: LedgerRow,
    previous: Optional[LedgerRow],
    contract_multiplier: Optional[float],
) -> List[CheckResult]:
    """Run every ledger check for one trade, in stable order."""

    return [
        check_net_pnl(row),
        check_equity_chain(row, previous),
        check_result_r(row, contract_multiplier),
        check_exit_after_entry(row),
        check_quantity(row),
        check_level_sides(row),
    ]


def audit_ledger(
    rows: Sequence[LedgerRow],
    contract_multiplier: Optional[float],
) -> List[List[CheckResult]]:
    """Audit a whole ledger, chaining each row to the one recorded before it.

    Returns one check list per row, in ledger order, so a caller can zip
    the results straight onto the trade ids it built from the same rows in
    the same order.
    """

    results: List[List[CheckResult]] = []
    previous: Optional[LedgerRow] = None
    for row in rows:
        results.append(audit_ledger_row(row, previous, contract_multiplier))
        previous = row
    return results
