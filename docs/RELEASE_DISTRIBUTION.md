# Agent Capsule Release Distribution

This document tracks the public launch path for Agent Capsule.

## Distribution Plan

1. Build and test from source in CI.
2. Publish source releases through GitHub Releases.
3. Optionally attach binary artifacts for users who do not want to install
   from source.
4. Publish the Python package to PyPI once the release process is stable.

## GitHub Release Plan

- Tag the release from a reviewed commit on `main`.
- Attach source archives generated from the release tag.
- Attach any binary bundles or checksum files that are produced by the build
  pipeline.
- Link back to the changelog, install docs, and protocol docs.

Current automation:

- `.github/workflows/release-artifacts.yml` builds `sdist`, `wheel`, and
  `SHA256SUMS.txt` on `v*` tags and uploads them to GitHub Releases.
- `scripts/build_release_artifacts.sh` is the shared local/CI build entrypoint.

## PyPI Publishing Checklist

- Confirm the package name is `agentcapsule`.
- Confirm the console entry points are `agentcapsule` and `capsule`.
- Confirm the wheel installs cleanly on Python 3.11, 3.12, and 3.13.
- Confirm the README renders on the package page.
- Confirm the published metadata does not advertise experimental backends as
  part of the main install.
- Confirm the license file is committed before the first public upload.

Current automation:

- `.github/workflows/pypi-publish.yml` builds distributions and publishes on
  `v*` tags with `pypa/gh-action-pypi-publish` using GitHub OIDC trusted
  publishing.
- Configure a PyPI trusted publisher for this repository before cutting public
  release tags.

## Binary Distribution Plan

Binary distribution should use GitHub Releases as the primary download channel.
That keeps the source package and any build outputs tied to the same reviewed
tag.

Candidate artifacts:

- source tarball
- wheel files
- platform-specific command-line bundles for `agentcapsule` and `capsule`, if
  added later
- checksum manifest for downloaded artifacts

Recommended binary packaging phases:

1. Phase 1 (now): publish `sdist` + `wheel` + checksums.
2. Phase 2: add platform bundles via PyInstaller or equivalent for
   Linux/macOS/Windows, then attach to GitHub Releases.
3. Phase 3: add signing/attestation metadata for release artifacts.

The binary release format is intentionally separate from the protocol format.
Agent Capsule is a transport artifact; the release bundle is just one way to
install or distribute the CLI.

## License

The repository is licensed under Apache-2.0. See `LICENSE`.
