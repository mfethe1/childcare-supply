#!/usr/bin/env python3
"""Normalize fetched registries into a unified SQLite schema, HPT-style:
delete-before-insert per source (idempotent re-ingest).

Unified schema (one row per licensed provider):
  source, provider_id, name, type, status, address, city, county, state, zip,
  phone, capacity_total, capacity_infant, capacity_toddler, capacity_preschool,
  capacity_school_age, ages_served, lat, lon, raw_json
"""
import csv, json, os, re, sqlite3, sys

DB = os.path.join(os.environ.get("CHILDCARE_DB_DIR") or os.path.dirname(__file__), "childcare.db")
DATA = os.path.join(os.environ.get("CHILDCARE_DB_DIR") or os.path.dirname(__file__), "data")

DDL = """
CREATE TABLE IF NOT EXISTS providers (
  source TEXT NOT NULL,
  provider_id TEXT,
  name TEXT NOT NULL,
  type TEXT,
  status TEXT,
  address TEXT, city TEXT, county TEXT, state TEXT, zip TEXT,
  phone TEXT,
  capacity_total INTEGER, capacity_infant INTEGER, capacity_toddler INTEGER,
  capacity_preschool INTEGER, capacity_school_age INTEGER,
  ages_served TEXT, lat REAL, lon REAL,
  raw_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_prov_state ON providers(state);
CREATE INDEX IF NOT EXISTS idx_prov_county ON providers(county);
"""


def num(x):
    if x is None: return None
    m = re.search(r"\d+", str(x))
    return int(m.group(0)) if m else None


def load(path):
    with open(path) as f:
        return json.load(f) if path.endswith(".json") else list(csv.DictReader(f))


# fetch.py already emits normalized records with these keys; ingest maps them
# into the DB columns directly (all five sources share the normalized shape).
NORM_KEYS = {
    "provider_id": "provider_id", "name": "name", "type": "type", "status": "status",
    "address": "address", "city": "city", "county": "county", "state": "state",
    "zip": "zip", "phone": "phone", "capacity_total": "capacity_total",
    "capacity_infant": "capacity_infant", "capacity_toddler": "capacity_toddler",
    "capacity_preschool": "capacity_preschool",
    "capacity_school_age": "capacity_school_age", "ages_served": "ages_served",
    "lat": "lat", "lon": "lon", "url": "url",
}


def norm_generic(r, source, default_state):
    out = {"source": source}
    out.update({k: r.get(v) for k, v in NORM_KEYS.items()})
    out["state"] = clean_state(out.get("state"), default_state)
    out["capacity_total"] = num(out.get("capacity_total"))
    for a in ("infant", "toddler", "preschool", "school_age"):
        out[f"capacity_{a}"] = num(out.get(f"capacity_{a}"))
    return out


def clean_state(s, default):
    s = (s or "").strip().upper()
    return s if len(s) == 2 else default


def norm_ny(r):
    return dict(
        source="NY-OCFS", provider_id=r.get("facility_id"),
        name=r.get("facility_name") or r.get("provider_name") or "UNKNOWN",
        type=r.get("program_type"), status=r.get("facility_status"),
        address=(r.get("address_omitted") == "Y" and "[address omitted]")
                 or " ".join(str(r.get(k) or "") for k in
                             ("street_number","street_name")).strip() or None,
        city=r.get("city"), county=r.get("county"), state="NY", zip=r.get("zip_code"),
        phone=r.get("phone_number"),
        capacity_total=num(r.get("total_capacity")),
        capacity_infant=num(r.get("infant_capacity")),
        capacity_toddler=num(r.get("toddler_capacity")),
        capacity_preschool=num(r.get("preschool_capacity")),
        capacity_school_age=num(r.get("school_age_capacity")),
        ages_served=r.get("capacity_description"),
        lat=None, lon=None,
    )


def norm_tx(r):
    ages = r.get("licensed_to_serve_ages")
    return dict(
        source="TX-HHSC", provider_id=r.get("operation_id"),
        name=r.get("operation_name") or "UNKNOWN",
        type=r.get("operation_type"), status=r.get("type_of_issuance"),
        address=r.get("location_address"), city=None,
        county=(r.get("county") or "").title(), state="TX", zip=None,
        phone=r.get("phone_number"),
        capacity_total=num(r.get("total_capacity")),
        capacity_infant=None, capacity_toddler=None, capacity_preschool=None,
        capacity_school_age=None,
        ages_served=ages, lat=None, lon=None,
    )


def norm_de(r):
    return dict(
        source="DE-DSCYF", provider_id=r.get("resource_id"),
        name=r.get("resource_name") or "UNKNOWN",
        type=r.get("resource_type"), status="LICENSED",
        address=r.get("site_street_address"), city=r.get("site_city"),
        county=r.get("site_county"), state="DE", zip=r.get("site_zip_code"),
        phone=r.get("phone_number"),
        capacity_total=num(r.get("capacity")),
        capacity_infant=None, capacity_toddler=None, capacity_preschool=None,
        capacity_school_age=None,
        ages_served=r.get("age_range"), lat=None, lon=None,
    )


