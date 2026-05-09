"""Deterministic Agent Capsule bundle packing and safe unpacking."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath

from agentcapsule.errors import CapsuleUnpackError

BUNDLE_CONTENT_TYPE = "application/vnd.agent.bundle+json"
SINGLE_FILE_CONTENT_TYPE = "application/octet-stream"
BUNDLE_FORMAT = "agent-capsule-bundle-v0"


def pack_path(path: Path) -> tuple[bytes, str, str | None]:
    if path.is_file():
        return path.read_bytes(), SINGLE_FILE_CONTENT_TYPE, path.name
    if path.is_dir():
        return pack_directory(path), BUNDLE_CONTENT_TYPE, None
    raise CapsuleUnpackError(f"input path is not a file or directory: {path}")


def pack_directory(root: Path) -> bytes:
    root = root.resolve()
    files = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirname for dirname in dirnames if dirname != "__pycache__")
        for filename in sorted(filenames):
            file_path = Path(current) / filename
            rel = file_path.relative_to(root).as_posix()
            data = file_path.read_bytes()
            files.append(
                {
                    "path": rel,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "content_base64": base64.b64encode(data).decode("ascii"),
                }
            )
    bundle = {
        "format": BUNDLE_FORMAT,
        "files": files,
    }
    return json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")


def unpack_payload(payload: bytes, content_type: str, out_dir: Path, *, filename: str | None = None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    if content_type == BUNDLE_CONTENT_TYPE:
        return unpack_bundle(payload, out_dir)
    safe_name = _safe_filename(filename or "payload.bin")
    target = _safe_join(out_dir, safe_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return [target]


def unpack_bundle(payload: bytes, out_dir: Path) -> list[Path]:
    try:
        bundle = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CapsuleUnpackError("invalid bundle JSON") from exc
    if bundle.get("format") != BUNDLE_FORMAT:
        raise CapsuleUnpackError("unsupported bundle format")
    files = bundle.get("files")
    if not isinstance(files, list):
        raise CapsuleUnpackError("invalid bundle files list")

    written = []
    for entry in files:
        if not isinstance(entry, dict):
            raise CapsuleUnpackError("invalid bundle file entry")
        rel_path = entry.get("path")
        expected_size = entry.get("size")
        expected_sha = entry.get("sha256")
        encoded = entry.get("content_base64")
        if not isinstance(rel_path, str) or not isinstance(expected_size, int):
            raise CapsuleUnpackError("invalid bundle file metadata")
        if not isinstance(expected_sha, str) or not isinstance(encoded, str):
            raise CapsuleUnpackError("invalid bundle file metadata")
        data = base64.b64decode(encoded.encode("ascii"), validate=True)
        if len(data) != expected_size:
            raise CapsuleUnpackError(f"bundle size mismatch: {rel_path}")
        if hashlib.sha256(data).hexdigest() != expected_sha:
            raise CapsuleUnpackError(f"bundle SHA256 mismatch: {rel_path}")
        target = _safe_join(out_dir, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written.append(target)
    return written


def _safe_filename(name: str) -> str:
    candidate = Path(name).name
    return candidate or "payload.bin"


def _safe_join(out_dir: Path, rel_path: str) -> Path:
    pure = PurePosixPath(rel_path)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise CapsuleUnpackError(f"unsafe bundle path: {rel_path}")
    root = out_dir.resolve()
    target = (root / Path(*pure.parts)).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise CapsuleUnpackError(f"unsafe bundle path: {rel_path}") from exc
    return target
