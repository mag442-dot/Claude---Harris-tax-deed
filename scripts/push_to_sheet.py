#!/usr/bin/env python3
"""Push runs/<sale_id>/analisis_sheet.csv to the Google Sheet webhook (apps_script/Code.gs).

Usage: python3 scripts/push_to_sheet.py runs/<sale_id> [--file NAME.csv] [--tab TAB]

Env: SHEET_WEBHOOK_URL, SHEET_WEBHOOK_TOKEN (see apps_script/README.md).
Rebuilds analisis_sheet.csv first (build_analysis.py + sheet_export.py) unless --no-build.
Replaces the contents of the tab (default 'Analisis'); never creates a new Sheet.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None
    if len(args) < 1:
        sys.exit(__doc__)
    run = Path(args[0])
    url, token = os.environ.get("SHEET_WEBHOOK_URL"), os.environ.get("SHEET_WEBHOOK_TOKEN")
    if not url or not token:
        sys.exit("Faltan SHEET_WEBHOOK_URL / SHEET_WEBHOOK_TOKEN (ver apps_script/README.md). "
                 "Sin ellos, usa el conector de Drive o entrega el CSV a mano.")
    name = opt("--file") or "analisis_sheet.csv"
    if "--no-build" not in argv and name == "analisis_sheet.csv":
        for s in ("build_analysis.py", "sheet_export.py"):
            subprocess.run([sys.executable, str(HERE / s), str(run)], check=True)
    csv_path = run / name
    if not csv_path.exists():
        sys.exit(f"No existe {csv_path}")
    payload = {"token": token, "csv": csv_path.read_text(encoding="utf-8"),
               "sheet": opt("--tab") or "Analisis", "source": f"{run.name}/{name}"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "text/plain;charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:   # Apps Script answers via a redirect; the POST already ran
            resp = r.read().decode()
    except urllib.error.URLError as e:
        sys.exit(f"No se pudo llamar al webhook: {e} (¿está permitido script.google.com en Network access?)")
    try:
        j = json.loads(resp)
    except json.JSONDecodeError:
        sys.exit(f"Respuesta inesperada (no es JSON): {resp[:200]}")
    if not j.get("ok"):
        sys.exit(f"El Sheet rechazó la carga: {j.get('error')}")
    print(f"OK: {j['rows']} filas escritas en la pestaña '{j['sheet']}'")


if __name__ == "__main__":
    main(sys.argv)
