# /forge-publish

Publish the current KB state to the consumer repo (hive/hive.support).

## Usage

```
/forge-publish [--dry-run]
```

## Behavior

Run `./tools/publish.sh` which assembles the consumer subset (reference/,
findings/, agents, skills, contrib infrastructure, verification.md) and
pushes to the consumer repo. No AI involved — pure file copy + git.

With `--dry-run`: show what would be published without pushing.

## Steps

1. Run `./tools/publish.sh` (or `./tools/publish.sh --dry-run`)
2. Report what was published (files changed, commit SHA)
