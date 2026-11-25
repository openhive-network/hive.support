# median_props: the median is over the scheduled witnesses of a round, not "all witness-voted properties"

- **Topic**: hive-core
- **Type**: correction
- **Affects**: reference/state-objects.md:302 (`median_props` row), reference/economics.md (HBD Interest), reference/consensus.md:27 and schedule recalculation step 5, research/hive-core/findings/05-state-objects.md:553, research/hive-core/findings/00-consolidated.md:260
- **Source**: hive-core 1.28.8 (`274384a8ad`): `libraries/chain/witness_schedule.cpp:42-150, 157-171, 209-231, 395, 403-433`

## Description

reference/state-objects.md:302 describes `median_props` as "Median of all witness-voted properties" (research
05:553 "Median of witness-voted properties", similar in 00-consolidated:260 and reference/consensus.md:27). That
reads as a median over every witness. The code takes it over the witnesses of one schedule
(`wso.num_scheduled_witnesses`, 21 on mainnet: the top 20 by votes among witnesses whose signing key is not null,
plus the timeshare witness), each property sorted on its own, element `size()/2` (index 10, the 11th smallest of
21). Research 06 and 07 already say this, and research 06:275 (also 09 and 17) already has the HF26/HF28 timing;
only the reference layer and the two research lines above are vague. Note that the upstream doc
`doc/witness_parameters.md:9` at this anchor says "the median of the top 20 elected witnesses", which the code
contradicts; a revision should not be "corrected" toward it.

What the reference layer should carry, because it decides when a witness's vote has any effect:

1. Only the scheduled witnesses count: a witness outside the top 20 counts only in rounds where it holds the
   timeshare slot, and one witness changes the result only if it changes which value sits at `size()/2`.
   Because the timeshare slot rotates, the result can alternate between rounds: when 10 of the elected 20 are at
   or below some value and the 11th value is decided by the timeshare witness, the median flips from round to round.
2. Timing since HF26/HF28: the median is computed from the values the witnesses have when the *future* schedule is
   built (`update_witness_schedule4(db, future_wso)` ends with `update_median_witness_props(db, wso)` at `:395`),
   and the schedule is promoted to current one round later (`:420-426`). `update_global_witness_properties`
   copies only `maximum_block_size` and `hbd_interest_rate` to the dgpo (`:42-56`), after HF28 at promotion
   (`:428-429`), before HF28 at computation time (`:147-148`). The fee and subsidy medians are used from the
   current schedule's `median_props` once it is promoted.

Suggested wording:
- state-objects.md `median_props`: "Median of the properties of the witnesses scheduled for that round (21: 20
  elected + 1 timeshare), each property sorted separately, element size()/2 (11th smallest)".
- economics.md HBD Interest: "Rate = dgpo `hbd_interest_rate` (basis points APR), the median of the scheduled
  witnesses' votes, copied from the schedule when it becomes current".
- consensus.md:27 and step 5: "median of the scheduled witnesses' votes" instead of "median of witness votes".

## Evidence

- `update_median_witness_props` builds `active` from `wso.current_shuffled_witnesses[0 .. num_scheduled_witnesses)` (`witness_schedule.cpp:61-65`) and takes `active[active.size()/2]` after sorting by each property (`:67-107`; `hbd_interest_rate` at `:81-86`).
- Elected: the top `max_voted_witnesses` by vote, skipping disabled (null-key) witnesses after HF14 (`:157-171`, skip at `:166-167`). Timeshare: `:209-231`. `HIVE_MAX_VOTED_WITNESSES_HF17` 20, `HIVE_MAX_RUNNER_WITNESSES_HF17` 1 (`config.hpp:223, 225`).
- `update_global_witness_properties` sets only `maximum_block_size` and `hbd_interest_rate` in the dgpo (`:42-56`). Interest is paid with `dgpo.get_hbd_interest_rate()` (`database.cpp:3248, 3323`).
- Mainnet, 2026-11-22, block 111885827: dgpo `hbd_interest_rate` 1000; in both the current schedule (`current_shuffled_witnesses`) and the future one (`future_shuffled_witnesses`, `database_api.get_witness_schedule` with `{"include_future": true}`) 9 of 21 witnesses are at or below 800 and the 11th smallest value is 1000, equal to `median_props.hbd_interest_rate`, as `size()/2` predicts. Earlier checks the same day found 10 of 21 in some rounds: the count moves with the timeshare slot and with rotation at the edge of the top 20.