def norm_nyc(r):
    return dict(
        source="NYC-DOHMH", provider_id=r.get("dcid"),
        name=r.get("program_name") or "UNKNOWN",
        type=r.get("facility_type"), status=r.get("permit_status") or "ACTIVE",
        address=r.get("address"), city=r.get("borough"),
        county=None, state="NY", zip=r.get("zipcode"),
        phone=r.get("phone"),
        capacity_total=num(r.get("capacity")),
        capacity_infant=None, capacity_toddler=None, capacity_preschool=None,
        capacity_school_age=None,
        ages_served=r.get("age_range"),
        lat=float(r["latitude"]) if r.get("latitude") else None,
        lon=float(r["longitude"]) if r.get("longitude") else None,
    )


def norm_ca(r):
    st = (r.get("facility_status") or "").upper()
    return dict(
        source="CA-DSS", provider_id=r.get("facility_number"),
        name=r.get("facility_name") or "UNKNOWN",
        type=r.get("facility_type"),
        status=st if st in ("LICENSED","CLOSED","PENDING","SUSPENDED","PROBATION") else (st or None),
        address=r.get("facility_address"), city=r.get("facility_city"),
        county=(r.get("county_name") or "").title(), state="CA", zip=r.get("facility_zip"),
        phone=r.get("facility_telephone_number"),
        capacity_total=num(r.get("facility_capacity")),
        capacity_infant=None, capacity_toddler=None, capacity_preschool=None,
        capacity_school_age=None,
        ages_served=None, lat=None, lon=None,
    )


SOURCES = {
    "co": ("co.json", "norm_extra"), "ct": ("ct.json", "norm_extra"),
    "nj": ("nj.json", "norm_extra"), "pa": ("pa.json", "norm_extra"),
    "wa": ("wa.json", "norm_extra"), "wi": ("wi.json", "norm_extra"),
    "ne": ("ne.json", "norm_extra"),
    "ma": ("ma.json", "norm_extra"), "vt": ("vt.json", "norm_extra"),
    "mn": ("mn.json", "norm_extra"), "ok": ("ok.json", "norm_extra"),
    "va": ("va_*.json", "norm_extra"), "hi": ("hi.json", "norm_extra"),
    "ny": ("ny.json", "norm_generic"), "tx": ("tx.json", "norm_generic"),
    "de": ("de.json", "norm_generic"), "nyc": ("nyc.json", "norm_generic"),
    "ca": ("ca.csv", "norm_ca"),
}


def main():
    only = sys.argv[1:] or list(SOURCES)
    con = sqlite3.connect(DB)
    con.executescript(DDL)
    cols = ["source","provider_id","name","type","status","address","city","county",
            "state","zip","phone","capacity_total","capacity_infant","capacity_toddler",
            "capacity_preschool","capacity_school_age","ages_served","lat","lon","raw_json"]
    for key in only:
        fname, fn = SOURCES[key]
        path = os.path.join(DATA, fname)
        if "*" in fname:
            import glob as _g
            parts = []
            for p in sorted(_g.glob(path)):
                parts.append(load(p))
            # tag each file's rows with its layer file for traceability
            import os.path as _op
            layer_files = sorted(_op.basename(p) for p in _g.glob(path))
            raw = []
            for lf, part in zip(layer_files, parts):
                for r in part:
                    r = dict(r)
                    r["_layer_file"] = lf
                    raw.append(r)
        else:
            raw = load(path)
        kind = SOURCES[key][1]
        if kind == "norm_ca":
            rows = [norm_ca(r) for r in raw]
        elif kind == "norm_extra":
            from normalize_extra import NORMALIZERS
            rows = [NORMALIZERS[key](r) for r in raw]
        else:
            srcmap = {"ny": "NY-OCFS", "tx": "TX-HHSC", "de": "DE-DSCYF", "nyc": "NYC-DOHMH"}
            rows = [norm_generic(r, srcmap[key], {"ny":"NY","tx":"TX","de":"DE","nyc":"NY"}[key]) for r in raw]
        for r in rows:
            r["raw_json"] = json.dumps(r, default=str)
        ph = ",".join("?" * len(cols))
        con.execute(f"DELETE FROM providers WHERE source=?", (rows[0]["source"],))
        con.executemany(
            f"INSERT INTO providers ({','.join(cols)}) VALUES ({ph})",
            [tuple(r.get(c) for c in cols) for r in rows])
        con.commit()
        print(f"{key}: {len(rows)} rows ingested (source={rows[0]['source']})")
    n = con.execute("SELECT COUNT(*) FROM providers").fetchone()[0]
    print(f"TOTAL {n}")
    for row in con.execute("SELECT source, COUNT(*), SUM(capacity_total) FROM providers GROUP BY source"):
        print(" ", row)
    con.close()


if __name__ == "__main__":
    main()
