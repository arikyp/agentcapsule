# LMCodec Algorithm

LMCodec is a deterministic byte-to-text transport codec. It turns arbitrary
bytes into carrier text, then reconstructs the original bytes exactly.

The core idea is split into two parts:

- A language model supplies a probability distribution over the next carrier
  token.
- A range coder supplies the reversible mapping between payload bits and token
  choices.

The language model decides what token probabilities are allowed at each step.
The payload bits decide which token is selected inside that distribution.

```text
payload bytes -> framed bits -> range decoder -> token choices -> carrier text
                                      ^                 |
                                      |                 v
                                 LM probabilities <- LM state
```

## What LMCodec Is Not

LMCodec V1 is not encryption. The armour is plain text, and anyone with the
same model and settings can decode it.

It is not compression-first. A good language model may eventually improve the
shape of the carrier text, but V1 prioritizes deterministic, lossless
roundtrip correctness over size.

It is not currently natural prose generation. The fixed carrier is deliberately
simple, and the n-gram and Transformer carriers are experimental.

It is not steganography-grade secrecy. It can produce text-shaped transport
data, but V1 does not claim that the output hides the existence of a payload
from a motivated observer.

## Encoding Flow

Encoding starts with raw payload bytes.

```text
payload
  -> frame
  -> bits
  -> source RangeDecoder
  -> LM-guided token stream
  -> armour
```

The frame adds enough structure to know when decode has recovered the payload:

```text
magic        4 bytes  b"LMC1"
payload_len 4 bytes  uint32 little endian
crc32        4 bytes  uint32 little endian over raw payload
payload      N bytes
```

The framed bytes are converted to canonical bits. Those bits back a source
`RangeDecoder` with deterministic zero padding after EOF. At each step, the
encoder does the following:

1. Ask the model for probabilities using the current LM state.
2. Apply probability shaping settings.
3. Quantize the shaped probabilities into an integer CDF.
4. Pop one symbol from the source `RangeDecoder` using that CDF.
5. Convert the symbol id to a carrier token.
6. Push the same symbol and CDF into a mirror `RangeEncoder`.
7. Advance the LM state with the selected token.
8. Stop only when the mirror encoder can prove the framed payload bits are a
   prefix of the finalized arithmetic stream.

Pseudo-code:

```python
frame = build_frame(payload)
target_bits = bytes_to_bits(frame)
source = RangeDecoder(target_bits, eof_pad_bit=0)
mirror = RangeEncoder()
state = model.init_state()
tokens = []

while not has_prefix(mirror.preview_finish(), target_bits):
    probs = model.step_probs(state)
    shaped = shape_probabilities(probs, settings.shape)
    cdf = quantize(shaped, total=settings.total).cdf

    token_id = source.pop_symbol(cdf)
    tokens.append(model.id_to_token(token_id))

    mirror.push_symbol(cdf, token_id)
    assert mirror.bits is still compatible with target_bits

    model.advance(state, token_id)

message = make_armour(tokens, model.fingerprint, settings)
```

The source range decoder is unusual at first glance: it reads the payload bits
as if they were an arithmetic-coded stream, and the LM distributions determine
which token sequence those bits correspond to. The mirror encoder confirms that
the generated token sequence maps back to the original framed bits.

## Decoding Flow

Decoding runs the inverse direction over the carrier text.

```text
armour
  -> parsed carrier text and settings
  -> model fingerprint check
  -> LM-guided RangeEncoder
  -> reconstructed bits
  -> frame parser
  -> payload
```

The decoder first parses the copy/paste armour, normalizes line endings, reads
the settings, and checks the model fingerprint. Text outside the armour markers
is ignored.

For each carrier token:

1. Convert the token to its model token id.
2. Ask the same model state for probabilities.
3. Apply the same probability shaping settings from the armour.
4. Quantize with the same deterministic quantizer.
5. Push the observed token id into a `RangeEncoder`.
6. Advance the LM state in exactly the same way encode did.
7. Try to parse a complete frame from emitted bits.

Pseudo-code:

