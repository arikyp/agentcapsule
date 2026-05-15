"""Copy/paste-safe text armour."""

from __future__ import annotations

from dataclasses import dataclass

from lmcodec.errors import LMCodecError

BEGIN = "-----BEGIN LMCODEC-----"
END = "-----END LMCODEC-----"


@dataclass(frozen=True)
class ArmourBlock:
    version: int
    model_fingerprint: str
    settings: dict[str, str]
    payload_text: str


def make_armour(
    payload_text: str,
    *,
    model_fingerprint: str,
    settings: dict[str, str],
    wrap: int = 0,
) -> str:
    if wrap < 0:
        raise ValueError("wrap must be non-negative")
    payload = _wrap(payload_text, wrap) if wrap else payload_text
    settings_text = "; ".join(f"{key}={value}" for key, value in settings.items())
    return "\n".join(
        [
            BEGIN,
            "version: 1",
            f"model_fingerprint: {model_fingerprint}",
            f"settings: {settings_text}",
            "",
            payload,
            END,
            "",
        ]
    )


def parse_armour(text: str) -> ArmourBlock:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")

    begin_idx = _find_marker(lines, BEGIN)
    if begin_idx is None:
        raise LMCodecError("invalid armour block")
    end_idx = _find_marker(lines[begin_idx + 1 :], END)
    if end_idx is None:
        raise LMCodecError("invalid armour block")
    end_idx += begin_idx + 1

    inner = lines[begin_idx + 1 : end_idx]
    headers: dict[str, str] = {}
    payload_start = None
    for idx, line in enumerate(inner):
        if line == "":
            payload_start = idx + 1
            break
        if ":" not in line:
            payload_start = idx
            break
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()

    if payload_start is None:
        payload_start = len(inner)

    try:
        version = int(headers["version"])
        fingerprint = headers["model_fingerprint"]
        settings = parse_settings(headers["settings"])
    except (KeyError, ValueError) as exc:
        raise LMCodecError("invalid armour block") from exc

    if version != 1:
        raise LMCodecError("unsupported version")

    # Newlines in the payload block are presentation wrapping, not symbols.
    payload_text = "".join(inner[payload_start:])
    return ArmourBlock(
        version=version,
        model_fingerprint=fingerprint,
        settings=settings,
        payload_text=payload_text,
    )


def parse_settings(settings_text: str) -> dict[str, str]:
    settings: dict[str, str] = {}
    if not settings_text.strip():
        raise ValueError("empty settings")
    for item in settings_text.split(";"):
        if not item.strip():
            continue
        if "=" not in item:
            raise ValueError("invalid settings item")
        key, value = item.split("=", 1)
        settings[key.strip()] = value.strip()
    return settings


def _wrap(text: str, width: int) -> str:
    return "\n".join(text[idx : idx + width] for idx in range(0, len(text), width))


def _find_marker(lines: list[str], marker: str) -> int | None:
    for idx, line in enumerate(lines):
        if line.strip() == marker:
            return idx
    return None

