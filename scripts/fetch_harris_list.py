#!/usr/bin/env python3
"""Download the Harris County tax sale listing into runs/<sale_id>/candidatos.csv.

Usage: python3 scripts/fetch_harris_list.py runs/harris-2026-11-03 [--chromium PATH]

The county page (hctax.net/Property/listings/taxsalelisting) needs JavaScript and a
terms-of-use click, and shows 10 rows per page, so this drives Chromium via Playwright
(pip install playwright). It reads account, cause, precinct, type, sale#, judgment date
and, when the county has filled them in, address / minimum bid. It never invents values:
missing fields stay empty. Writes scout_report.md next to the CSV.
"""
import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.hctax.net/Property/listings/taxsalelisting"
CHROMIUM = "/opt/pw-browsers/chromium"

JS_ROWS = """() => [...document.querySelectorAll('li.listing')].map(li => {
  const t = s => (li.querySelector(s)?.innerText || '').trim();
  const cells = {};
  li.querySelectorAll('.modal tr').forEach(tr => {
    const td = tr.querySelectorAll('td');
    if (td.length >= 2) cells[td[0].innerText.replace(':','').trim()] = td[1].innerText.trim();
  });
  return {
    account: (li.querySelector('.account strong')?.innerText || '').trim(),
    cause: (li.querySelector('.SuitNumber strong')?.innerText || '').trim(),
    precinct: t('.precinct'),
    address: t('.address'), city: t('.city'), zip: t('.zip'),
    minbid: t('.minBid'), adjudged: t('.adjudgedValue'),
    cells,
  };
})"""


def main(argv):
    from playwright.sync_api import sync_playwright
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    run = Path(args[0])
    sale_id = run.name
    m = re.fullmatch(r"([a-z]+)-(\d{4})-(\d{2})-\d{2}", sale_id)
    if not m or m.group(1) != "harris":
        sys.exit("sale_id must look like harris-YYYY-MM-DD")
    ym = f"{m.group(2)}-{m.group(3)}"
    exe = CHROMIUM
    if "--chromium" in argv:
        exe = argv[argv.index("--chromium") + 1]

    rows, seen, sale_date = [], set(), ""
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        pg = b.new_page()
        pg.goto(URL, timeout=60000)
        pg.wait_for_timeout(2500)
        mm = re.search(r"Sale Date:\s*([A-Za-z]+ \d{1,2}, \d{4})", pg.inner_text("body"))
        sale_date = mm.group(1) if mm else ""
        try:
            pg.click("a.agree.close", timeout=5000)
        except Exception:
            pass
        pg.wait_for_timeout(1500)
        for _ in range(500):
            page_rows = pg.evaluate(JS_ROWS)
            new = [r for r in page_rows if r["account"] and r["account"] not in seen]
            for r in new:
                seen.add(r["account"])
            rows.extend(new)
            nxt = pg.locator("ul.pagination li.active + li a")
            if not new or nxt.count() == 0:
                break
            nxt.first.click()
            pg.wait_for_timeout(300)
        b.close()

    out = run / "candidatos.csv"
    run.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["property_id", "address", "account_no", "cause_no", "opening_bid", "notes"])
        for r in rows:
            c = r["cells"]
            addr = " ".join(x for x in (r["address"], r["city"], r["state"] if "state" in r else "", r["zip"]) if x).strip()
            bid = re.sub(r"[^0-9.]", "", r["minbid"])
            note = "; ".join(x for x in (
                r["precinct"], f"tipo {c.get('Type','')}".strip(), f"sale# {c.get('Sale#','')}".strip(),
                f"sentencia {c.get('Judgment','')}".strip(),
                f"anios_en_sentencia {c.get('Tax Years in Judgement','').strip()}".strip(),
                "" if addr else "sin direccion publicada aun",
                "" if bid else "sin apertura publicada aun",
                f"fuente {URL}") if x and not x.endswith(" "))
            w.writerow([f"harris-{ym}-acct-{r['account']}", addr, r["account"], r["cause"], bid, note])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (run / "scout_report.md").write_text(
        f"# Scout {sale_id}\n\n- Fuente: {URL}\n- Fecha de venta en la pagina: {sale_date or 'no encontrada'}\n"
        f"- Consultado: {now}\n- Filas escritas: {len(rows)}\n"
        f"- Con direccion: {sum(1 for r in rows if r['address'])}; con apertura: {sum(1 for r in rows if r['minbid'])}\n")
    print(f"{len(rows)} rows ({sale_date}) -> {out}")


if __name__ == "__main__":
    main(sys.argv)
