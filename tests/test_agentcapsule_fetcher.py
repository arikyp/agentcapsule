import socket
import unittest
from unittest.mock import patch

from agentcapsule.errors import CapsuleVerificationError
from agentcapsule.fetcher import _validate_fetch_uri


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


if __name__ == "__main__":
    unittest.main()
