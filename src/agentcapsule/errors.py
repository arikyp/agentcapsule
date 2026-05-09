"""Agent Capsule error types."""

from __future__ import annotations


class CapsuleError(Exception):
    """Base class for Agent Capsule failures."""


class CapsuleParseError(CapsuleError):
    """Raised when an envelope cannot be parsed."""


class CapsuleVerificationError(CapsuleError):
    """Raised when capsule verification fails."""


class CapsulePolicyError(CapsuleError):
    """Raised when a capsule violates local policy."""


class CapsuleUnpackError(CapsuleError):
    """Raised when decoded content cannot be unpacked safely."""
