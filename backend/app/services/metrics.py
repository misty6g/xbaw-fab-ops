"""Pure KPI and SPC math.

These functions do not touch the database so yield, scrap, throughput, and
control-limit calculations can be tested directly.

SPC notes
---------
Sigma is the sample standard deviation (Bessel's correction, n - 1).
Control limits are an individuals-chart approximation: mean ± 3σ.
This is not a full I-MR chart and it does not estimate sigma from the
moving range. Cp needs both spec limits and a non-zero sigma. Cpk uses
every spec limit that is present. Points exactly on a limit are in control
and in spec.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


def die_yield(good_die: int, tested_die: int) -> float | None:
    """Good die divided by die that reached test."""
    if tested_die < 0 or good_die < 0:
        raise ValueError("die counts must be non-negative")
    if good_die > tested_die:
        raise ValueError("good_die cannot exceed tested_die")
    if tested_die == 0:
        return None
    return good_die / tested_die


def wafer_scrap_rate(scrap_wafers: int, wafers_started: int) -> float | None:
    """Wafers scrapped divided by wafers started on the lot or population."""
    if scrap_wafers < 0 or wafers_started < 0:
        raise ValueError("wafer counts must be non-negative")
    if scrap_wafers > wafers_started:
        raise ValueError("scrap_wafers cannot exceed wafers_started")
    if wafers_started == 0:
        return None
    return scrap_wafers / wafers_started


def line_yield(good_die: int, wafers_started: int, die_per_wafer: int) -> float | None:
    """Good die divided by die opportunities, counting scrapped wafers as lost.

    ``die_per_wafer`` is the route's theoretical die count. Wafers that never
    reach test contribute zero good die and still sit in the denominator.
    """
    if good_die < 0 or wafers_started < 0 or die_per_wafer < 0:
        raise ValueError("counts must be non-negative")
    opportunities = wafers_started * die_per_wafer
    if opportunities == 0:
        return None
    if good_die > opportunities:
        raise ValueError("good_die cannot exceed die opportunities")
    return good_die / opportunities


def step_yield(wafers_out: int, wafers_in: int) -> float | None:
    """Wafers leaving a step divided by wafers that entered it."""
    if wafers_out < 0 or wafers_in < 0:
        raise ValueError("wafer counts must be non-negative")
    if wafers_out > wafers_in:
        raise ValueError("wafers_out cannot exceed wafers_in")
    if wafers_in == 0:
        return None
    return wafers_out / wafers_in


def throughput_wph(wafers: int, window_hours: float) -> float | None:
    """Wafers per hour across a wall-clock window."""
    if wafers < 0:
        raise ValueError("wafers must be non-negative")
    if window_hours < 0:
        raise ValueError("window_hours must be non-negative")
    if window_hours == 0:
        return None
    return wafers / window_hours


@dataclass(frozen=True)
class SpcSummary:
    n: int
    mean: float | None
    sigma: float | None
    ucl: float | None
    lcl: float | None
    cp: float | None
    cpk: float | None
    ooc: int
    oos: int


def _sample_sigma(values: list[float], mean: float) -> float | None:
    n = len(values)
    if n < 2:
        return None
    variance = sum((value - mean) ** 2 for value in values) / (n - 1)
    return math.sqrt(variance)


def spc_summary(
    values: list[float],
    lsl: float | None = None,
    usl: float | None = None,
) -> SpcSummary:
    """Mean, sample sigma, ±3σ limits, Cp/Cpk, and exception counts."""
    n = len(values)
    if n == 0:
        return SpcSummary(0, None, None, None, None, None, None, 0, 0)

    mean = sum(values) / n
    sigma = _sample_sigma(values, mean)
    if sigma is None:
        ucl = lcl = None
    else:
        ucl = mean + 3 * sigma
        lcl = mean - 3 * sigma

    cp: float | None = None
    cpk: float | None = None
    if sigma is not None and sigma > 0:
        if lsl is not None and usl is not None:
            if usl < lsl:
                raise ValueError("usl must be greater than or equal to lsl")
            cp = (usl - lsl) / (6 * sigma)
        sides: list[float] = []
        if usl is not None:
            sides.append((usl - mean) / (3 * sigma))
        if lsl is not None:
            sides.append((mean - lsl) / (3 * sigma))
        if sides:
            cpk = min(sides)

    ooc = 0
    oos = 0
    for value in values:
        if ucl is not None and lcl is not None and (value > ucl or value < lcl):
            ooc += 1
        if (usl is not None and value > usl) or (lsl is not None and value < lsl):
            oos += 1

    return SpcSummary(n, mean, sigma, ucl, lcl, cp, cpk, ooc, oos)


def point_flags(
    value: float,
    lsl: float | None,
    usl: float | None,
    lcl: float | None,
    ucl: float | None,
) -> tuple[bool, bool]:
    """Return ``(out_of_control, out_of_spec)`` for one reading."""
    ooc = ucl is not None and lcl is not None and (value > ucl or value < lcl)
    oos = (usl is not None and value > usl) or (lsl is not None and value < lsl)
    return ooc, oos


def utilization(
    states: list[tuple[datetime, str]],
    window_start: datetime,
    window_end: datetime,
    productive: str = "EXECUTING",
) -> float | None:
    """Fraction of the window spent in ``productive``.

    ``states`` is a chronological list of ``(timestamp, state)``. The state
    in effect at ``window_start`` is the latest sample at or before it. Time
    before the first sample is treated as not productive.
    """
    if window_end <= window_start:
        return None
    if not states:
        return None

    ordered = sorted(states, key=lambda item: item[0])
    state = None
    future: list[tuple[datetime, str]] = []
    for timestamp, name in ordered:
        if timestamp <= window_start:
            state = name
        elif timestamp < window_end:
            future.append((timestamp, name))

    if state is None:
        state = ""

    productive_seconds = 0.0
    cursor = window_start
    for timestamp, name in future:
        if state == productive:
            productive_seconds += (timestamp - cursor).total_seconds()
        cursor = timestamp
        state = name
    if state == productive:
        productive_seconds += (window_end - cursor).total_seconds()

    total = (window_end - window_start).total_seconds()
    if total <= 0:
        return None
    return productive_seconds / total


@dataclass(frozen=True)
class YieldTotals:
    lots: int
    wafers_started: int
    scrap_wafers: int
    good_die: int
    tested_die: int
    die_opportunities: int

    @property
    def die_yield(self) -> float | None:
        return die_yield(self.good_die, self.tested_die)

    @property
    def scrap_rate(self) -> float | None:
        return wafer_scrap_rate(self.scrap_wafers, self.wafers_started)

    @property
    def line_yield(self) -> float | None:
        if self.die_opportunities == 0:
            return None
        if self.good_die > self.die_opportunities:
            raise ValueError("good_die cannot exceed die opportunities")
        return self.good_die / self.die_opportunities


def combine_lots(rows: list[tuple[int, int, int, int, int]]) -> YieldTotals:
    """Sum ``(wafers, scrap, good, tested, die_per_wafer)`` rows."""
    wafers = scrap = good = tested = opportunities = 0
    for wafer_count, scrap_wafers, good_die, tested_die, die_per_wafer in rows:
        if scrap_wafers > wafer_count:
            raise ValueError("scrap_wafers cannot exceed wafers_started")
        if good_die > tested_die:
            raise ValueError("good_die cannot exceed tested_die")
        wafers += wafer_count
        scrap += scrap_wafers
        good += good_die
        tested += tested_die
        opportunities += wafer_count * die_per_wafer
    return YieldTotals(
        lots=len(rows),
        wafers_started=wafers,
        scrap_wafers=scrap,
        good_die=good,
        tested_die=tested,
        die_opportunities=opportunities,
    )
