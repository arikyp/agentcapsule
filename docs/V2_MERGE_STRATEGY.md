# V2 Merge Strategy

Date: 2026-05-08

Current branch: `codex/v2-profile-encode-hotpath`

## Recommended Shape

Merge this branch as one V2 runtime-and-evidence PR if review stays manageable.
The branch is coherent:

1. It preserves V1 codec semantics, golden fixtures, frame layout, armour
   behavior, and runtime dependencies.
2. It removes measured runtime bottlenecks without changing encoded streams.
3. It reruns the large-payload evidence after the runtime fixes.
4. It adds a broader 256KB/512KB real-corpus ladder to verify the new ceiling.

## Commit Layers

The commits are already split into reviewable layers:

- Runtime hot-path fixes.
- Distribution-preparation caching.
- 100KB large-payload rerun documentation.
- 256KB/512KB real-corpus payload ladder and results.

If the PR becomes too large, split at those boundaries rather than rewriting the
work into unrelated chunks.

## Merge Gates

Before merging to the V2 base branch, require:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
sh scripts/verify_v1.sh
```

Optional but useful:

```bash
sh scripts/release_check.sh
scripts/run_matrix.py experiments/matrices/v2_real_corpus_payload_ladder.json --resume --timeout-seconds 120
```

The matrix command may reuse the current ignored result artifacts. Run without
`--resume` only when fresh timings are needed.

## PR Positioning

Recommended title:

```text
Strengthen V2 runtime and large-payload evidence
```

Recommended summary:

- Keeps codec semantics and V1 fixtures unchanged.
- Optimizes encode/decode hot paths around prefix checks, frame probing,
  distribution preparation, and trusted internal CDF validation.
- Moves routine n-gram payload evidence from 100KB to 512KB.
- Keeps `order3_quality` as the quality candidate and
  `order3_balanced_shape` as the entropy/safety candidate.
- Defers Transformer training until a separate branch.

## Next Branch

The follow-on ceiling-finding branch is:

```text
codex/v2-1mb-real-corpus-ceiling
```

It focuses on 1MB deterministic payloads and broader local corpora. It does not
mix in Transformer training.

Result summary:

- Matrix: `experiments/matrices/v2_1mb_real_corpus_ceiling.json`
- Results: `docs/V2_1MB_REAL_CORPUS_CEILING_RESULTS.md`
- Outcome: 12/12 hard gates passed.

If this branch is reviewed before the runtime branch merges, treat it as a
stacked branch on top of `codex/v2-profile-encode-hotpath`. If the runtime
branch merges first, rebase this branch onto the V2 base branch and keep only
the 1MB matrix/results commit.

After this branch, a Transformer-focused comparison branch is reasonable. It
should compare against the n-gram evidence rather than replacing it.
