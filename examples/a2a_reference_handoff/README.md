# A2A Reference Handoff

This example shows a receiving agent ingesting a mixed thread with inline and reference capsules.

```python
from pathlib import Path
from agentcapsule import ingest_messages

thread_messages = [Path("thread.txt").read_text(encoding="utf-8")]

result = ingest_messages(
    messages=thread_messages,
    out_dir="./sandbox",
    policy="../../examples/agent_capsule_demo/policy-strict.json",
)

print(result.inline_capsules)
print(result.references)
print(result.unpacked_files)
```

CLI equivalent:

```bash
agentcapsule ingest thread.txt --out ./sandbox --json
```
