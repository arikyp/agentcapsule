"""Agent Capsule compression helpers."""

from __future__ import annotations

import os

from agentcapsule.errors import CapsuleVerificationError

COMPRESSION_NONE = "none"
COMPRESSION_ZSTD = "zstd"
DEFAULT_ZSTD_MAX_OUTPUT_SIZE = 64 * 1024 * 1024  # 64 MiB


def compress_payload(payload: bytes, mode: str = COMPRESSION_ZSTD) -> tuple[bytes, str]:
    if mode == COMPRESSION_NONE:
        return payload, COMPRESSION_NONE
    
    if mode == COMPRESSION_ZSTD:
        try:
            import zstandard as zstd
        except ImportError:
            raise CapsuleVerificationError("zstd compression requires installing agentcapsule[compression]")
        
        cctx = zstd.ZstdCompressor()
        return cctx.compress(payload), COMPRESSION_ZSTD
    
    raise CapsuleVerificationError(f"unsupported compression mode: {mode}")


def decompress_payload(payload: bytes, mode: str) -> bytes:
    if mode == COMPRESSION_NONE:
        return payload
    
    if mode == COMPRESSION_ZSTD:
        try:
            import zstandard as zstd
        except ImportError:
            raise CapsuleVerificationError("zstd decompression requires installing agentcapsule[compression]")

        dctx = zstd.ZstdDecompressor()
        max_output_size = _zstd_max_output_size()
        try:
            return dctx.decompress(payload, max_output_size=max_output_size)
        except Exception as exc:
            raise CapsuleVerificationError(
                f"zstd decompression failed or exceeded max output size ({max_output_size} bytes)"
            ) from exc
    
    raise CapsuleVerificationError(f"unsupported compression mode: {mode}")


def _zstd_max_output_size() -> int:
    raw = os.getenv("AGENTCAPSULE_ZSTD_MAX_OUTPUT_SIZE")
    if raw is None:
        return DEFAULT_ZSTD_MAX_OUTPUT_SIZE
    try:
        value = int(raw)
    except ValueError as exc:
        raise CapsuleVerificationError("invalid AGENTCAPSULE_ZSTD_MAX_OUTPUT_SIZE value") from exc
    if value <= 0:
        raise CapsuleVerificationError("AGENTCAPSULE_ZSTD_MAX_OUTPUT_SIZE must be > 0")
    return value
