# Agent Capsule Install

Agent Capsule is distributed as a standard Python package.

## Recommended Local Install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

This exposes:

- `agentcapsule`: primary product CLI
- `capsule`: short alias for `agentcapsule`

## PyPI Install

For script and framework usage without cloning this repository:

```bash
python3 -m pip install agentcapsule
```

Then verify:

```bash
agentcapsule --help
agentcapsule pack --help
agentcapsule verify --help
```

If receivers need to fetch reference capsules from `capsule_uri`, install fetch extras:

```bash
python3 -m pip install "agentcapsule[fetch]"
```

Optional experimental extras:

- `agentcapsule[signing]`: Ed25519 signing + AES-256-GCM encryption support via `cryptography`.
- `agentcapsule[compression]`: Zstandard compression support.
- `agentcapsule[fetch]`: reference capsule fetching support via `httpx`.
- `agentcapsule[all]`: installs all optional extras in one step.

```bash
python3 -m pip install "agentcapsule[all]"
```

## pipx Install

For a user-local install on machines where you do not want to manage a project
virtual environment:

```bash
python3 -m pip install --user pipx
pipx ensurepath
pipx install .
```

Using PyPI directly:

```bash
pipx install agentcapsule
```

## What To Verify After Install

```bash
agentcapsule --help
agentcapsule pack --help
agentcapsule inspect --help
agentcapsule verify --help
```

The default path should be Base64 capsule packing and unpacking.
