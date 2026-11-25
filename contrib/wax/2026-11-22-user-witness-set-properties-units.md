# WitnessSetPropertiesOperation: hbdInterestRate is basis points, not percent; fee and price are packed in NAI form

- **Topic**: wax
- **Type**: addition
- **Affects**: reference/wax/operations.md (`WitnessSetPropertiesOperation` row), research/wax/findings/07-complex-operations.md (section 2.2)
- **Source**: wax 2.0.2 (`c9c4918a`): `ts/wasm/lib/detailed/complex_operations/witness_set_properties.ts:39-42, 80`, `core/foundation.cpp:158-159, 1281-1289, 1304-1311`, `core/types.hpp:105-106`

## Description

reference/wax/operations.md says only "binary props encoding" for `WitnessSetPropertiesOperation`. Two facts
an agent needs:

1. `hbdInterestRate` takes the raw chain value in basis points (`800` = 8%), which wax packs as uint16 into the hex
   `props` value (`"2003"`). The TypeScript docstring says only "The HBD interest rate." (the C++ core struct does
   say "in BPS - basis points", `core/types.hpp:105-106`), so `8` is the natural mistake, and it is accepted: it
   sets 0.08%. clive, which uses wax, takes the same option in percent (`--hbd-interest-rate 8`) and converts it
   before calling wax, so the two interfaces differ by a factor of 100. The other numeric props
   (`maximumBlockSize`, `accountSubsidyBudget`, `accountSubsidyDecay`) are raw chain values too.
2. wax packs `accountCreationFee` and `hbdExchangeRate` in hf26 mode, i.e. with the 4-byte NAI symbol (12-byte
   asset, 24-byte price), while dhive and hive-js write the 8-byte legacy symbol. The chain accepts both; a
   decoder of props must handle both.

## Evidence

- `hbdInterestRate?: number` with docstring "The HBD interest rate." (`witness_set_properties.ts:39-42`), passed through unchanged as `hbd_interest_rate` (`:80`).
- `core/foundation.cpp:158-159`: `result.emplace("hbd_interest_rate", fc::to_hex(fc::raw::pack_to_vector(value.hbd_interest_rate.value())))`; `std::optional<uint16_t> hbd_interest_rate` documented "in BPS - basis points" (`core/types.hpp:105-106`).
- hf26 pack mode for `json_asset` and `json_price` (`core/foundation.cpp:1281-1289, 1304-1311`). The NAI form occurs on chain, e.g. tx `eb46e9fb728bfd903a13e79b1f46db76a50f14b5` (block 103678501): `hbd_exchange_rate` = `47000000000000000320bcbee8030000000000002320bcbe`.
- clive (for contrast, not KB scope; local develop `4c20770788`): `--hbd-interest-rate` help "in percent (0.00-100.00)" (`clive/__private/cli/process/main.py:273-277`), converted with `percent_to_hive_percent` (`clive/__private/core/wax_operation_wrapper.py`).
