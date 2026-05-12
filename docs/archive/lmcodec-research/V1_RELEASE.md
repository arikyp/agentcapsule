# LMCodec V1 Release Notes

LMCodec V1 is a research prototype for deterministic, lossless byte transport
through copy/paste-safe text.

## Status

V1 is complete as a reproducible checkpoint.

- Fixed carrier is the stable default.
- Order-1 n-gram carrier is pinned as an experimental fixture.
- Transformer carrier is pinned as an experimental fixture.
- Training and sweep tooling are available for V2 work, but are not required to
  use or verify V1.

## Verification

Run the full V1 verification suite:

```bash
sh scripts/verify_v1.sh
```

The script regenerates golden messages, runs fixed/n-gram/Transformer demos,
runs the unit suite, and compile-checks Python modules and scripts.

## Pinned Artifacts

Fixed carrier:

- Message fixture: `tests/fixtures/golden_message_v1.txt`
- Model fingerprint:
  `d60583f4d741e42cb713b11c78b8ffc89cda1ee05eca522929bec8cbdb423be8`
- Message SHA256:
  `f53ec3604a378788b20cf6e0aadbfe441a063aa7ce1cea0bef9b1427cbd21e35`

Order-1 n-gram carrier:

- Model fixture: `tests/fixtures/ngram_model_v1.json`
- Message fixture: `tests/fixtures/ngram_golden_message_v1.txt`
- Model fingerprint:
  `b1cd62a9019b67e0a42913dac1dca09852b4931f09afa87bb8e62089fe184a3a`
- Message SHA256:
  `53c062a238764c72caa9dd338d37682ab350d7ace4251e9778ba13ae97d99512`

Transformer carrier:

- Model fixture: `tests/fixtures/transformer_model_v1.json`
- Message fixture: `tests/fixtures/transformer_golden_message_v1.txt`
- Settings: `SHAPE_UNIFORM_MIX=0.80; TEMPERATURE=1.25`
- Model fingerprint:
  `cfc75d7b54524f7a09a90454d89768aa4eb75b17546607c376760e2fc9d8f851`
- Message SHA256:
  `7713a0b7208462485f854ab58e5423f16c16360aeff524f1597ba49c840ad96b`

Payload for all golden fixtures:

- Payload: `bytes(range(256))`
- Payload SHA256:
  `40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880`

## Transformer Fixture Metrics

For `bytes(range(256))` with the pinned Transformer fixture and settings:

- Payload bytes: `256`
- Carrier chars: `362`
- Bits per carrier char: `5.923`
- Base64 baseline chars: `344`

## Known Limits

- The fixed carrier is reliable but not natural-looking text.
- The Transformer carrier is deterministic and reproducible, but still
  experimental.
- Greedy previews are not representative of encoded carrier text because
  LMCodec carrier text is selected by payload bits through the range coder.
- V1 uses CRC32 for payload integrity, not SHA256 inside the frame.
- V1 does not optimize for compression ratio.

## V2 Boundary

The following belong in V2:

- Better natural-language carrier corpora.
- Larger or better-trained Transformer models.
- Faster pure-Python Transformer inference beyond the current projection caches.
- Autoresearch-style experiment loops.
- Stronger payload integrity framing if a new frame version is introduced.
