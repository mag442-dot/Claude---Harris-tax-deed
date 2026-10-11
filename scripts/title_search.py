#!/usr/bin/env python3
"""Search the Harris County Clerk real-property index for each record's owner.

Usage: python3 scripts/title_search.py runs/<sale_id> [account_no ...]

For each record (optionally limited to the given accounts) it searches the public RP
index (no login/captcha) for the HCAD owner name as Grantee and as Grantor and writes
`title.rp_hits_grantee`, `title.rp_hits_grantor`, `title.rp_type_counts` and
`title.rp_summary` (all status "inferred": name search only, identity NOT confirmed,
index only, no images, name variants may be missed). Legal-description search and
reading the images are left to the title agent / a human. Rows are kept verbatim.
Needs Playwright + Chromium.
"""
import json
import re
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

URL = "https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx"
P = "#ctl00_ContentPlaceHolder1_"
MAX_PAGES = 6
JS = """() => [...document.querySelectorAll('tr')]
  .filter(tr => /^\\s*[A-Z]{1,4}-\\d{4}-\\d+/.test(tr.children[1]?.innerText || ''))
  .map(tr => [...tr.children].slice(1, 6).map(td => td.innerText.replace(/\\s+/g, ' ').trim()))"""


def clean_name(owner):
    first = re.split(r"\s*\(\d|;|&", owner)[0].strip()
    return " ".join(first.split()[:2]) if len(first.split()) > 2 else first


def run_search(pg, field, name):
    pg.goto(URL, timeout=60000)
    pg.fill(P + field, name)
    pg.click(P + "btnSearch")
    pg.wait_for_timeout(5000)
    rows, seen = [], set()
    for _ in range(MAX_PAGES):
        for r in pg.evaluate(JS):
            key = r[0]
            if key not in seen:
                seen.add(key)
                rows.append(" | ".join(r))
        nxt = pg.locator("a:has-text('Next'), a:has-text('>')").first
        if nxt.count() == 0 or not nxt.is_visible():
            break
        try:
            nxt.click()
            pg.wait_for_timeout(1500)
        except Exception:
            break
    return rows


def main(argv):
    from playwright.sync_api import sync_playwright
    if len(argv) < 2:
        sys.exit(__doc__)
    run, only = Path(argv[1]), set(argv[2:])
    today = date.today().isoformat()
    n = 0
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        pg = b.new_page()
        for f in sorted((run / "records").glob("*.json")):
            rec = json.loads(f.read_text())
            acct = (rec.get("account_no") or "").strip()
            if only and acct not in only:
                continue
            owner = (rec.get("intake", {}).get("hcad_owner") or {}).get("value", "")
            if not owner or "CURRENT OWNER" in owner.upper():
                continue
            name = clean_name(owner)
            sec = rec.setdefault("title", {})
            src = f"{URL} (grantee/grantor name search '{name}')"
            note = ("Name search only; identity not confirmed (same-name risk); index only, no images; "
                    "other spellings/entities not searched; verify with legal-description search.")
            try:
                ee = run_search(pg, "txtEE", name)
                time.sleep(0.5)
                orr = run_search(pg, "txtOR", name)
                counts = Counter(r.split(" | ")[2] if len(r.split(" | ")) > 2 else "?" for r in ee + orr)
                for key, val in (("rp_hits_grantee", ee), ("rp_hits_grantor", orr)):
                    sec[key] = {"value": val, "status": "inferred", "source": src, "retrieved_at": today, "note": note}
                sec["rp_type_counts"] = {"value": dict(counts), "status": "inferred", "source": src, "retrieved_at": today}
                sec["rp_summary"] = {"value": f"{len(ee)} instruments as grantee, {len(orr)} as grantor (index, name '{name}')",
                                     "status": "inferred", "source": src, "retrieved_at": today, "note": note}
            except Exception as e:
                sec["rp_summary"] = {"value": None, "status": "blocked", "source": src, "retrieved_at": today,
                                     "note": f"search failed: {e}"}
                rec.setdefault("human_blockers", []).append(
                    {"agent": "title", "item": f"Buscar '{name}' en cclerk RP index (fallo automatico)", "why": str(e)[:120]})
            f.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n")
            n += 1
            time.sleep(0.5)
        b.close()
    print(f"title-searched {n} records")


if __name__ == "__main__":
    main(sys.argv)
