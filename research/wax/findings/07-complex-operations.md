# Wax Part 07 - Complex Operations & Hive Apps

**Anchor:** wax `2.0.2` (`c9c4918a`).
**Scope:** wax's high-level operation builders - the convenience layer over raw proto
operations (part 02). Two families: `complex_operations/` (builders that compose one or
more *protocol* operations) and `hive_apps_operations/` (builders for the `custom_json`
"apps" layer: follow, community, rc). Both plug into `pushOperation` via the
`OperationBase.finalize` contract from part 02.

---

## 1. The mechanism (recap)

Every high-level builder extends `OperationBase` (`operation_base.ts:8-10`) and
implements `finalize(sink): Iterable<operation>`. `Transaction.pushOperation` detects an
`OperationBase` (by the `finalize` method) and pushes each produced proto operation
(part 02, `transaction.ts:240-253`). So a builder is just a typed, fluent way to produce
the same raw operations you could hand-write - it adds no new protocol capability, only
ergonomics and correctness.

`IOperationSink` (`operation_base.ts:4-6`) gives `finalize` access to the wax api (for
asset coercion, serialization helpers, etc.).

---

## 2. complex_operations/ - composing protocol operations

Catalog (`ts/wasm/lib/detailed/complex_operations/`):

| Builder | Produces | Notes |
|---------|----------|-------|
| `CommentOperation` + `BlogPostOperation` / `ReplyOperation` (`comment.ts:136`,`:316`,`:336`) | `comment_operation` (+ optional `comment_options_operation`) | manages `json_metadata` (images/links/tags) and beneficiaries via comment-options extensions (`comment.ts:155-165`,`:303-307`) |
| `AccountAuthorityUpdateOperation` (`account_update.ts:58`) | `account_update` / `account_update2` | decomposed into role builders (section 2.1) |
| `DefineRecurrentTransferOperation` / `RecurrentTransferRemovalOperation` (`recurrent_transfer.ts:91`,`:117`) | `recurrent_transfer_operation` | removal = amount 0; pair/extension support (`:67`,`:83`,`:121-125`) |
| `WitnessSetPropertiesOperation` (`witness_set_properties.ts:53`) | `witness_set_properties_operation` | serializes the props map via the core (section 2.2) |
| `LegacyVoteOperation` (`legacy_vote_operation.ts:11`) | `vote_operation` | legacy-format helper |
| `UpdateProposalOperation` (`update_proposal.ts`) | `update_proposal_operation` | extension handling |

The defining trait: a single builder can emit **multiple** operations. `CommentOperation`
is the clearest case - one `.finalize()` may push both `comment_operation` and
`comment_options_operation` (`comment.ts:149-165`), so "post with beneficiaries" is one
fluent object, not two manual operations.

### 2.1 Authority updates via role classes

`AccountAuthorityUpdateOperation.finalize` (`account_update.ts:161-165`) iterates a set
of **role builders** and concatenates their output:
```ts
for (const role of roles) operations.push(...role.finalize(sink));
```
The roles live in `complex_operations/role_classes/` (`level_base.ts`,
`role_category_base.ts`, `categories/`) - one category per authority (owner / active /
posting / memo), each managing weight thresholds and key/account auths. This turns the
fiddly authority-math of an `account_update2` into a fluent `.owner.add(...)` /
`.active.remove(...)` style API. (`AccountAuthorityUpdateOperation` is also the type the
`scanForMatchingPrivateKeys` guard from part 05 references.)

### 2.2 Witness properties

`WitnessSetPropertiesOperation.finalize` (`witness_set_properties.ts:89-102`) emits
`{ witness_set_properties_operation: this.witnessProps }`, where the props map is
serialized via the core `cpp_serialize_witness_set_properties` (`foundation.hpp:112`,
exposed as `serializeWitnessProps` in part 04). Witness props are a typed key/value set
(signing key, HBD interest rate, account creation fee, ...) that must be binary-encoded -
the builder hides that encoding.

---

## 3. hive_apps_operations/ - the custom_json apps layer

These build the **off-chain / app-layer** `custom_json` operations. Base class
`HiveAppsOperation<ChildT, BodyT>` (`hive_apps_operations/factory.ts:7`) implements a
two-stage **stage -> authorize** pattern:

1. **Stage.** Fluent methods append JSON entries to `this.body` (`factory.ts:13`). E.g.
   `FollowOperation.followBlog(follower, blog, ...)` pushes
   `["follow", { follower, following, what: ["blog"] }]` (`follow.ts:52-68`,`:80`).
2. **Authorize / commit.** `authorize(requiredPostingAuths, requiredAuths?)`
   (`factory.ts:32-54`) wraps each staged body into a `custom_json_operation`:
   ```ts
   { custom_json_operation: { id: this.id, json: JSON.stringify(body, bigintReplacer),
                              required_auths, required_posting_auths } }
   ```
   then clears the stage. It throws `"Missing authority"` if neither auth list is set
   (`factory.ts:36-37`). The abstract `id` (`factory.ts:20`) is the custom_json id.
