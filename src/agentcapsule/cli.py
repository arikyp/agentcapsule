"""Agent Capsule command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentcapsule.backends import known_codecs, ngram_v2_headers_from_model_path
from agentcapsule.envelope import build_envelope, parse_envelope, render_envelope, verify_envelope
from agentcapsule.errors import CapsuleError
from agentcapsule.manifest import pack_path, unpack_payload
from agentcapsule.policy import DEFAULT_POLICY, CapsulePolicy, load_policy, policy_to_dict
from agentcapsule.registry import list_codecs
from agentcapsule.scanner import scan_text
from agentcapsule.signing import (
    SIGNATURE_ED25519,
    SIGNATURE_HMAC_SHA256,
    SIGNATURE_NONE,
    generate_ed25519_keypair,
    key_from_env,
    load_private_key_file,
    load_public_key_file,
    public_key_fingerprint,
    sign_envelope,
    sign_envelope_ed25519,
    verify_ed25519_signature,
    verify_signature,
    write_key_file,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="capsule")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pack_parser = subparsers.add_parser("pack", help="pack a file or directory into an Agent Capsule")
    pack_parser.add_argument("path")
    pack_parser.add_argument("--out", required=True)
    pack_parser.add_argument("--codec", choices=known_codecs(), default="base64")
    pack_parser.add_argument("--model", help="LMCodec model JSON for model-backed capsule codecs")
    pack_parser.add_argument("--sign-key-env", help="environment variable containing HMAC-SHA256 signing key")
    pack_parser.add_argument("--sign-ed25519-key", help="base64 raw Ed25519 private key file")
    pack_parser.add_argument(
        "--no-inline-public-key",
        action="store_true",
        help="omit inline Ed25519 public key metadata from signed capsules",
    )
    pack_parser.add_argument("--signature-key-id", help="optional signature key identifier written to capsule metadata")

    inspect_parser = subparsers.add_parser("inspect", help="inspect capsule metadata")
    inspect_parser.add_argument("capsule")
    inspect_parser.add_argument("--policy", help="JSON policy file")
    inspect_parser.add_argument("--key-env", help="environment variable containing HMAC-SHA256 verification key")
    inspect_parser.add_argument("--ed25519-public-key", help="base64 raw Ed25519 public key file")
    inspect_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    verify_parser = subparsers.add_parser("verify", help="verify capsule payload hash")
    verify_parser.add_argument("capsule")
    verify_parser.add_argument("--policy", help="JSON policy file")
    verify_parser.add_argument("--key-env", help="environment variable containing HMAC-SHA256 verification key")
    verify_parser.add_argument("--ed25519-public-key", help="base64 raw Ed25519 public key file")
    verify_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    unpack_parser = subparsers.add_parser("unpack", help="verify and unpack a capsule")
    unpack_parser.add_argument("capsule")
    unpack_parser.add_argument("--out", required=True)
    unpack_parser.add_argument("--policy", help="JSON policy file")
    unpack_parser.add_argument("--key-env", help="environment variable containing HMAC-SHA256 verification key")
    unpack_parser.add_argument("--ed25519-public-key", help="base64 raw Ed25519 public key file")

    scan_parser = subparsers.add_parser("scan", help="scan a text file for capsules and dense payload risks")
    scan_parser.add_argument("text_file")
    scan_parser.add_argument("--policy", help="JSON policy file")
    scan_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    codecs_parser = subparsers.add_parser("codecs", help="list registered capsule codecs")
    codecs_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    keys_parser = subparsers.add_parser("keys", help="manage local Agent Capsule signing keys")
    key_subparsers = keys_parser.add_subparsers(dest="key_command", required=True)
    key_generate = key_subparsers.add_parser("generate", help="generate a raw Ed25519 key pair")
    key_generate.add_argument("--private-key", required=True, help="output path for base64 raw private key")
    key_generate.add_argument("--public-key", required=True, help="output path for base64 raw public key")
    key_generate.add_argument("--force", action="store_true", help="overwrite existing key files")
    key_fingerprint = key_subparsers.add_parser("fingerprint", help="print an Ed25519 public key fingerprint")
    key_fingerprint.add_argument("--public-key", required=True, help="base64 raw Ed25519 public key file")

    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            if args.sign_key_env and args.sign_ed25519_key:
                raise CapsuleError("choose only one signature mode")
            payload, content_type, filename = pack_path(Path(args.path))
            envelope = build_envelope(
                payload,
                codec=args.codec,
                content_type=content_type,
                filename=filename,
                extra_headers=_backend_headers_from_args(args),
            )
            if args.sign_key_env:
                envelope = sign_envelope(
                    envelope,
                    key=key_from_env(args.sign_key_env),
                    key_id=args.signature_key_id,
                )
            if args.sign_ed25519_key:
                envelope = sign_envelope_ed25519(
                    envelope,
                    private_key_bytes=load_private_key_file(Path(args.sign_ed25519_key)),
                    key_id=args.signature_key_id,
                    inline_public_key=not args.no_inline_public_key,
                )
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
            inspection = _inspect_envelope(
                envelope,
                policy,
                key_env=args.key_env,
                ed25519_public_key=args.ed25519_public_key,
            )
            if args.json:
                _print_json(inspection)
            else:
                _print_inspection(inspection)
            return 0
        if args.command == "verify":
            policy = _policy_from_args(args)
            envelope = parse_envelope(Path(args.capsule).read_text(encoding="utf-8"))
            policy.check_metadata(envelope)
            _verify_signature_from_args(envelope, args)
            payload = verify_envelope(envelope)
            policy.check_payload(payload)
            result = {
                "verification": "ok",
                "signature_verification": "ok"
                if envelope.headers.get("signature", SIGNATURE_NONE) != SIGNATURE_NONE
                else "unsigned",
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
            _verify_signature_from_args(envelope, args)
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
            scan_payload = _scan_report(result, policy)
            if args.json:
                _print_json(scan_payload)
            else:
                _print_scan_report(scan_payload)
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
        if args.command == "keys":
            if args.key_command == "generate":
                private_path = Path(args.private_key)
                public_path = Path(args.public_key)
                if not args.force:
                    for path in (private_path, public_path):
                        if path.exists():
                            raise CapsuleError(f"key file already exists: {path}")
                private_key, public_key = generate_ed25519_keypair()
                write_key_file(private_path, private_key)
                private_path.chmod(0o600)
                write_key_file(public_path, public_key)
                print(f"private key: {private_path}")
                print(f"public key: {public_path}")
                print(f"public key fingerprint: {public_key_fingerprint(public_key)}")
                return 0
            if args.key_command == "fingerprint":
                public_key = load_public_key_file(Path(args.public_key))
                print(f"public key fingerprint: {public_key_fingerprint(public_key)}")
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


def _scan_report(result, policy: CapsulePolicy) -> dict[str, object]:
    return {
        "report_type": "agent_capsule_governance_scan",
        "schema_version": 1,
        "disposition": _scan_disposition(result.risk_level),
        "capsules_detected": result.capsules_detected,
        "valid_capsules": result.valid_capsules,
        "invalid_capsules": result.invalid_capsules,
        "risk_level": result.risk_level,
        "reasons": result.reasons,
        "policy": policy_to_dict(policy),
        "findings": [finding.to_dict() for finding in result.findings],
    }


def _scan_disposition(risk_level: str) -> str:
    if risk_level == "high":
        return "block"
    if risk_level == "medium":
        return "review"
    return "allow"


def _print_scan_report(report: dict[str, object]) -> None:
    print("Agent Capsule Governance Report")
    print(f"report type: {report['report_type']}")
    print(f"schema version: {report['schema_version']}")
    print(f"risk level: {report['risk_level']}")
    print(f"disposition: {report['disposition']}")
    print(f"capsules detected: {report['capsules_detected']}")
    print(f"valid capsules: {report['valid_capsules']}")
    print(f"invalid capsules: {report['invalid_capsules']}")
    policy = report["policy"]
    if isinstance(policy, dict):
        print(
            "policy: "
            f"known_codec={policy['require_known_codec']} "
            f"hash_required={policy['require_hash']} "
            f"allow_unsigned={policy['allow_unsigned']} "
            f"max_payload_bytes={policy['max_payload_bytes']}"
        )
        required_modes = policy.get("required_signature_modes")
        if required_modes:
            print(f"policy signatures: {', '.join(str(mode) for mode in required_modes)}")
    reasons = report["reasons"]
    if isinstance(reasons, list):
        for reason in reasons:
            print(f"reason: {reason}")
    findings = report["findings"]
    if isinstance(findings, list):
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            print(
                "finding: "
                f"[{str(finding['risk']).upper()}] {finding['type']} "
                f"line {finding['line']}, column {finding['column']}: {finding['message']}"
            )


def _inspect_envelope(
    envelope,
    policy: CapsulePolicy,
    *,
    key_env: str | None = None,
    ed25519_public_key: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "capsule_version": envelope.headers["capsule_version"],
        "codec": envelope.codec,
        "content_type": envelope.content_type,
        "compression": envelope.headers["compression"],
        "encryption": envelope.headers["encryption"],
        "signature_mode": envelope.headers["signature"],
        "signature_key_id": envelope.headers.get("signature_key_id"),
        "signature_public_key_fingerprint": envelope.headers.get("signature_public_key_fingerprint"),
        "signature_public_key_inline": "signature_public_key" in envelope.headers,
        "signature_verification": _signature_status(envelope),
        "payload_sha256": envelope.payload_sha256,
        "created_by": envelope.headers["created_by"],
        "created_at": envelope.headers["created_at"],
        "payload_character_length": len(envelope.payload_text),
        "codec_metadata": {key: value for key, value in envelope.headers.items() if key.startswith("lmcodec_")},
        "risk_notes": _risk_notes(envelope),
    }
    try:
        if envelope.headers.get("signature") == SIGNATURE_HMAC_SHA256 and key_env:
            verify_signature(envelope, key=key_from_env(key_env))
            result["signature_verification"] = "ok"
        if envelope.headers.get("signature") == SIGNATURE_ED25519:
            if ed25519_public_key:
                verify_ed25519_signature(
                    envelope,
                    public_key_bytes=load_public_key_file(Path(ed25519_public_key)),
                )
                result["signature_verification"] = "ok"
            elif envelope.headers.get("signature_public_key"):
                verify_ed25519_signature(envelope)
                result["signature_verification"] = "ok"
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
    if inspection.get("signature_key_id"):
        print(f"signature key id: {inspection['signature_key_id']}")
    if inspection.get("signature_public_key_fingerprint"):
        print(f"signature public key fingerprint: {inspection['signature_public_key_fingerprint']}")
        print(f"signature public key inline: {inspection['signature_public_key_inline']}")
    print(f"signature verification: {inspection['signature_verification']}")
    print(f"payload sha256: {inspection['payload_sha256']}")
    metadata = inspection["codec_metadata"]
    if isinstance(metadata, dict):
        for key in sorted(metadata):
            value = str(metadata[key])
            if key.endswith("_json_b64"):
                print(f"{key}: <{len(value)} chars>")
            else:
                print(f"{key}: {value}")
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
    if envelope.headers.get("signature") == SIGNATURE_HMAC_SHA256:
        notes.append("HMAC signature proves shared-secret authenticity, not public identity")
    if envelope.headers.get("signature") == SIGNATURE_ED25519:
        notes.append("Ed25519 signature proves public-key authenticity only if the key is trusted")
        if envelope.headers.get("signature_public_key"):
            notes.append("inline public key verifies the signature but does not establish trust")
    if envelope.headers.get("encryption") == "none":
        notes.append("payload is not encrypted")
    if envelope.codec != "base64":
        notes.append("non-base64 codec requires matching decoder support")
    return notes


def _verify_signature_from_args(envelope, args: argparse.Namespace) -> None:
    mode = envelope.headers.get("signature", SIGNATURE_NONE)
    if mode == SIGNATURE_NONE:
        return
    if mode == SIGNATURE_HMAC_SHA256:
        key_env = getattr(args, "key_env", None)
        if not key_env:
            raise CapsuleError(f"{mode} signature requires --key-env")
        verify_signature(envelope, key=key_from_env(key_env))
        return
    if mode == SIGNATURE_ED25519:
        public_key_path = getattr(args, "ed25519_public_key", None)
        if public_key_path:
            verify_ed25519_signature(envelope, public_key_bytes=load_public_key_file(Path(public_key_path)))
        else:
            verify_ed25519_signature(envelope)
        return
    raise CapsuleError(f"unsupported signature mode: {mode}")


def _signature_status(envelope) -> str:
    mode = envelope.headers.get("signature", SIGNATURE_NONE)
    return "unsigned" if mode == SIGNATURE_NONE else "not_checked"


def _backend_headers_from_args(args: argparse.Namespace) -> dict[str, str]:
    if args.codec == "lmcodec-ngram-v2":
        if not args.model:
            raise CapsuleError("lmcodec-ngram-v2 requires --model")
        return ngram_v2_headers_from_model_path(args.model)
    if args.model:
        raise CapsuleError(f"--model is not supported for codec: {args.codec}")
    return {}


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
