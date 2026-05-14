"""Agent Capsule reference fetching helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from agentcapsule.errors import CapsuleVerificationError

if TYPE_CHECKING:
    from typing import Iterator


def fetch_capsule(
    uri: str,
    *,
    expected_sha256: str | None = None,
    save_path: Path | None = None,
    resumable: bool = False,
) -> bytes:
    """Fetch a capsule from a URI and optionally verify its hash."""
    try:
        import httpx
    except ImportError:
        raise CapsuleVerificationError("fetching capsules requires installing agentcapsule[fetch]")

    if resumable and save_path and save_path.exists():
        return _fetch_resumable(uri, save_path, expected_sha256=expected_sha256)

    with httpx.Client(follow_redirects=True) as client:
        response = client.get(uri)
        response.raise_for_status()
        data = response.content

    if expected_sha256:
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256.lower():
            raise CapsuleVerificationError("fetched capsule SHA256 mismatch")

    if save_path:
        save_path.write_bytes(data)

    return data


def _fetch_resumable(uri: str, path: Path, expected_sha256: str | None = None) -> bytes:
    import httpx
    current_size = path.stat().st_size
    headers = {"Range": f"bytes={current_size}-"}
    
    with httpx.Client(follow_redirects=True) as client:
        # Check if server supports Range
        head = client.head(uri)
        if head.status_code == 200 and head.headers.get("Accept-Ranges") == "bytes":
            with client.stream("GET", uri, headers=headers) as response:
                if response.status_code == 206: # Partial Content
                    with path.open("ab") as f:
                        for chunk in response.iter_bytes():
                            f.write(chunk)
                elif response.status_code == 416: # Range Not Satisfiable (already finished?)
                    pass
                else:
                    # Fallback to full download if Range fails
                    data = client.get(uri).content
                    path.write_bytes(data)
        else:
            # Fallback
            data = client.get(uri).content
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
) -> Iterator[bytes]:
    """Stream fetch a capsule and verify hash incrementally."""
    try:
        import httpx
    except ImportError:
        raise CapsuleVerificationError("fetching capsules requires installing agentcapsule[fetch]")

    hasher = hashlib.sha256() if expected_sha256 else None

    with httpx.stream("GET", uri, follow_redirects=True) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes(chunk_size=chunk_size):
            if hasher:
                hasher.update(chunk)
            yield chunk

    if hasher and expected_sha256:
        actual = hasher.hexdigest()
        if actual != expected_sha256.lower():
            raise CapsuleVerificationError("fetched capsule SHA256 mismatch")
