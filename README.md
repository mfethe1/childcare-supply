# childcare-supply

A continuously refreshable, openly redistributable, **row-level** dataset of licensed child-care supply in the United States — built from official state licensing registries.

## Why

The price side of childcare has federal data (DOL's National Database of Childcare Prices, county-level, archive version ends 2018). The **supply side** — which licensed providers exist, where, and with how many seats — lives in ~50 fragmented state registries. The best national analysis (Bipartisan Policy Center / Buffett Institute / Child Care Aware, 2025) is a static map built from private conversations with states; there is no redistributable, refreshable row-level national dataset. This fills that gap.

## Coverage (v0.2, 2026-09-21)

12 machine-verified state/registry sources, **93,672 providers / 4.58M licensed seats**:

| Source | State | Providers | Licensed seats |
|---|---|---|---|
| NY OCFS | NY | 16,706 | 689,960 |
| CA DSS | CA | 19,426 (14,072 active) | 1,042,279 |
| TX HHSC | TX | 14,971 | 1,171,854 |
| CT OEC | CT | 16,253 | 78,688 |
| PA OCDEL | PA | 7,455 | 412,247 |
| WI DCF | WI | 4,733 | 194,717 |
| CO CDHS | CO | 4,528 | 263,000 |
| NJ DCF | NJ | 4,163 | 386,436 |
| WA DCYF | WA | 3,167 | 201,788 |
| NYC DOHMH | NYC | 2,751 | 148,274 |
| NE DHHS | NE | 2,726 | 128,064 |
| DE DSCYF | DE | 1,241 | 69,896 |

`coverage.json` tracks all 51 states+DC: **12 verified** machine-readable endpoints, **24 leads** (official registry found but HTML-only or gated — includes Ohio's email-gated full CSV export), **16 with no discoverable registry**. That distribution is itself a finding about the state of US childcare data.

New sources discovered via `discover_states.py` (Socrata + ArcGIS open-data catalogs) and `scrape_childcaregov.py` (childcare.gov state-resource pages → `state_registries.json`). Every verified endpoint was confirmed with a live fetch returning row-level data before entering the pipeline.

## Gap analysis (v0.2)

`gap.py` joins licensed seats against ACS 2023 under-5 population per county (via the keyless CensusReporter API — the official Census API now requires a key even for small requests), using the CAP/CEEL threshold: a county is a *childcare desert* when licensed capacity could serve < 33 per 100 children under 5.

**Result: 197 of 652 counties (30.2%) in 10 states are childcare deserts.**

Largest desert counties by under-5 population: Riverside CA, San Bernardino CA, Fresno CA, Kern CA, San Joaquin CA — the Inland Empire and Central Valley.

## Pipeline

```
python3 fetch.py            # 5 original Socrata/CSV sources
python3 fetch.py --extra    # 7 additional sources (CO CT NJ PA WA WI NE)
python3 ingest.py           # normalize -> SQLite (idempotent: delete-before-insert per source)
python3 ingest.py ny        # re-ingest one source
python3 seats.py summary
python3 seats.py county "Santa Clara" CA
python3 seats.py search "KinderCare"
python3 gap.py              # national desert table (covered counties)
python3 gap.py county "Travis"
python3 test_pipeline.py    # synthetic-fixture regression assertions
python3 discover_states.py  # sweep open-data catalogs for new endpoints
python3 scrape_childcaregov.py  # official registry URLs for all states
```

Unified schema per provider: `source, provider_id, name, type, status, address, city, county, state, zip, phone, capacity_total, capacity_{infant,toddler,preschool,school_age}, ages_served, lat, lon, raw_json`.

## Limitations

- **Licensed capacity ≠ availability**: capacity is a licensing ceiling, not open seats. No state publishes live vacancy data; this dataset makes the *supply ceiling* uniformly queryable.
- **County gaps**: WI, CT, and NYC sources publish no county field; those areas are excluded from the county-level desert rate rather than reported as false deserts.
- **No status field**: NJ and PA publish no license status; all their providers are counted (may include recently-closed facilities).
- **County-level granularity**: deserts are properly census-tract-level phenomena (CAP's methodology); county granularity overstates supply in mixed counties.
- **Status vocabularies** differ per state (see `normalize_extra.py`); CA excludes CLOSED from active seats.
- **Not a recommendation**: licensing status is a floor, not a quality measure.

## License & attribution

Data remains under each state's terms (all official open data; check each portal). Code: MIT.
