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

## pipx Install

For a user-local install on machines where you do not want to manage a project
virtual environment:

```bash
python3 -m pip install --user pipx
pipx ensurepath
pipx install .
```

If the project is published to PyPI, the same flow becomes:

```bash
pipx install agentcapsule
```

This is the intended public developer install path after the first PyPI
release.

## What To Verify After Install

```bash
agentcapsule --help
agentcapsule pack --help
agentcapsule inspect --help
agentcapsule verify --help
```

The default path should be Base64 capsule packing and unpacking. Experimental
research backends are not part of the primary install story.
