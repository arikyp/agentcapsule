import json
import unittest

from agentcapsule.assurance import canonical_json, validate_completion_receipt, validate_delegation_contract
from agentcapsule.errors import CapsuleParseError


class DelegationAssuranceTests(unittest.TestCase):
    def contract(self):
        return {
            "schema_version": "1.0",
            "capsule_type": "delegation_contract",
            "capsule_id": "cap_123",
            "issuer": {"id": "agent-a", "identity_ref": "spiffe://example/agent-a"},
            "intended_receiver": {"id": "agent-b"},
            "issued_at": "2026-09-09T00:00:00Z",
            "delegation": {
                "objective": "Create shipment",
                "scope": ["shipment:create"],
                "authority_refs": ["authz://decision/42"],
                "constraints": ["service=express"],
            },
            "source_state": [],
            "assertions": [],
            "preconditions": [{"id": "pre_1", "type": "state", "required": True}],
            "payload": {"files": [], "references": []},
            "postconditions": [{"id": "pc_1", "type": "state", "required": True}],
            "evidence_requirements": [{"postcondition_id": "pc_1", "type": "resource_read"}],
            "lineage": {"task_id": "task_123", "trace_id": None, "parent_span_id": None},
        }

    def receipt(self):
        return {
            "schema_version": "1.0",
            "capsule_type": "completion_receipt",
            "receipt_id": "rcpt_123",
            "capsule_id": "cap_123",
            "executor": {"id": "agent-b"},
            "actions_performed": ["create_shipment"],
            "evidence": [],
            "postcondition_results": [
                {"postcondition_id": "pc_1", "status": "unknown", "evidence_refs": []}
            ],
            "exceptions": [],
            "lineage": {"trace_id": None, "span_id": None},
            "completed_at": "2026-09-09T00:01:00Z",
        }

    def test_valid_contract(self):
        validate_delegation_contract(self.contract())

    def test_missing_required_contract_field_is_rejected(self):
        value = self.contract()
        del value["preconditions"]
        with self.assertRaisesRegex(CapsuleParseError, "missing delegation contract fields: preconditions"):
            validate_delegation_contract(value)

    def test_unknown_is_valid_receipt_status(self):
        validate_completion_receipt(self.receipt())

    def test_success_alias_is_rejected(self):
        value = self.receipt()
        value["postcondition_results"][0]["status"] = "success"
        with self.assertRaisesRegex(CapsuleParseError, "pass, fail, or unknown"):
            validate_completion_receipt(value)

    def test_canonical_json_is_deterministic(self):
        first = canonical_json(self.contract())
        second = canonical_json(json.loads(first))
        self.assertEqual(first, second)
        self.assertLess(first.index('"capsule_id"'), first.index('"capsule_type"'))


if __name__ == "__main__":
    unittest.main()
