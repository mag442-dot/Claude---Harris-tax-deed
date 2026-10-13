#!/usr/bin/env python3
"""After valuation changes, refresh ONLY the numeric fields inside agent-written reviews.

Usage: python3 scripts/refresh_review_numbers.py runs/<sale_id> [account_no ...]

For records whose review was written by the reviewer agent (rationale lacks the rules marker), copies
valuation.bid_ceiling and valuation.all_in_cost_at_expected_close into review.bid_ceiling /
review.all_in_cost_estimate, keeps the agent's decision and text, and appends a dated note to
review.contradictions saying the figures were refreshed (and the old values), so the reader knows the
agent's prose may quote older numbers. Never touches the decision.
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _recio import save_sections


def g(rec, sec, key):
    return ((rec.get(sec) or {}).get(key) or {}).get("value")


def main(argv):
    run, only = Path(argv[1]), set(a for a in argv[2:])
    n = 0
    for f in sorted((run / "records").glob("*.json")):
        rec = json.loads(f.read_text())
        acct = (rec.get("account_no") or "").strip()
        rv = rec.get("review") or {}
        if not rv or "nunca COMPRA FUERTE sin esa revision" in rv.get("rationale", "") or (only and acct not in only):
            continue
        new_c, new_a = g(rec, "valuation", "bid_ceiling"), g(rec, "valuation", "all_in_cost_at_expected_close")
        old_c, old_a = rv.get("bid_ceiling"), rv.get("all_in_cost_estimate")
        if (new_c, new_a) == (old_c, old_a):
            continue
        rv["bid_ceiling"], rv["all_in_cost_estimate"] = new_c, new_a
        rv.setdefault("contradictions", []).append(
            f"[{date.today().isoformat()}] Cifras actualizadas tras corregir el calculo de anios en sentencia (rango 'a - b'): "
            f"techo ${old_c if old_c is not None else 'n/d'} -> ${new_c if new_c is not None else 'n/d'}; costo total ${old_a if old_a is not None else 'n/d'} -> ${new_a if new_a is not None else 'n/d'}. "
            "El texto del revisor puede citar las cifras anteriores; la decision no cambio.")
        rec["review"] = rv
        save_sections(f, rec, ["review"])
        n += 1
    print(f"refreshed {n} agent reviews")


if __name__ == "__main__":
    main(sys.argv)
