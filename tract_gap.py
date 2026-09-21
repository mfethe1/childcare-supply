#!/usr/bin/env python3
"""Tract-level childcare desert analysis (step 3).

1. Census geocoder BATCH endpoint (keyless, 10k rows/request) -> tract GEOID
   for providers with street+city, cached in data/tract_geo.csv.
2. CensusReporter keyless API -> B01001 under-5 population per tract per state,
   cached in data/tract_u5_<st>.json.
3. Score seats per 100 under-5 per tract; <33 = desert (CAP/CEEL threshold).

Limitations (documented in README): capacity attributed to the provider's
tract (supply location), not where enrolled children live; no-match addresses
dropped (count reported); WI/CT/NYC excluded (no county/address completeness).
"""
import csv
import io
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
GEO_CACHE = os.path.join(DATA, "tract_geo_cache.json")
FIPS = {"ca": "06", "de": "10", "hi": "15", "ma": "25", "mn": "27",
        "ne": "31", "nj": "34", "ny": "36", "pa": "42",
        "va": "51", "vt": "50", "wa": "53"}


def batch_geocode(records):
    """records: list of (key, street, city, state, zip). Returns {key: geoid|None}.
    Census addressbatch returns: id, input, Match, matchtype, matched, coords,
    tigerlineid, side, state, county, tract, block."""
    out = {}
    for i in range(0, len(records), 9000):
        chunk = records[i:i + 9000]
        buf = io.StringIO()
        w = csv.writer(buf, quoting=csv.QUOTE_ALL)
        for j, (key, street, city, st, zc) in enumerate(chunk):
            w.writerow([j, street, city, st, zc or ""])
        path = f"/tmp/tract_batch_{i}.csv"
        open(path, "w").write(buf.getvalue())
        r = subprocess.run(
            ["curl", "-sk", "--max-time", "600",
             "-F", "benchmark=Public_AR_Current",
             "-F", "vintage=Census2020_Current",
             f"-F", f"addressFile=@{path};type=text/csv",
             "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"],
            capture_output=True, text=True)
        lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
        if not lines:
            print(f"  batch {i}: EMPTY RESPONSE")
            for key, *_ in chunk:
                out[key] = None
            continue
        matched = 0
        for line in lines:
            f = next(csv.reader([line]))
            if len(f) < 12 or f[2] != "Match":
                continue
            st_f, co_f, tr_f = f[8], f[9], f[10]
            if st_f and co_f and tr_f:
                idx = int(f[0])
                out[chunk[idx][0]] = st_f + co_f + tr_f
                matched += 1
        print(f"  batch {i}: {len(lines)} rows, {matched} tract matches", flush=True)
    return out


def fetch_tract_u5(state):
    path = os.path.join(DATA, f"tract_u5_{state}.json")
    if os.path.exists(path):
        return json.load(open(path))
    fips = FIPS[state]
    url = (f"https://api.censusreporter.org/1.0/data/show/latest"
           f"?table_ids=B01001&geo_ids=140|04000US{fips}")
    r = subprocess.run(["curl", "-sk", "--max-time", "600", url],
                       capture_output=True, text=True)
    d = json.loads(r.stdout)
    out = {}
    for geoid, blk in d["data"].items():
        est = blk["B01001"]["estimate"]
        u5 = (est.get("B01001003") or 0) + (est.get("B01001027") or 0)
        out[geoid.replace("14000US", "")] = int(u5)
    json.dump(out, open(path, "w"))
    return out


def main():
    import sqlite3
    db = sqlite3.connect(os.path.join(HERE, "childcare.db"))
    cache = json.load(open(GEO_CACHE)) if os.path.exists(GEO_CACHE) else {}
    rows = db.execute("""
        SELECT state, provider_id, address, city, zip, capacity_total
        FROM providers
        WHERE address IS NOT NULL AND address != ''
          AND city IS NOT NULL AND city != ''
          AND state IN ('CA','DE','HI','MA','MN','NE','NJ','NY','PA','VA','VT','WA')
    """).fetchall()
    print(f"{len(rows)} providers with addresses; cache {len(cache)}")

    todo = [(f"{a}|{c}|{s}|{z}", a, c, s, z)
            for s, p, a, c, z, cap in rows
            if f"{a}|{c}|{s}|{z}" not in cache]
    if todo:
        print(f"geocoding {len(todo)} new addresses...")
        got = batch_geocode(todo)
        cache.update(got)
        json.dump(cache, open(GEO_CACHE, "w"))
    matched = sum(1 for s, p, a, c, z, cap in rows
                  if cache.get(f"{a}|{c}|{s}|{z}"))
    print(f"tract matched: {matched}/{len(rows)} "
          f"({100.0*matched/max(1,len(rows)):.1f}%)")

    seats = {}
    for s, p, a, c, z, cap in rows:
        t = cache.get(f"{a}|{c}|{s}|{z}")
        if t and cap:
            seats[t] = seats.get(t, 0) + cap

    scored, deserts = [], []
    for st_ab in sorted(FIPS):
        u5 = fetch_tract_u5(st_ab)
        for t, u5v in u5.items():
            s = seats.get(t, 0)
            rate = (100.0 * s / u5v) if u5v else None
            rec = [t, u5v, s, round(rate, 2) if rate is not None else None]
            scored.append(rec)
            if rate is not None and u5v >= 50 and rate < 33:
                deserts.append(rec)
    sc = [x for x in scored if x[3] is not None and x[1] >= 50]
    print(f"scored tracts (u5>=50): {len(sc)} | deserts: {len(deserts)} "
          f"({100.0*len(deserts)/max(1,len(sc)):.1f}%)")
    json.dump({"scored": scored, "deserts": deserts},
              open(os.path.join(HERE, "tract_deserts.json"), "w"))
    print("-> tract_deserts.json")


if __name__ == "__main__":
    main()
