#!/usr/bin/env python3
"""Write the `valuation` section: value proxy, expected close, all-in cost and bid ceiling.

Usage: python3 scripts/valuation.py runs/<sale_id> [account_no ...]

Inputs: records (intake HCAD values, tax tail, physical), runs/<sale_id>/params.json
(target_margin_pct, exit_strategy, assumptions). NO comps are available (Texas does not publish sale
prices; listing portals are not reachable), so value_base is the HCAD market value used as an
INFERRED proxy and no low/high range is invented.
  expected_close = max(opening*(1+premium), HCAD value * median close/value ratio)   [playbook benchmarks]
  tax tail used  = buyer_tax_tail_estimate, else total_due_all_years as a conservative upper bound
  bid_ceiling    = (value/(1+margin) - tax_tail - quiet_title) / (1+closing_pct)        [resale exit]
Duplex exit is NOT priced (no build cost / zoning data) -> exit_strategy_used says so.
"""
import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _recio import save_sections


def val(rec, sec, key):
    return ((rec.get(sec) or {}).get(key) or {}).get("value")


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    run, only = Path(argv[1]), set(argv[2:])
    params = json.loads((run / "params.json").read_text())
    A, margin = params["assumptions"], params["target_margin_pct"] / 100
    bids = {r["account_no"]: r["opening_bid"] for r in csv.DictReader((run / "candidatos.csv").open(encoding="utf-8-sig"))}
    today = date.today().isoformat()
    n = 0
    for f in sorted((run / "records").glob("*.json")):
        rec = json.loads(f.read_text())
        acct = (rec.get("account_no") or "").strip()
        if not acct or (only and acct not in only):
            continue
        sec = rec.setdefault("valuation", {})
        fv = lambda value, st, note=None, src="calculo propio (scripts/valuation.py)": {"value": value, "status": st, "source": src,
                                                                                    "retrieved_at": today, **({"note": note} if note else {})}
        try:
            value = float(val(rec, "intake", "hcad_market_value") or val(rec, "tax", "appraised_value_county") or 0) or None
        except (TypeError, ValueError):
            value = None
        bid = float(bids[acct]) if bids.get(acct) else None
        bsf = float(val(rec, "intake", "hcad_building_sqft") or 0)
        if value is None:
            sec["value_base"] = fv(None, "unknown", "HCAD sin valor para la cuenta")
            sec["bid_ceiling"] = fv(None, "unknown", "sin valor base")
            save_sections(f, rec, ["valuation"]); n += 1; continue
        haircut = A.get("resale_value_haircut_vs_hcad", 0.0)
        net = value * (1 - haircut)
        sec["value_base"] = fv(value, "inferred", "Valor de mercado HCAD 2026 como proxy; NO hay comparables (Texas no publica precios de venta).", "HCAD real_acct.txt tot_mkt_val")
        sec["value_low"] = fv(None, "unknown", "sin comparables no se inventa rango")
        sec["value_high"] = fv(None, "unknown", "sin comparables no se inventa rango")
        sec["comps"] = fv([], "unknown", "no accesibles desde este entorno")
        by_ratio = round(value * A["close_to_value_median"], 2)
        sec["expected_close_from_ratio"] = fv(by_ratio, "inferred", f"valor HCAD x {A['close_to_value_median']} (mediana cierre/valor de 14 lotes del 04/08/2026)")
        by_prem = round(bid * (1 + A["premium_over_opening_median"]), 2) if bid else None
        sec["expected_close_from_premium"] = fv(by_prem, "inferred" if bid else "unknown", f"apertura x {1 + A['premium_over_opening_median']} (benchmark del playbook)")
        exp_close = max(x for x in (by_ratio, by_prem) if x)
        tail = val(rec, "tax", "buyer_tax_tail_estimate")
        tail_note = "buyer_tax_tail_estimate (inferred)"
        if tail is None:
            tail = val(rec, "tax", "total_due_all_years")
            tail_note = "COTA SUPERIOR: total adeudado de todos los anios (el condado no separa anios de la sentencia)" if tail is not None else None
        if tail is None:
            sec["bid_ceiling"] = fv(None, "unknown", "sin estado de cuenta de impuestos no se calcula techo")
            sec["all_in_costs"] = fv(None, "unknown")
            sec["exit_strategy_used"] = fv("ninguna", "unknown")
            save_sections(f, rec, ["valuation"]); n += 1; continue
        qt, cp = A["quiet_title_cost_usd"], A["closing_cost_pct"]
        ceiling = (net / (1 + margin) - tail - qt) / (1 + cp)
        ceiling = round(max(ceiling, 0), 2)
        all_in = {"puja_esperada": exp_close, "impuestos_que_hereda": tail, "quiet_title_supuesto": qt,
                  "cierre_supuesto": round(exp_close * cp, 2), "liens_que_sobreviven": "NO CUANTIFICADO (indice del Clerk sin leer)"}
        total = round(exp_close + tail + qt + exp_close * cp, 2)
        sec["all_in_costs"] = fv(all_in, "inferred", f"impuestos: {tail_note}; quiet title y cierre son SUPUESTOS editables en params.json")
        sec["all_in_cost_at_expected_close"] = fv(total, "inferred")
        sec["bid_ceiling"] = fv(ceiling, "inferred", f"(valor/(1+{margin:.2f}) - impuestos - quiet title)/(1+cierre); margen = retorno sobre costo; salida REVENTA al valor HCAD")
        sec["margin_at_expected_close"] = fv(round(net / total - 1, 3), "inferred", "retorno sobre costo total si se gana a la puja esperada y se revende al valor HCAD")
        sec["exit_strategy_used"] = fv("resale (duplex NO evaluado: faltan costo de construccion, zonificacion/restricciones y topografia)", "inferred")
        if bsf > 0:
            sec["improved_warning"] = fv("Propiedad con mejoras: el valor HCAD no refleja deterioro/ocupacion; revender al valor HCAD es optimista sin inspeccion.", "inferred")
        save_sections(f, rec, ["valuation"])
        n += 1
    print(f"valuation: {n} records")


if __name__ == "__main__":
    main(sys.argv)
