# Verification Report

- Topic: `hivemind`
- Pinned: `1.28.6` (`cab9e328bfd5bd9da2d228d68db75b07b7ae8f93`)
- Run: 2026-08-01 (first full pass, pre-merge self-review of MR !25)
- Method: 7 parallel subagents, one per findings part, each auditing every Code
  References row (plus targeted spot-checks of load-bearing numeric claims:
  the 41/13/21 schema counts, the 25-branch bridge router, the 17-op filter,
  the x1e6 rshares scaling, the hardcoded reptracker refs, the -32602 code,
  the cache headers, the dead-code claims) against the pinned worktree
  `workspace/hivemind/cab9e328bf/`.

## Summary

| Part | Rows | Confirmed | Drifted | Broken | Unparseable |
|------|------|-----------|---------|--------|-------------|
| 01 architecture-deployment | 58 | 51 | 4 | 3* | 0 |
| 02 schema-data-model | 30 | 27 | 3 | 0 | 0 |
| 03 sync-internals | 31 | 31 | 0 | 0 | 0 |
| 04 operation-semantics | 28 | 24 | 4 | 0 | 0 |
| 05 bridge-api | 22 | 18 | 4 | 0 | 0 |
| 06 legacy-apis | 16 | 12 | 4 | 0 | 0 |
| 07 serving-internals | 19 | 12 | 7 | 0 | 0 |
| **Total** | **204** | **175** | **26** | **3*** | **0** |

\* The 3 "broken" rows are part 01's **deliberate stale-docs table** (section
12: repo README claims SQLAlchemy / Python 3.10 / `hive server` vs code
reality). The auditor verified that the README really makes those claims and
that the code really contradicts them - i.e. it confirmed exactly what those
rows document. No findings content is contradicted by source anywhere.

**Zero genuine broken citations.** All 26 "drifted" rows were range-precision
issues, not content errors. 18 were fixed in the same commit as this report;
8 are accepted block-range conventions (below).

## Fixes applied (18 rows)

| Part | Row | Change |
|------|-----|--------|
| 02 | Notification snowflake | `utility_functions.sql:101-149` -> `101-153` (inverse fn end) |
| 02 | Muted-reasons bitmask | `muted_reasons_operations.sql:10-46` -> `10-77` (encode fn body) |
| 02 | View-deps helper | `postgres_handle_view_changes.sql:8-45` -> `8-36` (the described quirk only) |
| 04 | Batch post fns | `hive_post_operations.sql:555-990` -> `416-990` (include `process_root_posts_batch` at 416) |
| 05 | Ranked dispatch | `bridge_api_get_ranked_posts.sql:15-97` -> `15-86` (was past EOF) |
| 05 | Ranked sort fns (x2 sites) | `get_ranked_posts.sql:5-2297` -> `5-2383` (2297 was the LAST fn's start) |
| 05 | Account posts fns | `get_account_posts.sql:2-482` -> `2-569` (same start-vs-end slip) |
| 05 | Unread notifications (x2 sites) | `:15-52` -> `15-51` (off-by-one past EOF) |
| 06 | Condenser/follow/database routers (4 sites each x2 places) | `2-66`/`67-99`/`211-235` -> `2-64`/`67-97`/`211-233` (trailing blank + next DROP trimmed) |
| 06 | Author-before-date | `:19-108` -> `19-112` |
| 07 | Raise base | `exceptions.sql:39-90` -> `39-62` |
| 07 | Method-not-found (x2 sites) | `:90-114` -> `90-112` |
| 07 | OpenAPI dynamic home() (x2 sites) | `endpoint_schema.sql:1-39,445` -> `1-453` (whole mechanism) |
| 07 | REST ops endpoint | `:149-213` -> `149-215` |
| 07 | Query preprocessor | `:1-176` -> `1-173` |
| 07 | Notification rendering | `:11-117` -> `11-27,52-117` |

## Accepted imprecisions (8 rows, left as-is)

Block-range convention: these ranges deliberately include adjacent context
(constants, comments, echo lines, or a caller/wrapper) that is part of the
described construct.

| Part | Row | Note |
|------|-----|------|
| 01 | `haf_functions.py:16-21` (stage array) | line 16 is `LIMIT_FOR_PROCESSED_BLOCKS = 1000` - the batch size the row describes |
| 01 | `home.sql:34-43` (no-params whitelist) | 34-35/40-43 are the comment + IF/raise wrapping the 36-39 list |
| 01 | `install_app.sh:76-78` and `80-82` (grants) | include the echo lines announcing the grants |
| 04 | `massive_sync.sql:1732-2231` (community dispatch) | intentionally spans `process_community_op` + the `process_community_from_staging` wrapper ("dispatch + phases") |
| 04 | `hafapp_api.sql:54-508` (follow machine) | ends at the fn boundary (next fn at 509) |
| 04 | `community.sql:84-171` | spans the two adjacent role/registration functions the row describes |
| 04 | `update_posts_rshares.sql:1-96` | whole-file cite (file holds the fn + variants) |

(Part 07's `get_profiles.sql:29-67` was also flagged; the range is correct -
it covers both the field set (29-42) and the missing-account entries (48-60)
named in the Purpose column.)

## Auditor-summary corrections

Two subagents' one-line summaries miscounted their own tables (part 05 said
"19 confirmed, 3 drifted" for a table with 18/4; part 07 said "4 confirmed,
10 drifted" for a table with 12/7 including spot-checks). The Summary table
above is recounted from the per-row classifications, which are consistent
with the quoted evidence.
