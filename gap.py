#!/usr/bin/env python3
"""Gap analysis: licensed childcare seats (DB) vs under-5 population (ACS 2023 via CensusReporter).

Per-county seats-per-100-under-5; deserts flagged at <33 (the CAP/CEEL standard threshold:
a county is a childcare desert when licensed capacity could serve < 1/3 of children under 5).
Usage:
  python3 gap.py                    # full national table for covered states
  python3 gap.py county "Travis"    # single county lookup
"""
import json, sqlite3, sys, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "childcare.db")
INACTIVE = {"INACTIVE","CLOSED","Not Active","Suspended","Pending Revocation","Pending Revocation and Denial","PENDING","ON PROBATION"}
DESERT_THRESHOLD = 33  # seats per 100 under-5 children

# state name -> fips for our covered states
STATE_FIPS = {"california":"06","colorado":"08","connecticut":"09","delaware":"10","nebraska":"31",
              "new jersey":"34","new york":"36","pennsylvania":"42","texas":"48","washington":"53","wisconsin":"55"}
# postal codes, as stored in the providers.state column
STATE_FIPS.update({"ca":"06","co":"08","ct":"09","de":"10","ne":"31","nj":"34","ny":"36",
                   "pa":"42","tx":"48","wa":"53","wi":"55",
                   "ma":"25","vt":"50","mn":"27","ok":"40","va":"51","hi":"15"})

def norm_county(name):
    n = str(name).strip().lower()
    for suffix in (" county", " parish", " borough", " census area", " municipality", " city and borough"):
        if n.endswith(suffix):
            n = n[: -len(suffix)]
    return n.strip()

def load_census():
    d = json.load(open(os.path.join(HERE, "data", "census_u5.json")))
    out = {}
    for geo, info in d.items():
        fips = geo.replace("05000US", "")
        name = info["name"]  # e.g. "Alameda County, CA"
        county_part, st_part = (name.rsplit(", ", 1) + [None])[:2] if ", " in name else (name, None)
        # derive state fips from geo code
        st_fips = fips[:2]
        out[(st_fips, norm_county(county_part))] = info["u5"]
    return out

def main():
    db = sqlite3.connect(DB)
    census = load_census()

    q = """SELECT county, state, SUM(capacity_total), COUNT(*) FROM providers
           WHERE county IS NOT NULL AND county != ''
           AND (status IS NULL OR status = '' OR status NOT IN ({}))
           GROUP BY lower(county), state""".format(",".join(f"'{s}'" for s in INACTIVE))
    rows = db.execute(q).fetchall()

    # county-level seats from our DB grouped by (state_fips, normalized county)
    seats = {}
    unmatched = []
    for county, state, cap, n in rows:
        st_fips = None
        if state:
            st_fips = STATE_FIPS.get(str(state).strip().lower())
        if st_fips is None:
            # infer state from county match uniqueness later
            unmatched.append((county, state, cap, n))
            continue
        key = (st_fips, norm_county(county))
        a = seats.setdefault(key, [0, 0])
        a[0] += cap or 0
        a[1] += n

    # resolve unmatched by unique county name within covered states
    by_county_name = {}
    for (sf, cn) in census:
        by_county_name.setdefault(cn, []).append(sf)
    for county, state, cap, n in unmatched:
        cn = norm_county(county)
        cands = by_county_name.get(cn, [])
        if len(cands) == 1:
            key = (cands[0], cn)
            a = seats.setdefault(key, [0, 0])
            a[0] += cap or 0
            a[1] += n

    # states with NO county field in provider data would create false deserts;
    # only score counties in states where we have at least one county-keyed seat row
    states_with_county_data = {sf for (sf, cn) in seats}
    ALL_COVERED_FIPS = set(STATE_FIPS.values())
    excluded_states = ALL_COVERED_FIPS - states_with_county_data

    # NY exception: NYC's five borough counties are served by the NYC-DOHMH source
    # which has no county field — exclude them rather than report false deserts
    NYC_COUNTIES = {"new york", "kings", "queens", "bronx", "richmond"}
    census = {(sf, cn): u5 for (sf, cn), u5 in census.items()
              if not (sf == "36" and cn in NYC_COUNTIES)}

    print(f"{'county':38} {'u5':>8} {'seats':>7} {'per100':>7} {'provs':>6} desert")
    deserts = []
    total_counties = 0
    for (sf, cn), u5 in sorted(census.items(), key=lambda kv: kv[1]):
        cap, n = seats.get((sf, cn), (0, 0))
        if u5 == 0 or sf in excluded_states:
            continue
        total_counties += 1
        per100 = round(100.0 * cap / u5, 1)
        is_desert = per100 < DESERT_THRESHOLD
        if is_desert:
            deserts.append((cn, u5, cap, per100))
        flag = "DESERT" if is_desert else ""
        print(f"{cn + ' (' + sf + ')':38} {int(u5):>8} {int(cap):>7} {per100:>7} {n:>6} {flag}")

    print(f"\ncovered counties: {total_counties} | deserts (<{DESERT_THRESHOLD}/100): {len(deserts)} "
          f"({100.0*len(deserts)/max(total_counties,1):.1f}%)")
    if excluded_states:
        print(f"excluded (no county field in source data): state FIPS {sorted(excluded_states)} "
              f"(WI has no county column; CT/NYC sources lack it — see README limitations)")


if __name__ == "__main__":
    main()
