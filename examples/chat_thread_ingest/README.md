# Chat Thread Ingest

Ingest a text transcript and unpack all verified capsules into an isolated directory.

```bash
agentcapsule ingest thread.txt --out ./sandbox --policy ../../examples/agent_capsule_demo/policy-strict.json --json
```

Python equivalent:

```python
from pathlib import Path
from agentcapsule import ingest_messages

result = ingest_messages(
    messages=[Path("thread.txt").read_text(encoding="utf-8")],
    out_dir="./sandbox",
)

print(result.unpacked_files)
```
