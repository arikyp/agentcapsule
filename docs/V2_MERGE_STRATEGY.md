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

Use a separate branch for the next ceiling-finding pass:

```text
v2-1mb-real-corpus-ceiling
```

That branch should focus on 1MB deterministic payloads and larger or external
corpora. It should not mix in Transformer training unless the n-gram ceiling and
candidate ordering are already clear.
