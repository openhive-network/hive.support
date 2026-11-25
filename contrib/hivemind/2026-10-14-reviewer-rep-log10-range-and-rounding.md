# rep_log10 values exceed 100 (ceiling ~114.7 for an int64 raw); 2-decimal rounding matters to clients that floor

- **Topic**: hivemind
- **Type**: addition
- **Affects**: reference/rules/hivemind.md (HM-005); reference/hivemind/serving.md (Utility belt: rep_log10); reference/hivemind/api.md (Response objects); research/hivemind/findings/07-serving-internals.md (rep_log10)
- **Source**: code under review: denser MR !1141 / issue #920 (`packages/ui/lib/reputation.ts`); hivemind `hive/db/sql_scripts/postgrest/utilities/rep_log10.sql:1-35` as the KB cites it

## Description

HM-005 says bridge objects and `get_profile(s)` return `rep_log10 = (log10(rep) - 9) * 9 + 25`
(0 -> 25, sign-preserving, 2 decimals) and that condenser returns the RAW bigint. Two
consequences that consumers get wrong are not stated anywhere in the KB:

1. **The calibrated scale is not bounded by 100.** With the raw value a bigint (int64), the
   ceiling is `(log10(2^63 - 1) - 9) * 9 + 25 = 114.68` and the floor is `-64.68`. Real
   accounts sit above 100 today (the #920 report shows `bridge.get_profile.reputation` =
   100.99). denser's develop helper used `Math.abs(input) <= 100` as its "already
   calibrated" test; 100.99 failed it, went through the log10 formula, `log10(100.99) - 9 < 0`
   clamped to 0, and the badge showed 25 (the "new account" default). This is exactly the
   HM-005 trap ("bridge author_reputation or profile reputation fed into a log10 formula"),
   reached through a range check rather than through an unconditional conversion. Suggested
   additions to HM-005: in **Detect**, "a cap or range check at 100 (or any magnitude
   heuristic) used to decide whether a value is already calibrated"; in **Wrong**,
   `Math.abs(rep) <= 100 ? Math.floor(rep) : repLog10(rep)`; in **Why** or **Rule**, the
   114.68 / -64.68 bounds.

2. **Magnitude is not a safe discriminator in either direction.** Raw values below 1e9
   (|raw| <= 1e9 -> `GREATEST(log10 - 9, 0)` = 0 -> display 25) are legitimately raw, so a
   "small means calibrated" threshold echoes them as integers; and the calibrated band
   [-65, 115] overlaps the raw integers of that magnitude. The only reliable routing is by
   source method (what HM-005 already prescribes); the KB could say so explicitly.

3. **Rounding.** `rep_log10` applies ROUND(..., 2) and (per findings 07) computes log10 from
   the first 4 digits. A client that floors the server value (every Hive frontend does) and
   also floors its own exact `(log10(raw) - 9) * 9 + 25` for condenser data can differ by one
   at a .xx5 boundary (exact 69.995 -> floor 69; server 70.00 -> floor 70). Worth one line in
   the Utility belt row so that mixed-namespace UIs do not chase phantom off-by-one bugs.

## Evidence

- Formula and rounding: reference/hivemind/serving.md (Utility belt: "rep_log10 | display
  reputation (log10-9)*9+25 (0 -> 25, ROUND 2)"); research/hivemind/findings/07-serving-internals.md
  ("first-4-digits log trick, (GREATEST(log10-9,0) * sign * 9) + 25, 0 -> 25, ROUND 2",
  `utilities/rep_log10.sql:1-35`).
- Raw type: reference/hivemind/api.md (Response objects: condenser `author_reputation` = RAW
  bigint); bigint = int64, so `log10(9223372036854775807) = 18.96497`, giving 114.684 and
  -64.684 (computed).
- The trap in the wild: denser issue #920 (profile reputation 100.99 rendered as 25; 76.01
  and 61.21 rendered correctly) and the develop code `packages/ui/lib/reputation.ts:17-19`
  (`Math.abs(input) > 0 && Math.abs(input) <= 100`), fixed in MR !1141 by routing per source
  method.
- Recorded responses in denser's playwright fixtures show the 2-decimal scale on
  `bridge.get_post` (76.01), `bridge.get_discussion` (37.35 .. 64.27) and `bridge.get_profile`
  (34.15).
