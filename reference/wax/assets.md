# Wax Reference - Assets & Formatters

Native assets, asset math, and the `waxify` formatter. Deep detail:
`findings/04-assets-formatters.md`. For the economic formulas, use the hive-core
reference (`../economics.md`).

## NaiAsset

```ts
interface NaiAsset { amount: string; precision: number; nai: string; }
```
`amount` is the integer count of smallest units, as a **string** (BigInt-backed,
precision-safe). Metadata (`ASSETS` record) is sourced from the C++ core at runtime.

| Asset | `nai` | `precision` | smallest unit |
|-------|-------|-------------|---------------|
| HIVE | `@@000000021` | 3 | 0.001 |
| HBD | `@@000000013` | 3 | 0.001 |
| VESTS | `@@000000037` | 6 | 0.000001 |

## Building (TypeScript)

| Builder | Input | Example |
|---------|-------|---------|
| `wax.hiveSatoshis(n)` / `hbdSatoshis` / `vestsSatoshis` | smallest units | `hiveSatoshis(1000)` = 1.000 HIVE |
| `wax.hive(n)` / `hbd` / `vests` | smallest units (aliases) | |
| `wax.hiveCoins(n)` / `hbdCoins` / `vestsCoins` | whole coins (decimal) | `hiveCoins(1.5)` = 1.500 HIVE |
| `wax.getAsset(nai)` | a NaiAsset | -> `{ amount, symbol }` |

`createAssetWithRequiredSymbol(symbol, source)` coerces+validates (rejects wrong
NAI/precision). Python: `wax.hive(n)` via an `AssetFactory`; core `general_asset`,
`hive`/`hbd`/`vests`.

## Conversions / economics helpers

Each forwards to the same `cpp_*` hived uses (wax mirrors the chain, never approximates):

| wax method | Converts |
|------------|----------|
| `vestsToHp(vests, totalVestingFundHive, totalVestingShares)` | VESTS -> HP |
| `hpToVests(hive, ...)` | HP -> VESTS |
| `hbdToHive(hbd, base, quote)` / `hiveToHbd(amount, base, quote)` | via price feed |
| `estimateHiveCollateral(...)` | collateralized convert |
| `estimateHbdInterest(...)` | HBD savings interest |
| `calculateCurrentManabarValue(...)` / `calculateManabarFullRegenerationTime(...)` | manabar |

(Python: `calculate_vests_to_hp`, `calculate_hbd_to_hive`, `calculate_hp_to_vests`, ...)

## waxify formatter (TypeScript-only)

A decorator-driven, template-literal formatter that renders Hive objects to readable text.

```ts
wax.waxify`Transfer of ${{ amount, asset }} from ${from}`;   // "... 1.000 HIVE ..."
```

- Default renderers (`DefaultFormatters`): assets (`nai` -> `"1.000 HIVE"`), operations,
  `custom_json` ids `rc` / `community` / `follow`, witness props.
- `formatNumber(amount, precision?, locales?)` - BigInt-based, locale grouping,
  arbitrary precision (Intl caps at 20; SMTs may exceed).
- Extend with `wax.formatter.extend(CustomFormatter)`; options: `displayAsNai`,
  `formatAmount`, `appendTokenName`, `locales`.
- **No Python equivalent** - Python consumers format assets themselves.
