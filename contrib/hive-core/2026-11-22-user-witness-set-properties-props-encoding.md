# witness_set_properties: the KB never says how a props value is encoded (fc::raw as hex), per key, with examples

- **Topic**: hive-core
- **Type**: addition
- **Affects**: reference/operations.md (witness_set_properties_operation, ID 42), research/hive-core/findings/02-operations-catalog.md (recognized `props` keys), research/hive-core/findings/03-operation-validation.md (witness_set_properties table), evals/hive-core.json
- **Source**: hive-core 1.28.8 (`274384a8ad`): `libraries/protocol/include/hive/protocol/hive_operations.hpp:468-488`, `libraries/protocol/hive_operations.cpp:287-396`, `libraries/chain/hive_evaluator.cpp:113-208`, `libraries/protocol/include/hive/protocol/asset_symbol.hpp:157-216`; fc `4ab43c0357` (the 1.28.8 submodule; same lines in `7951549d` on develop): `include/fc/io/raw.hpp:718-725`, `src/variant.cpp:665-673`, `src/crypto/hex.cpp:6-40`

## Description

The unit and the type of `hbd_interest_rate` are already in the KB (`reference/state-objects.md:75` "BPS",
`reference/economics.md:96`, research 02 and 03 with the 0..10000 range), and research/wax part 07 says props
"must be binary-encoded". What is missing everywhere is how an op-42 `props` value is actually built: that it is
the `fc::raw` packing of a typed value written as hex, the type and byte layout per key, and an example. Without
that, an agent asked "vote an 8% HBD APR" will write `8`, `"8"`, `800` or `"0.08"`, and two of those are
accepted and do the wrong thing (see below).

Please add to the op 42 entry in reference/operations.md (and the research parts it cites):

1. `props` is a JSON array of `[name, hex]` pairs (a `flat_map`; an object form is not accepted, and the binary form,
   which is what gets signed, is sorted by key, so a client packing it itself must sort). Each value is the
   `fc::raw` packing of the key's type, as hex. Integers are little-endian.
2. Type and layout per key (from the `unpack_from_vector` calls in `validate()` and the evaluator):

| key | type | layout |
|---|---|---|
| `key`, `new_signing_key` | `public_key_type` | 33 bytes: base58-decode the part after `STM` (37 bytes) and drop the trailing 4-byte RIPEMD-160 checksum |
| `account_creation_fee` | `asset` | int64 amount (satoshis) + symbol, legacy or NAI form (below): 16 or 12 bytes |
| `maximum_block_size` | `uint32_t` | 4 bytes |
| `hbd_interest_rate` (legacy `sbd_interest_rate`) | `uint16_t` | 2 bytes, basis points of `HIVE_100_PERCENT` (10000) |
| `account_subsidy_budget` | `int32_t` | 4 bytes |
| `account_subsidy_decay` | `uint32_t` | 4 bytes |
| `hbd_exchange_rate` (legacy `sbd_exchange_rate`) | `price` | base asset (HBD) + quote asset (HIVE): 32 or 24 bytes |
| `url` | `std::string` | varint length + UTF-8 bytes |

   Asset symbol, two accepted forms (`asset_symbol.hpp:157-216`: the unpacker reads 4 bytes, completes a legacy
   symbol if they match one, otherwise takes them as the asset number):
   - legacy, 8 bytes: precision `03` + `STEEM` padded with zeros for HIVE (`03535445454d0000`), `03` + `SBD` padded for HBD (`0353424400000000`); `TESTS`/`TBD` on testnet;
   - NAI, 4 bytes: asset number, HIVE 3200000035 = `2320bcbe`, HBD 3200000003 = `0320bcbe`.
   Both occur on mainnet: wax 2.0.2 packs fee and price in hf26 (NAI) mode (`core/foundation.cpp:1281-1289, 1304-1311`), dhive and hive-js write the legacy form.
3. Worked examples: `hbd_interest_rate` 800 (8%) = `"2003"`, 1000 = `"e803"`; `account_creation_fee` 1.000 HIVE =
   `"e80300000000000003535445454d0000"` or `"e8030000000000002320bcbe"`; `hbd_exchange_rate` 0.034 HBD / 1.000 HIVE =
   `"22000000000000000353424400000000e80300000000000003535445454d0000"`; `url` `https://testurl` =
   `"0f68747470733a2f2f7465737475726c"`; `key` for `STM5dLh5HxjjawY4Gm6o6ugmJUmEXgnfXXXRJPRTxRnvfFBJ24c1M` =
   `"02614c335eae65faadc307003549cf491126a883c10a57d918c651b9040ed82616"`.
4. Lenient decoding, which is what makes wrong encodings dangerous (source-derived, then verified 2026-11-22 on a solo
   testnet chain of the official `testnet:1.28.8` image, values signed with the image's `sign_transaction` and broadcast;
   a witness at 700 (`"bc02"`) before each case):
   - JSON hex to bytes sizes the buffer to `len/2` and stops when it is full (`variant.cpp:665-673`, `hex.cpp:27-41`): an odd final character is dropped unchecked (`"2003z"` reads as 800), any other non-hex character throws.
   - `unpack_from_vector` does nothing on an empty vector and never checks for leftover bytes (`raw.hpp:718-725`).
   - So: `"0.08"` is rejected (invalid hex); `800` as a JSON number becomes `"800"` = 1 byte, too short for uint16, rejected; `"20030000"` reads as 800 (extra bytes ignored); `8` or `"8"` (any one-character value) becomes an empty vector, `validate()` passes with 0, and the evaluator marks the field changed and writes its default-constructed `chain_properties` value, `HIVE_DEFAULT_HBD_INTEREST_RATE` = 1000, i.e. **silently votes 10%** (`hive_evaluator.cpp:120, 149-154, 192-193`; `witness_objects.hpp:49`).
