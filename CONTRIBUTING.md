# Contributing

Thanks for helping improve Agent Capsule.

## Before You Start

- Read [docs/ROADMAP.md](docs/ROADMAP.md) to see the current priorities.
- Check [docs/README.md](docs/README.md) for the public docs surface.
- Run the test suite before opening a pull request.

## Working Rules

- Keep changes small and reviewable.
- Prefer changes that improve verifiability, trust, and installability.
- Add or update tests when behavior changes.
- Avoid unrelated refactors in the same pull request.

## Local Checks

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
sh scripts/release_check.sh
```

## Pull Requests

- Describe the problem being solved.
- Link the related issue or roadmap item when applicable.
- Call out any behavior changes, docs changes, or release impact.
