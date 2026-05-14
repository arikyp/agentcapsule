"""Agent Capsule reference fetching helpers.

This module is experimental and now enforces conservative default network safety guards.
"""

from __future__ import annotations

import hashlib
import ipaddress
import socket
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from agentcapsule.errors import CapsuleVerificationError

if TYPE_CHECKING:
    from typing import Iterator

DEFAULT_ALLOWED_SCHEMES = {"https", "http"}
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_REDIRECTS = 3
DEFAULT_BLOCK_PRIVATE_NETWORKS = True


def fetch_capsule(
    uri: str,
    *,
    expected_sha256: str | None = None,
    save_path: Path | None = None,
    resumable: bool = False,
    allowed_schemes: set[str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    follow_redirects: bool = False,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    block_private_networks: bool = DEFAULT_BLOCK_PRIVATE_NETWORKS,
) -> bytes:
    """Fetch a capsule from a URI and optionally verify its hash."""
    try:
        import httpx
    except ImportError:
        raise CapsuleVerificationError("fetching capsules requires installing agentcapsule[fetch]")

    _validate_fetch_uri(
        uri,
        allowed_schemes=allowed_schemes or DEFAULT_ALLOWED_SCHEMES,
        block_private_networks=block_private_networks,
    )
    _validate_limits(timeout_seconds=timeout_seconds, max_download_bytes=max_download_bytes, max_redirects=max_redirects)

    if resumable and save_path and save_path.exists():
        return _fetch_resumable(
            uri,
            save_path,
            expected_sha256=expected_sha256,
            timeout_seconds=timeout_seconds,
            max_download_bytes=max_download_bytes,
            follow_redirects=follow_redirects,
            max_redirects=max_redirects,
        )

    with httpx.Client(
        follow_redirects=follow_redirects,
        timeout=timeout_seconds,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        max_redirects=max_redirects,
    ) as client:
        response = client.get(uri)
        response.raise_for_status()
        data = response.content
        if len(data) > max_download_bytes:
            raise CapsuleVerificationError("fetched capsule exceeds max download size")

    if expected_sha256:
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256.lower():
            raise CapsuleVerificationError("fetched capsule SHA256 mismatch")

    if save_path:
        save_path.write_bytes(data)

    return data


def _fetch_resumable(
    uri: str,
    path: Path,
    expected_sha256: str | None = None,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    follow_redirects: bool = False,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> bytes:
    import httpx
    current_size = path.stat().st_size
    headers = {"Range": f"bytes={current_size}-"}
    
    with httpx.Client(follow_redirects=follow_redirects, timeout=timeout_seconds, max_redirects=max_redirects) as client:
        # Check if server supports Range
        head = client.head(uri)
        if head.status_code == 200 and head.headers.get("Accept-Ranges") == "bytes":
            with client.stream("GET", uri, headers=headers) as response:
                if response.status_code == 206: # Partial Content
                    with path.open("ab") as f:
                        for chunk in response.iter_bytes():
                            f.write(chunk)
                            if path.stat().st_size > max_download_bytes:
                                raise CapsuleVerificationError("fetched capsule exceeds max download size")
                elif response.status_code == 416: # Range Not Satisfiable (already finished?)
                    pass
                else:
                    # Fallback to full download if Range fails
                    data = client.get(uri).content
                    if len(data) > max_download_bytes:
                        raise CapsuleVerificationError("fetched capsule exceeds max download size")
                    path.write_bytes(data)
        else:
            # Fallback
            data = client.get(uri).content
            if len(data) > max_download_bytes:
                raise CapsuleVerificationError("fetched capsule exceeds max download size")
            path.write_bytes(data)

    data = path.read_bytes()
    if expected_sha256:
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256.lower():
            raise CapsuleVerificationError("fetched capsule SHA256 mismatch")
    return data


def stream_fetch_capsule(
    uri: str,
    *,
    expected_sha256: str | None = None,
    chunk_size: int = 65536,
    allowed_schemes: set[str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    follow_redirects: bool = False,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    block_private_networks: bool = DEFAULT_BLOCK_PRIVATE_NETWORKS,
) -> Iterator[bytes]:
    """Stream fetch a capsule and verify hash incrementally."""
    try:
        import httpx
    except ImportError:
        raise CapsuleVerificationError("fetching capsules requires installing agentcapsule[fetch]")

    _validate_fetch_uri(
        uri,
        allowed_schemes=allowed_schemes or DEFAULT_ALLOWED_SCHEMES,
        block_private_networks=block_private_networks,
    )
    _validate_limits(timeout_seconds=timeout_seconds, max_download_bytes=max_download_bytes, max_redirects=max_redirects)

    hasher = hashlib.sha256() if expected_sha256 else None
    total = 0

    with httpx.stream(
        "GET",
        uri,
        follow_redirects=follow_redirects,
        timeout=timeout_seconds,
        max_redirects=max_redirects,
    ) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes(chunk_size=chunk_size):
            total += len(chunk)
            if total > max_download_bytes:
                raise CapsuleVerificationError("fetched capsule exceeds max download size")
            if hasher:
                hasher.update(chunk)
            yield chunk

    if hasher and expected_sha256:
        actual = hasher.hexdigest()
        if actual != expected_sha256.lower():
            raise CapsuleVerificationError("fetched capsule SHA256 mismatch")


def _validate_limits(*, timeout_seconds: float, max_download_bytes: int, max_redirects: int) -> None:
    if timeout_seconds <= 0:
        raise CapsuleVerificationError("timeout_seconds must be > 0")
    if max_download_bytes <= 0:
        raise CapsuleVerificationError("max_download_bytes must be > 0")
    if max_redirects < 0:
        raise CapsuleVerificationError("max_redirects must be >= 0")


def _validate_fetch_uri(uri: str, *, allowed_schemes: set[str], block_private_networks: bool) -> None:
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    if scheme not in allowed_schemes:
        raise CapsuleVerificationError(f"unsupported URI scheme: {scheme}")
    host = parsed.hostname
    if not host:
        raise CapsuleVerificationError("missing URI host")
    if block_private_networks:
        _reject_private_host(host)


def _reject_private_host(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise CapsuleVerificationError(f"failed to resolve host: {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
            raise CapsuleVerificationError(f"blocked private or local network host: {host}")