3. `finalize` (`factory.ts:59-61`) returns the accumulated `custom_json` operations.

Catalog:

| Builder | `id` | Examples |
|---------|------|----------|
| `FollowOperation` (`follow.ts:49`) | `"follow"` | `followBlog` / `unfollowBlog` / `muteBlog` / `blacklistBlog` / `reblog` (`follow.ts:80-314`); `EFollowActions` enum (`:31-47`); following list capped at 100 (`:55-56`) |
| community builder (`community.ts`) | community ids | community management custom_json |
| rc builder (`rc.ts`) | `"rc"` | RC delegation custom_json |

> **Consensus note (cross-KB):** of these app ids, **only `"rc"` is interpreted by the
> chain** (RC delegation; see `reference/rc.md` and the hive-core key fact "Only `\"rc\"`
> custom_json ID is chain-interpreted"). `follow` and `community` are **hivemind /
> social-API** conventions - the blockchain stores them verbatim as opaque `custom_json`
> and never validates their JSON. wax builds well-formed bodies, but their *meaning* is
> an app-layer contract, not consensus.

### Serialization quirk

`authorize` stringifies with a replacer that turns `bigint` into a decimal string
(`factory.ts:45`). The comment explains why: it relies on the node's fc JSON serializer
`as_int64` directive (stringified numbers), pending a custom nested-object stringifier -
a known temporary measure worth remembering when debugging large-number fields.

---

## 4. Python parallel

Python ships the same two families - `python/wax/wax/complex_operations/` and
`python/wax/wax/hive_apps_operations/` (seen in the package layout, part 01) - over the
identical C++ core, so the same compositions (comment+options, authority roles, follow
custom_json) are available. The fluent surface differs idiomatically (Python builders vs
TS classes), but the produced operations are identical because both serialize through the
shared `foundation`.

---

## 5. Notable findings

1. **Two convenience layers, no new protocol power.** `complex_operations` compose raw
   protocol operations; `hive_apps_operations` compose `custom_json`. Both are pure
   client-side ergonomics - the bytes are identical to hand-built operations.
2. **One builder can emit several operations** (`CommentOperation` -> comment +
   comment_options), which is the main reason to prefer them over raw `pushOperation`.
3. **Stage -> authorize is explicit** for apps ops (`factory.ts:32-54`): you must call
   `authorize(...)` to attach required auths and materialize the `custom_json`, or
   nothing is produced.
4. **Only `rc` is consensus** among the app ids; `follow`/`community` are hivemind-layer
   conventions the chain stores blindly. A malformed follow body is a client/app bug, not
   a chain rejection.
5. **Authority math is encapsulated** in `role_classes`, and witness-property binary
   encoding in `WitnessSetPropertiesOperation` - the two most error-prone raw operations
   get the most builder support.
6. **bigint JSON workaround** (`factory.ts:45`) leans on fc's `as_int64` - flagged as
   temporary in-source.

---

## 6. Code References

| Topic | File:line |
|-------|-----------|
| OperationBase contract | `ts/wasm/lib/detailed/operation_base.ts:4-10` |
| complex_operations catalog | `ts/wasm/lib/detailed/complex_operations/` |
| Comment (+options, subclasses) | `complex_operations/comment.ts:136`,`:149-165`,`:316`,`:336` |
| Account authority update + roles | `complex_operations/account_update.ts:58`,`:161-165`; `complex_operations/role_classes/` |
| Recurrent transfer (define/removal) | `complex_operations/recurrent_transfer.ts:58`,`:91`,`:117-125` |
| Witness set properties | `complex_operations/witness_set_properties.ts:53`,`:89-102`; `core/foundation.hpp:112` |
| HiveAppsOperation base (stage/authorize) | `hive_apps_operations/factory.ts:7`,`:32-61` |
| Follow builder | `hive_apps_operations/follow.ts:49`,`:52-68`,`:80`,`:303` |
| Community / RC builders | `hive_apps_operations/community.ts`, `hive_apps_operations/rc.ts` |
| Python builders | `python/wax/wax/complex_operations/`, `python/wax/wax/hive_apps_operations/` |

---

## 7. Open Questions (for later parts / zoom)

- **role_classes internals.** The exact weight-threshold/level math in
  `role_classes/level_base.ts` and `categories/` (and how it maps to `account_update` vs
  `account_update2`) is a zoom candidate.
- **comment json_metadata schema.** The full set of metadata fields wax populates
  (`app`, `format`, `tags`, `images`, `links`) and any validation was only sampled.
- **community op vocabulary.** The community custom_json action set (subscribe,
  setRole, mute post, ...) was not enumerated.
- **Builder discoverability.** Whether builders are reachable from the api object
  (factory methods) or only via direct construction/import is worth confirming for an
  end-to-end usage example.
