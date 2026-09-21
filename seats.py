#!/usr/bin/env python3
"""Query layer over the unified childcare provider DB.

Usage:
  python3 seats.py summary                     # national(ish) totals by source/state
  python3 seats.py county <county> [<state>]   # providers + seats in a county
  python3 seats.py search <name-substring>     # find provider by name
  python3 seats.py gap <county> <state> <under5-pop>  # seats per child
"""
import sqlite3, sys, os

DB = os.path.join(os.environ.get("CHILDCARE_DB_DIR") or os.path.dirname(__file__), "childcare.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

ACTIVE = "AND (status IS NULL OR UPPER(status) NOT IN ('CLOSED','REVOKED','SURRENDERED'))"


def summary():
    print(f"{'source':12} {'providers':>10} {'seats':>10}")
    for r in con.execute(f"SELECT source, COUNT(*) n, SUM(capacity_total) s FROM providers WHERE 1=1 {ACTIVE} GROUP BY source ORDER BY s DESC"):
        print(f"{r['source']:12} {r['n']:>10,} {r['s'] or 0:>10,}")
    t = con.execute(f"SELECT COUNT(*) n, COALESCE(SUM(capacity_total),0) s FROM providers WHERE 1=1 {ACTIVE}").fetchone()
    print(f"{'TOTAL':12} {t['n']:>10,} {t['s']:>10,}")


def county(name, state=None):
    q = f"SELECT * FROM providers WHERE county = ? COLLATE NOCASE {('AND state=?' if state else '')} {ACTIVE}"
    args = [name] + ([state.upper()] if state else [])
    rows = con.execute(q, args).fetchall()
    seats = sum(r["capacity_total"] or 0 for r in rows)
    print(f"{len(rows)} active providers, {seats:,} seats in {name}{' County, ' + state.upper() if state else ''}")
    for r in rows[:15]:
        print(f"  {r['name'][:50]:50} {str(r['type'] or '')[:18]:18} seats={r['capacity_total']}")
    if len(rows) > 15:
        print(f"  … and {len(rows)-15} more")


def search(term):
    rows = con.execute(f"SELECT * FROM providers WHERE name LIKE ? {ACTIVE} LIMIT 25", (f"%{term}%",)).fetchall()
    for r in rows:
        print(f"  {r['source']:10} {r['name'][:45]:45} {r['city'] or '':15} {r['state']} seats={r['capacity_total']}")


def gap(county, state, pop):
    q = f"SELECT COUNT(*) n, COALESCE(SUM(capacity_total),0) s FROM providers WHERE county=? COLLATE NOCASE AND state=? {ACTIVE}"
    r = con.execute(q, (county, state.upper())).fetchone()
    ratio = r["s"] / int(pop) if int(pop) else None
    print(f"{county}, {state.upper()}: {r['n']} providers, {r['s']:,} seats, pop under 5 = {int(pop):,} → seats/child = {ratio:.3f}" if ratio else "no data")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if cmd == "summary":
        summary()
    elif cmd == "county":
        county(*sys.argv[2:4])
    elif cmd == "search":
        search(sys.argv[2])
    elif cmd == "gap":
        gap(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__)
