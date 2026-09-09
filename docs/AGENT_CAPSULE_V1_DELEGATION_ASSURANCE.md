# Agent Capsule V1 — Delegation Assurance

Status: design foundation

Agent Capsule V1 reframes the project from a verifiable artifact envelope into a
portable delegation-assurance layer for agentic systems.

The V0 implementation remains valid and useful. V1 builds on its deterministic
manifest, integrity verification, receiver policy, safe unpacking, and audit
outputs. The change is primarily one of scope: integrity is one assurance signal,
not the definition of a trustworthy handoff.

## 1. Problem

Autonomous systems increasingly operate through delegated state transitions:

```text
human -> agent -> agent -> tool -> external system -> agent -> workflow
```

Each boundary requires the receiving component to decide whether it may safely
rely on what it has been given.

A silent failure occurs when an invalid transition is accepted as valid and the
workflow continues without detection before consequence.

```text
silent_failure = invalid_transition AND accepted_as_valid AND not_detected
```

An invalid transition may be:

- corrupted or tampered in transit;
- incomplete before packaging;
- semantically wrong despite being well formed;
- based on stale source state;
- outside delegated authority;
- executed partially while reported as complete;
- accepted from a tool/API that returned plausible success without the intended
  state change;
- impossible to reconstruct later because evidence or lineage was lost.

V0 is intentionally strong against transport corruption, tampering, malformed
payloads, and audit/replay ambiguity. V1 must make the remaining semantic,
state, authority, and completion risks explicit without pretending they can all
be cryptographically proven.

## 2. Product boundary

Agent Capsule V1 is an assurance layer, not a transport, identity provider,
policy engine, orchestration system, tracing system, or evaluation platform.

It should compose with existing layers:

- A2A: task and artifact transport;
- MCP: capability and tool invocation;
- OAuth/OIDC/SPIFFE or enterprise IAM: identity and authority;
- runtime policy/control middleware: intervention and enforcement;
- OpenTelemetry: traces, spans, metrics, and execution correlation;
- DSSE/in-toto/Sigstore or existing V0 signatures: artifact attestation;
- workflow engines: scheduling and orchestration;
- eval systems: statistical performance assessment.

Agent Capsule owns one question:

> What exactly is being delegated, what may the receiver rely on, under what
> authority and conditions, and what evidence is required before the intended
> outcome may be accepted as complete?

## 3. V1 primitives

V1 introduces two first-class logical objects.

### 3.1 Delegation Contract

The contract describes the state transition being delegated and the grounds on
which a receiver may accept it.

Illustrative shape:

```json
{
  "schema_version": "1.0",
  "capsule_type": "delegation_contract",
  "capsule_id": "cap_...",
  "parent_capsule_id": null,
  "issuer": {
    "id": "agent-a",
    "identity_ref": "spiffe://example/agent-a"
  },
  "intended_receiver": {
    "id": "agent-b"
  },
  "issued_at": "2026-09-09T00:00:00Z",
  "expires_at": null,
  "delegation": {
    "objective": "...",
    "scope": [],
    "authority_refs": [],
    "constraints": []
  },
  "source_state": [],
  "assertions": [],
  "preconditions": [],
  "payload": {
    "files": [],
    "references": []
  },
  "postconditions": [],
  "evidence_requirements": [],
  "lineage": {
    "task_id": "...",
    "trace_id": null,
    "parent_span_id": null
  }
}
```

### 3.2 Completion Receipt

A receipt records the evidence used to decide whether the delegated outcome
occurred.

Illustrative shape:

```json
{
  "schema_version": "1.0",
  "capsule_type": "completion_receipt",
  "receipt_id": "rcpt_...",
  "capsule_id": "cap_...",
  "executor": {
    "id": "agent-b",
    "identity_ref": "spiffe://example/agent-b"
  },
  "actions_performed": [],
  "evidence": [],
  "postcondition_results": [
    {
      "postcondition_id": "pc_1",
      "status": "unknown",
      "evidence_refs": []
    }
  ],
  "exceptions": [],
  "lineage": {
    "trace_id": null,
    "span_id": null
  },
  "completed_at": "2026-09-09T00:00:00Z"
}
```

Postcondition status MUST distinguish:

- `pass` — sufficient evidence establishes the condition;
- `fail` — evidence establishes that the condition did not hold;
- `unknown` — the system cannot establish either result.

`unknown` is not success. Receivers and policy layers decide whether an unknown
condition blocks, escalates, or permits continuation.

## 4. Assurance dimensions

V1 should expose assurance as separate dimensions rather than one overloaded
`verified` boolean.

