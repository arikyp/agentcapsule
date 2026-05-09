# Governance Examples

This folder contains small inputs for demonstrating Agent Capsule governance
states:

- unsigned capsule: integrity checked by SHA256, but no sender authenticity
- signed capsule: HMAC-SHA256 checked with a shared secret
- tampered capsule: metadata or payload changed after signing

Run:

```sh
sh scripts/demo_agent_capsule_governance.sh
```

The script writes temporary capsules, scans them with observe and strict
policies, and verifies that the tampered capsule is rejected.
