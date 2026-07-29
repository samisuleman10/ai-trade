"""Unit tests for the strategy-independent ledger checks.

Every check here must be shown to FAIL on a corrupted ledger, not merely to
pass on a clean one. A check that cannot fail is worse than no check: it
reports "audited" over evidence it never examined.
"""

import pytest

from ai_trade.ledger_audit import (
    CheckResult,
    LedgerRow,
    audit_ledger,
    audit_ledger_row,
    check_equity_chain,
    check_exit_after_entry,
    check_level_sides,
    check_net_pnl,
    check_quantity,
    check_result_r,
)

# A clean long trade, every field derived from the arithmetic
# backtest_strategy_01.run_backtest actually performs.
QUANTITY = 100
ENTRY = 437.94
STOP = 436.95
TARGET = ENTRY + (ENTRY - STOP)
PLANNED_RISK = abs(ENTRY - STOP) * QUANTITY
GROSS_PNL = 98.0
COSTS = 1.0
NET_PNL = GROSS_PNL - COSTS
RESULT_R = NET_PNL / PLANNED_RISK
STARTING_EQUITY = 100_000.0


def _row(**overrides) -> LedgerRow:
    values = dict(
        decision_timestamp="2021-08-03T14:30:00Z",
        entry_timestamp="2021-08-03T14:30:00Z",
        exit_timestamp="2021-08-03T15:45:00Z",
        side="long",
        quantity=QUANTITY,
        entry_price=ENTRY,
        stop_price=STOP,
        target_price=TARGET,
        exit_price=TARGET,
        exit_reason="target",
        gross_pnl=GROSS_PNL,
        costs=COSTS,
        net_pnl=NET_PNL,
        result_r=RESULT_R,
        equity_after=STARTING_EQUITY + NET_PNL,
    )
    values.update(overrides)
    return LedgerRow(**values)


def _result(results, check_id: str) -> CheckResult:
    return next(item for item in results if item.check_id == check_id)


# --- net_pnl == gross_pnl - costs ------------------------------------------


def test_net_pnl_matching_gross_minus_costs_passes():
    assert check_net_pnl(_row()).passed is True


def test_net_pnl_that_ignores_costs_fails():
    """Recording gross as net hides every dollar the broker took."""

    assert check_net_pnl(_row(net_pnl=GROSS_PNL)).passed is False


def test_net_pnl_with_the_sign_of_costs_reversed_fails():
    assert check_net_pnl(_row(net_pnl=GROSS_PNL + COSTS)).passed is False


def test_net_pnl_off_by_one_cent_fails():
    """The money tolerance is 1e-4: a cent is a real discrepancy."""

    assert check_net_pnl(_row(net_pnl=NET_PNL + 0.01)).passed is False


def test_net_pnl_within_float_noise_passes():
    assert check_net_pnl(_row(net_pnl=NET_PNL + 1e-9)).passed is True


# --- the equity chain -------------------------------------------------------


def test_equity_chain_links_to_the_previous_row():
    first = _row()
    second = _row(equity_after=first.equity_after + NET_PNL)
    assert check_equity_chain(second, first).passed is True


def test_a_broken_equity_chain_fails():
    """A trade whose P&L never reached the balance is a lost trade."""

    first = _row()
    second = _row(equity_after=first.equity_after)
    assert check_equity_chain(second, first).passed is False


def test_equity_chain_ignoring_a_deducted_cost_fails():
    first = _row()
    second = _row(equity_after=first.equity_after + GROSS_PNL)
    assert check_equity_chain(second, first).passed is False


def test_the_first_row_has_no_predecessor_and_says_so():
    """It cannot be checked; it must not silently read as verified."""

    result = check_equity_chain(_row(), None)
    assert result.passed is True
    assert "no predecessor" in result.expected


# --- result_r, with the contract multiplier --------------------------------


def test_result_r_matches_net_pnl_over_planned_risk():
    assert check_result_r(_row(), 1.0).passed is True


def test_result_r_off_by_ten_percent_fails():
    assert check_result_r(_row(result_r=RESULT_R * 1.1), 1.0).passed is False


def test_result_r_derived_from_gross_instead_of_net_fails():
    """Costs are real: R measured before them overstates every trade."""

    assert check_result_r(_row(result_r=GROSS_PNL / PLANNED_RISK), 1.0).passed is False


def test_result_r_sized_with_the_wrong_quantity_fails():
    assert check_result_r(_row(quantity=QUANTITY * 2), 1.0).passed is False


def test_result_r_with_no_risk_distance_fails():
    """A stop at the entry makes R undefined, which is a defect, not a pass."""

    assert check_result_r(_row(stop_price=ENTRY), 1.0).passed is False


def test_result_r_with_zero_quantity_fails():
    assert check_result_r(_row(quantity=0), 1.0).passed is False


def test_short_result_r_uses_the_absolute_risk_distance():
    """A short's stop sits above its entry; risk is a distance, not a signed gap."""

    entry = 437.94
    stop = entry + 1.0
    planned = 1.0 * QUANTITY
    row = _row(
        side="short",
        entry_price=entry,
        stop_price=stop,
        target_price=entry - 1.0,
        exit_reason="stop",
        exit_price=stop,
        gross_pnl=-104.0,
        costs=1.0,
        net_pnl=-105.0,
        result_r=-105.0 / planned,
    )
    assert check_result_r(row, 1.0).passed is True


