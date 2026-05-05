# Carrier Quality

LMCodec carrier quality work is about making the text envelope less artificial
without weakening deterministic transport. Roundtrip correctness, deterministic
decode, and entropy safety are mandatory. Naturalness is secondary.

## Greedy Preview Is Misleading

A language model preview usually chooses the most likely next token at each
step. That is useful for seeing whether a model collapses into repetition, but
it is not how LMCodec produces carrier text.

LMCodec carrier text is payload-driven. The range coder maps framed payload
bits into token choices under the model distribution. The model shapes the
probability intervals, but the payload bits choose where each step lands.

```text
greedy preview:
  model probabilities -> most likely token -> next state

encoded carrier:
  payload bits + model probabilities -> range-coded token -> next state
```

That means a model can have a repetitive greedy preview while encoded carrier
samples still show broader token use. It also means prose quality cannot be
judged from greedy text alone.

## Why Entropy Matters

Entropy measures how much choice the model leaves at each step. A very sharp
distribution may look more model-like, but it can hurt transport because most
payload bit patterns are forced through tiny probability intervals. That can
increase carrier length or cause encode convergence failures.

For V2 research, a candidate model should preserve enough average entropy for
the range coder to carry data reliably. If a config sets an entropy guard, the
promotion gate should fail when held-out entropy falls below that threshold.

## Shaping Trade-Offs

Uniform mixing blends the model distribution toward a flat distribution. Higher
mixing usually improves transport safety and entropy, but it reduces the
influence of the trained model.

Temperature flattens or sharpens the distribution. Temperature above `1.0`
raises entropy and lowers top-token concentration. Lower temperature can make a
model more decisive, but it is risky for transport if the distribution becomes
too sharp.

Minimum probability floors keep all tokens active before quantization. They are
a guardrail for pathological distributions, not a prose-quality feature.

## Current Metrics

Comparison and experiment scripts report conservative carrier metrics:

- Held-out negative log likelihood when quality text is provided.
- Average entropy per step.
- Average top-token probability.
- Unique character count in the encoded carrier.
- Longest repeated run in the encoded carrier.
- Character frequency distribution.
- Character frequency L1 divergence against held-out text when available.
- Smoothed character frequency KL-style divergence in bits when available.
- Encoded carrier sample preview.

These metrics are intentionally simple. They are meant to catch obvious
regressions such as low entropy, repeated-character collapse, narrow character
use, or carrier distributions far from held-out corpus distributions.

## Corpus Utilities

`scripts/build_carrier_corpus.py` creates deterministic synthetic carrier text.
It supports domain-style template mixes:

```bash
scripts/build_carrier_corpus.py \
  --out examples/carrier_corpus_v2.txt \
  --lines 5000 \
  --seed 42 \
  --domain mixed \
  --report-json /tmp/carrier-corpus-report.json
```

Available domains are `codec`, `operations`, `notes`, and `mixed`.

`scripts/split_corpus.py` creates deterministic train/held-out splits and can
write a validation report:

```bash
scripts/split_corpus.py \
  --input examples/carrier_corpus_v2.txt \
  --train-out examples/carrier_train_v2.txt \
  --heldout-out examples/carrier_heldout_v2.txt \
  --heldout-ratio 0.20 \
  --filter-vocab \
  --report-json /tmp/carrier-split-report.json
```

The split report records segment counts, train/held-out sizes, invalid
characters before and after filtering, and character coverage.

## What Better Means For V2

A better V2 carrier configuration should:

- Pass byte-for-byte roundtrip.
- Produce deterministic output for the same payload, model, and settings.
- Preserve model fingerprint stability.
- Keep held-out entropy above the configured minimum.
- Avoid encode convergence failures.
- Improve held-out NLL, character distribution match, diversity, or repeated
  run metrics without damaging transport safety.

Do not promote a model only because it looks more natural in a preview. Promote
it only when the transport checks remain clean and the quality metrics improve
under reproducible configs.
