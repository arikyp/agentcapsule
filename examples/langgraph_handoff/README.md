# LangGraph Handoff Receiver

Use `ingest_messages` inside your LangGraph node that handles inbound thread state.

```python
from agentcapsule import ingest_messages


def receive_capsules(state: dict) -> dict:
    result = ingest_messages(
        messages=state.get("messages", []),
        out_dir="./sandbox",
        policy="./policy.json",
    )
    return {
        **state,
        "capsule_unpacked_files": result.unpacked_files,
        "capsule_inline": result.inline_capsules,
        "capsule_references": result.references,
        "capsule_malformed_blocks": result.malformed_blocks,
    }
```
