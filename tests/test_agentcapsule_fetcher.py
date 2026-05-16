import socket
import sys
import types
import unittest
from unittest.mock import patch

from agentcapsule.errors import CapsuleVerificationError
from agentcapsule.fetcher import _validate_fetch_uri, _validate_limits, fetch_capsule


class AgentCapsuleFetcherTests(unittest.TestCase):
    def test_rejects_unsupported_scheme(self) -> None:
        with self.assertRaisesRegex(CapsuleVerificationError, "unsupported URI scheme"):
            _validate_fetch_uri("file:///tmp/capsule.txt", allowed_schemes={"https"}, block_private_networks=True)

    def test_rejects_private_network_host(self) -> None:
        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, 0, 0, "", ("127.0.0.1", 0))]):
            with self.assertRaisesRegex(CapsuleVerificationError, "blocked private or local network host"):
                _validate_fetch_uri("https://localhost/capsule.txt", allowed_schemes={"https"}, block_private_networks=True)

    def test_allows_public_host(self) -> None:
        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, 0, 0, "", ("93.184.216.34", 0))]):
            _validate_fetch_uri("https://example.com/capsule.txt", allowed_schemes={"https"}, block_private_networks=True)

    def test_rejects_uri_without_host(self) -> None:
        with self.assertRaisesRegex(CapsuleVerificationError, "missing URI host"):
            _validate_fetch_uri("https:///capsule.txt", allowed_schemes={"https"}, block_private_networks=True)

    def test_limit_validation_rejects_invalid_values(self) -> None:
        with self.assertRaisesRegex(CapsuleVerificationError, "timeout_seconds must be > 0"):
            _validate_limits(timeout_seconds=0, max_download_bytes=1, max_redirects=0)
        with self.assertRaisesRegex(CapsuleVerificationError, "max_download_bytes must be > 0"):
            _validate_limits(timeout_seconds=1, max_download_bytes=0, max_redirects=0)
        with self.assertRaisesRegex(CapsuleVerificationError, "max_redirects must be >= 0"):
            _validate_limits(timeout_seconds=1, max_download_bytes=1, max_redirects=-1)

    def test_fetch_rejects_oversized_download(self) -> None:
        payload = b"x" * 32

        class _FakeResponse:
            content = payload

            def raise_for_status(self) -> None:
                return None

        class _FakeClient:
            def __init__(self, **kwargs) -> None:
                del kwargs

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                del exc_type, exc, tb
                return False

            def get(self, uri: str):
                del uri
                return _FakeResponse()

        class _FakeLimits:
            def __init__(self, **kwargs) -> None:
                del kwargs

        fake_httpx = types.SimpleNamespace(Client=_FakeClient, Limits=_FakeLimits)
        with patch.dict(sys.modules, {"httpx": fake_httpx}):
            with self.assertRaisesRegex(CapsuleVerificationError, "exceeds max download size"):
                fetch_capsule(
                    "https://example.com/capsule.txt",
                    max_download_bytes=8,
                    block_private_networks=False,
                )

    def test_fetch_rejects_sha256_mismatch(self) -> None:
        payload = b"capsule payload"

        class _FakeResponse:
            content = payload

            def raise_for_status(self) -> None:
                return None

        class _FakeClient:
            def __init__(self, **kwargs) -> None:
                del kwargs

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                del exc_type, exc, tb
                return False

            def get(self, uri: str):
                del uri
                return _FakeResponse()

        class _FakeLimits:
            def __init__(self, **kwargs) -> None:
                del kwargs

        fake_httpx = types.SimpleNamespace(Client=_FakeClient, Limits=_FakeLimits)
        with patch.dict(sys.modules, {"httpx": fake_httpx}):
            with self.assertRaisesRegex(CapsuleVerificationError, "SHA256 mismatch"):
                fetch_capsule(
                    "https://example.com/capsule.txt",
                    expected_sha256="0" * 64,
                    block_private_networks=False,
                )


if __name__ == "__main__":
    unittest.main()