def test_a_multiplied_instrument_needs_its_multiplier():
    """Gold futures move ten dollars per point; R is scaled by that.

    Omitting the multiplier produced 35 false failures across the MGC runs,
    every one of them exactly 10x out. This is that discrepancy in miniature.
    """

    planned = abs(ENTRY - STOP) * QUANTITY * 10.0
    row = _row(result_r=NET_PNL / planned)
    assert check_result_r(row, 10.0).passed is True
    assert check_result_r(row, 1.0).passed is False


def test_an_unknown_multiplier_is_inconclusive_not_a_pass():
    """A run whose multiplier cannot be read has not been verified.

    Defaulting to 1.0 here would silently pass every equity run and
    silently fail every futures run, and both outcomes would be reported
    with the same confidence as a real check.
    """

    result = check_result_r(_row(), None)
    assert result.passed is False
    assert "inconclusive" in result.expected


# --- exit_timestamp >= entry_timestamp -------------------------------------


def test_an_exit_after_its_entry_passes():
    assert check_exit_after_entry(_row()).passed is True


def test_an_exit_on_the_entry_bar_passes():
    """Entry and exit inside the same bar is legal; time travel is not."""

    assert check_exit_after_entry(_row(exit_timestamp="2021-08-03T14:30:00Z")).passed is True


def test_an_exit_before_its_entry_fails():
    assert check_exit_after_entry(_row(exit_timestamp="2021-08-03T13:00:00Z")).passed is False


def test_an_unparseable_timestamp_fails_rather_than_raising():
    assert check_exit_after_entry(_row(exit_timestamp="yesterday")).passed is False


# --- quantity > 0 -----------------------------------------------------------


def test_a_positive_quantity_passes():
    assert check_quantity(_row()).passed is True


def test_a_zero_quantity_fails():
    assert check_quantity(_row(quantity=0)).passed is False


def test_a_negative_quantity_fails():
    """Direction is carried by 'side'; a negative size is double-counted."""

    assert check_quantity(_row(quantity=-100)).passed is False


# --- stop / entry / target ordering ----------------------------------------


def test_a_long_with_its_stop_below_and_target_above_passes():
    assert check_level_sides(_row()).passed is True


def test_a_long_with_stop_and_target_flipped_fails():
    assert check_level_sides(_row(stop_price=TARGET, target_price=STOP)).passed is False


def test_a_short_with_its_stop_above_and_target_below_passes():
    row = _row(side="short", stop_price=ENTRY + 1.0, target_price=ENTRY - 1.0)
    assert check_level_sides(row).passed is True


def test_a_short_with_stop_and_target_flipped_fails():
    row = _row(side="short", stop_price=ENTRY - 1.0, target_price=ENTRY + 1.0)
    assert check_level_sides(row).passed is False


def test_a_stop_exactly_at_the_entry_fails():
    """Zero risk is not a trade the engine can size."""

    assert check_level_sides(_row(stop_price=ENTRY)).passed is False


def test_an_unrecognised_side_fails():
    assert check_level_sides(_row(side="flat")).passed is False


# --- the audit as a whole ---------------------------------------------------


def test_a_clean_row_passes_every_check():
    results = audit_ledger_row(_row(), None, 1.0)
    assert [result.check_id for result in results] == [
        "net_pnl",
        "equity_chain",
        "result_r",
        "exit_after_entry",
        "quantity",
        "level_sides",
    ]
    assert all(result.passed for result in results), [r for r in results if not r.passed]


def test_audit_ledger_chains_each_row_to_the_one_before_it():
    first = _row()
    second = _row(equity_after=first.equity_after + NET_PNL)
    third = _row(equity_after=first.equity_after)  # skips second's P&L
    results = audit_ledger([first, second, third], 1.0)
    assert len(results) == 3
    assert _result(results[0], "equity_chain").passed is True
    assert _result(results[1], "equity_chain").passed is True
    assert _result(results[2], "equity_chain").passed is False


def test_audit_ledger_of_an_empty_ledger_is_empty():
    assert audit_ledger([], 1.0) == []


@pytest.mark.parametrize(
    "overrides,expected_check",
    [
        ({"net_pnl": GROSS_PNL}, "net_pnl"),
        ({"equity_after": STARTING_EQUITY}, "equity_chain"),
        ({"result_r": RESULT_R * 2}, "result_r"),
        ({"exit_timestamp": "2021-08-03T00:00:00Z"}, "exit_after_entry"),
        ({"quantity": 0}, "quantity"),
        ({"stop_price": TARGET, "target_price": STOP}, "level_sides"),
    ],
)
def test_each_corruption_is_caught_by_its_own_check(overrides, expected_check):
    """One mutation must trip the check that owns that field."""

    predecessor = _row(equity_after=STARTING_EQUITY)
    results = audit_ledger_row(_row(**overrides), predecessor, 1.0)
    failed = [result.check_id for result in results if not result.passed]
    assert expected_check in failed, results


def test_the_clean_row_the_corruptions_are_derived_from_passes():
    """Without this, every corruption test above could be passing vacuously."""

    predecessor = _row(equity_after=STARTING_EQUITY)
    results = audit_ledger_row(_row(), predecessor, 1.0)
    assert all(result.passed for result in results), [r for r in results if not r.passed]
