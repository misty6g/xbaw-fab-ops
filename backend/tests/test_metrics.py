"""KPI and SPC math."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.metrics import (
    combine_lots,
    die_yield,
    line_yield,
    spc_summary,
    step_yield,
    throughput_wph,
    utilization,
    wafer_scrap_rate,
)


def test_die_yield_basic():
    assert die_yield(900, 1000) == pytest.approx(0.9)


def test_die_yield_empty_test_is_undefined():
    assert die_yield(0, 0) is None


def test_die_yield_rejects_impossible_counts():
    with pytest.raises(ValueError):
        die_yield(10, 4)
    with pytest.raises(ValueError):
        die_yield(-1, 4)


def test_wafer_scrap_rate():
    assert wafer_scrap_rate(1, 25) == pytest.approx(0.04)
    assert wafer_scrap_rate(0, 0) is None
    with pytest.raises(ValueError):
        wafer_scrap_rate(3, 2)


def test_line_yield_counts_scrapped_wafers_as_lost_die():
    # 24 wafers reach test, 1 was scrapped. 90% of tested die are good,
    # but the scrapped wafer never contributes die.
    assert line_yield(54000, 25, 2500) == pytest.approx(54000 / 62500)
    assert line_yield(0, 0, 2500) is None
    with pytest.raises(ValueError):
        line_yield(10, 1, 4)


def test_step_yield():
    assert step_yield(24, 25) == pytest.approx(0.96)
    assert step_yield(0, 0) is None
    with pytest.raises(ValueError):
        step_yield(5, 4)


def test_throughput_wafers_per_hour():
    assert throughput_wph(24, 2) == pytest.approx(12)
    assert throughput_wph(0, 4) == 0
    assert throughput_wph(10, 0) is None
    with pytest.raises(ValueError):
        throughput_wph(-1, 1)


def test_spc_known_series():
    stats = spc_summary([1, 2, 3], lsl=0, usl=4)
    assert stats.n == 3
    assert stats.mean == pytest.approx(2)
    assert stats.sigma == pytest.approx(1)
    assert stats.ucl == pytest.approx(5)
    assert stats.lcl == pytest.approx(-1)
    assert stats.cp == pytest.approx(4 / 6)
    assert stats.cpk == pytest.approx(2 / 3)
    assert stats.ooc == 0
    assert stats.oos == 0


def test_spc_flags_out_of_control_and_spec():
    # A single spike inflates sigma, so it can be out of spec and still inside ±3σ.
    stats = spc_summary([0, 0, 0, 10], lsl=0, usl=4)
    assert stats.oos == 1
    assert stats.ooc == 0

    shifted = spc_summary([0.0] * 20 + [100.0], lsl=-1, usl=5)
    assert shifted.oos == 1
    assert shifted.ooc == 1


def test_spc_zero_sigma_has_no_capability():
    stats = spc_summary([10, 10, 10], lsl=9, usl=11)
    assert stats.sigma == pytest.approx(0)
    assert stats.cp is None
    assert stats.cpk is None
    assert stats.ooc == 0
    assert stats.oos == 0


def test_spc_empty_and_single_point():
    empty = spc_summary([])
    assert empty.n == 0
    assert empty.mean is None
    single = spc_summary([5.0], lsl=4, usl=6)
    assert single.sigma is None
    assert single.cp is None
    assert single.oos == 0


def test_spc_one_sided_spec_skips_cp():
    stats = spc_summary([1, 2, 3], usl=4)
    assert stats.cp is None
    assert stats.cpk == pytest.approx((4 - 2) / 3)


def test_spc_rejects_inverted_limits():
    with pytest.raises(ValueError):
        spc_summary([1, 2, 3], lsl=5, usl=1)


def test_utilization_splits_the_window():
    start = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=2)
    states = [
        (start - timedelta(hours=1), "IDLE"),
        (start + timedelta(minutes=30), "EXECUTING"),
        (start + timedelta(hours=1), "IDLE"),
    ]
    assert utilization(states, start, end) == pytest.approx(0.25)


def test_utilization_unknown_prefix_is_not_productive():
    start = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=2)
    states = [
        (start + timedelta(minutes=30), "EXECUTING"),
        (start + timedelta(hours=1, minutes=30), "IDLE"),
    ]
    assert utilization(states, start, end) == pytest.approx(0.5)


def test_utilization_empty():
    start = datetime(2026, 9, 21, tzinfo=timezone.utc)
    assert utilization([], start, start + timedelta(hours=1)) is None
    assert utilization([(start, "EXECUTING")], start, start) is None


def test_combine_lots_rolls_up_die_and_line_yield():
    totals = combine_lots(
        [
            (25, 1, 54000, 60000, 2500),
            (25, 25, 0, 0, 2500),
        ]
    )
    assert totals.lots == 2
    assert totals.die_yield == pytest.approx(0.9)
    assert totals.scrap_rate == pytest.approx(26 / 50)
    assert totals.line_yield == pytest.approx(54000 / (50 * 2500))
