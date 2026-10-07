#!/usr/bin/env python3
"""Merge property record JSONs into one CSV ready to paste/import into the Google Sheet.

Usage: python3 scripts/merge_to_csv.py <records-dir> <output.csv>

Columns: key identifiers, one-line summary per section, decision, bid ceiling,
conditions, contradictions, and pending human actions. Sorted by decision priority.
"""
import csv
import json
import sys
from pathlib import Path

PRIORITY = ["COMPRA FUERTE", "CONDICIONAL", "VIGILAR", "SOLO CERCA DE LA APERTURA",
            "NO PARA DUPLEX", "BAJA", "DESCARTADA"]


def val(section, key):
    f = (section or {}).get(key)
    if isinstance(f, dict):
        v = f.get("value")
        tag = f.get("status")
        if v is None:
            return ""
        s = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
        return f"{s} [{tag}]" if tag in ("inferred", "blocked", "unknown") else s
    return ""


def row(rec):
    review = rec.get("review") or {}
    blockers = rec.get("human_blockers") or []
    return {
        "Propiedad": rec.get("address", ""),
        "ID": rec.get("property_id", ""),
        "Condado": rec.get("county", ""),
        "Cuenta": rec.get("account_no") or "",
        "Cause": rec.get("cause_no") or "",
        "Apertura": val(rec.get("intake"), "opening_bid"),
        "Estatus venta": val(rec.get("intake"), "status"),
        "Impuestos que hereda": val(rec.get("tax"), "buyer_tax_tail_estimate"),
        "Homestead": val(rec.get("tax"), "homestead"),
        "Resumen título": val(rec.get("title"), "title_summary"),
        "Resumen legal": val(rec.get("legal"), "legal_summary"),
        "Inundación FEMA": val(rec.get("physical"), "fema_effective_zone"),
        "Inundación borrador": val(rec.get("physical"), "maapnext_draft"),
        "Lote sqft": val(rec.get("physical"), "lot_sqft"),
        "Dúplex": val(rec.get("physical"), "duplex_feasibility"),
        "Valor base": val(rec.get("valuation"), "value_base"),
        "Techo de puja": review.get("bid_ceiling") if review.get("bid_ceiling") is not None else "",
        "Costo total est.": review.get("all_in_cost_estimate") if review.get("all_in_cost_estimate") is not None else "",
        "Decisión": review.get("decision", "SIN REVISAR"),
        "Justificación": review.get("rationale", ""),
        "Condiciones para comprar": " | ".join(review.get("conditions_to_buy") or []),
        "Contradicciones": " | ".join(review.get("contradictions") or []),
        "Pendiente de Miguel": " | ".join(f"[{b.get('agent')}] {b.get('item')}" for b in blockers),
    }


def sort_key(r):
    d = r["Decisión"]
    return (PRIORITY.index(d) if d in PRIORITY else len(PRIORITY), r["Propiedad"])


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    src, out = Path(argv[1]), Path(argv[2])
    rows = []
    for f in sorted(src.glob("*.json")):
        rows.append(row(json.loads(f.read_text())))
    if not rows:
        sys.exit(f"No records in {src}")
    rows.sort(key=sort_key)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main(sys.argv)
