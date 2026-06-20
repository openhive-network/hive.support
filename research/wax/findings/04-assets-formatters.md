# Wax Part 04 - Assets & Formatters

**Anchor:** wax `2.0.2` (`c9c4918a`).
**Scope:** how wax represents and builds the three native assets (HIVE / HBD / VESTS),
the asset-math / economics helpers it exposes, and the `waxify` output formatter. The
economic *formulas* themselves (vests<->HP, HBD interest, inflation, ...) are the
hive-core KB's domain (`reference/economics.md`); wax runs the **same C++ core** math,
so this part documents the wax surface and cross-references the formulas rather than
re-deriving them.

Central file: `ts/wasm/lib/detailed/base_api.ts`.

---

## 1. The three native assets and the NAI representation

wax represents every asset as a **`NaiAsset`** (`ts/wasm/lib/detailed/api/types/asset.ts:1-5`):

```ts
interface NaiAsset { amount: string; precision: number; nai: string; }
```

`amount` is a **string** (the integer count of smallest units) - deliberately not a JS
`number`, so large balances survive without floating-point loss. `nai` is the Hive asset
identifier and `precision` the decimal places:

| Asset | `nai` | `precision` | smallest unit |
|-------|-------|-------------|---------------|
| HIVE | `@@000000021` | 3 | 0.001 HIVE |
| HBD | `@@000000013` | 3 | 0.001 HBD |
| VESTS | `@@000000037` | 6 | 0.000001 VESTS |

(The three NAIs are verified present in wax's own tests; the canonical definitions are
in the hive-core KB / `asset_symbol.hpp`.) wax does **not** hardcode these as TS
constants - the `ASSETS` record (`base_api.ts:43`) is built at construction by calling
`hbdSatoshis(0)` / `hiveSatoshis(0)` / `vestsSatoshis(0)` (`base_api.ts:54-58`), i.e. the
`nai`/`precision` metadata comes from the C++ core at runtime. `EAssetName`
(`base_api.ts:26`) is the `{ HIVE, HBD, VESTS }` enum keying that record.

---

## 2. Building assets (TypeScript)

Two unit conventions, both producing a `NaiAsset`:

| Builder | Input | Notes |
|---------|-------|-------|
| `hiveSatoshis` / `hbdSatoshis` / `vestsSatoshis(amount)` (`base_api.ts:247-257`) | smallest units (integer) | thin wrappers over the core `cpp_hive` / `cpp_hbd` / `cpp_vests` (`foundation.hpp:108-110`) |
| `hive` / `hbd` / `vests(amount)` (`base_api.ts:235-244`) | smallest units | aliases of the `*Satoshis` form |
| `hiveCoins` / `hbdCoins` / `vestsCoins(amount)` (`base_api.ts:223-232`) | whole coins (decimal) | scales by precision via `naiAssetToLong(amount, precision)` |

`cpp_general_asset(asset_num, amount)` (`foundation.hpp:107`) is the generic builder
behind them.

### Coercion and validation

- `createAssetWithRequiredSymbol(requiredSymbol, source)` (`base_api.ts:139`) coerces a
  loose input (`TNaiAssetSource` - a `NaiAsset` or a convertible number/string) into a
  `NaiAsset` of the required symbol; if already a `NaiAsset` it validates via
  `assertAssetSymbol` (`base_api.ts:126`), which checks `nai` **and** `precision` match
  and throws a `WaxError` otherwise. This is how the operation/economics builders refuse
  a HIVE asset where HBD is required.
- `getAsset(nai)` (`base_api.ts:331`) -> `{ amount, symbol }` via the core
  `cpp_asset_value` / `cpp_asset_symbol` (`foundation.hpp:115-116`) - the inverse, used
  by the formatter.

---

## 3. Asset math / economics helpers