| Dimension | Question |
|---|---|
| integrity | Did the object change after creation? |
| provenance | Which identity produced it, and is that identity trusted here? |
| completeness | Are all contract-required fields and assertions present? |
| freshness | Is the referenced source state still within its acceptable validity window/version? |
| authority | Is the delegated scope bound to an external authority decision/reference? |
| preconditions | Are conditions required before execution established? |
| outcome | Are postconditions established by acceptable evidence? |
| lineage | Can the handoff be correlated to its parent task/trace/delegation? |

A receiver report should be able to return different results for each dimension.
For example, a handoff can have `integrity=pass`, `provenance=pass`, and
`freshness=unknown`.

## 5. Evidence model

V1 does not claim to prove arbitrary semantic truth. It defines evidence that a
receiver can validate deterministically or delegate to an external verifier.

Candidate evidence classes:

- immutable artifact hash/version;
- system-of-record resource version or ETag;
- API response plus resource re-read;
- test or validation result;
- database/object identifier and state observation;
- signed attestation;
- policy decision reference;
- OpenTelemetry trace/span reference;
- human approval/decision reference;
- external verifier result.

Evidence entries should contain stable type identifiers and optional verifier
bindings. The protocol should avoid embedding vendor-specific policy or tracing
implementations into the core schema.

## 6. Failure taxonomy and expected coverage

| Failure class | V0 | V1 target |
|---|---|---|
| transport corruption | strong | strong |
| tampering / wrong signer | strong when configured | strong |
| malformed payload | strong | strong |
| missing required handoff state | weak | deterministic contract completeness |
| semantic wrong value | none | evidence-dependent; never imply solved |
| stale source state | none | freshness/version requirements |
| scope / authority mismatch | partial hints | explicit authority binding + policy check |
| tool/API false success | none | completion evidence/postcondition verification |
| partial execution | none | postcondition-by-postcondition status |
| audit/replay ambiguity | strong | strong + lineage |

## 7. Compatibility strategy

V1 should not replace V0 transport modes.

The existing text envelope, attachment mode, and reference descriptor remain
serialisation/delivery options. The V1 contract and receipt should also be usable
as ordinary JSON objects in structured transports.

Bindings should be thin:

```text
A2A Artifact -> Delegation Contract / Completion Receipt
MCP structuredContent -> Delegation Contract / Completion Receipt
text/email/ticket -> existing Agent Capsule envelope carrying V1 object
object storage -> reference descriptor + content identity
```

The canonical semantics must not depend on Base64, a specific agent framework,
or a specific transport.

## 8. Explicit non-goals

V1 core MUST NOT become:

- a hosted global identity or trust registry;
- a replacement for OAuth/OIDC/SPIFFE/IAM;
- a general agent firewall or runtime policy engine;
- an orchestration framework;
- an agent discovery/marketplace protocol;
- a proprietary tracing backend;
- a SIEM or DLP product;
- a generic model-evaluation framework;
- a claim that cryptographic verification implies semantic correctness.

Integrations may reference or emit evidence for those systems, but core semantics
remain portable.

## 9. Receiver decision model

The receiver remains the trust boundary.

Recommended order:

```text
detect
-> parse
-> integrity / provenance
-> contract completeness
-> authority / policy
-> freshness / preconditions
-> expose payload
-> execute
-> collect evidence
-> evaluate postconditions
-> emit receipt
-> allow / review / block / escalate
```

The V0 `allow/review/block` disposition can remain as an orchestration-friendly
summary, but V1 should always expose the underlying dimension results and reason
codes.

## 10. First implementation slice

The first code increment should be deliberately small and backward compatible.

1. Add typed validation helpers for a V1 delegation contract and completion
   receipt without changing the V0 manifest format.
2. Add stable reason codes for missing required contract fields and invalid
   postcondition statuses.
3. Add canonical JSON encoding for both object types.
4. Add unit tests for deterministic serialisation and strict validation.
5. Add a single demo showing:
   - a valid delegation;
   - a handoff rejected for a missing required condition;
   - an execution whose postcondition remains `unknown`, proving that unknown is
     not silently converted to success.
6. Only after those semantics are stable, decide how V1 maps into the existing
   envelope and receiver APIs.

## 11. Evaluation target

The headline V1 research metric should be silent failure rate rather than
payload reproduction accuracy.

```text
silent_failure_rate =
  P(wrong_downstream_state AND no_block_or_escalation)
```

Compare at minimum:

1. natural-language handoff;
2. JSON Schema / structured handoff;
3. native A2A/MCP structured artifact;
4. Agent Capsule V0;
5. V1 delegation contract;
6. V1 delegation contract + completion receipt.

Inject omissions, stale state, corruption, authority mismatch, partial
execution, false-success API/tool responses, and unverifiable outcomes.

Secondary measures: false blocks, escalation rate, recovery rate, latency,
payload size, and token overhead.

## 12. Design rule

Every V1 feature must answer:

> Does this help a receiver determine whether it may safely rely on a
> consequential delegation or claimed outcome?

If not, it probably does not belong in Agent Capsule core.
