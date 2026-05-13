# LMCodec Implementation Plan

## 1. Goal

Build a deterministic, lossless codec that maps arbitrary bytes to
plausible-looking text and back again.

The codec is not a normal compressor. It uses a language model distribution to
shape the carrier text, while a range coder guarantees a reversible mapping
between byte payload bits and generated symbols.

## 2. Core Components

### Language Model

V1 starts with a deterministic 64-symbol uniform carrier model. This is a
transport-kernel baseline: `65536 / 64` is exact, so each token carries six bits
and the arithmetic coder avoids severe underflow stalls.

A character n-gram model is recommended before a Transformer because the
arithmetic layer is the main correctness risk.

Required interface:

```python
class LMState:
    pass

def lm_init_state() -> LMState:
    ...

def lm_step_probs(state: LMState) -> list[float]:
    """Return probabilities over vocab in fixed token-id order."""

def lm_advance(state: LMState, token_id: int) -> None:
    """Advance state by one observed/generated token."""
```

Determinism requirements:

- Fixed vocab ordering persisted with the model.
- Fixed beginning-of-stream behavior.
- No randomness during inference.
- Stable probability calculation.
- Model fingerprint checked before decode.

### Probability Quantizer

The quantizer converts floating-point probabilities into an integer cumulative
distribution function for range coding.

V1 constants:

```text
TOT = 65536
TOPK = 0
```

V1 should avoid TOPK until the base codec is stable. TOPK introduces ambiguity
around zero-frequency inactive tokens and should be specified later.

Required invariants:

- `sum(freq) == TOT`
- `freq[i] >= 1` for every active token
- CDF length is `V + 1`
- `cdf[0] == 0`
- `cdf[-1] == TOT`
- Ties are resolved by token id ascending

Reference algorithm:

1. Compute `x[i] = p[i] * TOT`.
2. Set `freq[i] = floor(x[i])`.
3. Clamp active token frequencies to at least `1`.
4. Compute `delta = TOT - sum(freq)`.
5. If `delta > 0`, add one to tokens with largest fractional remainders.
6. If `delta < 0`, subtract one from tokens with smallest fractional remainders where `freq[i] > 1`.
7. Build cumulative sums.

### Range Coder

Use an integer range coder with a fixed bitstream convention.

Decisions to lock before implementation:

- Integer width: prefer 64-bit internal arithmetic for safety.
- Bit order: define as MSB-first within bytes unless a reason exists not to.
- EOF behavior for source bits during encode: deterministic infinite zero padding.
- Flush/finalization behavior for emitted bits.

The range coder must support:

```python
encoder.push_symbol(cdf, symbol) -> None
encoder.emitted_bits() -> BitView
encoder.finish() -> bytes

decoder.pop_symbol(cdf) -> int
```

### Framing and Armour

Armour format:

```text
-----BEGIN LMCODEC-----
version: 1
model_fingerprint: <sha256 hex>
settings: TOT=65536; TOPK=0

<payload text>
-----END LMCODEC-----
```

Decoder behavior:

- Ignore text outside markers.
- Normalize `\r\n` and `\r` to `\n`.
- Parse and validate header fields.
- Fail early on model fingerprint mismatch.
- Fail clearly on invalid armour.

Important wrapping decision:

Presentation wrapping must not mutate the encoded token stream. For V1, reserve
newlines for armour/wrapping by excluding `\n` from the carrier alphabet, or do
not implement wrapping. Allowing generated newline tokens and inserted wrapping
newlines at the same time is ambiguous.

### Payload Header

The arithmetic-recovered bitstream begins with:

```text
magic        4 bytes  b"LMC1"
payload_len 4 bytes  uint32 little endian
crc32        4 bytes  uint32 little endian over raw payload
payload      N bytes
```

Optional later field:

```text
sha256      32 bytes  sha256 over raw payload
```

V1 should start with CRC32 only. SHA256 can be added once versioning is in
place.

## 3. Critical Algorithm Detail

The naive stopping rule "stop when the range decoder has consumed all payload
bits" is not precise enough. Range decoders maintain lookahead state and may
consume bits before the inverse encoder would have emitted them.

Use a mirror encoder while generating text.
The implementation also uses a finish-preview check: encode may stop when
finalizing the mirror encoder would reveal the target framed bit prefix. Decode
therefore attempts normal streaming recovery after each token and then performs
a final encoder flush at the end of the carrier text.

### Encode: Bytes to Text

1. Build framed bytes:

```text
F = magic || payload_len || crc32 || payload
```

