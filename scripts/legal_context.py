#!/usr/bin/env python3
"""Write the `legal` section from what is public without login, and flag the rest as blocked.

Usage: python3 scripts/legal_context.py runs/<sale_id> [account_no ...]

From the county sale list (candidatos.csv notes): sale type, judgment date, tax years in judgment,
cause number. Computes the TRCP 329 window (2 years after judgment, relevant ONLY if a defendant was
served by publication, which is unknown). Defendants / service method (District Clerk login) and
bankruptcy (PACER account) are written as status "blocked" with human_blockers. Redemption is
INFERRED text for attorney review, not a legal conclusion.
"""
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _recio import save_sections

SALE_DATE = {"harris-2026-11-03": date(2026, 11, 3)}


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    run, only = Path(argv[1]), set(argv[2:])
    sale_date = SALE_DATE.get(run.name) or date(int(run.name.split("-")[1]), int(run.name.split("-")[2]), int(run.name.split("-")[3]))
    notes = {r["account_no"]: r["notes"] for r in csv.DictReader((run / "candidatos.csv").open(encoding="utf-8-sig"))}
    today = date.today().isoformat()
    n = 0
    for f in sorted((run / "records").glob("*.json")):
        rec = json.loads(f.read_text())
        acct = (rec.get("account_no") or "").strip()
        if not acct or (only and acct not in only):
            continue
        nt = notes.get(acct, "")
        src = "https://www.hctax.net/Property/listings/taxsalelisting (lista oficial del condado)"
        v = lambda val, st="verified", note=None, s=src: {"value": val, "status": st, "source": s, "retrieved_at": today, **({"note": note} if note else {})}
        sec = rec.setdefault("legal", {})
        stype = re.search(r"tipo ([A-Z ]+?);", nt)
        jd = re.search(r"sentencia (\d\d/\d\d/\d{4})", nt)
        sec["sale_type"] = v(stype.group(1).strip() if stype else None, "verified" if stype else "unknown")
        sec["cause_no"] = v(rec.get("cause_no"), "verified" if rec.get("cause_no") else "unknown")
        if jd:
            jdate = datetime.strptime(jd.group(1), "%m/%d/%Y").date()
            end = date(jdate.year + 2, jdate.month, min(jdate.day, 28))
            sec["judgment_date"] = v(jd.group(1))
            open_ = end >= sale_date
            sec["redemption_or_new_trial_risk"] = v(
                (f"Ventana TRCP 329 (2 anios desde la sentencia) sigue abierta hasta {end.isoformat()}: aplica SOLO si algun demandado fue citado por publicacion (no verificado)"
                 if open_ else f"Ventana TRCP 329 cerro el {end.isoformat()} (si hubo citacion por publicacion)"),
                "inferred", "calculo de fechas; el metodo de citacion esta bloqueado (District Clerk requiere login). Revisar con abogado.", "calculo propio sobre lista oficial")
            if rec.get("cause_no") and str(rec["cause_no"]).strip() and "ALIAS" in (stype.group(1) if stype else "") or "PLURIES" in (stype.group(1) if stype else ""):
                sec["writ_note"] = v("Orden de venta ALIAS/PLURIES: reemision de una orden previa que no se ejecuto; revisar historial del caso", "inferred", None, "tipo de venta en lista oficial")
        else:
            sec["judgment_date"] = v(None, "unknown", "la lista oficial no trae fecha de sentencia")
        sec["redemption_note"] = v("Sin homestead en el roll de HCAD: normalmente el plazo de redencion es corto (confirmar plazo y prima con abogado); si el dueno fuera de edad avanzada/exento por otra via, revisar.",
                                   "inferred", "No es asesoria legal: attorney review recommended", "inferido de HCAD jur_exempt")
        sec["tax_suit_defendants"] = v(None, "blocked", "hcdistrictclerk.com requiere login", "https://www.hcdistrictclerk.com")
        sec["service_method"] = v(None, "blocked", "hcdistrictclerk.com requiere login", "https://www.hcdistrictclerk.com")
        sec["bankruptcy"] = v(None, "blocked", "PACER requiere cuenta", "https://pacer.uscourts.gov")
        sec["legal_summary"] = v("Sentencia y tipo de venta leidos del condado; demandados, citacion y bancarrota NO verificados (bloqueados). Flag for attorney review.", "inferred")
        owner = (rec.get("intake", {}).get("hcad_owner") or {}).get("value", "el dueno")
        for it in (f"Leer demandados y citacion del cause {rec.get('cause_no')} en hcdistrictclerk.com (login)", f"Buscar bancarrota de {owner[:40]} en PACER"):
            b = {"agent": "legal", "item": it, "why": "requiere login/cuenta"}
            if b not in rec.setdefault("human_blockers", []):
                rec["human_blockers"].append(b)
        save_sections(f, rec, ["legal"])
        n += 1
    print(f"legal context: {n} records")


if __name__ == "__main__":
    main(sys.argv)
