# Agent Capsule Framework Integrations

Agent Capsule provides plug-and-play helpers for major multi-agent frameworks. These integrations ensure that artifacts are passed between agents with byte-perfect fidelity, encryption, and compression.

## 🦜 LangGraph

LangGraph handoffs often happen by updating the shared `messages` state. `LangGraphIntegration` helps you pack artifacts into a system message that the next node can easily consume.

### Handoff Pattern (Sender)

```python
from agentcapsule.integrations import LangGraphIntegration

def research_node(state):
    # Perform work, save to a directory
    # ...
    
    # Pack the directory into a secure handoff message
    return LangGraphIntegration.create_handoff_message(
        path="./research_data",
        created_by="researcher",
        encryption_key=os.environ["CAPSULE_KEY"]
    )
```

### Unpack Pattern (Receiver)

```python
from agentcapsule.integrations import LangGraphIntegration

def write_node(state):
    # The last message contains the capsule
    capsule_text = state["messages"][-1].content
    
    # Unpack into a sandbox
    LangGraphIntegration.unpack_handoff(
        message_content=capsule_text,
        out_dir="./sandbox/writer",
        encryption_key=os.environ["CAPSULE_KEY"]
    )
    
    # Now use the files
    # ...
```

## 👥 CrewAI

CrewAI agents collaborate via tasks. Use Agent Capsule to ensure that `expected_output` from one task is reliably delivered to the next agent's `context`.

### Pattern

1. Use `output_json` or `output_pydantic` in your `Task`.
2. In the `expected_output`, specify that the agent should wrap results in an Agent Capsule if they exceed a certain size or contain binary data.
3. The next agent uses the `agentcapsule` CLI or SDK to unpack.

## 🦙 LlamaIndex (AgentWorkflow)

LlamaIndex `AgentWorkflow` uses autonomous handoffs.

### Pattern

Inject a tool called `prepare_handoff_capsule` that the agents can call when they want to transfer a complex artifact.

```python
def prepare_handoff_capsule(directory_path: str) -> str:
    """Useful for preparing a secure, compressed Agent Capsule for handoff."""
    # (Implementation using agentcapsule.integrations)
    return capsule_text
```

## 🤖 AutoGen

In AutoGen, use the `AgentCapsuleMessenger` (coming soon) to intercept messages and automatically wrap binary/large data.

---

### Custom Integrations

To build your own integration, use the `agentcapsule.envelope` and `agentcapsule.manifest` modules directly.

```python
from agentcapsule.envelope import build_envelope, render_envelope
from agentcapsule.manifest import pack_path_with_manifest

# Lower-level packing
packed = pack_path_with_manifest("./data")
envelope = build_envelope(packed.payload, ...)
capsule_text = render_envelope(envelope)
```
