#!/usr/bin/env python3
"""Synthetic-fixture regression tests for ingest.py + seats.py logic.

Run: python3 test_pipeline.py
Asserts normalization, idempotency, and active-status filtering against
hand-built fixtures — no live network, no real databases.
"""
import csv, io, json, os, re, sqlite3, subprocess, sys, tempfile, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
INGEST = os.path.join(HERE, "ingest.py")
SEATS = os.path.join(HERE, "seats.py")

FIXTURES = {
    # normalized-record shape emitted by fetch.py
    "ny": [
        {"provider_id": "1", "name": "Alpha Center", "type": "DCC", "status": "License",
         "county": "Erie", "state": "NY", "capacity_total": 40,
         "capacity_infant": 8, "capacity_toddler": 8, "capacity_preschool": 24,
         "capacity_school_age": 0, "city": "Buffalo"},
        {"provider_id": "2", "name": "Beta Home", "type": "GFDC", "status": "License",
         "county": "Erie", "state": "NY", "capacity_total": 12,
         "capacity_infant": 0, "capacity_toddler": 0, "capacity_preschool": 0,
         "capacity_school_age": 0, "city": "Buffalo"},
        {"provider_id": "3", "name": "Gamma Closed", "type": "DCC", "status": "CLOSED",
         "county": "Erie", "state": "NY", "capacity_total": 99, "city": "Buffalo"},
    ],
    "de": [
        {"provider_id": "10", "name": "Delta Care", "type": "Licensed Family Child Care",
         "status": "LICENSED", "county": "Kent", "state": "DE",
         "capacity_total": 6, "city": "Smyrna"},
    ],
}
# CA raw CSV fixture (source uses raw CSV, normalized by norm_ca)
CA_CSV = """facility_type,facility_number,facility_name,facility_city,facility_state,facility_zip,county_name,facility_capacity,facility_status
DAY CARE CENTER,111,A Kiddie Place,Los Angeles,CA,90001,LOS ANGELES,55,LICENSED
DAY CARE CENTER,222,Old Shut Doors,Los Angeles,CA,90002,LOS ANGELES,80,CLOSED
"""


def src(name):
    """File text with adjacent string literals joined, so multi-line URLs match."""
    return re.sub(r'"\s*\n\s*"', "", open(os.path.join(HERE, name)).read())


def ingest_sources():
    """Keys of ingest.py's SOURCES dict."""
    return set(re.findall(r'"(\w+)": \("', src("ingest.py").split("SOURCES = {")[1]))


def fetcher_sources():
    """Sources some fetcher actually produces, read from the fetchers themselves."""
    extra = src("fetch_extra.py")
    return (
        set(re.findall(r"^def fetch_(\w+)", src("fetch.py"), re.M))            # fetch.py
        | set(re.findall(r'"(\w+)": "https', extra.split("SOCRATA = {")[1]))   # socrata
        | set(re.findall(r'"(\w+)", \w+\)', extra.split("for name, url in (")[1]))
        | {"va", "hi"}  # VA_LAYERS glob; HI via fetch_hi.py + harvest_hi_oahu.py
    )


# path segments that identify nothing on their own
GENERIC = {"rest", "services", "arcgis", "resource", "server", "query", "dataset",
           "download", "featureserver", "mapserver", "agency", "api", "0", "1"}


def endpoint_mismatches():
    """Verified coverage.json endpoints whose host+identifier aren't in the fetchers.

    Socrata URLs are assembled from host+ident at runtime, so compare parts,
    not whole strings.
    """
    code = "".join(src(f) for f in ("fetch.py", "fetch_extra.py", "fetch_hi.py"))
    cov = json.load(open(os.path.join(HERE, "coverage.json")))["sources"]
    bad = set()
    for st, v in cov.items():
        if v.get("status") != "verified":
            continue
        u = urllib.parse.urlparse(v.get("endpoint") or "")
        segs = [s.rsplit(".", 1)[0] for s in u.path.split("/") if s]
        ident = max((s for s in segs if s.lower() not in GENERIC), key=len, default="")
        if u.netloc not in code or ident not in code:
            bad.add(st)
    return bad


