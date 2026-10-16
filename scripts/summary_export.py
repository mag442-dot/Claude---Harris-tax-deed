#!/usr/bin/env python3
"""Build the 'Resumen' sheet: properties that PASSED the independent reviewer (decision CONDICIONAL).

Usage: python3 scripts/summary_export.py runs/<sale_id> [--all-reviewed]

Reads the records (agent-written reviews only; rule-based pre-reviews are not included) and writes
runs/<sale_id>/resumen_sheet.csv. 'Passed' = reviewer decision CONDICIONAL. With --all-reviewed every
reviewed property is listed, passed ones first. The order is fewest contradictions first, then lowest
opening bid -- it is NOT an investment ranking. Push with:
  python3 scripts/push_to_sheet.py runs/<sale_id> --file resumen_sheet.csv --tab Resumen --no-build
"""
import csv
import json
import sys
from pathlib import Path


def g(rec, sec, key):
    return ((rec.get(sec) or {}).get(key) or {}).get("value")


def main(argv):
    run = Path(argv[1])
    allr = "--all-reviewed" in argv
    bids = {r["account_no"]: r["opening_bid"] for r in csv.DictReader((run / "candidatos.csv").open(encoding="utf-8-sig"))}
    rows = []
    for f in sorted((run / "records").glob("*.json")):
        rec = json.loads(f.read_text())
        rv = rec.get("review") or {}
        if not rv or "nunca COMPRA FUERTE sin esa revision" in rv.get("rationale", ""):
            continue  # no agent review
        contr = [c for c in (rv.get("contradictions") or []) if not c.startswith("[20")]   # skip auto 'cifras actualizadas' notes
        passed = rv.get("decision") == "CONDICIONAL"
        if not passed and not allr:
            continue
        acct = (rec.get("account_no") or "").strip()
        bid = bids.get(acct) or ""
        exp = max([x for x in (g(rec, "valuation", "expected_close_from_ratio"), g(rec, "valuation", "expected_close_from_premium")) if x] or [""])
        bsf = str(g(rec, "intake", "hcad_building_sqft") or "0")
        tipo = "LOTE (estrategia)" if bsf in ("0", "0.0") and str(g(rec, "intake", "hcad_state_class") or "").startswith(("C", "D", "E")) else "CASA/OTRO (fuera de estrategia)"
        rows.append({
            "tipo": tipo, "paso_revision": "SI" if passed else "NO", "decision": rv.get("decision", ""),
            "property_id": rec["property_id"], "direccion": rec.get("address", ""),
            "jurisdiccion": g(rec, "physical", "parcel_city") or "",
            "lote_sqft_gis": g(rec, "physical", "lot_sqft_gis") or g(rec, "intake", "hcad_land_sqft") or "",
            "dimensiones_est": g(rec, "physical", "lot_dimensions_est") or "",
            "zona_fema": g(rec, "physical", "fema_effective_zone") or "",
            "valor_hcad": g(rec, "intake", "hcad_market_value") or "", "apertura": bid,
            "impuestos_que_hereda_est": g(rec, "tax", "buyer_tax_tail_estimate") if g(rec, "tax", "buyer_tax_tail_estimate") is not None else "",
            "cierre_esperado": exp, "techo_teorico": rv.get("bid_ceiling") if rv.get("bid_ceiling") is not None else "",
            "motivo_del_revisor": rv.get("rationale", ""),
            "condiciones_para_comprar": " || ".join(f"{i + 1}) {c}" for i, c in enumerate((rv.get("conditions_to_buy") or [])[:5])),
            "n_contradicciones": len(contr),
            "primera_contradiccion": (contr or [""])[0],
            "pendientes_tuyos": len(rec.get("human_blockers") or []),
            "foto_condado": g(rec, "intake", "county_image_url") or "",
            "account_no": acct})
    rows.sort(key=lambda r: (r["paso_revision"] != "SI", not r["tipo"].startswith("LOTE"), r["n_contradicciones"], float(r["apertura"] or 1e12)))
    for i, r in enumerate(rows, 1):
        r["orden"] = i
    cols = ["orden", "tipo", "paso_revision", "decision", "direccion", "jurisdiccion", "lote_sqft_gis", "dimensiones_est", "zona_fema", "valor_hcad",
            "apertura", "impuestos_que_hereda_est", "cierre_esperado", "techo_teorico", "motivo_del_revisor", "condiciones_para_comprar",
            "n_contradicciones", "primera_contradiccion", "pendientes_tuyos", "foto_condado", "property_id", "account_no"]
    with (run / "resumen_sheet.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])
    print(f"{len(rows)} filas -> {run / 'resumen_sheet.csv'}")


if __name__ == "__main__":
    main(sys.argv)
