#!/usr/bin/env python3
"""Read the county tax statement of each record and write the `tax` section.

Usage: python3 scripts/tax_statement.py runs/<sale_id> [account_no ...]

Source: https://www.hctax.net/property/listings/saledetail?account=<acct> (public, no login;
Playwright because the statement is rendered by JS). For every record it stores:
  delinquent_by_year        rows {year, tax, penalties_interest, collection_penalty, total}
  total_due_all_years       sum of the statement's "Total Due"
  taxes_in_judgment         years listed by the county as inside the judgment (from candidatos.csv notes)
  post_judgment_taxes       statement years NOT inside the judgment (buyer inherits these) -> sum
  current_year_estimate     INFERRED = most recent billed year's base tax (next bill due 31 Jan)
  buyer_tax_tail_estimate   post_judgment_taxes + current_year_estimate (INFERRED)
  assessed_owner / appraised_value / tax_exemptions_note
Statement figures are as of the retrieval date and grow with penalties; a statement that the county
cannot produce ("uncertified") is recorded as status "blocked" with a human_blockers entry.
HCAD homestead exemptions are in `intake` (hcad_*), not here.
"""
import json
import sys as _s
_s.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from _recio import save_sections
import re
import sys
from datetime import date
from pathlib import Path

URL = "https://www.hctax.net/property/listings/saledetail?account={}"
MONEY = r"\$([\d,]+\.\d{2})"


def money(x):
    return float(x.replace(",", ""))


def parse(text):
    t = re.sub(r"\s+", " ", text)
    if "There was a problem retrieving the statement" in t:
        return None
    rows = []
    for m in re.finditer(r"\b(20\d\d) " + MONEY + " " + MONEY + " " + MONEY + " " + MONEY, t):
        rows.append({"year": int(m.group(1)), "tax": money(m.group(2)), "penalties_interest": money(m.group(3)),
                     "collection_penalty": money(m.group(4)), "total": money(m.group(5))})
    tot = re.search(r"Total Due >>> " + MONEY, t)
    owner = re.search(r"Current As Of: Assessed Owner Property Description \S+ [\d/]+ [\d:]+ [AP]M (.*?) 20\d\d Appraised Values", t)
    appr = re.search(r"Appraised Value: ([\d,]+)", t)
    asof = re.search(r"Property Description [\d-]+ ([\d/]+)", t)
    return {"rows": rows, "total_due": money(tot.group(1)) if tot else None,
            "header": owner.group(1) if owner else None,
            "appraised": money(appr.group(1)) if appr else None, "asof": asof.group(1) if asof else None}


def main(argv):
    from playwright.sync_api import sync_playwright
    if len(argv) < 2:
        sys.exit(__doc__)
    run, only = Path(argv[1]), set(argv[2:])
    import csv
    notes = {r["account_no"]: r["notes"] for r in csv.DictReader((run / "candidatos.csv").open(encoding="utf-8-sig"))}
    today = date.today().isoformat()
    n = 0
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        pg = b.new_page()
        for f in sorted((run / "records").glob("*.json")):
            rec = json.loads(f.read_text())
            acct = (rec.get("account_no") or "").strip()
            if not acct or (only and acct not in only):
                continue
            src = URL.format(acct)
            sec = rec.setdefault("tax", {})
            try:
                pg.goto(src, timeout=60000)
                pg.wait_for_timeout(2500)
                body = pg.inner_text("main") if pg.locator("main").count() else pg.inner_text("body")
                d = parse(body)
            except Exception as e:
                d, body = None, f"error {e}"
            if not d or not d["rows"]:
                sec["tax_statement"] = {"value": None, "status": "blocked", "source": src, "retrieved_at": today,
                                        "note": "El condado no produjo estado de cuenta (cuenta no certificada, inexistente o error)."}
                rec.setdefault("human_blockers", []).append({"agent": "tax", "item": f"Pedir estado de cuenta de {acct} al Tax Office (713-274-8120)",
                                                             "why": "statement no disponible en hctax.net"})
            else:
                yj = re.search(r"anios_en_sentencia ([^;]*)", notes.get(acct, ""))
                jyears = []
                if yj:
                    txt = yj.group(1)
                    for y1, y2 in re.findall(r"(\d{4})\s*-\s*(\d{4})", txt):          # county shows a RANGE: '2004 - 2018'
                        jyears += list(range(int(y1), int(y2) + 1))
                    rest = re.sub(r"\d{4}\s*-\s*\d{4}", " ", txt)
                    jyears += [int(y) for y in re.findall(r"\b(?:19|20)\d\d\b", rest)]
                    jyears = sorted(set(jyears))
                rows = d["rows"]
                post = [r for r in rows if r["year"] not in jyears] if jyears else None
                post_sum = round(sum(r["total"] for r in post), 2) if post is not None else None
                last = max(rows, key=lambda r: r["year"])
                cur = last["tax"]
                tail = round(post_sum + cur, 2) if post_sum is not None else None
                v = lambda val, status="verified", note=None: {"value": val, "status": status, "source": src,
                                                               "retrieved_at": today, **({"note": note} if note else {})}
                sec["delinquent_by_year"] = v(rows, note=f"statement as of {d['asof']}")
                sec["total_due_all_years"] = v(d["total_due"])
                sec["taxes_in_judgment"] = v(jyears, note="from county sale list ('Tax Years in Judgement'); a range 'a - b' is expanded to every year from a to b") if jyears else \
                    v(None, "unknown", "el condado no lista los anios incluidos en la sentencia")
                sec["post_judgment_taxes"] = v(post_sum) if post_sum is not None else v(None, "unknown", "sin anios de sentencia no se puede separar")
                sec["current_year_estimate"] = v(cur, "inferred", f"base tax of {last['year']} as proxy for the {last['year'] + 1} bill (due 31 Jan); penalties not included")
                sec["buyer_tax_tail_estimate"] = v(tail, "inferred" if tail is not None else "unknown",
                                                   "post-judgment years (statement totals incl. penalties) + current-year proxy; excludes later-year penalties and any account of other jurisdictions")
                sec["assessed_owner_county"] = v(d["header"])
                sec["appraised_value_county"] = v(d["appraised"])
            save_sections(f, rec, ['tax'])
            n += 1
        b.close()
    print(f"tax statements: {n} records")


if __name__ == "__main__":
    main(sys.argv)
