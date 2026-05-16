# Testing

The Agent Capsule suite focuses on deterministic envelope, verification, policy,
fetch, scan, and unpack behavior.

GitHub Actions runs this verification path on pull requests and pushes to
`main` across Python 3.11, 3.12, and 3.13:

```bash
python3 -m pip install -e .
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall src scripts tests
sh scripts/release_check.sh
```

For optional experimental extras (`signing`, `compression`, `fetch`), run the
same path with `agentcapsule[all]`:

```bash
python3 -m pip install -e ".[all]"
PYTHONPATH=src python3 -m unittest discover -s tests
sh scripts/release_check.sh
```

Any test or demo path that exercises Ed25519 signing or registry-trusted
verification must install the optional signing extra first:

```bash
python3 -m pip install -e ".[signing]"
```

Core protocol and integration coverage is validated by the unit suite and
`scripts/release_check.sh`.
