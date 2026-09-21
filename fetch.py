#!/usr/bin/env python3
"""Fetch public child-care licensing registries and normalize to one schema.

Sources (all official state/city open data):
  NY  - OCFS Child Care Regulated Programs (Socrata, age-split capacity)
  TX  - HHSC CCL Daycare Operations (Socrata, deficiencies, ages served)
  DE  - DHSS Licensed Child Care Providers (Socrata)
  NYC - DOHMH Active Child Care Programs (Socrata, geo)
  CA  - CHHS Community Care Licensing Facilities (CSV, filter child care types)

Output: data/<src>.json — list of dicts in the unified schema below.
"""
import csv
import io
import json
import os
import sys
import urllib.parse
import urllib.request

DATA = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA, exist_ok=True)

UA = {"User-Agent": "childcare-supply/0.1 (open-data research; github.com/mfethe1)"}


def get(url, timeout=120, binary=False, permissive_tls=False):
    req = urllib.request.Request(url, headers=UA)
    ctx = None
    if permissive_tls:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        b = r.read()
    return b if binary else b.decode("utf-8", "replace")


def socrata(host, ident, limit=50000):
    """Page through a Socrata dataset via the JSON API."""
    rows, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"$limit": 1000, "$offset": offset})
        url = f"https://{host}/resource/{ident}.json?{q}"
        chunk = json.loads(get(url, permissive_tls=True))
        if not chunk:
            break
        rows.extend(chunk)
        offset += len(chunk)
        if offset >= limit:
            break
    return rows


def num(x):
    if x is None:
        return None
    x = str(x).strip().replace(",", "")
    if x in ("", "N/A", "None"):
        return None
    try:
        return int(float(x))
    except ValueError:
        return None


def rec(**kw):
    """Unified schema. Missing keys -> None."""
    base = dict(source=None, provider_id=None, name=None, type=None, status=None,
                address=None, city=None, county=None, state=None, zip=None,
                lat=None, lon=None, capacity_total=None, capacity_infant=None,
                capacity_toddler=None, capacity_preschool=None,
                capacity_school_age=None, ages_served=None, phone=None,
                accepts_subsidy=None, deficiency_count=None, url=None)
    base.update(kw)
    return base


def fetch_ny():
    rows = socrata("data.ny.gov", "fymg-3wv3")
    out = []
    for r in rows:
        ai = r.get("additional_information") or {}
        out.append(rec(
            source="NY-OCFS", provider_id=r.get("facility_id"),
            name=r.get("facility_name"),
            type=r.get("program_type"),
            status=r.get("facility_status"),
            address=" ".join(filter(None, [r.get("street_number"),
                                           r.get("street_name")])),
            city=r.get("city"), county=r.get("county"),
            state=r.get("state") or "NY", zip=r.get("zip_code"),
            lat=num(r.get("latitude")), lon=num(r.get("longitude")),
            capacity_total=num(r.get("total_capacity")),
            capacity_infant=num(r.get("infant_capacity")),
            capacity_toddler=num(r.get("toddler_capacity")),
            capacity_preschool=num(r.get("preschool_capacity")),
            capacity_school_age=num(r.get("school_age_capacity")),
            phone=r.get("phone_number"),
            url=(ai.get("url") if isinstance(ai, dict) else None),
        ))
    return out


def fetch_tx():
    rows = socrata("data.texas.gov", "bc5r-88dy")
    out = []
    for r in rows:
        d = sum(num(r.get(f"deficiency_{k}")) or 0
                for k in ("high", "medium_high", "medium", "medium_low", "low"))
        out.append(rec(
            source="TX-HHSC", provider_id=r.get("operation_id"),
            name=r.get("operation_name"),
            type=r.get("operation_type"),
            status=r.get("type_of_issuance"),
            address=r.get("location_address"),
            county=(r.get("county") or "").title(),
            state="TX",
            capacity_total=num(r.get("total_capacity")),
            ages_served=r.get("licensed_to_serve_ages"),
            phone=r.get("phone_number"),
            accepts_subsidy=(None if r.get("accepts_child_care_subsidies") is None
                             else r.get("accepts_child_care_subsidies") == "Y"),
            deficiency_count=d,
        ))
    return out


def fetch_de():
    rows = socrata("data.delaware.gov", "jxu7-wnw2")
    out = []
    for r in rows:
        out.append(rec(
            source="DE-DHSS", provider_id=r.get("resource_id"),
            name=r.get("resource_name"),
            type=r.get("resource_type"),
            status="Licensed",
            address=r.get("site_street_address"),
            city=r.get("site_city"), county=r.get("site_county"),
            state=r.get("site_state") or "DE", zip=r.get("site_zip_code"),
            capacity_total=num(r.get("capacity")),
            ages_served=r.get("age_range"),
            phone=r.get("phone_number"),
        ))
    return out


def fetch_nyc():
    rows = socrata("data.cityofnewyork.us", "gy3q-4tzp")
    out = []
    for r in rows:
        out.append(rec(
            source="NYC-DOHMH", provider_id=r.get("dcid"),
            name=r.get("program_name"),
            type=(r.get("facility_type") or "") + " / " + (r.get("program_type") or ""),
            status="Permitted",
            address=r.get("address"), city=r.get("borough"),
            state="NY", zip=r.get("zipcode"),
            lat=num(r.get("latitude")), lon=num(r.get("longitude")),
            capacity_total=num(r.get("capacity")),
            ages_served=r.get("age_range"),
            phone=r.get("phone"),
        ))
    return out


def fetch_ca():
    url = ("https://data.chhs.ca.gov/dataset/ccl-facilities/resource/"
           "7aed8063-cea7-4367-8651-c81643164ae0/download")
    text = get(url, binary=False)
    rdr = csv.DictReader(io.StringIO(text))
    keep = ("DAY CARE CENTER", "FAMILY CHILD CARE HOME",
            "INFANT CENTER", "SCHOOL AGE DAY CARE CENTER")
    out = []
    for r in rdr:
        if r.get("facility_type") not in keep:
            continue  # CCL covers many facility kinds; child care only
        out.append(rec(
            source="CA-CDSS", provider_id=r.get("facility_number"),
            name=r.get("facility_name"), type=r.get("facility_type"),
            status=r.get("facility_status"),
            address=r.get("facility_address"), city=r.get("facility_city"),
            county=r.get("county_name"), state="CA", zip=r.get("facility_zip"),
            capacity_total=num(r.get("facility_capacity")),
            phone=r.get("facility_telephone_number"),
        ))
    return out


FETCHERS = {"ny": fetch_ny, "tx": fetch_tx, "de": fetch_de,
            "nyc": fetch_nyc, "ca": fetch_ca}


def main():
    which = sys.argv[1:] or list(FETCHERS)
    for name in which:
        fn = FETCHERS[name]
        try:
            rows = fn()
        except Exception as e:
            print(f"{name}: FETCH FAILED: {e}", file=sys.stderr)
            continue
        path = os.path.join(DATA, f"{name}.json")
        with open(path, "w") as f:
            json.dump(rows, f)
        print(f"{name}: {len(rows)} rows -> {path}")


if __name__ == "__main__":
    main()
