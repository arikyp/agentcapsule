"""Canonical MSB-first bitstream helpers."""

from __future__ import annotations

from collections.abc import Iterable


def bytes_to_bits(data: bytes) -> list[int]:
    """Return bits in MSB-first order within each byte."""

    bits: list[int] = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


def bits_to_bytes(bits: Iterable[int], *, allow_partial: bool = False) -> bytes:
    """Pack MSB-first bits into bytes.

    If ``allow_partial`` is true, the final byte is padded with zero bits.
    """

    bit_list = list(bits)
    if len(bit_list) % 8 and not allow_partial:
        raise ValueError("bit length must be a multiple of 8")

    out = bytearray()
    for offset in range(0, len(bit_list), 8):
        chunk = bit_list[offset : offset + 8]
        if len(chunk) < 8:
            chunk = chunk + [0] * (8 - len(chunk))
        value = 0
        for bit in chunk:
            if bit not in (0, 1):
                raise ValueError("bits must be 0 or 1")
            value = (value << 1) | bit
        out.append(value)
    return bytes(out)


class BitReader:
    """Read a finite bitstream with deterministic EOF padding."""

    def __init__(self, bits: Iterable[int], *, eof_pad_bit: int = 0) -> None:
        if eof_pad_bit not in (0, 1):
            raise ValueError("eof_pad_bit must be 0 or 1")
        self._bits = list(bits)
        self._pos = 0
        self._eof_pad_bit = eof_pad_bit

    @property
    def consumed(self) -> int:
        return self._pos

    def read(self) -> int:
        if self._pos >= len(self._bits):
            self._pos += 1
            return self._eof_pad_bit
        bit = self._bits[self._pos]
        self._pos += 1
        if bit not in (0, 1):
            raise ValueError("bits must be 0 or 1")
        return bit