```python
block = parse_armour(message)
if block.model_fingerprint != model.fingerprint:
    raise LMCodecError("fingerprint mismatch")

settings = CodecSettings.from_header(block.settings)
state = model.init_state()
encoder = RangeEncoder()

for token in block.payload_text:
    token_id = model.token_to_id(token)

    probs = model.step_probs(state)
    shaped = shape_probabilities(probs, settings.shape)
    cdf = quantize(shaped, total=settings.total).cdf

    encoder.push_symbol(cdf, token_id)
    model.advance(state, token_id)

    payload = try_parse_frame_bits(encoder.bits)
    if payload is not None:
        return payload

payload = try_parse_frame_bits(encoder.finish())
if payload is not None:
    return payload

raise LMCodecError("truncated message")
```

The frame parser validates the magic, waits until `payload_len` bytes are
available, then checks the CRC32. A mutation that changes decoded payload bits
should fail as invalid framing, truncation, invalid token, fingerprint mismatch,
or CRC mismatch.

## Why Model Fingerprinting Matters

The same carrier token sequence only decodes correctly under the same model and
settings used during encode. If the vocabulary order, probabilities, training
data, model parameters, or serialization change, the per-step CDFs can change.
Once a CDF changes, the arithmetic stream maps to different bits.

The model fingerprint is stored in the armour so decode can fail early instead
of returning nonsense or reporting a misleading corruption error.

## Why Deterministic Quantization Matters

Range coding needs integer cumulative distributions. Language models usually
produce floating-point probabilities. LMCodec bridges that gap with a
deterministic quantizer:

- Frequencies sum exactly to `65536`.
- Every active token receives at least one count.
- The CDF starts at zero and ends at `65536`.
- Tie-breaking is stable by token id.
- Invalid or all-zero probability inputs are cleaned into usable distributions.

Encode and decode must produce exactly the same CDF at every token position.
Even a one-count difference can desynchronize the arithmetic stream.

## Why The Stopping Condition Is Subtle

A naive encoder might try to stop when the source range decoder has consumed
all payload bits. That is unsafe.

Range decoders maintain lookahead state. They may read bits before those bits
are fully committed by the inverse encoder. EOF padding also means the source
decoder can keep producing symbols after the real framed bits are exhausted.

LMCodec therefore uses a mirror `RangeEncoder` while generating carrier tokens.
After each token, it asks what bits the mirror would emit if finalized. Encode
stops only when that finalized preview has the target framed bits as a prefix.

```text
target framed bits: 101100...

tokens so far
  -> mirror RangeEncoder
  -> preview_finish()
  -> emitted bits begin with target framed bits
  -> safe to stop
```

This makes stopping depend on the inverse mapping, not on an internal read
position in the source decoder.

## Why Probability Shaping Exists

Real model distributions can be too sharp for transport. If one token receives
nearly all probability mass, the arithmetic coder may need many symbols to
carry a small amount of payload information. Very low entropy can also make
encode convergence harder.

Probability shaping is a deterministic guardrail layer before quantization. It
can mix the model distribution toward uniform, apply temperature, enforce a
minimum probability floor, and optionally reject distributions below an entropy
threshold.

The shaping settings are written into the armour. Decode reads them back and
replays the same shaping before quantization.

## V1 Limitations

- V1 is a research prototype.
- The fixed 64-symbol carrier is stable but not natural-looking.
- The n-gram and Transformer carriers are pinned experimental fixtures.
- CRC32 detects corruption but is not a cryptographic integrity check.
- The frame does not embed a SHA256 payload digest.
- Pure-Python Transformer inference is intended for demos and small
  experiments, not large-scale generation.
- V1 has not been stress-tested as a large-file archival format.
- Carrier text quality is limited by the current model and corpus choices.

## V2 Research Path

Useful V2 work should preserve the V1 correctness contract while improving the
carrier model and evaluation loop:

- Better carrier corpora with held-out quality evaluation.
- Larger or better-trained deterministic Transformer carriers.
- Faster runtime inference for model-shaped distributions.
- Stronger frame integrity through an explicit frame version.
- Experiment sweeps that track held-out NLL, entropy, convergence failures,
  roundtrip correctness, and bits per carrier character.
- Autoresearch-style loops that propose bounded model, corpus, and shaping
  changes, then promote only reproducible improvements.
