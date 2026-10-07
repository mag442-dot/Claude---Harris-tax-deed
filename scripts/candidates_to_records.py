#!/usr/bin/env python3
"""Create stub property records from runs/<sale_id>/candidatos.csv.

Usage: python3 scripts/candidates_to_records.py runs/<sale_id>

For each CSV row, writes runs/<sale_id>/records/<property_id>.json with the header
fields and an `intake` section (opening_bid, notes). Existing records are never
overwritten. The intake agent then enriches them. County is inferred from the
sale_id prefix (harris-... / montgomery-...).
"""
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

REQUIRED = ["property_id", "address"]


def finding(value, note=None):
    return {"value": value, "status": "verified", "source": "candidatos.csv (scout)",
            "retrieved_at": date.today().isoformat(), **({"note": note} if note else {})}


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    run = Path(argv[1])
    sale_id = run.name
    county = sale_id.split("-")[0].capitalize()
    if county not in ("Harris", "Montgomery"):
        sys.exit(f"Cannot infer county from sale_id '{sale_id}'")
    src = run / "candidatos.csv"
    if not src.exists():
        sys.exit(f"Missing {src}")
    out = run / "records"
    out.mkdir(exist_ok=True)
    created = skipped = 0
    with src.open(newline="", encoding="utf-8-sig") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            row = {k: (v or "").strip() for k, v in row.items()}
            if any(not row.get(k) for k in REQUIRED):
                sys.exit(f"{src}:{n}: missing {REQUIRED}")
            pid = row["property_id"]
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", pid):
                sys.exit(f"{src}:{n}: bad property_id '{pid}' (lowercase slug)")
            dest = out / f"{pid}.json"
            if dest.exists():
                skipped += 1
                continue
            intake = {}
            if row.get("opening_bid"):
                try:
                    intake["opening_bid"] = finding(float(row["opening_bid"].replace(",", "")))
                except ValueError:
                    sys.exit(f"{src}:{n}: opening_bid '{row['opening_bid']}' is not a number")
            if row.get("notes"):
                intake["scout_notes"] = finding(row["notes"])
            rec = {"property_id": pid, "sale_id": sale_id, "county": county,
                   "address": row["address"], "account_no": row.get("account_no") or None,
                   "cause_no": row.get("cause_no") or None, "intake": intake}
            dest.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n")
            created += 1
    print(f"created {created}, skipped {skipped} existing -> {out}")


if __name__ == "__main__":
    main(sys.argv)
