import socket
import unittest
from unittest.mock import patch

from agentcapsule.errors import CapsuleVerificationError
from agentcapsule.fetcher import _validate_fetch_uri, _validate_limits


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


if __name__ == "__main__":
    unittest.main()
