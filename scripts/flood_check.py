#!/usr/bin/env python3
"""Write FEMA effective flood zone into each record's `physical` section.

Usage: python3 scripts/flood_check.py runs/<sale_id> [account_no ...]

For each record with an address: geocode it (US Census geocoder), then query the FEMA
NFHL flood hazard layer at that point. Writes physical.fema_effective_zone,
physical.floodway, physical.fema_sfha (+ note). Accounts given on the command line
restrict the run; default is every record.
Limits (stated in each note): the point is the geocoded ADDRESS, not the parcel
centroid; this is the effective NFHL map, not the draft MAAPnext; no depth grids.
"""
import json
import sys as _s
_s.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from _recio import save_sections
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

GEO = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
NFHL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"


def get(url, params):
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=40) as r:
        return json.load(r)


def geocode(addr):
    j = get(GEO, {"address": addr, "benchmark": "Public_AR_Current", "format": "json"})
    m = j["result"]["addressMatches"]
    return (m[0]["coordinates"]["x"], m[0]["coordinates"]["y"], m[0]["matchedAddress"]) if m else None


def flood(x, y):
    j = get(NFHL, {"where": "1=1", "geometry": f"{x},{y}", "geometryType": "esriGeometryPoint", "inSR": 4326,
                   "spatialRel": "esriSpatialRelIntersects", "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE",
                   "returnGeometry": "false", "f": "json"})
    if "error" in j:
        raise RuntimeError(j["error"])
    return [f["attributes"] for f in j.get("features", [])]


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    run, only = Path(argv[1]), set(argv[2:])
    today = date.today().isoformat()
    n = 0
    for f in sorted((run / "records").glob("*.json")):
        rec = json.loads(f.read_text())
        if only and (rec.get("account_no") or "").strip() not in only:
            continue
        addr = rec.get("address", "").strip()
        if not addr:
            continue
        phys = rec.setdefault("physical", {})
        src = "FEMA NFHL MapServer layer 28 (hazards.fema.gov); geocode: US Census"
        try:
            g = geocode(addr)
            if not g:
                phys["fema_effective_zone"] = {"value": None, "status": "unknown", "source": src, "retrieved_at": today,
                                               "note": f"Census geocoder found no match for '{addr}'"}
            else:
                x, y, matched = g
                feats = flood(x, y)
                note = (f"Point = geocoded address ({matched}), not parcel centroid; effective NFHL only, "
                        "draft MAAPnext not checked; no depth grids.")
                if not feats:
                    phys["fema_effective_zone"] = {"value": "no NFHL polygon at point (likely outside mapped area / zone X unmapped)",
                                                   "status": "inferred", "source": src, "retrieved_at": today, "note": note}
                    phys["floodway"] = {"value": "no", "status": "inferred", "source": src, "retrieved_at": today, "note": note}
                else:
                    zones = sorted({a["FLD_ZONE"] for a in feats if a.get("FLD_ZONE")})
                    sub = sorted({a["ZONE_SUBTY"] for a in feats if a.get("ZONE_SUBTY")})
                    fw = any("FLOODWAY" in (a.get("ZONE_SUBTY") or "").upper() and "0.2" not in (a.get("ZONE_SUBTY") or "")
                             for a in feats)
                    phys["fema_effective_zone"] = {"value": "/".join(zones) + (f" ({'; '.join(sub)})" if sub else ""),
                                                   "status": "verified", "source": src, "retrieved_at": today, "note": note}
                    phys["floodway"] = {"value": "yes" if fw else "no", "status": "verified", "source": src,
                                        "retrieved_at": today, "note": note}
                    phys["fema_sfha"] = {"value": any(a.get("SFHA_TF") == "T" for a in feats), "status": "verified",
                                         "source": src, "retrieved_at": today}
            n += 1
        except Exception as e:  # network/API failure: say so, never guess
            phys["fema_effective_zone"] = {"value": None, "status": "unknown", "source": src, "retrieved_at": today,
                                           "note": f"lookup failed: {e}"}
        save_sections(f, rec, ['physical'])
        time.sleep(0.3)
    print(f"flood-checked {n} records")


if __name__ == "__main__":
    main(sys.argv)
