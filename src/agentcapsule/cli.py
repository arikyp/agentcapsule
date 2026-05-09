"""Agent Capsule command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentcapsule.envelope import build_envelope, parse_envelope, render_envelope, verify_envelope
from agentcapsule.errors import CapsuleError
from agentcapsule.manifest import pack_path, unpack_payload
from agentcapsule.policy import DEFAULT_POLICY, CapsulePolicy, load_policy
from agentcapsule.registry import list_codecs
from agentcapsule.scanner import scan_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="capsule")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pack_parser = subparsers.add_parser("pack", help="pack a file or directory into an Agent Capsule")
    pack_parser.add_argument("path")
    pack_parser.add_argument("--out", required=True)
    pack_parser.add_argument("--codec", choices=("base64", "lmcodec-fixed"), default="base64")

    inspect_parser = subparsers.add_parser("inspect", help="inspect capsule metadata")
    inspect_parser.add_argument("capsule")
    inspect_parser.add_argument("--policy", help="JSON policy file")
    inspect_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    verify_parser = subparsers.add_parser("verify", help="verify capsule payload hash")
    verify_parser.add_argument("capsule")
    verify_parser.add_argument("--policy", help="JSON policy file")
    verify_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    unpack_parser = subparsers.add_parser("unpack", help="verify and unpack a capsule")
    unpack_parser.add_argument("capsule")
    unpack_parser.add_argument("--out", required=True)
    unpack_parser.add_argument("--policy", help="JSON policy file")

    scan_parser = subparsers.add_parser("scan", help="scan a text file for capsules and dense payload risks")
    scan_parser.add_argument("text_file")
    scan_parser.add_argument("--policy", help="JSON policy file")
    scan_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    codecs_parser = subparsers.add_parser("codecs", help="list registered capsule codecs")
    codecs_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            payload, content_type, filename = pack_path(Path(args.path))
            envelope = build_envelope(payload, codec=args.codec, content_type=content_type, filename=filename)
            Path(args.out).write_text(render_envelope(envelope), encoding="utf-8", newline="\n")
            print(f"capsule path: {args.out}")
            print(f"codec: {args.codec}")
            print(f"content type: {content_type}")
            print(f"payload bytes: {len(payload)}")
            print(f"payload sha256: {envelope.payload_sha256}")
            return 0
        if args.command == "inspect":
            policy = _policy_from_args(args)
            envelope = parse_envelope(Path(args.capsule).read_text(encoding="utf-8"))
            policy.check_metadata(envelope)
            inspection = _inspect_envelope(envelope, policy)
            if args.json:
                _print_json(inspection)
            else:
                _print_inspection(inspection)
            return 0
        if args.command == "verify":
            policy = _policy_from_args(args)
            envelope = parse_envelope(Path(args.capsule).read_text(encoding="utf-8"))
            policy.check_metadata(envelope)
            payload = verify_envelope(envelope)
            policy.check_payload(payload)
            result = {
                "verification": "ok",
                "payload_bytes": len(payload),
                "payload_sha256": envelope.payload_sha256,
                "codec": envelope.codec,
                "content_type": envelope.content_type,
            }
            if args.json:
                _print_json(result)
            else:
                print("verification: ok")
                print(f"payload bytes: {len(payload)}")
            return 0
        if args.command == "unpack":
            policy = _policy_from_args(args)
            envelope = parse_envelope(Path(args.capsule).read_text(encoding="utf-8"))
            policy.check_metadata(envelope)
            payload = verify_envelope(envelope)
            policy.check_payload(payload)
            written = unpack_payload(
                payload,
                envelope.content_type,
                Path(args.out),
                filename=envelope.headers.get("filename"),
            )
            print("verification: ok")
            print(f"files written: {len(written)}")
            for path in written:
                print(path)
            return 0
        if args.command == "scan":
            policy = _policy_from_args(args)
            result = scan_text(Path(args.text_file).read_text(encoding="utf-8"), policy=policy)
            scan_payload = {
                "capsules_detected": result.capsules_detected,
                "valid_capsules": result.valid_capsules,
                "invalid_capsules": result.invalid_capsules,
                "risk_level": result.risk_level,
                "reasons": result.reasons,
                "findings": [finding.to_dict() for finding in result.findings],
            }
            if args.json:
                _print_json(scan_payload)
            else:
                print(f"capsules detected: {result.capsules_detected}")
                print(f"valid capsules: {result.valid_capsules}")
                print(f"invalid capsules: {result.invalid_capsules}")
                print(f"risk level: {result.risk_level}")
                for reason in result.reasons:
                    print(f"reason: {reason}")
                for finding in result.findings:
                    print(
                        "finding: "
                        f"{finding.risk} {finding.finding_type} "
                        f"line {finding.line}, column {finding.column}: {finding.message}"
                    )
            return 0
        if args.command == "codecs":
            codecs = [_codec_to_dict(codec) for codec in list_codecs()]
            if args.json:
                _print_json({"codecs": codecs})
            else:
                for codec in list_codecs():
                    print(f"{codec.name}\t{codec.stability}\t{codec.purpose}")
                    print(f"  external model: {'yes' if codec.requires_external_model else 'no'}")
                    print(f"  notes: {codec.notes}")
            return 0
    except CapsuleError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    parser.error("unreachable command")
    return 2


def _policy_from_args(args: argparse.Namespace) -> CapsulePolicy:
    policy_path = getattr(args, "policy", None)
    if policy_path:
        return load_policy(Path(policy_path))
    return DEFAULT_POLICY


def _inspect_envelope(envelope, policy: CapsulePolicy) -> dict[str, object]:
    result: dict[str, object] = {
        "capsule_version": envelope.headers["capsule_version"],
        "codec": envelope.codec,
        "content_type": envelope.content_type,
        "compression": envelope.headers["compression"],
        "encryption": envelope.headers["encryption"],
        "signature_mode": envelope.headers["signature"],
        "payload_sha256": envelope.payload_sha256,
        "created_by": envelope.headers["created_by"],
        "created_at": envelope.headers["created_at"],
        "payload_character_length": len(envelope.payload_text),
        "risk_notes": _risk_notes(envelope),
    }
    try:
        payload = verify_envelope(envelope)
        policy.check_payload(payload)
        result["verification_status"] = "ok"
        result["payload_bytes"] = len(payload)
    except CapsuleError as exc:
        result["verification_status"] = "failed"
        result["verification_error"] = str(exc)
    return result


def _print_inspection(inspection: dict[str, object]) -> None:
    print(f"capsule version: {inspection['capsule_version']}")
    print(f"codec: {inspection['codec']}")
    print(f"content type: {inspection['content_type']}")
    print(f"compression: {inspection['compression']}")
    print(f"encryption: {inspection['encryption']}")
    print(f"signature mode: {inspection['signature_mode']}")
    print(f"payload sha256: {inspection['payload_sha256']}")
    print(f"created_by: {inspection['created_by']}")
    print(f"created_at: {inspection['created_at']}")
    print(f"payload character length: {inspection['payload_character_length']}")
    if inspection["verification_status"] == "ok":
        print("verification status: ok")
    else:
        print(f"verification status: failed ({inspection['verification_error']})")
    notes = inspection["risk_notes"]
    if isinstance(notes, list) and notes:
        for note in notes:
            print(f"risk note: {note}")
    else:
        print("risk note: inspect decoded content before use")


def _risk_notes(envelope) -> list[str]:
    notes = []
    if envelope.headers.get("signature") == "none":
        notes.append("unsigned capsule; SHA256 only proves integrity against the header")
    if envelope.headers.get("encryption") == "none":
        notes.append("payload is not encrypted")
    if envelope.codec != "base64":
        notes.append("non-base64 codec requires matching decoder support")
    return notes


def _codec_to_dict(codec) -> dict[str, object]:
    return {
        "name": codec.name,
        "purpose": codec.purpose,
        "stability": codec.stability,
        "requires_external_model": codec.requires_external_model,
        "notes": codec.notes,
    }


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    raise SystemExit(main())
