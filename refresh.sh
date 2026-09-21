#!/bin/bash
# Weekly refresh: refetch all sources, re-ingest, rerun gap analysis, commit + push.
# Designed for unattended cron. Any failure exits non-zero without pushing.
set -euo pipefail
cd "$(dirname "$0")"

echo "=== $(date -u +%FT%TZ) childcare-supply refresh ==="

python3 fetch.py            || exit 1
python3 fetch_extra.py      || exit 1
python3 ingest.py         || exit 1
python3 gap.py > gap_latest.txt || exit 1
python3 test_pipeline.py  || exit 1

# Only push if the normalized DB or coverage actually changed
if ! git diff --quiet -- childcare.db coverage.json README.md 2>/dev/null; then
  git add -A
  git -c user.name=mfethe1 -c user.email=mfethe@users.noreply.github.com commit \
    -m "auto-refresh $(date -u +%F): $(sqlite3 childcare.db 'SELECT COUNT(*) FROM providers') providers" || exit 1
  git push origin main || exit 1
  echo "pushed"
else
  echo "no changes"
fi