2. Convert `F` to a bitstream `B` using the canonical bit order.
3. Initialize a range decoder over `B` plus infinite zero padding.
4. Initialize a mirror range encoder.
5. Generate symbols until the mirror encoder has emitted a bit prefix equal to
   `B`.

Pseudo-code:

```python
B = bits(frame(payload))
source = RangeDecoder(B, eof_pad_bit=0)
mirror = RangeEncoder()
state = lm_init_state()
tokens = []

while not mirror.has_prefix(B):
    probs = lm_step_probs(state)
    cdf = quantize(probs)
    token = source.pop_symbol(cdf)
    tokens.append(token)
    mirror.push_symbol(cdf, token)
    lm_advance(state, token)
```

`mirror.has_prefix(B)` means:

- The mirror has emitted at least `len(B)` bits.
- The first `len(B)` emitted bits exactly equal `B`.

Any mirror bits after `len(B)` are arithmetic-coder overhang and are not part of
the payload.

### Decode: Text to Bytes

1. Extract carrier payload text from armour.
2. Initialize a range encoder.
3. For each observed token:

```python
probs = lm_step_probs(state)
cdf = quantize(probs)
encoder.push_symbol(cdf, token)
lm_advance(state, token)
```

4. As bits are emitted:

- Parse the 12-byte frame header once available.
- Continue until `12 + payload_len` bytes are available.
- Verify magic and CRC.
- Return the payload.

Decode may stop as soon as the full framed payload has been recovered. Extra
arithmetic overhang bits are ignored.

## 4. Repository Structure

Planned layout:

```text
lmcodec/
  README.md
  docs/
    IMPLEMENTATION_PLAN.md
  src/
    lmcodec/
      __init__.py
      armour.py
      bitstream.py
      cli.py
      codec.py
      framing.py
      lm.py
      quantizer.py
      range_coder.py
  scripts/
    generate_golden.py
    demo_roundtrip.sh
  tests/
    fixtures/
      model_v1.pkl
      golden_message_v1.txt
    test_armour.py
    test_codec.py
    test_framing.py
    test_golden.py
    test_quantizer.py
    test_range_coder.py
```

## 5. Test Plan

### Quantizer Tests

- Sum of frequencies is exactly `TOT`.
- Every active token has `freq >= 1`.
- CDF is monotonic and ends at `TOT`.
- Tie-breaking is deterministic.
- Repeated calls produce identical CDFs.

### Range Coder Tests

- Roundtrip synthetic symbol sequences through encode/decode.
- Test fixed distributions and changing per-symbol distributions.
- Test edge frequencies near `1` and `TOT - V + 1`.
- Test deterministic emitted bits for a known short sequence.

### Framing Tests

- Empty payload.
- One-byte payload.
- 256-byte payload.
- CRC mismatch on corrupted payload.
- Invalid magic.
- Truncated header.

### Armour Tests

- Valid block parses.
- Text outside markers is ignored.
- CRLF and CR normalize to LF.
- Fingerprint mismatch fails before decode.
- Invalid settings fail clearly.

### End-to-End Tests

Payload sizes:

- `0B`
- `1B`
- `16B`
- `1KB`
- `10KB`
- `bytes(range(256))`

Assertions:

- Decode output equals input exactly.
- Encode is deterministic across repeated runs.
- Corrupting one carrier character fails with CRC mismatch.

### Golden Regression

Golden V1 fixture:

```text
payload = bytes(range(256))
TOT = 65536
TOPK = 0
model = tests/fixtures/model_v1.pkl
message = tests/fixtures/golden_message_v1.txt
```

Golden test asserts:

- Model fingerprint equals expected hex digest.
- Canonicalized message SHA256 equals expected digest.
- Decoding golden message yields exact payload.
- Encoding the payload twice yields identical message text.

## 6. CLI Plan

Commands:

```bash
lmcodec train --data <path|alias> --out model.pkl
lmcodec encode --model model.pkl --in payload.bin --out message.txt --wrap 0
lmcodec decode --model model.pkl --in message.txt --out payload.bin
```

Encode should print:

- Payload bytes.
- Payload frame bytes.
- Carrier character count.
- Full armour character count.
- Bits per carrier character.
- Base64 length baseline.
- Model fingerprint.

Decode should print:

- Parsed version.
- Parsed settings.
- Payload bytes recovered.
- CRC status.
- Model fingerprint status.

## 7. Failure Messages

Use specific exception messages:

- `invalid armour block`
- `unsupported version`
- `invalid settings`
- `fingerprint mismatch`
- `invalid carrier token`
- `truncated message`
- `invalid payload magic`
- `CRC mismatch / corrupted message`

## 8. Milestones

### Milestone 1: Transport Kernel

