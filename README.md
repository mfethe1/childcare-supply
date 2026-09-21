# childcare-supply

A continuously refreshable, openly redistributable, **row-level** dataset of licensed child-care supply in the United States — built from official state licensing registries.

## Why

The price side of childcare has federal data (DOL's National Database of Childcare Prices, county-level, archive version ends 2018). The **supply side** — which licensed providers exist, where, and with how many seats — lives in ~50 fragmented state registries. The best national analysis (Bipartisan Policy Center / Buffett Institute / Child Care Aware, 2025) is a static map built from private conversations with states; there is no redistributable, refreshable row-level national dataset. This fills that gap.

## Coverage (v0.3, 2026-09-21)

18 machine-verified state/registry sources, **124,967 providers / 5.73M licensed seats**:

| Source | State | Providers | Licensed seats |
|---|---|---|---|
| NY OCFS | NY | 19,457 | 838,234 |
| CA DSS | CA | 19,426 (14,072 active) | 1,042,279 |
| CT OEC | CT | 16,253 (3,799 active) | 78,688 |
| TX HHSC | TX | 14,971 | 1,171,854 |
| MA EEC | MA | 9,225 | 266,568 |
| MN DHS (HFLV) | MN | 9,146 | 229,560 |
| PA OCDEL | PA | 7,455 | 412,247 |
| WI DCF | WI | 4,733 | 194,717 |
| CO CDHS | CO | 4,528 | 263,000 |
| NJ DCF | NJ | 4,163 | 386,436 |
| VA (CCAoA layers) | VA | 3,919 | 272,845 |
| WA DCYF | WA | 3,167 | 201,788 |
| OK DHS | OK | 2,776 | 108,019 |
| NE DHHS | NE | 2,726 | 128,064 |
| NYC DOHMH | NYC | 2,751 | 148,274 |
| DE DSCYF | DE | 1,241 | 69,896 |
| VT (BBF) | VT | 1,048 | 33,583 |
| HI DHS | HI | 733 | 29,346 |

New in v0.3 (verified live, same day): **MA** (EEC open data, capacity + status), **VT** (BBF, age-split capacity + reported vacancies — the only source with live-availability fields), **MN** (HFLV: capacity, vacancies *and* county), **OK** (capacity + county), **VA** (4 Child Care Aware of America ArcGIS layers: centers Dec 2025, family day homes Jun 2026, religious-exempt, voluntarily-registered), **HI** (DHS portal reverse-engineered: public PowerAutomate search API → per-service detail pages with embedded capacity JSON; harvested per-island and per-Oahu-district to bypass the 100-provider result cap).

`coverage.json` tracks all 51 states+DC: **18 verified** machine-readable endpoints, **19 leads** (official registry found but HTML-only or gated — includes Ohio's email-gated full CSV export), **15 with no discoverable registry**. That distribution is itself a finding about the state of US childcare data.

New sources discovered via `discover_states.py` (Socrata + ArcGIS open-data catalogs) and `scrape_childcaregov.py` (childcare.gov state-resource pages → `state_registries.json`). Every verified endpoint was confirmed with a live fetch returning row-level data before entering the pipeline.

## Gap analysis (v0.3)

`gap.py` joins licensed seats against ACS 2023 under-5 population per county (via the keyless CensusReporter API — the official Census API now requires a key even for small requests), using the CAP/CEEL threshold: a county is a *childcare desert* when licensed capacity could serve < 33 per 100 children under 5.

**Result: 308 of 967 counties (31.9%) across the covered states are childcare deserts.**

Largest desert counties by under-5 population: Riverside CA, San Bernardino CA, Fresno CA, Kern CA, San Joaquin CA — the Inland Empire and Central Valley.

## Tract-level analysis (v0.3 exploratory)

`tract_gap.py` adds a tract-level companion layer using the Census Geocoder batch endpoint and CensusReporter ACS 2024 under-5 estimates. It geocodes provider street addresses to 2020-vintage Census tracts, aggregates licensed seats to the supply tract, and applies the same CAP/CEEL threshold (<33 seats per 100 children under 5). The current run matched 70,347 of 80,810 usable addresses (87.1%) and scored 26,091 tracts, of which 13,843 (53.1%) met the desert threshold.

This is an exploratory **supply-location** measure, not an enrollment or travel-access measure. It is not directly comparable to CAP's 3-mile-buffer methodology. Providers with no usable address or unmatched addresses are excluded; CT, WI, and NYC are excluded from this layer because their source rows do not provide complete address coverage. The Census geocoder can rate-limit large batches, so rerun `python3 tract_gap.py` to fill any missing cache entries before using this layer for publication.

## Machine-readability census

`coverage.json` records 52 state/DC registry leads and Jev classifications: 17 `direct_api`, 20 `scrape_only`, and 15 `no_data`. The independently verified coverage labels agree with Jev on 32 of 33 known-status sources; Hawaii is the sole disagreement because its PowerAutomate endpoint was reverse-engineered rather than documented as a conventional API. Jev is used as a classification aid, not as evidence that a source is redistributable or complete.

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
