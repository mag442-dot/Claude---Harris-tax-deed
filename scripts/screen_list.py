#!/usr/bin/env python3
"""First-pass screen of a sale list using only county list + HCAD roll data.

Usage: python3 scripts/screen_list.py runs/<sale_id>

Needs candidatos.csv and hcad_enrichment.csv (see enrich_from_hcad.py). Writes
runs/<sale_id>/screening.csv and prints a summary. This is a TRIAGE, not a decision:
it ranks nothing as "buy". Tiers:
  A  vacant land (HCAD building sqft = 0, state class C*/D*/E*) -> fits the vacant-lot strategy
  B  improved, no homestead on the roll, opening bid known
  C  improved with homestead on the roll (longer redemption exposure; attorney review)
  D  commercial / multifamily / unusual class, or no value on the roll
Opening bid is the county's published minimum; it is NOT the full cost to the buyer
(post-judgment taxes, surviving liens, redemption refund, etc. are checked by the agents).
"""
import csv
import sys
from pathlib import Path


def num(x):
    try:
        return float(str(x).replace(",", "").replace("$", ""))
    except ValueError:
        return None


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    run = Path(argv[1])
    cand = {r["account_no"]: r for r in csv.DictReader((run / "candidatos.csv").open(encoding="utf-8-sig"))}
    out = []
    for h in csv.DictReader((run / "hcad_enrichment.csv").open(encoding="utf-8-sig")):
        c = cand[h["account_no"]]
        mkt, bid = num(h["hcad_market_value"]), num(c["opening_bid"])
        bsf, cls = num(h["hcad_building_sqft"]) or 0, h["hcad_state_class"]
        hs = h["hcad_homestead_on_roll"] == "yes"
        flags = []
        if bsf == 0 and cls[:1] in "CDE":
            tier = "A"
        elif cls[:1] in "FBCXZ" or mkt is None or mkt == 0 or "LLC" in h["hcad_owner"].upper() and cls.startswith("F"):
            tier = "D"
        elif hs:
            tier = "C"
        else:
            tier = "B"
        if bid is None:
            flags.append("sin apertura publicada")
        if hs:
            flags.append("homestead en el roll (posible redencion de 2 anos; revisar con abogado)")
        if bid and mkt and bid / mkt < 0.05:
            flags.append("apertura <5% del valor HCAD: verificar si es el monto completo")
        if "CURRENT OWNER" in h["hcad_owner"].upper():
            flags.append("dueno generico en HCAD")
        out.append({
            "tier": tier, "account_no": h["account_no"], "direccion": h["hcad_site_address"],
            "clase": cls, "lote_sqft": h["hcad_land_sqft"], "construccion_sqft": h["hcad_building_sqft"],
            "valor_hcad": h["hcad_market_value"], "apertura": c["opening_bid"],
            "apertura_pct_valor": f"{bid / mkt:.1%}" if bid and mkt else "",
            "homestead": h["hcad_homestead_on_roll"], "dueno": h["hcad_owner"],
            "precinto_tipo": c["notes"].split(";")[0] + ";" + c["notes"].split(";")[1],
            "flags": " | ".join(flags)})
    out.sort(key=lambda r: (r["tier"], -(num(r["valor_hcad"]) or 0)))
    with (run / "screening.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    from collections import Counter
    print(Counter(r["tier"] for r in out), f"-> {run / 'screening.csv'}")


if __name__ == "__main__":
    main(sys.argv)
