#!/usr/bin/env python3
"""Download the county's aerial photo of each property on the sale list.

Usage: python3 scripts/fetch_county_images.py runs/<sale_id> [--all]

The county page (hctax.net/Property/listings/taxsalelisting) links every property to an image id; the JPEG is at
https://www.hctax.net/Property/listings/image?id=<id> (aerial view with the parcel highlighted). By default only
properties WITHOUT homestead on the HCAD roll are downloaded (homestead is excluded from analysis); --all includes
them. Saves runs/<sale_id>/images/<account>.jpg (skips files that exist) and writes intake.county_image_id /
county_image_url / county_image_file into each record. Images that the county serves as non-JPEG are skipped and
reported. The picture is a county-provided aid, not a survey: addresses and highlights can be wrong (see the
county's own disclaimer on the listing page).
"""
import json
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _recio import save_sections

LIST = "https://www.hctax.net/Property/listings/taxsalelisting"
IMG = "https://www.hctax.net/Property/listings/image?id={}"
JS = """() => [...document.querySelectorAll('li.listing')].map(li => {
  const a = li.querySelector('a[href^="image?id="]');
  return {acct: (li.querySelector('.account strong') || {}).innerText || '', href: a ? a.getAttribute('href') : ''};
})"""


def main(argv):
    from playwright.sync_api import sync_playwright
    run = Path(argv[1])
    allp = "--all" in argv
    ids = {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        pg = b.new_page()
        pg.goto(LIST, timeout=60000)
        pg.wait_for_timeout(2500)
        pg.click("a.agree.close", timeout=5000)
        pg.wait_for_timeout(1500)
        for _ in range(500):
            new = [r for r in pg.evaluate(JS) if r["acct"] and r["acct"] not in ids]
            for r in new:
                ids[r["acct"]] = r["href"].split("id=")[-1] if r["href"] else ""
            nxt = pg.locator("ul.pagination li.active + li a")
            if not new or nxt.count() == 0:
                break
            nxt.first.click()
            pg.wait_for_timeout(250)
        b.close()
    out = run / "images"
    out.mkdir(exist_ok=True)
    (run / "image_ids.json").write_text(json.dumps(ids, indent=1))
    today = date.today().isoformat()
    ok = skipped = bad = 0
    for f in sorted((run / "records").glob("*.json")):
        rec = json.loads(f.read_text())
        acct = (rec.get("account_no") or "").strip()
        iid = ids.get(acct)
        if not iid:
            continue
        hs = ((rec.get("intake") or {}).get("hcad_homestead_on_roll") or {}).get("value") == "yes"
        if hs and not allp:
            skipped += 1
            continue
        dest = out / f"{acct}.jpg"
        if not dest.exists():
            try:
                req = urllib.request.Request(IMG.format(iid), headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36", "Referer": LIST})
                with urllib.request.urlopen(req, timeout=60) as r:
                    data, ctype = r.read(), r.headers.get("Content-Type", "")
            except Exception as e:
                print(f"  {acct}: error {e}")
                bad += 1
                continue
            if not ctype.startswith("image/") or len(data) < 2000:
                print(f"  {acct}: el condado no tiene foto ({ctype or 'vacio'}, {len(data)} bytes)")
                bad += 1
                continue
            dest.write_bytes(data)
            time.sleep(0.2)
        src = IMG.format(iid)
        rec.setdefault("intake", {})
        for k, v in (("county_image_id", iid), ("county_image_url", src), ("county_image_file", f"images/{acct}.jpg")):
            rec["intake"][k] = {"value": v, "status": "verified", "source": LIST, "retrieved_at": today,
                                "note": "foto aerea del condado; ayuda visual, no es un levantamiento"}
        save_sections(f, rec, ["intake"])
        ok += 1
    print(f"imagenes: {ok} guardadas/verificadas, {bad} sin foto en el condado, {skipped} homestead omitidas -> {out}")


if __name__ == "__main__":
    main(sys.argv)
