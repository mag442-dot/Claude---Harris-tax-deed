#!/usr/bin/env python3
"""Funnel of ALL properties: at which stage each one stopped, and why.

Usage: python3 scripts/funnel_export.py runs/<sale_id>

Writes runs/<sale_id>/embudo_sheet.csv (one row per property on the official list) and
runs/<sale_id>/embudo_resumen_sheet.csv (counts per stage). Stages:
  1 Excluida: homestead en el roll de HCAD            (decision de Miguel)
  2 Sin datos HCAD                                     (no analizable)
  3 Descartada/en espera por el filtro automatico      (review_rules.py: floodway, techo<apertura, no dúplex, faltan datos)
  4 Paso el filtro automatico pero NO la leyo ningun agente
  5 Revisada por el agente reviewer                    (CONDICIONAL = paso; VIGILAR = en espera; NO PARA DUPLEX/BAJA/DESCARTADA = descartada)
"No revisada" is NOT a rejection: it only means no agent has read it yet.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

MARK = "nunca COMPRA FUERTE sin esa revision"


def g(rec, sec, key):
    return ((rec.get(sec) or {}).get(key) or {}).get("value")


def main(argv):
    run = Path(argv[1])
    cand = {r["account_no"]: r for r in csv.DictReader((run / "candidatos.csv").open(encoding="utf-8-sig"))}
    short = set((run / "shortlist.txt").read_text().split()) if (run / "shortlist.txt").exists() else set()
    rows = []
    for f in sorted((run / "records").glob("*.json")):
        rec = json.loads(f.read_text())
        acct = (rec.get("account_no") or "").strip()
        rv = rec.get("review") or {}
        bsf = str(g(rec, "intake", "hcad_building_sqft") or "0")
        lot = bsf in ("0", "0.0") and str(g(rec, "intake", "hcad_state_class") or "").startswith(("C", "D", "E"))
        tipo = "LOTE" if lot else "CASA/OTRO"
        hs = g(rec, "intake", "hcad_homestead_on_roll")
        agent = bool(rv) and MARK not in rv.get("rationale", "")
        dec = rv.get("decision", "")
        why = rv.get("rationale", "")
        if g(rec, "intake", "hcad_owner") is None:
            stage, sub = "2 Sin datos HCAD", "la cuenta no aparece en el roll de HCAD"
        elif hs == "yes":
            stage, sub = "1 Excluida: homestead", "exencion de vivienda en el roll de HCAD (decision de Miguel: se excluye)"
        elif agent:
            stage = "5 Revisada por agente"
            sub = {"CONDICIONAL": "PASO (condicional a verificar pendientes)", "VIGILAR": "EN ESPERA (falta informacion clave)"}.get(dec, "DESCARTADA o no apta: " + dec)
        elif dec in ("DESCARTADA", "BAJA", "NO PARA DUPLEX"):
            stage = "3 Filtro automatico"
            sub = {"DESCARTADA": "DESCARTADA: predio en floodway", "BAJA": "BAJA: techo teorico menor que la apertura",
                   "NO PARA DUPLEX": "NO PARA DUPLEX: lote chico (<4,000 sqft) o mayormente en zona de inundacion especial"}[dec]
        elif dec == "VIGILAR":
            stage, sub = "3 Filtro automatico", "EN ESPERA: falta apertura publicada o estado de cuenta de impuestos"
        elif dec in ("CONDICIONAL", "SOLO CERCA DE LA APERTURA"):
            stage = "4 Paso filtros, sin revision de agente"
            sub = ("lote que paso pero no entro a la lista corta" if lot else "casa: no revisada (la revision de agentes se hizo solo en lotes vacios, que es tu estrategia)")
            sub += f" [{dec}]"
        else:
            stage, sub = "2 Sin datos HCAD", "sin decision"
        c = cand.get(acct, {})
        rows.append({
            "etapa_final": stage, "detalle": sub, "decision": dec if (agent or stage.startswith(("3", "4"))) else "",
            "tipo": tipo, "direccion": rec.get("address", ""), "apertura": c.get("opening_bid", ""),
            "valor_hcad": g(rec, "intake", "hcad_market_value") or "", "techo_teorico": rv.get("bid_ceiling") if rv.get("bid_ceiling") is not None else "",
            "homestead": hs or "", "zona_fema": g(rec, "physical", "fema_effective_zone") or "",
            "motivo": (why[:300] + ("…" if len(why) > 300 else "")) if (agent or stage.startswith("3")) else "",
            "property_id": rec["property_id"], "account_no": acct})
    rows.sort(key=lambda r: (r["etapa_final"], r["decision"], r["direccion"]))
    cols = list(rows[0])
    with (run / "embudo_sheet.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
    cnt = Counter((r["etapa_final"], r["detalle"].split(" [")[0] if r["etapa_final"].startswith("4") else r["detalle"], r["tipo"]) for r in rows)
    with (run / "embudo_resumen_sheet.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["etapa_final", "detalle", "tipo", "cantidad"])
        for (a, b, t), n in sorted(cnt.items()):
            w.writerow([a, b, t, n])
        w.writerow(["TOTAL lista oficial", "", "", len(rows)])
    print(f"{len(rows)} propiedades")
    for (a, b, t), n in sorted(cnt.items()):
        print(f"{n:4d}  {a} | {b} | {t}")


if __name__ == "__main__":
    main(sys.argv)
