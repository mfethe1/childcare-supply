# childcare-supply

A continuously refreshable, openly redistributable, **row-level** dataset of licensed child-care supply in the United States — built from official state licensing registries.

## Why

The price side of childcare has federal data (DOL's National Database of Childcare Prices, county-level, archive version ends 2018). The **supply side** — which licensed providers exist, where, and with how many seats — lives in ~50 fragmented state registries. The best national analysis (Bipartisan Policy Center / Buffett Institute / Child Care Aware, 2025) is a static map built from private conversations with states; there is no redistributable, refreshable row-level national dataset. This fills that gap.

## Coverage (v0.1, 2026-09-21)

| Source | State | Providers | Licensed seats (active) |
|---|---|---|---|
| NY OCFS | NY | 16,706 | 689,960 |
| TX HHSC | TX | 14,971 | 1,171,854 |
| CA DSS | CA | 14,978 active (19,426 incl. closed) | 834,162 |
| NYC DOHMH | NYC | 2,751 | 148,274 |
| DE DSCYF | DE | 1,241 | 69,896 |
| **Total** | | **50,647 active** | **2,914,146** |

All five sources are official open data (Socrata APIs / state open-data CSV). Age-split capacity (infant/toddler/preschool/school-age) preserved where published (NY).

## Pipeline

```
python3 fetch.py       # pull all sources -> data/*.json|csv (Socrata paging, TLS quirks handled)
python3 ingest.py      # normalize -> SQLite (idempotent: delete-before-insert per source)
python3 ingest.py ny   # re-ingest one source
python3 seats.py summary
python3 seats.py county "Santa Clara" CA
python3 seats.py search "KinderCare"
python3 seats.py gap <county> <state> <under5-pop>
python3 test_pipeline.py   # 6 synthetic-fixture regression assertions
```

Unified schema per provider: `source, provider_id, name, type, status, address, city, county, state, zip, phone, capacity_total, capacity_{infant,toddler,preschool,school_age}, ages_served, lat, lon, raw_json`.

## Limitations

- **Licensed capacity ≠ availability**: licensed capacity is a ceiling, not open seats. No state publishes live vacancy data; this dataset makes the *supply ceiling* uniformly queryable for the first time.
- **Status filtering**: `CLOSED`/`REVOKED`/`SURRENDERED` excluded from active counts; state status vocabularies differ.
- **Coverage**: 5 of ~50 states in v0.1. CA row counts include historic closed licenses (kept in DB, excluded from active sums).
- **Not a recommendation**: licensing status is a floor, not a quality measure.

## License & attribution

Data remains under each state's terms (all official open data; check each portal). Code: MIT.
