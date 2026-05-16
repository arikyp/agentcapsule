"""Deterministic Agent Capsule bundle packing and safe unpacking."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from agentcapsule.errors import CapsuleParseError, CapsuleUnpackError, CapsuleVerificationError

BUNDLE_CONTENT_TYPE = "application/vnd.agent.bundle+json"
SINGLE_FILE_CONTENT_TYPE = "application/octet-stream"
BUNDLE_FORMAT = "agent-capsule-bundle-v0"
CAPSULE_MANIFEST_HEADER = "capsule_manifest"
DEFAULT_CAPSULE_TYPE = "agent_handoff"
DEFAULT_POLICY_HINTS = {
    "network_egress": False,
    "sandbox_required": True,
}
DELIVERY_MODES = ("inline", "attachment", "reference")


@dataclass(frozen=True)
class PackedPayload:
    payload: bytes
    content_type: str
    filename: str | None
    manifest_files: list[dict[str, object]]


def pack_path(path: Path) -> tuple[bytes, str, str | None]:
    packed = pack_path_with_manifest(path)
    return packed.payload, packed.content_type, packed.filename


def pack_path_with_manifest(path: Path) -> PackedPayload:
    if path.is_file():
        data = path.read_bytes()
        return PackedPayload(
            payload=data,
            content_type=SINGLE_FILE_CONTENT_TYPE,
            filename=path.name,
            manifest_files=[file_manifest_entry(path.name, data)],
        )
    if path.is_dir():
        payload, manifest_files = pack_directory_with_manifest(path)
        return PackedPayload(
            payload=payload,
            content_type=BUNDLE_CONTENT_TYPE,
            filename=None,
            manifest_files=manifest_files,
        )
    raise CapsuleUnpackError(f"input path is not a file or directory: {path}")


def pack_directory(root: Path) -> bytes:
    payload, _manifest_files = pack_directory_with_manifest(root)
    return payload


def pack_directory_with_manifest(root: Path) -> tuple[bytes, list[dict[str, object]]]:
    root = root.resolve()
    files = []
    manifest_files = []
    for current, dirnames, filenames in os.walk(root):
        safe_dirnames = []
        for dirname in sorted(dirnames):
            if dirname == "__pycache__":
                continue
            dir_path = Path(current) / dirname
            if dir_path.is_symlink():
                rel = dir_path.relative_to(root).as_posix()
                raise CapsuleUnpackError(f"symlink directories are not allowed in bundles: {rel}")
            safe_dirnames.append(dirname)
        dirnames[:] = safe_dirnames
        for filename in sorted(filenames):
            file_path = Path(current) / filename
            rel = file_path.relative_to(root).as_posix()
            if file_path.is_symlink():
                raise CapsuleUnpackError(f"symlink files are not allowed in bundles: {rel}")
            data = file_path.read_bytes()
            sha256 = hashlib.sha256(data).hexdigest()
            manifest_files.append(
                {
                    "path": rel,
                    "sha256": sha256,
                    "bytes": len(data),
                }
            )
            files.append(
                {
                    "path": rel,
                    "size": len(data),
                    "sha256": sha256,
                    "content_base64": base64.b64encode(data).decode("ascii"),
                }
            )
    bundle = {
        "format": BUNDLE_FORMAT,
        "files": files,
    }
    return json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8"), manifest_files


def file_manifest_entry(path: str, data: bytes) -> dict[str, object]:
    return {
        "path": path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def build_capsule_manifest(
    *,
    capsule_type: str = DEFAULT_CAPSULE_TYPE,
    created_by: str,
    task_id: str = "",
    files: list[dict[str, object]] | None = None,
    requested_capabilities: list[str] | None = None,
    policy_hints: dict[str, object] | None = None,
    delivery_mode: str = "inline",
    delivery_uri: str | None = None,
) -> dict[str, object]:
    manifest = {
        "capsule_type": capsule_type,
        "created_by": created_by,
        "task_id": task_id,
        "delivery": build_delivery_metadata(mode=delivery_mode, uri=delivery_uri),
        "files": files or [],
        "requested_capabilities": requested_capabilities or [],
        "policy_hints": {**DEFAULT_POLICY_HINTS, **(policy_hints or {})},
    }
    validate_capsule_manifest(manifest)
    return manifest


def build_delivery_metadata(*, mode: str, uri: str | None = None) -> dict[str, object]:
    delivery: dict[str, object] = {"mode": mode}
    if uri:
        delivery["uri"] = uri
    validate_delivery_metadata(delivery)
    return delivery


def encode_capsule_manifest(manifest: dict[str, object]) -> str:
    validate_capsule_manifest(manifest)
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"))


def parse_capsule_manifest(value: str) -> dict[str, object]:
    try:
        manifest = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CapsuleParseError("invalid capsule manifest JSON") from exc
    validate_capsule_manifest(manifest)
    return manifest


def validate_capsule_manifest(manifest: Any) -> None:
    if not isinstance(manifest, dict):
        raise CapsuleParseError("capsule manifest must be a JSON object")
    required = {
        "capsule_type",
        "created_by",
        "task_id",
        "files",
        "requested_capabilities",
        "policy_hints",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise CapsuleParseError(f"missing capsule manifest fields: {', '.join(missing)}")
    for key in ("capsule_type", "created_by", "task_id"):
        if not isinstance(manifest[key], str):
            raise CapsuleParseError(f"capsule manifest field must be a string: {key}")
    if not manifest["capsule_type"]:
        raise CapsuleParseError("capsule manifest capsule_type is required")
    if not manifest["created_by"]:
        raise CapsuleParseError("capsule manifest created_by is required")
    files = manifest["files"]
    if not isinstance(files, list):
        raise CapsuleParseError("capsule manifest files must be a list")
    for entry in files:
        _validate_manifest_file(entry)
    capabilities = manifest["requested_capabilities"]
    if not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities):
        raise CapsuleParseError("capsule manifest requested_capabilities must be a string list")
    policy_hints = manifest["policy_hints"]
    if not isinstance(policy_hints, dict) or not all(isinstance(key, str) for key in policy_hints):
        raise CapsuleParseError("capsule manifest policy_hints must be an object")
    if "delivery" in manifest:
        validate_delivery_metadata(manifest["delivery"])


def validate_delivery_metadata(delivery: Any) -> None:
    if not isinstance(delivery, dict):
        raise CapsuleParseError("capsule manifest delivery must be an object")
    mode = delivery.get("mode")
    if not isinstance(mode, str) or mode not in DELIVERY_MODES:
        raise CapsuleParseError("capsule manifest delivery mode is invalid")
    uri = delivery.get("uri")
    if uri is not None and (not isinstance(uri, str) or not uri):
        raise CapsuleParseError("capsule manifest delivery uri must be a non-empty string")
    if mode == "reference" and uri is None:
        raise CapsuleParseError("reference delivery requires a uri")


def _validate_manifest_file(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise CapsuleParseError("capsule manifest file entry must be an object")
    for key in ("path", "sha256", "bytes"):
        if key not in entry:
            raise CapsuleParseError(f"missing capsule manifest file field: {key}")
    if not isinstance(entry["path"], str) or not entry["path"]:
        raise CapsuleParseError("capsule manifest file path must be a non-empty string")
    if not isinstance(entry["sha256"], str) or len(entry["sha256"]) != 64:
        raise CapsuleParseError("capsule manifest file sha256 is invalid")
    try:
        int(entry["sha256"], 16)
    except ValueError as exc:
        raise CapsuleParseError("capsule manifest file sha256 is invalid") from exc
    if not isinstance(entry["bytes"], int) or entry["bytes"] < 0:
        raise CapsuleParseError("capsule manifest file bytes must be a non-negative integer")


def verify_manifest_matches_payload(
    *,
    manifest: dict[str, object] | None,
    payload: bytes,
    content_type: str,
    filename: str | None = None,
) -> None:
    """Verify that capsule manifest file metadata matches decoded payload content."""
    if manifest is None:
        return
    files_raw = manifest.get("files")
    if not isinstance(files_raw, list):
        raise CapsuleVerificationError("capsule manifest files must be a list")
    manifest_index = _manifest_file_index(files_raw)
    if content_type == SINGLE_FILE_CONTENT_TYPE:
        _verify_single_payload_manifest(manifest_index, payload=payload, filename=filename)
        return
    if content_type == BUNDLE_CONTENT_TYPE:
        _verify_bundle_payload_manifest(manifest_index, payload=payload)
        return
    raise CapsuleVerificationError(f"unsupported content type for manifest verification: {content_type}")


def _manifest_file_index(files_raw: list[object]) -> dict[str, tuple[int, str]]:
    manifest_index: dict[str, tuple[int, str]] = {}
    for entry in files_raw:
        _validate_manifest_file(entry)
        assert isinstance(entry, dict)  # for typing
        path = str(entry["path"])
        if path in manifest_index:
            raise CapsuleVerificationError(f"duplicate path in capsule manifest files: {path}")
        manifest_index[path] = (int(entry["bytes"]), str(entry["sha256"]).lower())
    return manifest_index


def _verify_single_payload_manifest(
    manifest_index: dict[str, tuple[int, str]],
    *,
    payload: bytes,
    filename: str | None,
) -> None:
    if len(manifest_index) != 1:
        raise CapsuleVerificationError("single-file payload requires exactly one manifest file entry")
    expected_name = _safe_filename(filename or "payload.bin")
    path, (expected_bytes, expected_sha) = next(iter(manifest_index.items()))
    if path != expected_name:
        raise CapsuleVerificationError("capsule manifest file path does not match single-file payload name")
    if expected_bytes != len(payload):
        raise CapsuleVerificationError("capsule manifest bytes do not match single-file payload")
    actual_sha = hashlib.sha256(payload).hexdigest()
    if expected_sha != actual_sha:
        raise CapsuleVerificationError("capsule manifest SHA256 does not match single-file payload")


def _verify_bundle_payload_manifest(manifest_index: dict[str, tuple[int, str]], *, payload: bytes) -> None:
    bundle_index = _bundle_payload_index(payload)
    manifest_paths = set(manifest_index)
    bundle_paths = set(bundle_index)
    if manifest_paths != bundle_paths:
        missing = sorted(bundle_paths - manifest_paths)
        extra = sorted(manifest_paths - bundle_paths)
        details = []
        if missing:
            details.append(f"missing paths: {', '.join(missing)}")
        if extra:
            details.append(f"unexpected paths: {', '.join(extra)}")
        raise CapsuleVerificationError("capsule manifest files do not match bundle payload files" + (f" ({'; '.join(details)})" if details else ""))
    for path, (actual_bytes, actual_sha) in bundle_index.items():
        expected_bytes, expected_sha = manifest_index[path]
        if expected_bytes != actual_bytes:
            raise CapsuleVerificationError(f"capsule manifest bytes do not match bundle payload: {path}")
        if expected_sha != actual_sha:
            raise CapsuleVerificationError(f"capsule manifest SHA256 does not match bundle payload: {path}")


def _bundle_payload_index(payload: bytes) -> dict[str, tuple[int, str]]:
    try:
        bundle = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CapsuleVerificationError("invalid bundle JSON") from exc
    if bundle.get("format") != BUNDLE_FORMAT:
        raise CapsuleVerificationError("unsupported bundle format")
    files = bundle.get("files")
    if not isinstance(files, list):
        raise CapsuleVerificationError("invalid bundle files list")
    index: dict[str, tuple[int, str]] = {}
    for entry in files:
        if not isinstance(entry, dict):
            raise CapsuleVerificationError("invalid bundle file entry")
        rel_path = entry.get("path")
        expected_size = entry.get("size")
        expected_sha = entry.get("sha256")
        encoded = entry.get("content_base64")
        if not isinstance(rel_path, str) or not isinstance(expected_size, int):
            raise CapsuleVerificationError("invalid bundle file metadata")
        if not isinstance(expected_sha, str) or not isinstance(encoded, str):
            raise CapsuleVerificationError("invalid bundle file metadata")
        if rel_path in index:
            raise CapsuleVerificationError(f"duplicate path in bundle payload: {rel_path}")
        try:
            data = base64.b64decode(encoded.encode("ascii"), validate=True)
        except Exception as exc:
            raise CapsuleVerificationError(f"invalid bundle file content encoding: {rel_path}") from exc
        if len(data) != expected_size:
            raise CapsuleVerificationError(f"bundle size mismatch: {rel_path}")
        actual_sha = hashlib.sha256(data).hexdigest()
        if actual_sha != expected_sha:
            raise CapsuleVerificationError(f"bundle SHA256 mismatch: {rel_path}")
        index[rel_path] = (len(data), actual_sha)
    return index


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
