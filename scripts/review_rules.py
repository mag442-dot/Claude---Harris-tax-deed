#!/usr/bin/env python3
"""Rule-based PRE-review: fills `review` using the playbook's labels and auto-discard rules.

Usage: python3 scripts/review_rules.py runs/<sale_id> [account_no ...]

This is the mechanical first pass of the reviewer role. It never assigns COMPRA FUERTE because legal
(defendants, service, bankruptcy) is always blocked without District Clerk login / PACER. The LLM
`reviewer` agent should re-read the shortlist cold and may change the decision.
Rules, in order:
  DESCARTADA                 floodway = yes
  VIGILAR                    no tax statement (tail unknown) or no opening bid published
  BAJA                       bid_ceiling < opening bid (economics negative at the ceiling model)
  SOLO CERCA DE LA APERTURA  ceiling covers the opening bid but not the playbook premium (opening*1.088)
  NO PARA DUPLEX             exit is duplex and (lot < 4,000 sqft or FEMA zone A*) -- heuristic, see rationale
  CONDICIONAL                ceiling >= expected close and none of the above
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _recio import save_sections

RED_TYPES = {"LIEN": "lien (tipo exacto por leer)", "A/J": "abstract of judgment", "JUDGE": "judgment", "LEVY": "levy",
             "BNKRCY": "bancarrota", "L/P": "lis pendens", "CONT": "lien de mecanico"}


def g(rec, sec, key):
    return ((rec.get(sec) or {}).get(key) or {}).get("value")


def matches_legal(hit, legal):
    import re
    m = re.search(r"Desc:\s*(.*?)(?:\s+(?:Lot|Block|Sec|Unit|Tract|Reserve|Abst)\b.*)?$", hit.split(" | ", 4)[-1])
    toks = [t for t in re.split(r"[^A-Z0-9]+", (m.group(1) if m else "").upper()) if len(t) > 2]
    return bool(toks) and all(t in legal.upper() for t in toks[:3])


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    run, only = Path(argv[1]), set(a for a in argv[2:] if not a.startswith("--"))
    params = json.loads((run / "params.json").read_text())
    prem = 1 + params["assumptions"]["premium_over_opening_median"]
    bids = {r["account_no"]: r["opening_bid"] for r in csv.DictReader((run / "candidatos.csv").open(encoding="utf-8-sig"))}
    n = 0
    for f in sorted((run / "records").glob("*.json")):
        rec = json.loads(f.read_text())
        acct = (rec.get("account_no") or "").strip()
        if not acct or (only and acct not in only):
            continue
        old = (rec.get("review") or {}).get("rationale", "")
        if old and "nunca COMPRA FUERTE sin esa revision" not in old and "--force" not in argv:
            continue  # written by the reviewer agent: do not overwrite
        bid = float(bids[acct]) if bids.get(acct) else None
        ceiling, tail = g(rec, "valuation", "bid_ceiling"), g(rec, "tax", "buyer_tax_tail_estimate")
        exp_close = max([x for x in (g(rec, "valuation", "expected_close_from_ratio"), g(rec, "valuation", "expected_close_from_premium")) if x] or [0])
        zone = str(g(rec, "physical", "fema_effective_zone") or "")
        lot = float(g(rec, "physical", "lot_sqft_gis") or g(rec, "intake", "hcad_land_sqft") or 0)
        sfha = g(rec, "physical", "fema_sfha_pct")
        city = g(rec, "physical", "parcel_city") or ""
        bsf = float(g(rec, "intake", "hcad_building_sqft") or 0)
        floodway = g(rec, "physical", "floodway") == "yes"
        legal_txt = g(rec, "intake", "hcad_legal") or ""
        hits = (g(rec, "title", "rp_hits_grantee") or []) + (g(rec, "title", "rp_hits_grantor") or [])
        same = [h for h in hits if matches_legal(h, legal_txt)]
        flags = sorted({RED_TYPES[t] for h in same for t in RED_TYPES if f" | {t} | " in h})
        why = []
        if floodway:
            dec = "DESCARTADA"; why.append("El predio cae en floodway (descarte automatico del playbook).")
        elif ceiling is None or bid is None:
            dec = "VIGILAR"
            if bid is None: why.append("El condado aun no publica la apertura.")
            if ceiling is None: why.append("No hay estado de cuenta de impuestos (cota de costo desconocida).")
        elif ceiling < bid:
            dec = "BAJA"; why.append(f"Techo teorico ${ceiling:,.0f} < apertura ${bid:,.0f}.")
        elif ceiling < bid * prem:
            dec = "SOLO CERCA DE LA APERTURA"; why.append(f"Techo ${ceiling:,.0f} cubre la apertura (${bid:,.0f}) pero no la prima tipica ({prem:.3f}x).")
        elif params.get("exit_strategy") == "duplex" and (0 < lot < 4000 or (sfha or 0) >= 50):
            dec = "NO PARA DUPLEX"; why.append(f"Lote {lot:,.0f} sqft / {sfha or 0:.0f}% del predio en zona de inundacion especial (SFHA): heuristica contra la salida dúplex (no es un limite legal).")
        elif exp_close and ceiling >= exp_close:
            dec = "CONDICIONAL"; why.append(f"Techo teorico ${ceiling:,.0f} >= cierre esperado ${exp_close:,.0f}.")
        else:
            dec = "SOLO CERCA DE LA APERTURA"; why.append(f"Techo ${ceiling:,.0f} < cierre esperado ${exp_close:,.0f}: solo conviene cerca de la apertura.")
        if bsf > 0: why.append("Es casa (HCAD): valor de reventa y ocupacion sin verificar.")
        if (sfha or 0) > 0 and dec != "NO PARA DUPLEX": why.append(f"{sfha:.0f}% del predio en SFHA (FEMA efectivo).")
        if city: why.append(f"Jurisdiccion: {city}.")
        if flags: why.append("Indice del Clerk (misma subdivision): " + ", ".join(flags) + ".")
        why.append("Legal bloqueado (demandados/citacion/bancarrota): nunca COMPRA FUERTE sin esa revision. Attorney review recommended.")
        cond = ["Leer los gravamenes del Clerk con imagen (tipo, acreedor, si sobreviven la venta)",
                "Confirmar demandados y citacion en hcdistrictclerk.com (login) y bancarrota en PACER",
                "Pedir estado de cuenta actualizado de impuestos antes de pujar (crece con penalidades)",
                "Confirmar apertura final el dia de la venta (el condado puede retirar o cambiar propiedades)"]
        cond.append("Visita al sitio: ocupacion y estado" if bsf > 0 else "Verificar acceso legal/fisico, linderos y restricciones del lote")
        rec["review"] = {"decision": dec, "rationale": " ".join(why),
                         "bid_ceiling": ceiling if isinstance(ceiling, (int, float)) else None,
                         "all_in_cost_estimate": g(rec, "valuation", "all_in_cost_at_expected_close"),
                         "contradictions": [], "conditions_to_buy": cond}
        save_sections(f, rec, ["review"])
        n += 1
    print(f"review_rules: {n} records")


if __name__ == "__main__":
    main(sys.argv)
