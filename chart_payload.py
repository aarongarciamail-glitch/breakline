#!/usr/bin/env python3
"""Additive chart fields for Breakline's publisher.

live.py and publish.py live on the Mac mini (the pine study points at
~/breakline/rules.yaml). They are not in this git repo. Do not change
entry, exit, or sizing logic in live.py. This module only shapes the
JSON the page draws.

Wire-in, where publish.py builds each stock's "chart" object::

    from chart_payload import enrich_chart, honest_exit

    chart = enrich_chart(
        chart,
        bars=session_bars,          # 5-min OHLC + volume, bar OPEN times
        option=option_payload,      # prints the bot already records
        shadows=skipped_setups,     # or None
        strategy_b=strategy_b_marks,
        trade=trade_levels,
        vwap=vwap_values,           # optional; the page also computes VWAP
    )
    note = honest_exit(note, option_result_pct)

Keep writing `times` and `closes`. Old pages ignore the new keys. This
page uses bars when they exist and falls back to closes when they don't.

Clock convention, same as today's data.json: `times[i]` / `bars[i].t`
is the bar OPEN ("9:30" is 9:30–9:35). A mark with index i happened at
that bar's close. The page draws the mark five minutes later, so a
09:50 buy sits on 9:50.

After pulling this file, restart the 5-minute publisher so the import
and the new fields actually ship. The page itself updates from GitHub
Pages and does not need a publisher restart.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence


def _num(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    return float(v)


def _clock(t: Any) -> str:
    """'09:30', '9:30', '9:30:00' -> '9:30'. Hour is unpadded, like data.json."""
    parts = str(t).strip().split(":")
    if len(parts) < 2:
        raise ValueError(f"bad bar time {t!r}")
    return f"{int(parts[0])}:{int(parts[1]):02d}"


def _sgn(pct: float) -> str:
    n = float(pct)
    if abs(n) < 0.05:
        return "0%"
    sign = "+" if n > 0 else "−"
    text = f"{abs(n):.1f}".rstrip("0").rstrip(".")
    return sign + text + "%"


def enrich_chart(
    chart: Optional[Mapping[str, Any]] = None,
    bars: Optional[Sequence[Mapping[str, Any]]] = None,
    option: Optional[Mapping[str, Any]] = None,
    shadows: Optional[Sequence[Mapping[str, Any]]] = None,
    strategy_b: Optional[Sequence[Mapping[str, Any]]] = None,
    trade: Optional[Mapping[str, Any]] = None,
    vwap: Optional[Sequence[Any]] = None,
) -> dict:
    """Copy `chart` and add fields. Never drops times, closes, box, lines, or marks.

    bars: each item has t (bar open), o, h, l, c, and v (volume, or null).
    option: {"contract", "points": [{"t", "px"}], "best_pct", "floor_pct", "trade_pct"}.
      t on a point is the real clock time of the print ("10:05"), not a bar open.
    shadows: skipped / paper-only setups. {"t" or "i", "price", "label", "note"}.
      i uses the same bar index as marks. t is a real clock time.
    strategy_b: same shape, for the strategy B paper test.
    trade: {"entry", "entry_t", "stop", "be", "be_t", "exit", "exit_t", "exit_label"}.
      Prices are the stock. be is the stock entry after a third is sold, not
      break-even on the option. Omit be when no third has been sold.
    vwap: one value per bar, or omit and let the page compute it from bars.
    """
    out = dict(chart or {})
    if bars is not None:
        clean = []
        for b in bars:
            item = {
                "t": _clock(b.get("t") if b.get("t") is not None else b.get("time")),
                "o": _num(b.get("o")),
                "h": _num(b.get("h")),
                "l": _num(b.get("l")),
                "c": _num(b.get("c")),
                "v": None if b.get("v") is None else _num(b.get("v")),
            }
            clean.append(item)
        out["bars"] = clean
        # Same clocks and closes an older page already understands.
        out["times"] = [b["t"] for b in clean]
        out["closes"] = [b["c"] for b in clean]
        out["opens"] = [b["o"] for b in clean]
        out["highs"] = [b["h"] for b in clean]
        out["lows"] = [b["l"] for b in clean]
        out["volumes"] = [b["v"] for b in clean]
    if option is not None:
        out["option"] = dict(option)
    if shadows is not None:
        out["shadows"] = [dict(x) for x in shadows]
    if strategy_b is not None:
        out["strategy_b"] = [dict(x) for x in strategy_b]
    if trade is not None:
        out["trade"] = dict(trade)
    if vwap is not None:
        out["vwap"] = [None if v is None else float(v) for v in vwap]
    return out


_BE = re.compile(
    r"break-even|back to the (?:buy|entry) price|came back to the buy price",
    re.I,
)


def honest_exit(reason: Any, option_pct: Optional[float] = None) -> str:
    """Say what the stop did. Does not change the stop.

    A "break-even" stop is the stock's entry price after the first third
    is sold. The option can still finish down. QQQ on 2026-11-24 came
    back to 641.98 and the option lost 36%. Calling that break-even is
    how the label lied.
    """
    text = "" if reason is None else str(reason)
    if not text or "not break-even on the option" in text.lower():
        return text
    if not _BE.search(text):
        return text
    m = re.search(r"(\d+\.\d+)", text)
    where = f"back at {m.group(1)}" if m else "back at its entry"
    opt = "" if option_pct is None else " Option " + _sgn(option_pct) + "."
    return f"Stock {where}. The stop is the stock entry, not break-even on the option.{opt}"


def honest_plan(text: Any) -> str:
    """The plan line 'Stop to break-even' means the stock's entry, not a flat option."""
    s = "" if text is None else str(text)
    return re.sub(
        r"stop to break-even",
        "then the stop is the stock's entry, not flat on the option",
        s,
        flags=re.I,
    )


