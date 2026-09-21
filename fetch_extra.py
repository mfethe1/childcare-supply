#!/usr/bin/env python3
"""Fetch all 13 'extra' verified sources (the ones beyond fetch.py's original 5).

Writes data/<name>.json in raw form (same as the ad-hoc harvests that built v0.3):
CO, CT, NJ, PA, WA, WI, NE via Socrata/ArcGIS; MA, VT via Socrata paging;
MN via HFLV paging; OK static JSON; VA via 4 ArcGIS layers (va_*.json);
HI is refreshed by harvest scripts (fetch_hi.py + harvest_hi_oahu.py).
"""
import json
import os
import ssl
import time
import urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (childcare-supply refresh)"}
DATA = os.path.join(os.path.dirname(__file__), "data")

SOCRATA = {
    "co": "https://data.colorado.gov/resource/a9rr-k8mu.json",
    "ct": "https://data.ct.gov/resource/h8mr-dn95.json",
    "nj": "https://data.nj.gov/resource/cru5-4rmm.json",
    "pa": "https://data.pa.gov/resource/ajn5-kaxt.json",
    "wa": "https://data.wa.gov/resource/was8-3ni8.json",
    "ma": "https://educationtocareer.data.mass.gov/resource/iyks-y3g6.json",
    "vt": "https://data.vermont.gov/resource/ctdw-tmfz.json",
}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, context=CTX, timeout=120) as r:
        return r.read()


def jget(url):
    return json.loads(get(url).decode("utf-8", "replace"))


def socrata_all(base, page=50000):
    out, off = [], 0
    while True:
        batch = jget(f"{base}?$limit={page}&$offset={off}&$order=:id")
        out.extend(batch)
        if len(batch) < page:
            return out
        off += page


def arcgis_all(url):
    out, off = [], None
    while True:
        q = f"{url}?where=1%3D1&outFields=*&f=json&resultOffset={off or 0}&resultRecordCount=2000"
        d = jget(q)
        feats = [f["attributes"] for f in d.get("features", [])]
        out.extend(feats)
        if d.get("exceededTransferLimit") is not True or not feats:
            return out
        off = (off or 0) + len(feats)


VA_LAYERS = {
    "va_centers": "https://services3.arcgis.com/PJoVv2u1K1SOrkmR/arcgis/rest/services/VA_Licensed_Child_Care_Centers_December_2025/FeatureServer/0/query",
    "va_fdh": "https://services3.arcgis.com/PJoVv2u1K1SOrkmR/arcgis/rest/services/VA_Licensed_Family_Day_Homes_June_2026/FeatureServer/0/query",
    "va_rex": "https://services3.arcgis.com/PJoVv2u1K1SOrkmR/arcgis/rest/services/VA_Religious_Exempt_Child_Care_Programs_June_2026/FeatureServer/0/query",
    "va_vr": "https://services3.arcgis.com/PJoVv2u1K1SOrkmR/arcgis/rest/services/VA_Voluntarily_Registered_June_2026/FeatureServer/0/query",
}


# MN: the state HFLV host (licenselookup.health.state.mn.us) intermittently fails DNS;
# the CCAoA mirror carries the identical HFLV schema (licnsecap/totalvacs/truevacs/county).
MN_HFLV = ("https://services7.arcgis.com/s3vGpGobX9nzlLH3/arcgis/rest/services/"
           "MN_Child_Care_Supply_HFLV/FeatureServer/0/query")

# OK: okdhs publishes via ArcGIS Online (krsunny account, official fields incl. Capacity/County_of_Facility)
OK_URL = ("https://services3.arcgis.com/yBwJ5BxqvbumespK/arcgis/rest/services/"
          "Oklahoma_Child_Care_Centers/FeatureServer/0/query")


def main():
    os.makedirs(DATA, exist_ok=True)
    for name, base in SOCRATA.items():
        try:
            rows = socrata_all(base)
            json.dump(rows, open(os.path.join(DATA, f"{name}.json"), "w"))
            print(f"{name}: {len(rows)} rows")
        except Exception as e:
            print(f"{name}: FETCH FAILED: {e}")
    for name, url in VA_LAYERS.items():
        try:
            rows = arcgis_all(url)
            json.dump(rows, open(os.path.join(DATA, f"{name}.json"), "w"))
            print(f"{name}: {len(rows)} rows")
        except Exception as e:
            print(f"{name}: FETCH FAILED: {e}")
    for name, url in (("mn", MN_HFLV), ("ok", OK_URL)):
        try:
            rows = arcgis_all(url)
            json.dump(rows, open(os.path.join(DATA, f"{name}.json"), "w"))
            print(f"{name}: {len(rows)} rows")
        except Exception as e:
            print(f"{name}: FETCH FAILED: {e}")


if __name__ == "__main__":
    main()
