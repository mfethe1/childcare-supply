#!/usr/bin/env python3
"""Synthetic-fixture regression tests for ingest.py + seats.py logic.

Run: python3 test_pipeline.py
Asserts normalization, idempotency, and active-status filtering against
hand-built fixtures — no live network, no real databases.
"""
import csv, io, json, os, sqlite3, subprocess, sys, tempfile

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

    print("ALL 6 FIXTURE ASSERTIONS PASSED")


if __name__ == "__main__":
    main()
