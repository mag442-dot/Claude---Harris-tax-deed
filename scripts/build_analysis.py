#!/usr/bin/env python3
"""Consolidate what is verified/inferred so far into runs/<sale_id>/analisis.csv.

Usage: python3 scripts/build_analysis.py runs/<sale_id> [--include-homestead]

One row per record (homestead-on-roll excluded by default) combining county list,
HCAD roll, FEMA flood zone and County Clerk index hits. It does NOT assign buy/pass
decisions or bid ceilings: tax tail, tax-suit defendants (District Clerk login),
bankruptcy (PACER), comps and repair costs are not collected, so those stay human
blockers. `señales` lists items that need a look before anyone bids.
"""
import csv
import json
import re
import sys
from pathlib import Path

RED = {"LIEN": "lien registrado (tipo exacto por ver)", "A/J": "abstract of judgment", "JUDGE": "judgment",
       "LEVY": "levy sobre inmueble", "BNKRCY": "bancarrota", "L/P": "lis pendens", "CONT": "lien de mecanico/contrato"}


def desc_of(hit):
    m = re.search(r"Desc:\s*(.*?)(?:\s+(?:Lot|Block|Sec|Unit|Tract|Reserve|Abst)\b.*)?$", hit.split(" | ", 4)[-1] if " | " in hit else hit)
    return (m.group(1) if m else "").strip().upper()


def matches_legal(hit, legal):
    d = desc_of(hit)
    toks = [t for t in re.split(r"[^A-Z0-9]+", d) if len(t) > 2]
    return bool(toks) and all(t in legal.upper() for t in toks[:3])


def f(rec, sec, key):
    return ((rec.get(sec) or {}).get(key) or {}).get("value")


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    run = Path(argv[1])
    incl = "--include-homestead" in argv
    cand = {r["account_no"]: r for r in csv.DictReader((run / "candidatos.csv").open(encoding="utf-8-sig"))}
    rows = []
    for fp in sorted((run / "records").glob("*.json")):
        rec = json.loads(fp.read_text())
        acct = (rec.get("account_no") or "").strip()
        hs = f(rec, "intake", "hcad_homestead_on_roll") == "yes"
        if hs and not incl:
            continue
        c = cand.get(acct, {})
        mkt = f(rec, "intake", "hcad_market_value")
        bid = c.get("opening_bid") or ""
        fz = f(rec, "physical", "fema_effective_zone") or ""
        fw = f(rec, "physical", "floodway")
        hits = (f(rec, "title", "rp_hits_grantee") or []) + (f(rec, "title", "rp_hits_grantor") or [])
        legal = f(rec, "intake", "hcad_legal") or ""
        same = [h for h in hits if matches_legal(h, legal)]
        types = [h.split(" | ")[2].strip() for h in hits if len(h.split(" | ")) > 2]
        stypes = [h.split(" | ")[2].strip() for h in same if len(h.split(" | ")) > 2]
        flagged = {t: stypes.count(t) for t in RED if t in stypes}
        sig = []
        if fw == "yes":
            sig.append("FLOODWAY (descarte automatico del playbook)")
        if fz.startswith("AE") or fz.startswith("A"):
            sig.append(f"zona de inundacion {fz}")
        for t, n in flagged.items():
            sig.append(f"{n}x {RED[t]} con descripcion que coincide con la subdivision HCAD")
        if hits and not same:
            sig.append("ningun instrumento del Clerk coincide con la subdivision HCAD (hits por nombre pueden ser de otra persona/predio)")
        if f(rec, "title", "rp_summary") is None:
            sig.append("indice del Clerk NO consultado/fallo")
        if not bid:
            sig.append("sin apertura publicada")
        try:
            if bid and mkt and float(bid) / float(mkt) < 0.05:
                sig.append("apertura <5% del valor HCAD: probablemente no es el costo total")
        except ValueError:
            pass
        sig.append("pendiente: impuestos que hereda, demandados/citacion (District Clerk login), PACER, ocupacion, comps")
        tail = f(rec, "tax", "buyer_tax_tail_estimate")
        tdue = f(rec, "tax", "total_due_all_years")
        rv = rec.get("review") or {}
        rows.append({
            "decision_previa": rv.get("decision", ""), "revisado_por": ("agente reviewer" if rv and "nunca COMPRA FUERTE sin esa revision" not in rv.get("rationale", "") else ("reglas (sin leer a mano)" if rv else "")), "tipo_lote": "LOTE" if str(f(rec, "intake", "hcad_building_sqft") or "0") in ("0", "0.0") and str(f(rec, "intake", "hcad_state_class") or "").startswith(("C", "D", "E")) else "CASA/OTRO",
            "impuestos_total_adeudado": tdue if tdue is not None else "", "impuestos_que_hereda_est": tail if tail is not None else "",
            "cierre_esperado": max([x for x in (f(rec, "valuation", "expected_close_from_ratio"), f(rec, "valuation", "expected_close_from_premium")) if x] or [""]),
            "techo_teorico": f(rec, "valuation", "bid_ceiling") if f(rec, "valuation", "bid_ceiling") is not None else "",
            "razon": rv.get("rationale", ""),
            "foto_condado": f(rec, "intake", "county_image_url") or "",
            "account_no": acct, "direccion": rec.get("address", ""), "dueno_hcad": f(rec, "intake", "hcad_owner") or "",
            "dueno_desde": f(rec, "intake", "hcad_owner_since") or "", "clase": f(rec, "intake", "hcad_state_class") or "",
            "lote_sqft": f(rec, "intake", "hcad_land_sqft") or "", "construccion_sqft": f(rec, "intake", "hcad_building_sqft") or "",
            "ano_construccion": f(rec, "intake", "hcad_year_improved") or "", "valor_hcad": mkt or "", "apertura": bid,
            "causa": rec.get("cause_no") or "", "precinto_tipo": "; ".join(c.get("notes", "").split(";")[:3]),
            "fema_zona": fz, "floodway": fw or "", "hits_clerk_nombre": len(hits), "hits_clerk_misma_subdivision": len(same), "tipos_misma_subdivision": json.dumps(
                {t: stypes.count(t) for t in sorted(set(stypes))}, ensure_ascii=False), "tipos_clerk_nombre": json.dumps(
                {t: types.count(t) for t in sorted(set(types))}, ensure_ascii=False),
            "señales": " | ".join(sig), "property_id": rec["property_id"]})
    order = ["CONDICIONAL", "SOLO CERCA DE LA APERTURA", "VIGILAR", "NO PARA DUPLEX", "BAJA", "DESCARTADA", ""]
    rows.sort(key=lambda r: (order.index(r["decision_previa"]) if r["decision_previa"] in order else 9, r["tipo_lote"] != "LOTE",
                             -(float(r["valor_hcad"]) if str(r["valor_hcad"]).replace(".", "").isdigit() else 0)))
    out = run / "analisis.csv"
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main(sys.argv)
