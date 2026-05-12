import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AgentCapsuleDesignDocsTests(unittest.TestCase):
    def test_ed25519_design_doc_exists_and_defers_implementation(self) -> None:
        text = (ROOT / "docs" / "AGENT_CAPSULE_ED25519_DESIGN.md").read_text(encoding="utf-8")

        self.assertIn("This document specifies the Ed25519", text)
        self.assertIn("The implementation is intentionally narrow", text)
        self.assertIn("signature: ed25519", text)
        self.assertIn("signature_public_key_fingerprint", text)
        self.assertIn("agentcapsule.signing.signed_bytes", text)
        self.assertIn("Keep core `agentcapsule` dependency-free", text)
        self.assertIn("Current Prototype Scope", text)

    def test_agent_capsule_docs_link_ed25519_design(self) -> None:
        for path in (
            ROOT / "README.md",
            ROOT / "docs" / "AGENT_CAPSULE_PROTOCOL_V0.md",
            ROOT / "docs" / "AGENT_CAPSULE_PRODUCT_BRIEF.md",
            ROOT / "docs" / "AGENT_CAPSULE_THREAT_MODEL.md",
        ):
            with self.subTest(path=path):
                self.assertIn("AGENT_CAPSULE_ED25519_DESIGN.md", path.read_text(encoding="utf-8"))

    def test_project_dependencies_remain_empty(self) -> None:
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(data["project"]["name"], "agentcapsule")
        self.assertEqual(data["project"]["dependencies"], [])
        self.assertEqual(data["project"]["optional-dependencies"]["signing"], ["cryptography>=46,<47"])
        self.assertEqual(data["project"]["scripts"]["agentcapsule"], "agentcapsule.cli:main")
        self.assertEqual(data["project"]["scripts"]["capsule"], "agentcapsule.cli:main")
        self.assertNotIn("lmcodec", data["project"]["scripts"])

    def test_audit_log_doc_is_linked(self) -> None:
        self.assertIn("AGENT_CAPSULE_AUDIT_LOG_V0.md", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn(
            "AGENT_CAPSULE_AUDIT_LOG_V0.md",
            (ROOT / "docs" / "AGENT_CAPSULE_PROTOCOL_V0.md").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
