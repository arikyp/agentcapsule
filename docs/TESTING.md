# Testing

LMCodec V1 relies on deterministic tests because the transport kernel is meant
to produce identical text for identical payload, model, and settings.

The stress tests use fixed pseudo-random seeds from the Python standard library.
They cover:

- Random payload roundtrips across empty, small, boundary, and multi-kilobyte payloads.
- Exact deterministic encode output for repeated calls.
- Single carrier-character mutation detection.
- Quantizer invariants for uniform, dominant-token, near-zero, invalid-float, and all-zero distributions.
- Range-coder roundtrips for fixed, changing, random, and highly skewed CDFs.

These tests intentionally do not use Hypothesis or external dependencies. If a
future property-test dependency is added, keep the current fixed-seed tests as
the stable regression baseline.

Known edge cases represented in the tests:

- Non-finite, negative, and zero probabilities are cleaned before quantization.
- All-zero probability input falls back to a uniform distribution.
- Every quantized token remains active with frequency at least one.
- Extremely skewed CDFs such as `(0, 1, 65536)` remain valid for range-coder roundtrip tests.
