#!/usr/bin/env python3
"""Coverage control: no property may stay "sin analizar".

Usage: python3 scripts/coverage_check.py runs/<sale_id>

Runs funnel_export.py logic first (embudo_sheet.csv must be fresh: run funnel_export.py before) and prints, per
stage, how many properties are in a TERMINAL state. Terminal = excluded (homestead), auto-discarded, reviewed by
an agent, or WAITING for a named missing datum (apertura / estado de cuenta). FAILS (exit 1) if any property is
"4 Paso filtros, sin revision de agente" (passed the filter but nobody read it) or has no stage. Homestead
properties are excluded on purpose and never counted as pending.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

run = Path(sys.argv[1])
rows = list(csv.DictReader((run / "embudo_sheet.csv").open(encoding="utf-8")))
c = Counter(r["etapa_final"] for r in rows)
bad = [r for r in rows if r["etapa_final"].startswith("4") or not r["etapa_final"]]
waiting = [r for r in rows if "EN ESPERA: falta" in r["detalle"]]
print(f"{len(rows)} propiedades en la lista oficial")
for k, v in sorted(c.items()):
    print(f"  {v:4d}  {k}")
print(f"  de las cuales EN ESPERA de un dato concreto: {len(waiting)}")
done = len(rows) - len(bad)
print(f"cobertura: {done}/{len(rows)} con estado terminal ({100 * done / len(rows):.0f}%)")
if bad:
    print(f"FALLA: {len(bad)} propiedades pasaron el filtro y nadie las ha leido:")
    for r in bad[:20]:
        print("   ", r["account_no"], r["direccion"][:40])
    sys.exit(1)
print("OK: ninguna propiedad queda sin estado")
