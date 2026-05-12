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

## PyPI Publishing Checklist

- Confirm the package name is `agentcapsule`.
- Confirm the console entry points are `agentcapsule` and `capsule`.
- Confirm the wheel installs cleanly on Python 3.11, 3.12, and 3.13.
- Confirm the README renders on the package page.
- Confirm the published metadata does not advertise experimental backends as
  part of the main install.
- Confirm the license file is committed before the first public upload.

## Binary Distribution Plan

Binary distribution should use GitHub Releases as the primary download channel.
That keeps the source package and any build outputs tied to the same reviewed
tag.

Candidate artifacts:

- source tarball
- wheel files
- platform-specific command-line bundles, if they are added later
- checksum manifest for downloaded artifacts

The binary release format is intentionally separate from the protocol format.
Agent Capsule is a transport artifact; the release bundle is just one way to
install or distribute the CLI.

## License Decision

This repository currently has no declared public license. Before public launch,
choose and commit one license file so the package terms are explicit.

Recommended choices:

- `Apache-2.0` if patent grant and conservative enterprise posture matter most
- `MIT` if the project wants the shortest common permissive license

Until a license is committed, the repository should be treated as all rights
reserved outside the owner’s intended context.
