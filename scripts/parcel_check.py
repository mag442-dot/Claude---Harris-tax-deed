#!/usr/bin/env python3
"""Parcel-level physical check -> `physical` section (replaces the address-point flood_check).

Usage: python3 scripts/parcel_check.py runs/<sale_id> [account_no ...]

For each record: fetch the parcel polygon from the county GIS (HCAD Parcels MapServer), then
  - intersect it with the FEMA NFHL flood hazard layer -> zones touching the parcel and the share of
    the parcel area in each zone (shapely, local metric approximation) and in the SFHA / floodway
  - ask the HCAD Cities layer whether the parcel centroid is inside a city (zoning/permits differ)
  - estimate lot width/depth (minimum rotated rectangle, in feet; an approximation, NOT a survey)
Writes physical.fema_effective_zone, fema_zone_shares, fema_sfha_pct, floodway, floodway_pct,
parcel_city, lot_sqft_gis, lot_dimensions_est, parcel_centroid. Effective NFHL only: the draft MAAPnext
and depth grids are not read. Needs `pip install shapely`.
"""
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _recio import save_sections
from shapely.geometry import Polygon, shape  # noqa: E402

GIS = "https://www.gis.hctx.net/arcgis/rest/services/HCAD"
NFHL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
FT_PER_DEG_LAT = 364000.0


def get(url, params, post=False):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url if post else url + "?" + data.decode(), data=data if post else None)
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # transient SSL/network errors from the proxy or the county servers
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def local(rings, lat0):
    k = math.cos(math.radians(lat0))
    return [[(x * k * FT_PER_DEG_LAT, y * FT_PER_DEG_LAT) for x, y in ring] for ring in rings]


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    run, only = Path(argv[1]), set(argv[2:])
    today = date.today().isoformat()
    n = 0
    for f in sorted((run / "records").glob("*.json")):
        rec = json.loads(f.read_text())
        acct = (rec.get("account_no") or "").strip()
        if not acct or (only and acct not in only):
            continue
        phys = rec.setdefault("physical", {})
        src_p = f"{GIS}/Parcels/MapServer/0 (HCAD_NUM={acct})"
        src_f = "FEMA NFHL MapServer layer 28 (hazards.fema.gov)"
        fv = lambda val, st="verified", src=src_f, note=None: {"value": val, "status": st, "source": src, "retrieved_at": today, **({"note": note} if note else {})}
        try:
            j = get(GIS + "/Parcels/MapServer/0/query", {"where": f"HCAD_NUM='{acct}'", "outFields": "land_sqft,site_city,state_class",
                                                          "returnGeometry": "true", "outSR": 4326, "f": "json"})
            feats = j.get("features", [])
            if not feats:
                phys["fema_effective_zone"] = fv(None, "unknown", src_p, "la cuenta no esta en la capa de parcelas del condado")
                save_sections(f, rec, ["physical"]); n += 1; continue
            rings = feats[0]["geometry"]["rings"]
            lat0 = sum(y for x, y in rings[0]) / len(rings[0])
            parcel = Polygon(local(rings, lat0)[0])
            area_ft = parcel.area
            c = parcel.centroid
            lon0 = sum(x for x, y in rings[0]) / len(rings[0])
            mrr = parcel.minimum_rotated_rectangle
            xs, ys = mrr.exterior.coords.xy
            e1 = math.dist((xs[0], ys[0]), (xs[1], ys[1])); e2 = math.dist((xs[1], ys[1]), (xs[2], ys[2]))
            w, d = sorted((e1, e2))
            phys["parcel_centroid"] = fv({"lon": round(lon0, 6), "lat": round(lat0, 6)}, "verified", src_p)
            phys["lot_sqft_gis"] = fv(round(area_ft), "verified", src_p, "area del poligono (aprox.); compara con HCAD land_ar")
            phys["lot_dimensions_est"] = fv(f"~{w:.0f} x {d:.0f} ft (rectangulo minimo rotado)", "inferred", src_p, "aproximacion geometrica, NO es un levantamiento topografico; forma irregular puede engañar")
            # flood intersection
            g = {"rings": rings, "spatialReference": {"wkid": 4326}}
            fj = get(NFHL, {"where": "1=1", "geometry": json.dumps(g), "geometryType": "esriGeometryPolygon", "inSR": 4326,
                            "spatialRel": "esriSpatialRelIntersects", "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF",
                            "returnGeometry": "true", "outSR": 4326, "f": "json"}, post=True)
            shares, sfha_ft, fw_ft = {}, 0.0, 0.0
            for ft in fj.get("features", []):
                at = ft["attributes"]
                try:
                    poly = Polygon(local(ft["geometry"]["rings"], lat0)[0])
                    inter = parcel.intersection(poly.buffer(0)).area
                except Exception:
                    continue
                key = at["FLD_ZONE"] + (f" ({at['ZONE_SUBTY']})" if at.get("ZONE_SUBTY") else "")
                shares[key] = shares.get(key, 0.0) + inter
                if at.get("SFHA_TF") == "T":
                    sfha_ft += inter
                if "FLOODWAY" in (at.get("ZONE_SUBTY") or "").upper() and "0.2" not in (at.get("ZONE_SUBTY") or ""):
                    fw_ft += inter
            pct = {k: round(100 * v / area_ft, 1) for k, v in shares.items() if v / area_ft > 0.005}
            if not fj.get("features"):
                phys["fema_effective_zone"] = fv("sin poligono NFHL sobre el predio (no mapeado)", "inferred", src_f, "NFHL no cubre el predio; no equivale a 'sin riesgo'")
                phys["floodway"] = fv("no", "inferred", src_f)
            else:
                top = max(pct, key=pct.get) if pct else "?"
                phys["fema_effective_zone"] = fv(top + (" + otras" if len(pct) > 1 else ""), note="zona con mayor area dentro del predio (NFHL efectivo)")
                phys["fema_zone_shares"] = fv(pct, note="% del area del predio por zona")
                phys["fema_sfha_pct"] = fv(round(100 * sfha_ft / area_ft, 1))
                phys["floodway"] = fv("yes" if fw_ft / area_ft > 0.005 else "no")
                phys["floodway_pct"] = fv(round(100 * fw_ft / area_ft, 1))
            try:
                cj = get(GIS + "/HCAD_Cities/MapServer/0/query", {"geometry": f"{lon0},{lat0}", "geometryType": "esriGeometryPoint", "inSR": 4326,
                                                                   "spatialRel": "esriSpatialRelIntersects", "outFields": "name", "returnGeometry": "false", "f": "json"})
                names = [x["attributes"]["name"] for x in cj.get("features", [])]
                phys["parcel_city"] = fv(", ".join(names) if names else "fuera de limites de ciudad en HCAD_Cities (probable condado no incorporado)",
                                         "verified" if names else "inferred", GIS + "/HCAD_Cities/MapServer/0")
            except Exception as e:
                phys["parcel_city"] = fv(None, "unknown", GIS + "/HCAD_Cities", f"fallo: {e}")
        except Exception as e:
            phys["fema_effective_zone"] = fv(None, "unknown", src_f, f"fallo de consulta: {e}")
        save_sections(f, rec, ["physical"])
        n += 1
        time.sleep(0.25)
    print(f"parcel_check: {n} records")


if __name__ == "__main__":
    main(sys.argv)
