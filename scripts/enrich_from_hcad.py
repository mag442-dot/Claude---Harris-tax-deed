#!/usr/bin/env python3
"""Enrich a run's records with HCAD bulk data (no captcha, no website scraping).

Usage: python3 scripts/enrich_from_hcad.py runs/<sale_id> <hcad-extract-dir>

<hcad-extract-dir> holds the unzipped files from https://download.hcad.org/data/CAMA/<year>/
  Real_acct_owner.zip      -> real_acct.txt, owners.txt, deeds.txt
  Real_building_land.zip   -> land.txt, building_res.txt
  Real_jur_exempt.zip      -> jur_exempt_cd.txt, jur_exemption_dscr.txt
(either flat in the directory or in subfolders x_<zipname>/).

For every record in runs/<sale_id>/records/ it fills the `intake` section with `hcad_*`
findings (status verified, source = the HCAD file) and sets `address` when empty.
Existing hcad_* fields are overwritten; other sections are untouched. Also writes
runs/<sale_id>/hcad_enrichment.csv. Data is the HCAD annual roll: it shows the owner
of record and appraised values, NOT current liens, taxes owed, or judgment details.
"""
import csv
import json
import sys
from datetime import date
from pathlib import Path

BASE = "https://download.hcad.org/data/CAMA/"


def find(root, name):
    for p in [root / name, *root.glob(f"*/{name}")]:
        if p.exists():
            return p
    sys.exit(f"Missing {name} under {root}")


def scan(path, accts, key_idx=0):
    """Yield (header, fields) for lines whose first column is a wanted account."""
    with open(path, encoding="latin-1", newline="") as fh:
        header = fh.readline().rstrip("\r\n").split("\t")
        for line in fh:
            tab = line.find("\t")
            if tab < 0:
                continue
            if line[:tab].strip() in accts:
                yield header, line.rstrip("\r\n").split("\t")


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    run, root = Path(argv[1]), Path(argv[2])
    year = None
    recs = {}
    for f in sorted((run / "records").glob("*.json")):
        r = json.loads(f.read_text())
        if r.get("account_no"):
            recs[r["account_no"].strip()] = (f, r)
    accts = set(recs)
    print(f"{len(accts)} accounts")
    data = {a: {} for a in accts}

    for header, v in scan(find(root, "real_acct.txt"), accts):
        d = dict(zip(header, (x.strip() for x in v)))
        data[d["acct"]]["acct"] = d
    for header, v in scan(find(root, "owners.txt"), accts):
        d = dict(zip(header, (x.strip() for x in v)))
        data[d["acct"]].setdefault("owners", []).append(f"{d['name']} ({d['pct_own']}%)")
    for header, v in scan(find(root, "land.txt"), accts):
        d = dict(zip(header, (x.strip() for x in v)))
        data[d["acct"]].setdefault("land", []).append(f"{d['use_dscr']} {d['uts']}x{d['tp']} ${d['val']}")
    for header, v in scan(find(root, "building_res.txt"), accts):
        d = dict(zip(header, (x.strip() for x in v)))
        data[d["acct"]].setdefault("bldg", []).append(f"{d['structure_dscr']} {d['act_ar']}sf built {d['date_erected']}")
    for header, v in scan(find(root, "deeds.txt"), accts):
        d = dict(zip(header, (x.strip() for x in v)))
        data[d["acct"]].setdefault("deeds", []).append(f"{d['dos']} {d['clerk_yr']}-{d['clerk_id']}")
    dscr = {}
    with open(find(root, "jur_exemption_dscr.txt"), encoding="latin-1") as fh:
        next(fh)
        for line in fh:
            k, _, val = line.rstrip("\r\n").partition("\t")
            dscr[k.strip()] = val.strip()
    for header, v in scan(find(root, "jur_exempt_cd.txt"), accts):
        d = dict(zip(header, (x.strip() for x in v)))
        data[d["acct"]].setdefault("exempt", set()).add(d["exempt_cat"])

    today = date.today().isoformat()
    out_rows = []
    for acct, (f, rec) in recs.items():
        d = data[acct]
        a = d.get("acct")
        if not a:
            print(f"  {acct}: not in HCAD real_acct")
            continue
        src = BASE + "<year>/Real_acct_owner.zip#real_acct.txt"
        ex = sorted(c for c in d.get("exempt", ()) if c)
        ex_txt = ", ".join(f"{c} ({dscr.get(c, '?')})" for c in ex)
        site = ", ".join(x for x in (a["site_addr_1"], a["site_addr_2"], a["site_addr_3"]) if x)
        fields = {
            "hcad_site_address": site,
            "hcad_owner": "; ".join(d.get("owners", [])),
            "hcad_mailing_address": ", ".join(x for x in (a["mail_addr_1"], a["mail_addr_2"], a["mail_city"], a["mail_state"], a["mail_zip"]) if x),
            "hcad_state_class": a["state_class"],
            "hcad_land_sqft": a["land_ar"], "hcad_acres": a["acreage"],
            "hcad_building_sqft": a["bld_ar"], "hcad_year_improved": a["yr_impr"],
            "hcad_land_value": a["land_val"], "hcad_building_value": a["bld_val"],
            "hcad_market_value": a["tot_mkt_val"], "hcad_prior_market_value": a["prior_tot_mkt_val"],
            "hcad_exemptions": ex_txt or "none on roll",
            "hcad_homestead_on_roll": "yes" if {"RES", "PAR", "APR", "FIR"} & set(ex) else "no",
            "hcad_land_detail": " | ".join(d.get("land", [])),
            "hcad_buildings": " | ".join(d.get("bldg", [])),
            "hcad_deeds_recorded": " | ".join(sorted(d.get("deeds", []))[-3:]),
            "hcad_legal": " ".join(x for x in (a["lgl_1"], a["lgl_2"], a["lgl_3"], a["lgl_4"]) if x),
            "hcad_owner_since": a["new_own_dt"],
        }
        for k, v in fields.items():
            rec["intake"][k] = {"value": v, "status": "verified", "source": src.replace("<year>", str(a["yr"])), "retrieved_at": today}
        if not rec.get("address") and site:
            rec["address"] = site
        f.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n")
        out_rows.append({"account_no": acct, "property_id": rec["property_id"], **fields})
    if out_rows:
        with (run / "hcad_enrichment.csv").open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
            w.writeheader()
            w.writerows(out_rows)
    print(f"enriched {len(out_rows)}/{len(recs)}")


if __name__ == "__main__":
    main(sys.argv)
