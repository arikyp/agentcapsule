"""Integer arithmetic coder used by LMCodec."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Sequence

from lmcodec.bitstream import BitReader

CODE_VALUE_BITS = 32
TOP_VALUE = (1 << CODE_VALUE_BITS) - 1
FIRST_QTR = (TOP_VALUE + 1) // 4
HALF = FIRST_QTR * 2
THIRD_QTR = FIRST_QTR * 3


def _validate_cdf(cdf: Sequence[int]) -> None:
    if len(cdf) < 2:
        raise ValueError("cdf must contain at least one symbol")
    if cdf[0] != 0:
        raise ValueError("cdf must start at zero")
    if cdf[-1] <= 0:
        raise ValueError("cdf total must be positive")
    for left, right in zip(cdf, cdf[1:], strict=False):
        if right <= left:
            raise ValueError("cdf must be strictly increasing")


class RangeEncoder:
    """Arithmetic encoder that emits bits incrementally."""

    def __init__(self) -> None:
        self.low = 0
        self.high = TOP_VALUE
        self._pending_bits = 0
        self._bits: list[int] = []
        self._finished = False

    @property
    def bits(self) -> tuple[int, ...]:
        return tuple(self._bits)

    def push_symbol(self, cdf: Sequence[int], symbol: int) -> None:
        if self._finished:
            raise ValueError("cannot push symbols after finish")
        _validate_cdf(cdf)
        if symbol < 0 or symbol >= len(cdf) - 1:
            raise ValueError("symbol out of range")

        total = cdf[-1]
        width = self.high - self.low + 1
        self.high = self.low + (width * cdf[symbol + 1] // total) - 1
        self.low = self.low + (width * cdf[symbol] // total)

        while True:
            if self.high < HALF:
                self._emit_bit_plus_pending(0)
            elif self.low >= HALF:
                self._emit_bit_plus_pending(1)
                self.low -= HALF
                self.high -= HALF
            elif self.low >= FIRST_QTR and self.high < THIRD_QTR:
                self._pending_bits += 1
                self.low -= FIRST_QTR
                self.high -= FIRST_QTR
            else:
                break
            self.low *= 2
            self.high = self.high * 2 + 1

    def finish(self) -> tuple[int, ...]:
        """Flush enough bits to identify the final arithmetic interval."""

        if not self._finished:
            self._pending_bits += 1
            if self.low < FIRST_QTR:
                self._emit_bit_plus_pending(0)
            else:
                self._emit_bit_plus_pending(1)
            self._finished = True
        return self.bits

    def preview_finish(self) -> tuple[int, ...]:
        """Return finished bits without mutating this encoder."""

        clone = RangeEncoder()
        clone.low = self.low
        clone.high = self.high
        clone._pending_bits = self._pending_bits
        clone._bits = list(self._bits)
        clone._finished = self._finished
        return clone.finish()

    def _emit_bit_plus_pending(self, bit: int) -> None:
        self._bits.append(bit)
        inverse = 1 - bit
        while self._pending_bits:
            self._bits.append(inverse)
            self._pending_bits -= 1


class RangeDecoder:
    """Arithmetic decoder backed by a bit reader with EOF padding."""

    def __init__(self, bits: Iterable[int], *, eof_pad_bit: int = 0) -> None:
        self.low = 0
        self.high = TOP_VALUE
        self._reader = BitReader(bits, eof_pad_bit=eof_pad_bit)
        self.code = 0
        for _ in range(CODE_VALUE_BITS):
            self.code = (self.code << 1) | self._reader.read()

    def pop_symbol(self, cdf: Sequence[int]) -> int:
        _validate_cdf(cdf)
        total = cdf[-1]
        width = self.high - self.low + 1
        scaled_value = ((self.code - self.low + 1) * total - 1) // width
        symbol = bisect_right(cdf, scaled_value) - 1
        if symbol < 0 or symbol >= len(cdf) - 1:
            raise ValueError("decoded symbol out of range")

        self.high = self.low + (width * cdf[symbol + 1] // total) - 1
        self.low = self.low + (width * cdf[symbol] // total)

        while True:
            if self.high < HALF:
                pass
            elif self.low >= HALF:
                self.code -= HALF
                self.low -= HALF
                self.high -= HALF
            elif self.low >= FIRST_QTR and self.high < THIRD_QTR:
                self.code -= FIRST_QTR
                self.low -= FIRST_QTR
                self.high -= FIRST_QTR
            else:
                break
            self.low *= 2
            self.high = self.high * 2 + 1
            self.code = self.code * 2 + self._reader.read()

        return symbol