wax surfaces the core economic calculators (each forwards to a `cpp_*` on the shared
`foundation`, so results are identical to hived's):

| wax method (TS) | Core call | hive-core formula |
|-----------------|-----------|-------------------|
| `vestsToHp(vests, totalVestingFundHive, totalVestingShares)` (`base_api.ts:259`) | `cpp_vests_to_hp` | `reference/economics.md` (VESTS<->HP) |
| `hpToVests(hive, ...)` (`base_api.ts:267`) | `cpp_hp_to_vests` | same |
| `hbdToHive(hbd, base, quote)` (`base_api.ts:275`) | `cpp_hbd_to_hive` | price-feed conversion |
| `hiveToHbd(amount, base, quote)` (`base_api.ts:283`) | `cpp_hive_to_hbd` | same |
| `estimateHiveCollateral(...)` (`base_api.ts:149`) | `cpp_estimate_hive_collateral` | collateralized convert |
| `estimateHbdInterest(...)` (`base_api.ts:165`) | `cpp_evaluate_hbd_interest` | HBD savings interest |
| `calculateCurrentManabarValue(...)` (`base_api.ts:430`) | `cpp_calculate_current_manabar_value` | manabar regen |
| `calculateManabarFullRegenerationTime(...)` (`base_api.ts:452`) | `cpp_calculate_manabar_full_regeneration_time` | manabar regen |

Two implementation notes worth recording:

- **64-bit splitting for interest.** `estimateHbdInterest` splits the account's
  `hbd_seconds` (a 128-bit-ish accumulator) into hi/lo 64-bit halves
  (`base_api.ts:167-168`) because the WASM boundary passes 64-bit integers; the C++
  side recombines them.
- **Manabar percent** is computed JS-side from the returned value vs max
  (`calculateManabarPercent`, `base_api.ts:421`), while the actual mana value and
  regeneration time come from C++.

The core also has `cpp_calculate_hp_apr` and `cpp_calculate_inflation_rate_for_block`
(`foundation.hpp:155`,`:208`); these are part of the same economic surface (cross-ref
`reference/economics.md`).

> **Cross-KB note:** because wax calls the identical C++ routines hived uses, a value wax
> computes (e.g. VESTS->HP) should match what the chain would compute for the same dgpo
> inputs. wax is a faithful client mirror, not a re-implementation.

---

## 4. The `waxify` formatter (TypeScript)

`waxify` turns raw Hive objects (operations, assets, transactions) into human-readable
strings via a **template-literal tag**:

- `WaxBaseApi.formatter = WaxFormatter.create(this)` (`base_api.ts:67`); the `waxify`
  getter (`base_api.ts:68-70`) exposes `WaxFormatterBase.waxify(strings, ...args)`
  (`formatters/base.ts:76`), so you write ``wax.waxify`... ${op} ...` `` and embedded
  Hive objects are formatted in place. `format(data)` (`formatters/base.ts:72`) formats
  a single object.

### The matching engine

`WaxFormatter` (`formatters/waxify.ts:21`) holds two rule sets: `matchers` (by property
name, optionally by property value) and `instances` (by `instanceof`). During traversal,
`handleProperty` / `handleInstanceOf` (`waxify.ts:152-191`) pick the format function for
each property. Rules are registered with the `@WaxFormattable({ matchProperty, matchValue,
... })` decorator (reflect-metadata).

### Default formatters

`WaxFormatter.create` installs `DefaultFormatters` when `options.createDefaultFormatters`
is set (`waxify.ts:35-36`). They cover (`formatters/default_formatters.ts`):

| Match | Renders |
|-------|---------|
| `matchProperty: "nai"` (`:28-30`) | a `NaiAsset` -> via `formatNai` (`:13-25`): `getAsset` then `formatNumber`, e.g. `"1.000 HIVE"` |
| `matchProperty: "operations"` (`:33`) | an operations array |
| `matchProperty: "id", matchValue: "rc"` (`:48`) | RC `custom_json` |
| `matchProperty: "id", matchValue: "community"` (`:68`) | community `custom_json` |
| `matchProperty: "id", matchValue: "follow"` (`:96`) | follow `custom_json` |
| `matchProperty: "props"` (`:117`) | witness props |

`formatNai` honors options: `displayAsNai` (return the raw `NaiAsset`), `formatAmount`
(run `formatNumber`), `appendTokenName` (`"<amount> <symbol>"`), and `locales`.

### Number formatting

`formatNumber(amount, precision?, locales?)` (`waxify.ts:60-85`) is BigInt-based and
locale-aware: it groups the integer part with `Intl.NumberFormat` and appends a
precision-padded fraction. The code comment notes why it does **not** just use
`Intl.NumberFormat`: that API caps precision at 20, but Hive (SMTs) may exceed it, and
amounts can exceed `MAX_SAFE_INTEGER`.

### Extending

`extend(CustomFormatter | options, options?)` (`waxify.ts:87-147`) clones the current
matcher/instance set and merges a decorated custom-formatter class, returning a new
immutable `WaxFormatter`. This is how an app adds rendering for its own `custom_json`
ids or operation types.

---

## 5. Python parallel

The asset/economics surface exists in Python (same C++ core); the formatter does not.

| Capability | TypeScript | Python |
|------------|------------|--------|
| Build asset | `wax.hive(amount)` etc. (`base_api.ts:235`) | `wax.hive` -> `AssetFactory` (`_private/base_api.py:149-157`; `interfaces.py:381-391`); core `hive(amount)` (`cpp_python_bridge.pyi:43-45`) |
| Generic | `cpp_general_asset` | `general_asset(asset_num, amount)` (`cpp_python_bridge.pyi:42`) |
| Conversions | `vestsToHp` / `hbdToHive` / ... | `calculate_vests_to_hp` / `calculate_hbd_to_hive` / `calculate_hp_to_vests` (`cpp_python_bridge.pyi:47-56`) |
| Asset value type | `NaiAsset` (`{amount,precision,nai}`) | `python_json_asset` |
| `waxify` formatter | **yes** (`formatters/`) | **no equivalent** |

So output formatting is a TypeScript-only convenience; Python consumers format assets
themselves (or use the raw `python_json_asset`).

---

## 6. Notable findings

1. **`NaiAsset.amount` is a string, not a number** (`asset.ts:2`) - precision-safe by
   design; the formatter parses it as `BigInt`. Treating it as a JS number elsewhere is
   a bug risk.
2. **Asset metadata is sourced from C++ at runtime**, not hardcoded in TS - `ASSETS` is
   built from `cpp_*` calls at construction (`base_api.ts:54-58`), so symbol/precision
   always match the linked core.
3. **wax's economics are the chain's economics.** Every conversion forwards to the same
   `cpp_*` routine hived uses; wax does not approximate. Cross-ref `reference/economics.md`
   for the formulas rather than reading them out of wax.
4. **`waxify` is TS-only** and decorator-driven; it ships default renderers for assets,
   operations, and the rc/community/follow `custom_json` ids, and is extensible per app.
5. **Symbol validation is strict** - `createAssetWithRequiredSymbol` rejects a wrong-NAI
   or wrong-precision asset (`base_api.ts:126-135`), so builders fail fast rather than
   emitting a malformed operation.

---

## 7. Code References

| Topic | File:line |
|-------|-----------|
| NaiAsset type | `ts/wasm/lib/detailed/api/types/asset.ts:1-5` |
| EAssetName / ASSETS record | `base_api.ts:26`, `:43`, `:54-58` |
| Asset builders (satoshis / coins / aliases) | `base_api.ts:223-257` |
| Core asset builders | `core/foundation.hpp:107-110` |
| createAssetWithRequiredSymbol / assertAssetSymbol | `base_api.ts:139`, `:126` |
| getAsset (value/symbol) | `base_api.ts:331`; `foundation.hpp:115-116` |
| Conversions (vests/hp, hbd/hive) | `base_api.ts:259-289`; `foundation.hpp:166-199` |
| Collateral / interest | `base_api.ts:149`, `:165`; `foundation.hpp:219`,`:233` |
| Manabar | `base_api.ts:421-458`; `foundation.hpp:138-139` |
| WaxFormatter + matching | `ts/wasm/lib/detailed/formatters/waxify.ts:21`,`:152-191` |
| formatNumber | `formatters/waxify.ts:60-85` |
| waxify tag / format | `formatters/base.ts:76`,`:72` |
| Default formatters | `formatters/default_formatters.ts:10`,`:13-30`,`:33-117` |
| extend | `formatters/waxify.ts:87-147` |
| Python assets / conversions | `python/wax/wax/_private/base_api.py:149-157`; `cpp_python_bridge.pyi:42-56` |

---

## 8. Open Questions (for later parts / zoom)

- **`naiAssetToLong` rounding.** How `hiveCoins(1.2345)` (more decimals than precision) is
  rounded/truncated was not traced.
- **`getAsset` legacy-string output.** Whether wax can emit the legacy `"1.000 HIVE"`
  asset string (vs the NAI object) on the serialization path is a part-03/06 cross-check.
- **Formatter traversal depth.** How `waxify` recurses into nested operations/extensions
  (and interacts with the binary-view metadata) is unexplored.
- **`cpp_calculate_hp_apr` / inflation exposure.** Whether these are surfaced as named
  TS/Python methods or only reachable via the chain is open (cross-ref part 06).
