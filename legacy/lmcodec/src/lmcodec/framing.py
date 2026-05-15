"""Binary payload framing."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

from lmcodec.bitstream import bits_to_bytes
from lmcodec.errors import LMCodecError

MAGIC = b"LMC1"
HEADER_SIZE = 12


@dataclass(frozen=True)
class FrameInfo:
    payload_len: int
    crc32: int
    total_len: int


def build_frame(payload: bytes) -> bytes:
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    return MAGIC + struct.pack("<II", len(payload), crc) + payload


def read_frame_header(frame_prefix: bytes) -> FrameInfo:
    if len(frame_prefix) < HEADER_SIZE:
        raise LMCodecError("truncated message")
    magic = frame_prefix[:4]
    if magic != MAGIC:
        raise LMCodecError("invalid payload magic")
    payload_len, crc = struct.unpack("<II", frame_prefix[4:HEADER_SIZE])
    return FrameInfo(payload_len=payload_len, crc32=crc, total_len=HEADER_SIZE + payload_len)


def parse_frame(frame: bytes) -> bytes:
    info = read_frame_header(frame)
    if len(frame) < info.total_len:
        raise LMCodecError("truncated message")
    payload = frame[HEADER_SIZE : info.total_len]
    actual_crc = zlib.crc32(payload) & 0xFFFFFFFF
    if actual_crc != info.crc32:
        raise LMCodecError("CRC mismatch / corrupted message")
    return payload


def try_parse_frame_bits(bits: tuple[int, ...] | list[int]) -> bytes | None:
    header_bits = HEADER_SIZE * 8
    if len(bits) < header_bits:
        return None

    header = bits_to_bytes(bits[:header_bits])
    info = read_frame_header(header)
    total_bits = info.total_len * 8
    if len(bits) < total_bits:
        return None

    frame = bits_to_bytes(bits[:total_bits])
    return parse_frame(frame)

