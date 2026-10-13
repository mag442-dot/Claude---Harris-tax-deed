#!/usr/bin/env python3
"""Pick the properties worth an LLM reviewer's time and print them.

Usage: python3 scripts/shortlist.py runs/<sale_id> [--all-types]

Default = vacant lots (the strategy) that pass the mechanical filters:
  decision_previa in (CONDICIONAL, SOLO CERCA DE LA APERTURA), floodway no, opening bid published,
  tax statement available. Writes runs/<sale_id>/shortlist.txt (one account per line) and prints a table
  ordered by fewest Clerk red flags in the same subdivision, then lowest tax tail.
"""
import csv
import sys
from pathlib import Path


def main(argv):
    run = Path(argv[1])
    allt = "--all-types" in argv
    rows = list(csv.DictReader((run / "analisis.csv").open(encoding="utf-8-sig")))
    def red(r):
        t = r["tipos_misma_subdivision"]
        return sum(t.count(k) for k in ('"L/P"', '"LIEN"', '"A/J"', '"JUDGE"', '"CONT"', '"LEVY"', '"BNKRCY"'))
    sel = [r for r in rows if r["decision_previa"] in ("CONDICIONAL", "SOLO CERCA DE LA APERTURA") and r["floodway"] != "yes"
           and r["apertura"] and r["impuestos_total_adeudado"] != "" and (allt or r["tipo_lote"] == "LOTE")]
    sel.sort(key=lambda r: (red(r), float(r["impuestos_que_hereda_est"] or r["impuestos_total_adeudado"] or 0)))
    (run / "shortlist.txt").write_text("\n".join(r["account_no"] for r in sel) + "\n")
    print(len(sel), "en la lista corta")
    for r in sel:
        print(r["account_no"], r["direccion"][:34].ljust(34), "lote", r["lote_sqft"].rjust(6), "valor", r["valor_hcad"].rjust(7), "apertura", r["apertura"].rjust(9),
              "imp", (r["impuestos_que_hereda_est"] or "ub:" + r["impuestos_total_adeudado"]).rjust(9), "zona", r["fema_zona"][:8].ljust(8), "banderas", red(r), r["decision_previa"][:9])


if __name__ == "__main__":
    main(sys.argv)
