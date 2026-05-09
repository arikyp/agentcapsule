# LMCodec V2 Baseline

Date: 2026-05-08

V2 starts from a clean V1 checkpoint. The goal is to improve carrier quality
and experiment discipline without changing the V1 correctness contract.

## Baseline Contract

Every V2 experiment must preserve these V1 properties:

- Byte-for-byte payload roundtrip.
- Deterministic output for the same payload, model, and settings.
- Stable model fingerprint before decode.
- Valid copy/paste armour.
- Existing fixed, n-gram, and Transformer golden fixtures remain unchanged.
- No frame or armour semantic change unless an explicit new version is added.

## Current Repository State

- Repository: `/home/ubuntu/code/lmcodec`
- Branch: `main`
- Upstream: `origin/main`
- Baseline commit: `c4ceb96`
- Verification on 2026-05-08:
  - `sh scripts/verify_v1.sh`: passed, 65 tests
  - `sh scripts/release_check.sh`: passed

## Current Experiment Baseline

The existing example runs use `pyproject.toml` as the payload.

| Experiment | Config | Roundtrip | Promotion | Entropy | Held-out NLL | Bits/char | Unique chars | Longest run |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| fixed | `experiments/configs/example_fixed.json` | pass | pass | 6.000 | 6.000 | 5.992 | 57 | 2 |
| n-gram order 1 | `experiments/configs/example_ngram.json` | pass | pass | 5.966 | 5.459 | 5.911 | 64 | 2 |
| Transformer fixture | `experiments/configs/example_transformer.json` | pass | pass | 5.930 | 5.334 | 5.922 | 63 | 2 |

Interpretation:

- The fixed carrier is the transport ceiling for entropy but has no prose
  quality.
- The n-gram and Transformer carriers improve held-out NLL while keeping enough
  entropy for tested payloads.
- The Transformer fixture still needs heavy shaping, so V2 should treat it as
  a starting point rather than a promoted final model.

## V2 Success Criteria

A V2 candidate can be promoted only when it:

- Passes roundtrip and decoded SHA256 checks.
- Keeps model fingerprint stability.
- Meets the configured entropy floor.
- Avoids encode convergence failures.
- Leaves V1 golden tests unaffected when `run_golden_tests` is enabled.
- Improves at least one carrier-quality metric without materially damaging
  transport metrics.

Useful quality metrics are:

- Held-out NLL.
- Average entropy.
- Average top-token probability.
- Character frequency divergence against held-out text.
- Unique carrier character count.
- Longest repeated run.
- Bits per carrier character.

## First V2 Track

The first track should stay cheap and reproducible:

1. Re-run fixed and n-gram configs against the existing V2 train/held-out
   corpus.
2. Compare n-gram corpus and order choices before training larger models.
3. Run bounded shaping sweeps against the pinned Transformer fixture.
4. Train/export a stronger deterministic Transformer only after corpus and
   shaping baselines are understood.

The autoagent can help generate and run bounded configs, but promotion remains
manual and metric-backed.

## Initial V2 Corpus Runs

These runs use the existing V2 corpus split:

- Train: `examples/carrier_train_v2.txt`
- Held-out: `examples/carrier_heldout_v2.txt`
- Payload: `pyproject.toml`

| Experiment | Config | Roundtrip | Promotion | Entropy | Held-out NLL | Bits/char | Unique chars | Longest run |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| fixed V2 baseline | `experiments/configs/v2_fixed_baseline.json` | pass | pass | 6.000 | 6.000 | 6.000 | 60 | 3 |
| n-gram mixed 5k order 1 | `experiments/configs/v2_ngram_mixed_5k_order1.json` | pass | pass | 5.760 | 4.522 | 5.787 | 64 | 3 |
| n-gram mixed 5k order 2 | `experiments/configs/v2_ngram_mixed_5k_order2.json` | pass | pass | 5.628 | 3.668 | 5.961 | 64 | 2 |
| Transformer fixture anchor | `experiments/configs/v2_transformer_fixture_anchor.json` | pass | pass | 5.930 | 5.334 | 5.961 | 64 | 3 |

Early read:

- The V2 corpus materially improves n-gram held-out NLL against the older V1
  corpus baseline.
- Order 2 is the current n-gram candidate to study next: it has much better
  held-out NLL than order 1 and still clears the entropy gate, but its sharper
  distribution needs more payload and shaping stress before promotion.
- The pinned Transformer fixture remains useful as a shaping anchor, but the
  current V2 n-gram order 2 run is a stronger near-term baseline on held-out
  NLL.
