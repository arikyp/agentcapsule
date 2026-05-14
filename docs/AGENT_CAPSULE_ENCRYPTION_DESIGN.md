# Agent Capsule Encryption Design

This document specifies the encryption layer for the Agent Capsule Protocol. The goal is to provide confidentiality for capsule payloads while maintaining the existing integrity and authenticity guarantees.

## Decision Summary

- Add an encryption mode named `aes-256-gcm`.
- Use AES-GCM for authenticated encryption with associated data (AEAD).
- Support two primary key management modes:
    - **Shared Secret:** Sender and receiver share a pre-distributed symmetric key.
    - **Asymmetric Handoff (X25519):** Sender encrypts for a specific receiver's public key (to be designed).
- Encryption applies to the **decoded payload bytes**.
- The `payload_sha256` header continues to represent the SHA256 of the **plaintext** payload.
- Integrity is provided by the GCM tag and the existing signature (HMAC or Ed25519) which covers the headers (including the GCM tag and nonce).

## Encryption Mode: aes-256-gcm

Proposed metadata:

```text
encryption: aes-256-gcm
encryption_key_id: <key lookup hint>
encryption_nonce: <base64 encoded 12-byte nonce>
encryption_tag: <base64 encoded 16-byte GCM tag>
```

### Why AES-GCM?
AES-GCM is the industry standard for high-performance AEAD. It provides both confidentiality and authentication. By including the nonce and tag in the capsule headers, we ensure they are covered by the capsule's signature.

## Key Management Modes

### 1. Shared Secret Mode (Symmetric)
- Similar to HMAC-SHA256 signing.
- Requires a 32-byte shared secret.
- `encryption_key_id` helps the receiver identify which local key to use.

### 2. Asymmetric Mode (X25519) - Deferred
- Use X25519 for Diffie-Hellman key exchange.
- Sender uses their private key and receiver's public key to derive a shared secret.
- Requires `encryption_public_key` header (sender's ephemeral or static public key).

## Implementation Details

### Workflow: Pack (Sender)
1. Prepare plaintext payload bytes.
2. Calculate `payload_sha256` of plaintext.
3. Generate a random 12-byte nonce.
4. Encrypt payload using AES-256-GCM with the selected key and nonce.
5. The output is ciphertext + 16-byte tag.
6. Set headers:
    - `encryption`: `aes-256-gcm`
    - `encryption_nonce`: base64(nonce)
    - `encryption_tag`: base64(tag)
    - `payload_sha256`: <plaintext-sha256>
7. Encode **ciphertext** using the selected codec (e.g., base64).
8. Sign the envelope (as usual, covers all headers).

### Workflow: Unpack (Receiver)
1. Parse envelope and verify signature (if any).
2. Apply policy.
3. Resolve encryption key using `encryption_key_id`.
4. Decode `payload_text` to get ciphertext.
5. Decode `encryption_nonce` and `encryption_tag`.
6. Decrypt ciphertext using AES-256-GCM, nonce, and tag.
7. Verify that decrypted plaintext matches `payload_sha256`.

## Policy Extensions

```json
{
  "require_encryption": true,
  "allowed_encryption_modes": ["aes-256-gcm"],
  "trusted_encryption_key_ids": ["team-shared-2026"]
}
```

## CLI Shape

```bash
# Encrypting with a shared secret from environment
export CAPSULE_ENCRYPTION_KEY=$(openssl rand -base64 32)
capsule pack payload.bin --out capsule.txt \
  --encrypt aes-256-gcm \
  --encryption-key-env CAPSULE_ENCRYPTION_KEY \
  --encryption-key-id team-shared-2026

# Decrypting
capsule unpack capsule.txt --out ./decoded/ \
  --encryption-key-env CAPSULE_ENCRYPTION_KEY
```

## Test Plan
- Verify that payload is indeed encrypted (ciphertext is different from plaintext).
- Verify that decryption recovers original plaintext.
- Verify that tampering with ciphertext, nonce, or tag results in decryption failure.
- Verify that policy can enforce encryption.
- Verify that signature verification still works and covers encryption metadata.

## Open Questions
- Should we encrypt the manifest as well? (V0 keeps manifest in headers, which are plaintext).
- Should we support `fernet` as a simpler alternative for Python users?
- How to handle large payloads where GCM might have limits (not an issue for typical agent capsules)?