- Bitstream utilities.
- Quantizer.
- Range coder.
- Unit tests for quantizer and range coder.

Status: implemented.

### Milestone 2: Toy Codec

- Fixed-distribution codec.
- Frame header and CRC.
- End-to-end roundtrip for small payloads.

Status: implemented with the 64-symbol uniform carrier.

### Milestone 3: Deterministic LM

- Character n-gram model.
- Model serialization.
- Model fingerprinting.
- Encode/decode with model-shaped distributions.

Status: partially implemented. The n-gram backend, JSON serialization, and
fingerprinting exist. Order-zero and flattened order-one trained models are
tested end-to-end. Heavily skewed higher-order models can still hit the
deterministic convergence limit, so `uniform_mix` is part of the model.

### Milestone 4: Armour and CLI

- BEGIN/END wrapper.
- Settings parsing.
- Newline normalization.
- CLI commands.

Status: implemented for the built-in carrier model.

### Milestone 5: Golden Regression

- Fixture model.
- Golden message.
- Golden generator.
- CI-friendly test suite.

Status: implemented for the built-in fixed carrier model.

### Milestone 6: Probability Shaping and Experiment Harness

- Shared probability shaping policy before quantization.
- Optional uniform mixing, temperature, probability floor, and entropy guard.
- Settings persisted through armour for deterministic decode.
- Reusable metric harness for fixed, n-gram, and future Transformer carriers.

Status: implemented.

### Milestone 7: Transformer Experiment

- MicroGPT-style character model.
- Deterministic CPU inference path.
- Compare carrier text quality and bits per character.

Status: first experimental backend implemented. It uses a deterministic causal
attention feature extractor with a trained output head, JSON serialization, and
model fingerprinting. Full end-to-end Transformer backprop remains future work.

### Milestone 8: Training and Quality Evaluation

- Report held-out negative log likelihood.
- Report per-step entropy and top-token concentration.
- Include deterministic preview text for model comparisons.
- Keep runtime dependency-free.
- Provide an optional PyTorch training/export path that emits the same JSON
  weights consumed by `TransformerLM`.
- Deterministic train/held-out corpus split utility.
- Deterministic synthetic corpus builder for larger carrier-corpus experiments.
- Held-out validation support in the optional PyTorch exporter.
- Shaping sweep utility that scores NLL, entropy, transport length, and encoded
  carrier diversity.
- Bounded held-out sweep mode for faster pure-Python iteration.
- Pure-Python Transformer runtime caches token-position attention projections
  to reduce repeated matrix work during trace evaluation and sweeps.
- Attention dot products use indexed loops to reduce iterator overhead while
  preserving deterministic accumulation order.

Status: implemented. PyTorch is optional and used only by
`scripts/train_transformer_torch.py`; exported Transformer JSON files can be
included in `scripts/compare_models.py` with `--transformer-model`. Current
corpus v2 is a deterministic 5000-line synthetic corpus with train and held-out
splits.

### Milestone 9: Pinned Transformer V1

- Transformer model fixture.
- Transformer golden message fixture.
- Golden test with pinned model fingerprint and message SHA256.
- Demo script for the pinned Transformer carrier and best current shaping
  settings.

Status: implemented. The V1 Transformer fixture uses
`SHAPE_UNIFORM_MIX=0.80` and `TEMPERATURE=1.25`.

### Milestone 10: Autoresearch Loop

- Karpathy `autoresearch`-style experiment loop for LMCodec.
- Agents propose bounded changes to corpus mix, model dimensions, training
  settings, and shaping settings.
- Each run trains or loads a model, evaluates held-out NLL, entropy,
  top-token concentration, convergence failures, codec roundtrip, and
  bits-per-character.
- Results are stored as JSON/CSV with enough metadata to reproduce the run.
- Only configurations that improve the composite score without breaking
  deterministic decode are promoted.

Status: planned for V2.

## 9. V1 Completion Status

V1 is a complete research prototype. The fixed carrier is the stable default,
and the n-gram and Transformer carriers are pinned experimental fixtures.

## 10. Open Decisions

- Whether V1 excludes newline from the carrier alphabet.
- Whether V1 supports `--wrap`; safest initial value is `--wrap 0`.
- Exact range coder implementation variant.
- Whether the first model is n-gram or Transformer.
- Whether SHA256 is included in V1 framing or deferred.

## 11. Definition of Done

- Arbitrary byte payloads roundtrip losslessly.
- Outputs are deterministic for identical input, model, and settings.
- Armour framing, CRC, and fingerprint checks are implemented.
- Golden vector regression is committed and passing.
- CLI supports file encode/decode.
- README contains quickstart, limitations, and golden values.