5. `key` must equal the witness's current on-chain signing key (`hive_evaluator.cpp:128-133`; already in research
   02 but not in the reference entry). Consequence: after a witness publishes the null key, `witness_set_properties`
   can never be used for it again; re-enabling needs `witness_update` with active authority (`hive_operations.hpp:465`).
6. Unknown keys are ignored by both `validate()` and the evaluator, so a misspelled key yields a valid op that changes
   nothing. Before HF24 the evaluator also ignores the `hbd_*` names (`hive_evaluator.cpp:149-151, 171-173`).
7. The 0..10000 range of `hbd_interest_rate` is checked only in `validate()` (`hive_operations.cpp:340`), not in the evaluator.

Proposed eval item for evals/hive-core.json (its `evidence.kb` entries hold the answer only once the addition above lands; until then a KB-backed run would miss it):

```json
{
  "id": "HC-E026",
  "kind": "trap",
  "question": "I'm a witness and want to vote an 8% HBD savings APR with witness_set_properties. What exactly goes into props, and what happens if I write the rate as 8?",
  "expected": "props is a JSON array of [name, hex] pairs: [\"hbd_interest_rate\", \"2003\"] (uint16 800 = 8% in basis points of 10000, fc::raw little-endian, as hex; legacy name sbd_interest_rate also accepted) plus [\"key\", <the witness's current signing key as 33-byte hex>], signed by that signing key, no active key. Through wax: WitnessSetPropertiesOperation with hbdInterestRate: 800. Writing 8 or \"8\" is not rejected: one hex character converts to an empty value and the evaluator stores the default 1000, i.e. it votes 10%.",
  "forbidden": [
    "\"hbd_interest_rate\": 8 sets 8%",
    "writing \"0.08\" (or 0.08) sets 8%",
    "\"hbd_interest_rate\": 800 as a JSON number works",
    "props is an object of plain JSON values"
  ],
  "evidence": {
    "kb": [
      "reference/operations.md (witness_set_properties_operation)",
      "research/hive-core/findings/02-operations-catalog.md (witness_set_properties recognized props keys)",
      "research/hive-core/findings/03-operation-validation.md (witness_set_properties)"
    ],
    "source": [
      "libraries/protocol/include/hive/protocol/hive_operations.hpp:475-487",
      "libraries/protocol/hive_operations.cpp:333-334",
      "libraries/protocol/hive_operations.cpp:340",
      "libraries/chain/hive_evaluator.cpp:128-133",
      "libraries/chain/hive_evaluator.cpp:149-154",
      "libraries/protocol/include/hive/protocol/config.hpp:211",
      "libraries/protocol/include/hive/protocol/config.hpp:251"
    ]
  },
  "applies": "HF24+ for the hbd_interest_rate name (current HF28)",
  "origin": "reference/operations.md witness_set_properties_operation"
}
```

## Evidence

- `props` type: `flat_map< string, vector< char > > props;` (`hive_operations.hpp:471`). Authority: `authority( 1, props["key"], 1 )`, or the unsatisfiable null account authority without `key` (`:475-487`).
- Per-key types in `validate()`: `asset` (`hive_operations.cpp:297-298`), `uint32_t` (`:315-316`), `uint16_t` (`:333-334`, range `:340`), `public_key_type` (`:346-347`), `price` (`:357-358`), `std::string` (`:367-368`), `int32_t` (`:378-379`), `uint32_t` (`:387-388`). The evaluator unpacks the same types (`hive_evaluator.cpp:113-208`).
- On chain, both asset forms: legacy in tx `60de01a1f358ee1052a26e7bbda78ad65e86ebd3` (block 63344580, `account_creation_fee` 16 bytes) and most hourly feeds sent with witness_set_properties; NAI in tx `eb46e9fb728bfd903a13e79b1f46db76a50f14b5` (block 103678501, `hbd_exchange_rate` = `47000000000000000320bcbee8030000000000002320bcbe`, 0.071 HBD / 1.000 HIVE).
- Example check: tx `a52e8103a588e2eaca042420f9f4e52c11d7a738` (block 111884910) carries `["hbd_interest_rate","2003"]`; `condenser_api.get_witness_by_account` then returns 800 for that witness.
- hive/hive#672 (closed) asked why these values must be serialized at all; its url example is the one used above.
- Testnet results (item 4): `"8"`, `8` and `""` -> accepted, rate 1000 (the three sign to the same digest); `"2003"`, `"2003z"`, `"20030000"` -> 800; `"800"` and `800` -> rejected, `Out of Range ... error unpacking uint16_t`; `"0.08"` -> rejected before broadcast, `Invalid hex character '.'`; `["hbd_interest","2003"]` -> accepted, rate unchanged.
