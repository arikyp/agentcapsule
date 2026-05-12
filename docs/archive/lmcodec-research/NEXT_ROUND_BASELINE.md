# Next Round Baseline

Date: 2026-05-05

## Current Repo Status

- Repository: `/home/ubuntu/code/lmcodec`
- Branch: `main`
- Upstream: `origin/main`
- Baseline state before this document: clean working tree
- Behaviour changes: none
- Generated artifacts: editable install used local `.venv`; generated install metadata is ignored by git

## Commands Run

```bash
python3 -m pip install -e .
```

Result: failed because the system Python environment is externally managed by
PEP 668.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
sh scripts/verify_v1.sh
.venv/bin/python -m compileall src scripts tests
```

## Pass/Fail Summary

- Editable install: passed in local `.venv`
- Unit tests: passed, 43 tests
- V1 verification: passed
- Compile check: passed
- Existing golden fixtures: passed
  - Fixed carrier SHA256: `f53ec3604a378788b20cf6e0aadbfe441a063aa7ce1cea0bef9b1427cbd21e35`
  - Order-1 n-gram carrier SHA256: `53c062a238764c72caa9dd338d37682ab350d7ace4251e9778ba13ae97d99512`
  - Transformer carrier SHA256: `7713a0b7208462485f854ab58e5423f16c16360aeff524f1597ba49c840ad96b`

## Known Limitations

- V1 is a research prototype, not a production privacy, compression, or steganography tool.
- The fixed carrier is stable but not natural-looking text.
- The n-gram and Transformer carriers are deterministic and pinned, but experimental.
- Carrier text is selected by payload bits through the range coder; greedy previews do not represent encoded output.
- Payload framing uses CRC32 for corruption detection, not an embedded SHA256 digest.
- V1 is not yet stress-tested as a large-file archival format.
- Pure-Python Transformer inference is suitable for demos and small experiments, but is slow for larger models.

## Recommended Next Steps

- Keep fixed, n-gram, and Transformer golden tests as the first regression gate for any change.
- Preserve the current frame, armour, quantizer, and range-coder behaviour unless intentionally versioning a new format.
- For V2 work, focus on better carrier corpora, stronger Transformer training, faster runtime inference, and a reproducible experiment loop.
- If stronger payload integrity is added, introduce it through an explicit frame version instead of changing V1 semantics.
