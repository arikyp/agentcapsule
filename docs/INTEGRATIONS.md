# Integrations

This page shows practical integration patterns for agent frameworks.

Agent Capsule recommends one receiver path for all frameworks:

- Detect capsule/reference in inbound messages.
- Verify policy and hashes.
- Unpack to a sandbox.

Use the high-level API:

```python
from agentcapsule import ingest_messages

result = ingest_messages(
    messages=thread_messages,
    out_dir="./sandbox",
    policy="./policy.json",
)
```

Or the CLI equivalent:

```bash
agentcapsule ingest thread.txt --out ./sandbox --policy ./policy.json --json
```

For CI gates, fail on invalid/malformed ingestion:

```bash
agentcapsule ingest thread.txt --out ./sandbox --policy ./policy.json --json --strict
```

## LangGraph

Typical pattern: call `ingest_messages` inside the receiver node and store outputs in graph state.

```python
def receive_capsules(state: dict) -> dict:
    from agentcapsule import ingest_messages

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
    }
```

## CrewAI

Typical pattern:

1. Producer task emits either inline capsule text or a reference descriptor.
2. Consumer task runs `agentcapsule ingest ...` before using artifacts.
3. Consumer only reads unpacked files from sandbox output.

## LlamaIndex AgentWorkflow

Typical pattern: expose a receiver tool that runs ingestion and returns unpacked file paths.

```python
def ingest_handoff(messages: list[str]) -> list[str]:
    from agentcapsule import ingest_messages

    result = ingest_messages(messages=messages, out_dir="./sandbox", policy="./policy.json")
    return result.unpacked_files
```

## A2A / Generic Chat Systems

For systems that provide plain message transcripts:

```bash
agentcapsule ingest thread.txt --out ./sandbox --json
```

If you ingest reference descriptors (`capsule_uri`), install fetch support:

```bash
python3 -m pip install "agentcapsule[fetch]"
```

For safe receiver order and policy details, see [RECEIVER_GUIDE.md](RECEIVER_GUIDE.md).
