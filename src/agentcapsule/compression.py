"""Agent Capsule compression helpers."""

from __future__ import annotations

import io
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
            reader = dctx.stream_reader(io.BytesIO(payload))
            chunks: list[bytes] = []
            total = 0
            with reader:
                while True:
                    remaining = max_output_size - total
                    read_size = min(1024 * 1024, max(remaining + 1, 1))
                    chunk = reader.read(read_size)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_output_size:
                        raise CapsuleVerificationError(
                            f"zstd decompression failed or exceeded max output size ({max_output_size} bytes)"
                        )
                    chunks.append(chunk)
            return b"".join(chunks)
        except Exception as exc:
            if isinstance(exc, CapsuleVerificationError):
                raise
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