if __name__ == "__main__":
    chart = {
        "symbol": "QQQ",
        "times": ["9:30", "9:35"],
        "closes": [1.0, 2.0],
        "box": {"hi": 3, "lo": 1},
        "lines": [{"name": "S1", "price": 4}],
        "marks": [{"i": 1, "kind": "buy", "label": "BUY"}],
    }
    bars = [
        {"t": "09:30", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100},
        {"t": "9:35", "o": 1.5, "h": 2.2, "l": 1.4, "c": 2.0, "v": 80},
    ]
    out = enrich_chart(
        chart,
        bars=bars,
        option={"contract": "QQQ 642 call", "points": [{"t": "10:00", "px": 4.0}], "trade_pct": -36},
        shadows=[{"i": 4, "label": "no volume", "note": "shadow"}],
        strategy_b=[{"t": "10:05", "price": 642.2, "label": "B"}],
        trade={"entry": 641.98, "stop": 641.25, "be": 641.98, "exit": 639.46},
    )
    assert out["times"] == ["9:30", "9:35"], out["times"]
    assert out["closes"] == [1.5, 2.0]
    assert out["box"]["hi"] == 3 and out["marks"][0]["kind"] == "buy"
    assert out["volumes"] == [100, 80]
    assert out["option"]["trade_pct"] == -36
    assert "shadows" in out and "strategy_b" in out and "trade" in out

    note = "Back to the entry price 641.98 (break-even stop)."
    fixed = honest_exit(note, -36)
    assert "641.98" in fixed and "−36%" in fixed and "not break-even on the option" in fixed, fixed
    assert honest_exit(fixed, -36) == fixed
    assert honest_exit("5-min close 716.79 back inside the box.", -34).startswith("5-min")
    assert "stock's entry" in honest_plan("Sell a third at 642.70. Stop to break-even")
    # No bars: chart is unchanged apart from being a copy.
    same = enrich_chart(chart)
    assert same["closes"] == [1.0, 2.0] and "bars" not in same
    print("chart_payload ok")
