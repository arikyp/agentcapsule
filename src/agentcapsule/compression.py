"""Agent Capsule compression helpers."""

from __future__ import annotations

from agentcapsule.errors import CapsuleVerificationError

COMPRESSION_NONE = "none"
COMPRESSION_ZSTD = "zstd"


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
        # Note: we might want to set max_output_size to avoid zip bombs
        return dctx.decompress(payload)
    
    raise CapsuleVerificationError(f"unsupported compression mode: {mode}")
