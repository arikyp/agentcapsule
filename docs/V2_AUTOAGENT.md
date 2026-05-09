# V2 Autoagent Boundary

The autoagent can help search the V2 experiment space, but it should not own
codec semantics or promotion decisions.

## Intended Role

The autoagent may:

- Propose bounded experiment configs.
- Run existing experiment scripts.
- Compare generated `result.json` files.
- Draft candidate reports.
- Flag regressions or suspicious metrics.
- Suggest next corpus, shaping, or training variants.

The autoagent must not:

- Change V1 fixtures automatically.
- Edit frame, armour, range-coder, quantizer, or decode semantics without
  explicit human approval.
- Promote a candidate without passing gates and a reviewed report.
- Treat natural-looking preview text as proof of carrier quality.
- Expand search space without a budget, seed, and output directory.

## Safe Operating Loop

```text
read baseline
  -> propose one bounded config or sweep
  -> run existing scripts
  -> read result.json
  -> compare against baseline
  -> write candidate report
  -> wait for manual promotion
```

## Good Autoagent Tasks

- Generate n-gram configs for domain, order, and smoothing comparisons.
- Generate Transformer shaping sweep batches.
- Summarize result deltas across runs.
- Detect failed promotion checks.
- Recommend the next smallest experiment that would reduce uncertainty.

## Manual Gates

Manual review is required before:

- Committing a new model fixture.
- Replacing any baseline.
- Adding a new frame version.
- Changing codec internals.
- Publishing a V2 release note.

## Candidate Report Shape

An autoagent-written report should include:

- Config path.
- Output directory.
- Git commit.
- Payload SHA256.
- Model fingerprint.
- Promotion status and failed checks.
- Metric deltas against fixed, n-gram, and Transformer baselines.
- Clear recommendation: promote, reject, or investigate.

The recommendation is advisory. Promotion remains a human decision.

Use `scripts/compare_results.py` for the first-pass metric table, and use
`docs/V2_CANDIDATE_REPORT_TEMPLATE.md` for any candidate that appears to beat
the current baseline.
