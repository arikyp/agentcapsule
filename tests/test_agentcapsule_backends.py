import json
import tempfile
import unittest
from pathlib import Path

from agentcapsule.backends import get_backend
from agentcapsule.errors import CapsuleUnpackError
from agentcapsule.manifest import pack_directory, unpack_bundle


class AgentCapsuleBackendTests(unittest.TestCase):
    def test_base64_roundtrip(self) -> None:
        payload = bytes(range(64))
        backend = get_backend("base64")

        self.assertEqual(backend.decode(backend.encode(payload)), payload)

    def test_lmcodec_fixed_roundtrip(self) -> None:
        payload = b"lmcodec fixed backend payload"
        backend = get_backend("lmcodec-fixed")

        self.assertEqual(backend.decode(backend.encode(payload)), payload)

    def test_directory_bundle_deterministic_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "b.txt").write_text("b", encoding="utf-8")
            (root / "dir").mkdir()
            (root / "dir" / "a.txt").write_text("a", encoding="utf-8")

            first = pack_directory(root)
            second = pack_directory(root)
            manifest = json.loads(first.decode("utf-8"))

            self.assertEqual(first, second)
            self.assertEqual([entry["path"] for entry in manifest["files"]], ["b.txt", "dir/a.txt"])

    def test_path_traversal_blocked_on_unpack(self) -> None:
        bundle = {
            "format": "agent-capsule-bundle-v0",
            "files": [
                {
                    "path": "../escape.txt",
                    "size": 0,
                    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "content_base64": "",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(CapsuleUnpackError, "unsafe bundle path"):
                unpack_bundle(json.dumps(bundle).encode("utf-8"), Path(tmp))


if __name__ == "__main__":
    unittest.main()
