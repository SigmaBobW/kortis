# IEEE Entity Resolution — Sigma data app

A human-in-the-loop **entity resolution** application built as a Sigma workbook
(workbooks-as-code, `POST/PUT /v2/workbooks/spec`) with the `sigma-input-table-app`
pattern. It collapses multi-source member records into one **governed golden record**
per member, and lets a steward review, edit and approve each recommendation with
writeback.

**Live workbook:** `IEEE Entity Resolution` — folder `ieee/OU Dashboard`
(`https://app.sigmacomputing.com/ieee/workbook/2weQhxjpIuFzwtwJj1OrRU`)

## Inputs
- `raw_source_records.csv` — 560 member records across 5 IEEE systems
  (Membership DB, Society Directory, Local Section Roster, Conference Registration,
  Xplore Access). Multiple records per member.
- `pairwise_match_scores.csv` — 566 pairwise match scores (deterministic /
  probabilistic) with the fields that matched.

## What the build does (`er_data.py`)
1. **Cluster** records into members via union-find on `member_number` + pairwise
   edges ≥ 0.70 → **255 members** (159 with 2+ records needing resolution).
2. **Survivorship** per attribute (name, email, phone, grade, society, section,
   address): pick the survivor by **source authority → completeness → recency**,
   then score **confidence** (agreement × authority × pairwise corroboration) and
   flag **conflicts** (sources disagree). 402 attribute-level conflicts surfaced.

## The app (`build_ieee_er.py`)
- **Page 1 — Command Center:** IEEE-branded header, population KPIs
  (records → members, collapsed, need-review, conflicts, avg confidence, golden
  approved), conflicts-by-attribute + confidence-band charts, and a **member triage
  table** (worst-first, confidence/conflict conditional formatting).
- **Page 2 — Golden Record Review (human-in-the-loop):** pick a member → compare the
  **source records** against the **recommended golden values** (confidence-shaded,
  conflicts flagged) → **Review & approve** opens a modal pre-filled with the survivor
  per field → edit, set a decision, **Save** → appends to the **Golden Record input
  table** (writeback, with user + timestamp).

## Rebuild / update
```bash
export SIGMA_TOKEN_FETCHER="$PWD/../../scripts/get-token-staging.sh"
eval "$(bash ../../scripts/get-token-staging.sh)"   # needs SIGMA_CLIENT_ID/SECRET/BASE_URL
# create a new workbook:
python3 build_ieee_er.py "$SIGMA_BASE_URL" "$SIGMA_API_TOKEN" <writeback_connection_id> <folder_id>
# or update in place (keeps the URL):
POST=0 python3 build_ieee_er.py "$SIGMA_BASE_URL" "$SIGMA_API_TOKEN" <conn> <folder>   # writes spec.json
curl -X PUT -H "Authorization: Bearer $SIGMA_API_TOKEN" -H "Content-Type: application/json" \
  --data-binary @spec.json "$SIGMA_BASE_URL/v2/workbooks/<workbookId>/spec"
```

## Notes / gotchas encountered
- **Spec envelope changed:** the workbook spec now nests under a top-level
  `document` key — `{"name","folderId","document":{"schemaVersion":1,"kind":"workbook",
  "pages":[...],"layout":...,"themeOverrides":...}}`. The older flat shape
  (`schemaVersion`/`pages` at top level) is rejected as a masked union error.
- Connection must be **writeback-enabled** for the input table (used
  `Sigma Sample Database`, Snowflake). Source data is embedded as SQL `VALUES`.
- Input-table rows only materialize on the first in-UI **Save** click — the app is
  empty on the "Golden Approved" side until a steward approves one member.