def run(cmd, env=None):
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert r.returncode == 0, f"FAILED {' '.join(cmd)}\n{r.stdout}\n{r.stderr}"
    return r.stdout


def main():
    tmp = tempfile.mkdtemp()
    data = os.path.join(tmp, "data")
    os.makedirs(data)
    for k, rows in FIXTURES.items():
        json.dump(rows, open(os.path.join(data, f"{k}.json"), "w"))
    with open(os.path.join(data, "ca.csv"), "w") as f:
        f.write(CA_CSV)

    env = dict(os.environ, CHILDCARE_DB_DIR=tmp)
    # ingest.py must honor CHILDCARE_DB_DIR for hermetic tests
    assert "CHILDCARE_DB_DIR" in open(INGEST).read(), "ingest.py lacks CHILDCARE_DB_DIR override"
    out = run([sys.executable, INGEST, "ny", "de", "ca"], env=env)
    assert "TOTAL 6" in out, out
    assert "ny: 3 rows" in out and "de: 1 rows" in out and "ca: 2 rows" in out, out

    db = sqlite3.connect(os.path.join(tmp, "childcare.db"))
    db.row_factory = sqlite3.Row

    # 1. capacity normalization landed
    r = db.execute("SELECT SUM(capacity_total) s FROM providers WHERE source='NY-OCFS'").fetchone()
    assert r["s"] == 151, r["s"]  # 40+12+99, closed rows stored but flagged

    # 2. age-split capacity preserved
    r = db.execute("SELECT capacity_infant, capacity_preschool FROM providers WHERE provider_id='1'").fetchone()
    assert (r["capacity_infant"], r["capacity_preschool"]) == (8, 24)

    # 3. CA raw-CSV normalization
    r = db.execute("SELECT county, state, capacity_total FROM providers WHERE provider_id='111'").fetchone()
    assert (r["county"], r["state"], r["capacity_total"]) == ("Los Angeles", "CA", 55), dict(r)

    # 4. idempotency: re-ingest single source, totals unchanged
    run([sys.executable, INGEST, "ny"], env=env)
    assert db.execute("SELECT COUNT(*) FROM providers").fetchone()[0] == 6
    r = db.execute("SELECT SUM(capacity_total) s FROM providers WHERE source='NY-OCFS'").fetchone()
    assert r["s"] == 151, "re-ingest duplicated or dropped rows"

    # 5. seats.py active-only filter excludes CLOSED
    out = run([sys.executable, SEATS, "summary"], env=env)
    assert "CHILDCARE_DB_DIR" in open(SEATS).read(), "seats.py lacks CHILDCARE_DB_DIR override"
    assert "Gamma Closed" not in out
    # active NY seats = 40+12=52, CA active = 55, DE = 6 → total 113
    for line in out.splitlines():
        if line.startswith("TOTAL"):
            assert "113" in line, line

    # 6. county query filters by state
    out = run([sys.executable, SEATS, "county", "Kent", "DE"], env=env)
    assert "1 active providers" in out and "Delta Care" in out, out

    # 7/8. wiring invariants — reported together so one can't mask the other.
    #      (NE and WI shipped for weeks with no fetcher; five coverage.json
    #       endpoints 404'd while the code called live ones.)
    orphans = sorted(ingest_sources() - fetcher_sources())
    liars = sorted(endpoint_mismatches())
    assert not (orphans or liars), (
        f"ingest.py expects sources nothing fetches: {orphans}\n"
        f"coverage.json endpoint != code endpoint: {liars}"
    )

    # 9. published numbers match the data (the README table drifted for a full
    #    release: NY off by 2,751 providers, TX by 10,212 seats)
    r = subprocess.run([sys.executable, os.path.join(HERE, "stats.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout.strip() or r.stderr.strip()

    print("ALL 9 ASSERTIONS PASSED")


if __name__ == "__main__":
    main()
