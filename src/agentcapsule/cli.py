"""Agent Capsule command-line interface."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from agentcapsule.audit import audit_event, disposition_from_risk, disposition_from_status, scan_audit_event
from agentcapsule.backends import known_codecs
from agentcapsule.envelope import build_envelope, parse_envelope, render_envelope, verify_envelope
from agentcapsule.errors import CapsuleError
from agentcapsule.fetcher import (
    DEFAULT_ALLOWED_SCHEMES,
    DEFAULT_BLOCK_PRIVATE_NETWORKS,
    DEFAULT_MAX_DOWNLOAD_BYTES,
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_TIMEOUT_SECONDS,
)
from agentcapsule.manifest import (
    DEFAULT_CAPSULE_TYPE,
    DELIVERY_MODES,
    pack_path_with_manifest,
    unpack_payload,
    verify_manifest_matches_payload,
)
from agentcapsule.policy import DEFAULT_POLICY, CapsulePolicy, load_policy, policy_to_dict
from agentcapsule.registry import list_codecs
from agentcapsule.receiver import ingest_messages as ingest_messages_api
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
from agentcapsule.trust import (
    SignatureRegistry,
    SignatureTrustResult,
    load_signature_registry,
    registry_entry_from_public_key_file,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="capsule")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pack_parser = subparsers.add_parser("pack", help="pack a file or directory into an Agent Capsule")
    pack_parser.add_argument("path")
    pack_parser.add_argument("--out", required=True)
    pack_parser.add_argument("--codec", choices=known_codecs(), default="base64")
    pack_parser.add_argument("--model", help="LMCodec model JSON for model-backed capsule codecs")
    pack_parser.add_argument("--capsule-type", default=DEFAULT_CAPSULE_TYPE)
    pack_parser.add_argument("--created-by", default="local")
    pack_parser.add_argument("--task-id", default="")
    pack_parser.add_argument("--delivery-mode", choices=DELIVERY_MODES, default="inline")
    pack_parser.add_argument("--delivery-uri", help="capsule URI for reference delivery mode")
    pack_parser.add_argument("--compression", choices=["none", "zstd"], default="none")
    pack_parser.add_argument(
        "--requested-capability",
        action="append",
        default=[],
        help="capability requested from the receiver; repeatable",
    )
    pack_parser.add_argument(
        "--policy-hint",
        action="append",
        default=[],
        metavar="KEY=true|false",
        help="boolean policy hint for the receiver; repeatable",
    )
    pack_parser.add_argument("--sign-key-env", help="environment variable containing HMAC-SHA256 signing key")
    pack_parser.add_argument("--sign-ed25519-key", help="base64 raw Ed25519 private key file")
    pack_parser.add_argument(
        "--no-inline-public-key",
        action="store_true",
        help="omit inline Ed25519 public key metadata from signed capsules",
    )
    pack_parser.add_argument("--signature-key-id", help="optional signature key identifier written to capsule metadata")
    pack_parser.add_argument("--encrypt", choices=["aes-256-gcm"], help="encrypt the payload")
    pack_parser.add_argument("--encryption-key-env", help="environment variable containing encryption key")
    pack_parser.add_argument("--encryption-key-id", help="optional encryption key identifier written to capsule metadata")

    inspect_parser = subparsers.add_parser("inspect", help="inspect capsule metadata")
    inspect_parser.add_argument("capsule")
    inspect_parser.add_argument("--policy", help="JSON policy file")
    inspect_parser.add_argument("--key-env", help="environment variable containing HMAC-SHA256 verification key")
    inspect_parser.add_argument("--encryption-key-env", help="environment variable containing decryption key")
    inspect_parser.add_argument("--ed25519-public-key", help="base64 raw Ed25519 public key file")
    inspect_parser.add_argument("--signature-registry", help="local JSON signature trust registry")
    inspect_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    inspect_parser.add_argument("--audit-json", action="store_true", help="emit structured audit event JSON")

    verify_parser = subparsers.add_parser("verify", help="verify capsule payload hash")
    verify_parser.add_argument("capsule")
    verify_parser.add_argument("--policy", help="JSON policy file")
    verify_parser.add_argument("--key-env", help="environment variable containing HMAC-SHA256 verification key")
    verify_parser.add_argument("--encryption-key-env", help="environment variable containing decryption key")
    verify_parser.add_argument("--ed25519-public-key", help="base64 raw Ed25519 public key file")
    verify_parser.add_argument("--signature-registry", help="local JSON signature trust registry")
    verify_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    verify_parser.add_argument("--audit-json", action="store_true", help="emit structured audit event JSON")

    unpack_parser = subparsers.add_parser("unpack", help="verify and unpack a capsule")
    unpack_parser.add_argument("capsule")
    unpack_parser.add_argument("--out", required=True)
    unpack_parser.add_argument("--policy", help="JSON policy file")
    unpack_parser.add_argument("--key-env", help="environment variable containing HMAC-SHA256 verification key")
    unpack_parser.add_argument("--encryption-key-env", help="environment variable containing decryption key")
    unpack_parser.add_argument("--ed25519-public-key", help="base64 raw Ed25519 public key file")
    unpack_parser.add_argument("--signature-registry", help="local JSON signature trust registry")
    unpack_parser.add_argument("--audit-json", action="store_true", help="emit structured audit event JSON")

    scan_parser = subparsers.add_parser("scan", help="scan a text file for capsules and dense payload risks")
    scan_parser.add_argument("text_file")
    scan_parser.add_argument("--policy", help="JSON policy file")
    scan_parser.add_argument("--signature-registry", help="local JSON signature trust registry")
    scan_parser.add_argument("--encryption-key-env", help="environment variable containing decryption key")
    scan_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    scan_parser.add_argument("--audit-json", action="store_true", help="emit structured audit event JSON")

    ingest_parser = subparsers.add_parser("ingest", help="ingest a message transcript and unpack capsules safely")
    ingest_parser.add_argument("text_file", nargs="?")
    ingest_parser.add_argument("--text-file", dest="text_file_flag", help="text transcript file to ingest")
    ingest_parser.add_argument("--out", required=True, help="sandbox output directory for unpacked files")
    ingest_parser.add_argument("--policy", help="JSON policy file")
    ingest_parser.add_argument("--key-env", help="environment variable containing HMAC-SHA256 verification key")
    ingest_parser.add_argument("--encryption-key-env", help="environment variable containing decryption key")
    ingest_parser.add_argument("--ed25519-public-key", help="base64 raw Ed25519 public key file")
    ingest_parser.add_argument("--signature-registry", help="local JSON signature trust registry")
    ingest_parser.add_argument("--no-fetch-references", action="store_true", help="detect references but do not fetch")
    ingest_parser.add_argument("--resumable", action="store_true", help="attempt to resume partial reference downloads")
    ingest_parser.add_argument(
        "--strict",
        "--fail-on-invalid",
        dest="strict_ingest",
        action="store_true",
        help="exit non-zero when disposition is block or malformed/invalid/failed capsule ingestion is detected",
    )
    ingest_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    policy_parser = subparsers.add_parser("policy", help="show effective policy and fetch defaults")
    policy_subparsers = policy_parser.add_subparsers(dest="policy_command", required=True)
    policy_show_parser = policy_subparsers.add_parser("show", help="show effective policy")
    policy_show_parser.add_argument("--policy", help="JSON policy file")
    policy_show_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    codecs_parser = subparsers.add_parser("codecs", help="list registered capsule codecs")
    codecs_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    reference_parser = subparsers.add_parser("reference", help="emit a capsule reference descriptor")
    reference_parser.add_argument("capsule")
    reference_parser.add_argument("--uri", required=True, help="URI where the full capsule can be fetched")
    reference_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    fetch_parser = subparsers.add_parser("fetch", help="fetch a capsule from a URI or reference")
    fetch_parser.add_argument("--uri", help="capsule URI to fetch")
    fetch_parser.add_argument("--reference", help="JSON reference descriptor file")
    fetch_parser.add_argument("--out", required=True, help="output path for the fetched capsule")
    fetch_parser.add_argument("--sha256", help="expected capsule SHA256")
    fetch_parser.add_argument("--resumable", action="store_true", help="attempt to resume a partial download")

    keys_parser = subparsers.add_parser("keys", help="manage local Agent Capsule signing keys")
    key_subparsers = keys_parser.add_subparsers(dest="key_command", required=True)
    key_generate = key_subparsers.add_parser("generate", help="generate a raw Ed25519 key pair")
    key_generate.add_argument("--private-key", required=True, help="output path for base64 raw private key")
    key_generate.add_argument("--public-key", required=True, help="output path for base64 raw public key")
    key_generate.add_argument("--force", action="store_true", help="overwrite existing key files")
    key_fingerprint = key_subparsers.add_parser("fingerprint", help="print an Ed25519 public key fingerprint")
    key_fingerprint.add_argument("--public-key", required=True, help="base64 raw Ed25519 public key file")
    key_registry_entry = key_subparsers.add_parser("registry-entry", help="emit a local registry key entry")
    key_registry_entry.add_argument("--key-id", required=True)
    key_registry_entry.add_argument("--public-key", required=True, help="base64 raw Ed25519 public key file")
    key_registry_entry.add_argument("--publisher")
    key_registry_entry.add_argument("--status", choices=("trusted", "revoked"), default="trusted")
    key_registry_entry.add_argument("--note")
    key_registry_entry.add_argument("--json", action="store_true", help="emit raw JSON object")

    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            if args.sign_key_env and args.sign_ed25519_key:
                raise CapsuleError("choose only one signature mode")
            
            encryption_key = None
            if args.encrypt:
                if not args.encryption_key_env:
                    raise CapsuleError(f"--encrypt {args.encrypt} requires --encryption-key-env")
                # Try base64 decoding first, fall back to utf-8
                raw_key = key_from_env(args.encryption_key_env)
                import base64
                try:
                    encryption_key = base64.b64decode(raw_key, validate=True)
                except Exception:
                    encryption_key = raw_key
                if len(encryption_key) != 32:
                    raise CapsuleError("encryption key must be 32 bytes (raw or base64)")

            packed = pack_path_with_manifest(Path(args.path))
            envelope = build_envelope(
                packed.payload,
                codec=args.codec,
                content_type=packed.content_type,
                filename=packed.filename,
                created_by=args.created_by,
                capsule_type=args.capsule_type,
                task_id=args.task_id,
                manifest_files=packed.manifest_files,
                requested_capabilities=args.requested_capability,
                policy_hints=_policy_hints_from_args(args),
                delivery_mode=args.delivery_mode,
                delivery_uri=args.delivery_uri,
                compression=args.compression,
                encryption_key=encryption_key,
                encryption_key_id=args.encryption_key_id,
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
            print(f"content type: {packed.content_type}")
            print(f"payload bytes: {len(packed.payload)}")
            print(f"payload sha256: {envelope.payload_sha256}")
            return 0
        if args.command == "inspect":
            policy = _policy_from_args(args)
            signature_registry = _signature_registry_from_args(args)
            envelope = parse_envelope(Path(args.capsule).read_text(encoding="utf-8"))
            policy.check_metadata(envelope)
            inspection = _inspect_envelope(
                envelope,
                policy,
                key_env=args.key_env,
                encryption_key_env=args.encryption_key_env,
                ed25519_public_key=args.ed25519_public_key,
                signature_registry=signature_registry,
            )
            if args.audit_json:
                _print_json(
                    audit_event(
                        operation="inspect",
                        disposition=disposition_from_status(
                            ok=inspection.get("verification_status") == "ok",
                            signature_trust=_dict_or_none(inspection.get("signature_trust")),
                        ),
                        policy=policy,
                        subject=str(args.capsule),
                        result=inspection,
                    )
                )
            elif args.json:
                _print_json(inspection)
            else:
                _print_inspection(inspection)
            return 0
        if args.command == "verify":
            policy = _policy_from_args(args)
            signature_registry = _signature_registry_from_args(args)
            encryption_key = _encryption_key_from_args(args)
            envelope = parse_envelope(Path(args.capsule).read_text(encoding="utf-8"))
            policy.check_metadata(envelope)
            trust = _verify_signature_from_args(envelope, args, signature_registry=signature_registry)
            policy.check_signature_trust(trust.status if trust else None)
            payload = verify_envelope(envelope, encryption_key=encryption_key)
            policy.check_payload(payload)
            verify_manifest_matches_payload(
                manifest=envelope.capsule_manifest,
                payload=payload,
                content_type=envelope.content_type,
                filename=envelope.headers.get("filename"),
            )
            result = {
                "verification": "ok",
                "signature_verification": "ok"
                if envelope.headers.get("signature", SIGNATURE_NONE) != SIGNATURE_NONE
                else "unsigned",
                "payload_bytes": len(payload),
                "payload_sha256": envelope.payload_sha256,
                "codec": envelope.codec,
                "content_type": envelope.content_type,
                "capsule_manifest": envelope.capsule_manifest,
                "signature_trust": trust.to_dict() if trust else None,
            }
            if args.audit_json:
                _print_json(
                    audit_event(
                        operation="verify",
                        disposition=disposition_from_status(ok=True, signature_trust=result["signature_trust"]),
                        policy=policy,
                        subject=str(args.capsule),
                        result=result,
                    )
                )
            elif args.json:
                _print_json(result)
            else:
                print("verification: ok")
                print(f"payload bytes: {len(payload)}")
            return 0
        if args.command == "unpack":
            policy = _policy_from_args(args)
            signature_registry = _signature_registry_from_args(args)
            encryption_key = _encryption_key_from_args(args)
            envelope = parse_envelope(Path(args.capsule).read_text(encoding="utf-8"))
            policy.check_metadata(envelope)
            trust = _verify_signature_from_args(envelope, args, signature_registry=signature_registry)
            policy.check_signature_trust(trust.status if trust else None)
            payload = verify_envelope(envelope, encryption_key=encryption_key)
            policy.check_payload(payload)
            verify_manifest_matches_payload(
                manifest=envelope.capsule_manifest,
                payload=payload,
                content_type=envelope.content_type,
                filename=envelope.headers.get("filename"),
            )
            written = unpack_payload(
                payload,
                envelope.content_type,
                Path(args.out),
                filename=envelope.headers.get("filename"),
            )
            result = {
                "verification": "ok",
                "signature_verification": "ok"
                if envelope.headers.get("signature", SIGNATURE_NONE) != SIGNATURE_NONE
                else "unsigned",
                "signature_trust": trust.to_dict() if trust else None,
                "payload_bytes": len(payload),
                "payload_sha256": envelope.payload_sha256,
                "codec": envelope.codec,
                "content_type": envelope.content_type,
                "capsule_manifest": envelope.capsule_manifest,
                "files_written": [str(path) for path in written],
            }
            if args.audit_json:
                _print_json(
                    audit_event(
                        operation="unpack",
                        disposition=disposition_from_status(ok=True, signature_trust=result["signature_trust"]),
                        policy=policy,
                        subject=str(args.capsule),
                        result=result,
                    )
                )
            else:
                print("verification: ok")
                print(f"files written: {len(written)}")
                for path in written:
                    print(path)
            return 0
        if args.command == "scan":
            policy = _policy_from_args(args)
            signature_registry = _signature_registry_from_args(args)
            result = scan_text(
                Path(args.text_file).read_text(encoding="utf-8"),
                policy=policy,
                signature_registry=signature_registry,
                encryption_key=_encryption_key_from_args(args),
            )
            scan_payload = _scan_report(result, policy)
            if args.audit_json:
                _print_json(scan_audit_event(report=scan_payload, policy=policy, subject=str(args.text_file)))
            elif args.json:
                _print_json(scan_payload)
            else:
                _print_scan_report(scan_payload)
            return 0
        if args.command == "ingest":
            policy = _policy_from_args(args)
            signature_registry = _signature_registry_from_args(args)
            text_path = _ingest_text_file_from_args(args)
            result = ingest_messages_api(
                messages=[Path(text_path).read_text(encoding="utf-8")],
                out_dir=Path(args.out),
                policy=policy,
                key_env=args.key_env,
                encryption_key_env=args.encryption_key_env,
                ed25519_public_key=args.ed25519_public_key,
                signature_registry=signature_registry,
                fetch_references=not args.no_fetch_references,
                resumable_fetch=args.resumable,
            )
            payload = result.to_dict()
            if args.json:
                _print_json(payload)
            else:
                print(f"inline capsules: {len(result.inline_capsules)}")
                print(f"references: {len(result.references)}")
                print(f"malformed blocks: {result.malformed_blocks}")
                print(f"unpacked files: {len(result.unpacked_files)}")
                for file_path in result.unpacked_files:
                    print(file_path)
            if args.strict_ingest and (result.has_failures or payload.get("disposition") == "block"):
                print(_ingest_strict_failure_summary(result, disposition=str(payload.get("disposition"))), file=sys.stderr)
                return 2
            return 0
        if args.command == "policy":
            if args.policy_command != "show":
                raise CapsuleError("unsupported policy command")
            policy_source = "file" if args.policy else "defaults"
            policy_path = str(Path(args.policy)) if args.policy else None
            policy = _policy_from_args(args)
            payload = {
                "report_type": "agent_capsule_effective_policy",
                "schema_version": 1,
                "policy_source": policy_source,
                "policy_path": policy_path,
                "effective_policy": policy_to_dict(policy),
                "fetch_policy": {
                    "allowed_schemes": sorted(DEFAULT_ALLOWED_SCHEMES),
                    "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
                    "max_download_bytes": DEFAULT_MAX_DOWNLOAD_BYTES,
                    "max_redirects": DEFAULT_MAX_REDIRECTS,
                    "follow_redirects": False,
                    "block_private_networks": DEFAULT_BLOCK_PRIVATE_NETWORKS,
                    "resumable_supported": True,
                },
            }
            if args.json:
                _print_json(payload)
            else:
                print(f"policy source: {policy_source}")
                if policy_path:
                    print(f"policy path: {policy_path}")
                print(json.dumps(payload["effective_policy"], indent=2, sort_keys=True))
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
        if args.command == "reference":
            descriptor = _capsule_reference(Path(args.capsule), args.uri)
            if args.json:
                _print_json(descriptor)
            else:
                print(f"reference type: {descriptor['reference_type']}")
                print(f"capsule uri: {descriptor['capsule_uri']}")
                print(f"capsule sha256: {descriptor['capsule_sha256']}")
                print(f"payload sha256: {descriptor['payload_sha256']}")
                signature = descriptor["signature"]
                if isinstance(signature, dict):
                    print(f"signature mode: {signature['mode']}")
                    if signature.get("key_id"):
                        print(f"signature key id: {signature['key_id']}")
                    if signature.get("public_key_fingerprint"):
                        print(f"signature public key fingerprint: {signature['public_key_fingerprint']}")
            return 0
        if args.command == "fetch":
            from agentcapsule.fetcher import fetch_capsule
            uri = args.uri
            expected_sha = args.sha256
            if args.reference:
                ref = json.loads(Path(args.reference).read_text(encoding="utf-8"))
                if ref.get("reference_type") != "agent_capsule_reference":
                    raise CapsuleError("invalid reference descriptor type")
                uri = ref["capsule_uri"]
                expected_sha = ref["capsule_sha256"]
            if not uri:
                raise CapsuleError("fetch requires --uri or --reference")
            
            fetch_capsule(uri, expected_sha256=expected_sha, save_path=Path(args.out), resumable=args.resumable)
            print(f"capsule fetched: {args.out}")
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
            if args.key_command == "registry-entry":
                entry = registry_entry_from_public_key_file(
                    key_id=args.key_id,
                    public_key_path=Path(args.public_key),
                    publisher=args.publisher,
                    status=args.status,
                    note=args.note,
                )
                if args.json:
                    _print_json(entry)
                else:
                    _print_json({"keys": [entry]})
                return 0
    except CapsuleError as exc:
        if _wants_audit_json(args):
            _print_json(_error_audit_event(args, str(exc)))
            return 2
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        if _wants_audit_json(args):
            _print_json(_error_audit_event(args, str(exc)))
            return 2
        print(str(exc), file=sys.stderr)
        return 2

    parser.error("unreachable command")
    return 2


def _encryption_key_from_args(args: argparse.Namespace) -> bytes | None:
    env_name = getattr(args, "encryption_key_env", None)
    if not env_name:
        return None
    raw_key = key_from_env(env_name)
    import base64
    try:
        encryption_key = base64.b64decode(raw_key, validate=True)
    except Exception:
        encryption_key = raw_key
    if len(encryption_key) != 32:
        raise CapsuleError("encryption key must be 32 bytes (raw or base64)")
    return encryption_key


def _policy_from_args(args: argparse.Namespace) -> CapsulePolicy:
    policy_path = getattr(args, "policy", None)
    if policy_path:
        return load_policy(Path(policy_path))
    return DEFAULT_POLICY


def _ingest_text_file_from_args(args: argparse.Namespace) -> str:
    positional = getattr(args, "text_file", None)
    flagged = getattr(args, "text_file_flag", None)
    if positional and flagged:
        raise CapsuleError("choose either positional text_file or --text-file")
    path = flagged or positional
    if not path:
        raise CapsuleError("ingest requires text_file positional argument or --text-file")
    return str(path)


def _wants_audit_json(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "audit_json", False))


def _error_audit_event(args: argparse.Namespace, error: str) -> dict[str, object]:
    result = {
        "verification": "failed",
        "verification_error": error,
    }
    return audit_event(
        operation=str(getattr(args, "command", "unknown")),
        disposition="block",
        policy=DEFAULT_POLICY,
        subject=str(getattr(args, "capsule", getattr(args, "text_file", None))),
        reasons=[error],
        result=result,
    )


def _signature_registry_from_args(args: argparse.Namespace) -> SignatureRegistry | None:
    registry_path = getattr(args, "signature_registry", None)
    if registry_path:
        return load_signature_registry(Path(registry_path))
    return None


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
    return disposition_from_risk(risk_level)


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
    encryption_key_env: str | None = None,
    ed25519_public_key: str | None = None,
    signature_registry: SignatureRegistry | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "capsule_version": envelope.headers["capsule_version"],
        "codec": envelope.codec,
        "content_type": envelope.content_type,
        "capsule_manifest": envelope.capsule_manifest,
        "compression": envelope.headers["compression"],
        "encryption": envelope.headers["encryption"],
        "encryption_key_id": envelope.headers.get("encryption_key_id"),
        "signature_mode": envelope.headers["signature"],
        "signature_key_id": envelope.headers.get("signature_key_id"),
        "signature_public_key_fingerprint": envelope.headers.get("signature_public_key_fingerprint"),
        "signature_public_key_inline": "signature_public_key" in envelope.headers,
        "signature_verification": _signature_status(envelope),
        "signature_trust": None,
        "payload_sha256": envelope.payload_sha256,
        "created_by": envelope.headers["created_by"],
        "created_at": envelope.headers["created_at"],
        "payload_character_length": len(envelope.payload_text),
        "codec_metadata": {key: value for key, value in envelope.headers.items() if key.startswith("codec_")},
        "risk_notes": _risk_notes(envelope),
    }
    try:
        if envelope.headers.get("signature") == SIGNATURE_HMAC_SHA256 and key_env:
            verify_signature(envelope, key=key_from_env(key_env))
            result["signature_verification"] = "ok"
        if envelope.headers.get("signature") == SIGNATURE_ED25519:
            trust = _signature_trust(envelope, signature_registry)
            result["signature_trust"] = trust.to_dict() if trust else None
            if ed25519_public_key:
                verify_ed25519_signature(
                    envelope,
                    public_key_bytes=load_public_key_file(Path(ed25519_public_key)),
                )
                result["signature_verification"] = "ok"
            elif envelope.headers.get("signature_public_key"):
                verify_ed25519_signature(envelope)
                result["signature_verification"] = "ok"
            elif trust and trust.public_key is not None:
                verify_ed25519_signature(envelope, public_key_bytes=trust.public_key)
                result["signature_verification"] = "ok"
            policy.check_signature_trust(trust.status if trust else None)
        
        encryption_key = None
        if encryption_key_env:
            raw_key = key_from_env(encryption_key_env)
            import base64
            try:
                encryption_key = base64.b64decode(raw_key, validate=True)
            except Exception:
                encryption_key = raw_key

        payload = verify_envelope(envelope, encryption_key=encryption_key)
        policy.check_payload(payload)
        verify_manifest_matches_payload(
            manifest=envelope.capsule_manifest,
            payload=payload,
            content_type=envelope.content_type,
            filename=envelope.headers.get("filename"),
        )
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
    manifest = inspection.get("capsule_manifest")
    if isinstance(manifest, dict):
        print(f"capsule type: {manifest['capsule_type']}")
        delivery = manifest.get("delivery")
        if isinstance(delivery, dict):
            print(f"delivery mode: {delivery['mode']}")
            if delivery.get("uri"):
                print(f"delivery uri: {delivery['uri']}")
        if manifest.get("task_id"):
            print(f"task id: {manifest['task_id']}")
        files = manifest.get("files")
        if isinstance(files, list):
            print(f"manifest files: {len(files)}")
        capabilities = manifest.get("requested_capabilities")
        if isinstance(capabilities, list) and capabilities:
            print(f"requested capabilities: {', '.join(str(item) for item in capabilities)}")
    print(f"compression: {inspection['compression']}")
    print(f"encryption: {inspection['encryption']}")
    print(f"signature mode: {inspection['signature_mode']}")
    if inspection.get("signature_key_id"):
        print(f"signature key id: {inspection['signature_key_id']}")
    if inspection.get("signature_public_key_fingerprint"):
        print(f"signature public key fingerprint: {inspection['signature_public_key_fingerprint']}")
        print(f"signature public key inline: {inspection['signature_public_key_inline']}")
    print(f"signature verification: {inspection['signature_verification']}")
    if inspection.get("signature_trust"):
        trust = inspection["signature_trust"]
        if isinstance(trust, dict):
            print(f"signature trust: {trust['status']} ({trust['reason']})")
            if trust.get("organization"):
                print(f"signature organization: {trust['organization']}")
            if trust.get("domain"):
                print(f"signature domain: {trust['domain']}")
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


def _verify_signature_from_args(
    envelope,
    args: argparse.Namespace,
    *,
    signature_registry: SignatureRegistry | None = None,
) -> SignatureTrustResult | None:
    mode = envelope.headers.get("signature", SIGNATURE_NONE)
    if mode == SIGNATURE_NONE:
        return None
    if mode == SIGNATURE_HMAC_SHA256:
        key_env = getattr(args, "key_env", None)
        if not key_env:
            raise CapsuleError(f"{mode} signature requires --key-env")
        verify_signature(envelope, key=key_from_env(key_env))
        return None
    if mode == SIGNATURE_ED25519:
        trust = _signature_trust(envelope, signature_registry)
        public_key_path = getattr(args, "ed25519_public_key", None)
        if public_key_path:
            verify_ed25519_signature(envelope, public_key_bytes=load_public_key_file(Path(public_key_path)))
        elif trust and trust.public_key is not None:
            verify_ed25519_signature(envelope, public_key_bytes=trust.public_key)
        else:
            verify_ed25519_signature(envelope)
        return trust
    raise CapsuleError(f"unsupported signature mode: {mode}")


def _signature_trust(envelope, signature_registry: SignatureRegistry | None) -> SignatureTrustResult | None:
    if envelope.headers.get("signature") != SIGNATURE_ED25519:
        return None
    if signature_registry is None:
        if envelope.headers.get("signature_public_key"):
            return SignatureTrustResult(
                "untrusted",
                "inline public key is not trusted by a registry",
                envelope.headers.get("signature_key_id"),
                envelope.headers.get("signature_public_key_fingerprint"),
            )
        return None
    return signature_registry.resolve(
        key_id=envelope.headers.get("signature_key_id"),
        fingerprint=envelope.headers.get("signature_public_key_fingerprint"),
    )


def _signature_status(envelope) -> str:
    mode = envelope.headers.get("signature", SIGNATURE_NONE)
    return "unsigned" if mode == SIGNATURE_NONE else "not_checked"


def _backend_headers_from_args(args: argparse.Namespace) -> dict[str, str]:
    if args.model:
        raise CapsuleError(f"--model is not supported for codec: {args.codec}")
    return {}


def _policy_hints_from_args(args: argparse.Namespace) -> dict[str, object]:
    hints: dict[str, object] = {}
    for raw in getattr(args, "policy_hint", []):
        if "=" not in raw:
            raise CapsuleError(f"invalid policy hint: {raw}")
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().lower()
        if not key:
            raise CapsuleError("policy hint key is required")
        if value == "true":
            hints[key] = True
        elif value == "false":
            hints[key] = False
        else:
            raise CapsuleError(f"policy hint value must be true or false: {raw}")
    return hints


def _capsule_reference(path: Path, uri: str) -> dict[str, object]:
    raw = path.read_bytes()
    envelope = parse_envelope(raw.decode("utf-8"))
    signature_headers = envelope.headers
    return {
        "reference_type": "agent_capsule_reference",
        "schema_version": 1,
        "capsule_uri": uri,
        "capsule_sha256": hashlib.sha256(raw).hexdigest(),
        "capsule_version": envelope.headers["capsule_version"],
        "payload_sha256": envelope.payload_sha256,
        "codec": envelope.codec,
        "content_type": envelope.content_type,
        "created_by": envelope.headers["created_by"],
        "created_at": envelope.headers["created_at"],
        "capsule_manifest": envelope.capsule_manifest,
        "signature": {
            "mode": signature_headers.get("signature", SIGNATURE_NONE),
            "key_id": signature_headers.get("signature_key_id"),
            "public_key_fingerprint": signature_headers.get("signature_public_key_fingerprint"),
            "value_encoding": signature_headers.get("signature_value_encoding"),
            "value": signature_headers.get("signature_value"),
        },
    }


def _codec_to_dict(codec) -> dict[str, object]:
    return {
        "name": codec.name,
        "purpose": codec.purpose,
        "stability": codec.stability,
        "requires_external_model": codec.requires_external_model,
        "notes": codec.notes,
    }


def _ingest_strict_failure_summary(result, *, disposition: str | None = None) -> str:
    invalid_inline = sum(1 for item in result.inline_capsules if item.get("status") == "invalid")
    invalid_references = sum(1 for item in result.references if item.get("status") == "invalid")
    failed_references = sum(1 for item in result.references if item.get("status") == "failed")
    disposition_note = f", disposition={disposition}" if disposition else ""
    return (
        "ingest strict mode failed: "
        f"malformed_blocks={result.malformed_blocks}, "
        f"invalid_inline={invalid_inline}, "
        f"invalid_references={invalid_references}, "
        f"failed_references={failed_references}"
        f"{disposition_note}"
    )


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _dict_or_none(value: object) -> dict[str, object] | None:
    return value if isinstance(value, dict) else None


if __name__ == "__main__":
    raise SystemExit(main())
