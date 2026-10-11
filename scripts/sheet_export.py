#!/usr/bin/env python3
"""Make the compact CSV that gets uploaded to Google Drive as a Google Sheet.

Usage: python3 scripts/sheet_export.py runs/<sale_id>
Reads analisis.csv, drops bulky columns and the boilerplate 'pendiente:' note, writes
runs/<sale_id>/analisis_sheet.csv (column order = reading order in the Sheet).
"""
import csv
import sys
from pathlib import Path

COLS = ["property_id", "account_no", "direccion", "dueno_hcad", "clase", "lote_sqft", "construccion_sqft", "ano_construccion",
        "valor_hcad", "apertura", "fema_zona", "floodway", "hits_clerk_misma_subdivision", "tipos_misma_subdivision", "señales"]


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    run = Path(argv[1])
    rows = list(csv.DictReader((run / "analisis.csv").open(encoding="utf-8-sig")))
    with (run / "analisis_sheet.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(COLS)
        for r in rows:
            r["señales"] = " | ".join(s for s in r["señales"].split(" | ") if not s.startswith("pendiente:"))
            r["dueno_hcad"] = r["dueno_hcad"].replace(" (1.0000%)", "")
            r["fema_zona"] = r["fema_zona"].replace(" (AREA OF MINIMAL FLOOD HAZARD)", " (minimo)").replace(" (0.2 PCT ANNUAL CHANCE FLOOD HAZARD)", " (0.2%)")
            w.writerow([r[c] for c in COLS])
    print(f"{len(rows)} rows -> {run / 'analisis_sheet.csv'}")


if __name__ == "__main__":
    main(sys.argv)
