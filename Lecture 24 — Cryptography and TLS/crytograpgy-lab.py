#!/usr/bin/env python3
"""
EC 441 — Lecture 24 Lab: Cryptography and Security — From Primitives to TLS
Covers: Symmetric encryption, hash functions, RSA arithmetic, Diffie-Hellman,
        HMAC, digital signature verification logic, PKI chain simulation, TLS handshake walkthrough
"""

import hashlib
import hmac
import os
import struct
import base64
import random
import math
from functools import reduce

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Hash Function Properties
# ─────────────────────────────────────────────────────────────────────────────

def section1_hash_properties():
    print("=" * 65)
    print("SECTION 1: Hash Function Properties")
    print("=" * 65)

    def sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    # Fixed output size regardless of input size
    inputs = [b"", b"A", b"Hello, World!", b"x" * 1_000_000]
    print("\n  Fixed output size (SHA-256 always 256 bits / 64 hex chars):")
    for inp in inputs:
        digest = sha256(inp)
        print(f"  Input length: {len(inp):>8} bytes → digest length: {len(digest)} hex chars = {len(digest)*4} bits")
        print(f"  Digest: {digest[:32]}...")

    # Avalanche effect
    print("\n  Avalanche effect (one bit change → ~50% of output bits flip):")
    base = b"EC441 networking"
    h1 = sha256(base)
    # Flip one bit in the input
    modified = bytearray(base)
    modified[0] ^= 0x01
    h2 = sha256(bytes(modified))
    # Count differing bits
    diff_bits = sum(bin(int(a, 16) ^ int(b, 16)).count('1')
                    for a, b in zip(h1, h2))
    print(f"  Original:  '{base.decode()}'  → {h1[:32]}...")
    print(f"  Modified:  '{bytes(modified).decode()}'  → {h2[:32]}...")
    print(f"  Bits flipped: {diff_bits}/256 ({100*diff_bits/256:.1f}%)")

    # Commitment scheme
    print("\n  Commitment scheme: h(nonce || bid)")
    nonce = os.urandom(16).hex()
    bid = "142500"
    commit_input = (nonce + bid).encode()
    commitment = sha256(commit_input)
    print(f"  Phase 1 (BEFORE auction closes):")
    print(f"    α publishes commitment: {commitment[:32]}...")
    print(f"    (bid and nonce are secret)")
    print(f"  Phase 2 (AFTER auction closes):")
    print(f"    α reveals nonce='{nonce[:16]}...' bid='{bid}'")
    verify_input = (nonce + bid).encode()
    verify_hash = sha256(verify_input)
    print(f"    Anyone verifies: h(nonce||bid) = {verify_hash[:32]}...")
    print(f"    Matches commitment: {commitment == verify_hash}")
    print(f"  → Preimage resistance prevents α from finding a different (nonce', bid') that hashes to the same commitment")

    # Password storage demo
    print("\n  Password storage: h(password) vs h(salt || password)")
    password = "hunter2"
    unsalted = sha256(password.encode())
    salt_a = os.urandom(8).hex()
    salt_b = os.urandom(8).hex()
    salted_a = sha256((salt_a + password).encode())
    salted_b = sha256((salt_b + password).encode())
    print(f"  h('{password}') = {unsalted[:32]}...")
    print(f"  h(salt_A||'{password}') = {salted_a[:32]}... (salt={salt_a[:8]}...)")
    print(f"  h(salt_B||'{password}') = {salted_b[:32]}... (salt={salt_b[:8]}...)")
    print(f"  Same password, unsalted: IDENTICAL — reveals same-password users")
    print(f"  Same password, salted:   DIFFERENT — rainbow tables useless per-user")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: RSA Arithmetic
# ─────────────────────────────────────────────────────────────────────────────

def section2_rsa():
    print("\n" + "=" * 65)
    print("SECTION 2: RSA Arithmetic")
    print("=" * 65)

    def gcd(a, b):
        while b:
            a, b = b, a % b
        return a

    def extended_gcd(a, b):
        if a == 0:
            return b, 0, 1
        g, x, y = extended_gcd(b % a, a)
        return g, y - (b // a) * x, x

    def mod_inverse(e, phi):
        g, x, _ = extended_gcd(e % phi, phi)
        if g != 1:
            raise ValueError("No modular inverse")
        return x % phi

    def fast_exp(base, exp, mod):
        return pow(base, exp, mod)

    def rsa_keygen(p, q):
        n = p * q
        phi = (p - 1) * (q - 1)
        e = 65537
        # Find valid e < phi that is coprime
        for candidate in [65537, 17, 13, 7, 3]:
            if gcd(candidate, phi) == 1 and candidate < phi:
                e = candidate
                break
        d = mod_inverse(e, phi)
        return (n, e), (n, d), phi

    print("\n  Example 1: p=7, q=11")
    pub, priv, phi = rsa_keygen(7, 11)
    n, e = pub
    _, d = priv
    print(f"  n={n}, φ(n)={phi}")
    print(f"  Public key:  (n={n}, e={e})")
    print(f"  Private key: (n={n}, d={d})")
    m = 5
    c = fast_exp(m, e, n)
    m2 = fast_exp(c, d, n)
    print(f"  Encrypt m={m}: c = {m}^{e} mod {n} = {c}")
    print(f"  Decrypt c={c}: m = {c}^{d} mod {n} = {m2}")
    print(f"  Recovered: {m2} {'✓' if m2 == m else '✗'}")

    print("\n  Example 2: p=11, q=13 (from lecture notes)")
    pub2, priv2, phi2 = rsa_keygen(11, 13)
    n2, e2 = pub2
    _, d2 = priv2
    print(f"  n={n2}, φ(n)={phi2}")
    print(f"  Public key:  (n={n2}, e={e2})")
    print(f"  Private key: (n={n2}, d={d2})")
    m2_in = 9
    c2 = fast_exp(m2_in, e2, n2)
    m2_out = fast_exp(c2, d2, n2)
    print(f"  Encrypt m={m2_in}: c = {c2}")
    print(f"  Decrypt c={c2}: m = {m2_out} {'✓' if m2_out == m2_in else '✗'}")

    # RSA signing
    print("\n  RSA Signing (sign hash, not raw message):")
    message = b"Transfer $500 to account 9988"
    msg_hash = int(hashlib.sha256(message).hexdigest(), 16) % n2
    signature = fast_exp(msg_hash, d2, n2)
    # Verify
    recovered = fast_exp(signature, e2, n2)
    print(f"  Message: '{message.decode()}'")
    print(f"  h(message) mod n = {msg_hash}")
    print(f"  Signature s = h^d mod n = {signature}")
    print(f"  Verify: s^e mod n = {recovered}")
    print(f"  Match:  {recovered == msg_hash} {'✓' if recovered == msg_hash else '✗'}")
    print(f"  → Only holder of private key d can produce valid signature")

    # Why RSA works
    print("\n  Why RSA works (Euler's theorem):")
    print(f"  ed ≡ 1 (mod φ(n))  →  ed = 1 + k·φ(n)")
    print(f"  c^d = (m^e)^d = m^(ed) = m^(1+k·φ(n))")
    print(f"  By Euler: m^φ(n) ≡ 1 (mod n)")
    print(f"  So m^(1+k·φ(n)) = m · (m^φ(n))^k ≡ m · 1^k ≡ m (mod n)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Diffie-Hellman Key Exchange
# ─────────────────────────────────────────────────────────────────────────────

def section3_diffie_hellman():
    print("\n" + "=" * 65)
    print("SECTION 3: Diffie-Hellman Key Exchange")
    print("=" * 65)

    def dh_exchange(p, g, a, b):
        A = pow(g, a, p)
        B = pow(g, b, p)
        shared_alice = pow(B, a, p)
        shared_bob   = pow(A, b, p)
        assert shared_alice == shared_bob, "DH failed — shared secrets don't match"
        return A, B, shared_alice

    # Small example (lecture numbers)
    p, g = 23, 5
    a, b = 6, 15
    A, B, shared = dh_exchange(p, g, a, b)
    print(f"\n  Small example (p=23, g=5):")
    print(f"  Alice private a={a}  →  A = g^a mod p = {A}")
    print(f"  Bob   private b={b}  →  B = g^b mod p = {B}")
    print(f"  Alice computes: B^a mod p = {B}^{a} mod {p} = {pow(B,a,p)}")
    print(f"  Bob   computes: A^b mod p = {A}^{b} mod {p} = {pow(A,b,p)}")
    print(f"  Shared secret: {shared} ✓")
    print(f"  Trudy sees A={A}, B={B} on wire — must solve discrete log to find a or b")

    # Larger example
    # Use a safe prime (simplified)
    p2 = 2**127 - 1  # Mersenne prime (illustrative; real DH uses 2048-bit)
    g2 = 2
    a2 = random.randint(2, p2 - 2)
    b2 = random.randint(2, p2 - 2)
    A2, B2, shared2 = dh_exchange(p2, g2, a2, b2)
    print(f"\n  Larger example (127-bit Mersenne prime):")
    print(f"  Alice A = g^a mod p = {A2}")
    print(f"  Bob   B = g^b mod p = {B2}")
    print(f"  Both derive shared secret (shown truncated): {shared2 % 10**12}...")
    print(f"  Shared secrets match: True ✓")

    print("\n  Forward secrecy illustration:")
    print("  TLS 1.3: session key = KDF(g^ab)  — ephemeral a,b discarded after handshake")
    print("  If server long-term RSA key leaks LATER:")
    print("    Attacker cannot recover a or b (discrete log hard)")
    print("    Cannot recompute g^ab")
    print("    Recorded session traffic remains secure ✓")
    print("  TLS 1.2 RSA key-transport: session key = RSA_decrypt(encrypted_premaster)")
    print("    If server RSA private key leaks LATER:")
    print("    Attacker decrypts premaster from recorded handshake")
    print("    Derives session keys → decrypts all recorded traffic ✗")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: HMAC — Message Authentication Code
# ─────────────────────────────────────────────────────────────────────────────

def section4_hmac():
    print("\n" + "=" * 65)
    print("SECTION 4: HMAC — Message Authentication Code")
    print("=" * 65)

    key = os.urandom(32)
    message = b"Transfer $1000 to account 12345"
    tampered = b"Transfer $9999 to account 12345"

    def compute_hmac(key, msg):
        return hmac.new(key, msg, hashlib.sha256).hexdigest()

    mac = compute_hmac(key, message)
    mac_tampered = compute_hmac(key, tampered)
    mac_wrong_key = compute_hmac(os.urandom(32), message)

    print(f"\n  Message:  '{message.decode()}'")
    print(f"  HMAC:      {mac[:32]}...")
    print(f"\n  Tampered: '{tampered.decode()}'")
    print(f"  HMAC:      {mac_tampered[:32]}... (completely different)")
    print(f"\n  Wrong key HMAC: {mac_wrong_key[:32]}... (unverifiable without key)")

    print(f"\n  Verification:")
    print(f"  Original message → HMAC valid: {hmac.compare_digest(compute_hmac(key, message), mac)} ✓")
    print(f"  Tampered message → HMAC valid: {hmac.compare_digest(compute_hmac(key, tampered), mac)} ✗")

    print(f"\n  MAC vs Signature — non-repudiation:")
    print(f"  MAC:  both Alice and Bob know key k → either could have generated the MAC")
    print(f"        Third party cannot determine who sent it")
    print(f"        ✗ No non-repudiation")
    print(f"  Sig:  only Alice holds private key → only she could sign")
    print(f"        Any third party can verify with public key")
    print(f"        ✓ Non-repudiation")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: PKI Chain of Trust Simulation
# ─────────────────────────────────────────────────────────────────────────────

def section5_pki():
    print("\n" + "=" * 65)
    print("SECTION 5: PKI Chain of Trust Simulation")
    print("=" * 65)

    # Simulated cert chain: root → intermediate → leaf
    cert_chain = {
        "root": {
            "subject":    "DigiCert Global Root CA",
            "issuer":     "DigiCert Global Root CA",
            "pubkey":     "AAAA1111...(root public key)",
            "valid_days": 7300,
            "in_root_store": True,
            "self_signed": True,
        },
        "intermediate": {
            "subject":    "DigiCert SHA2 Secure Server CA",
            "issuer":     "DigiCert Global Root CA",
            "pubkey":     "BBBB2222...(intermediate public key)",
            "valid_days": 3650,
            "in_root_store": False,
            "self_signed": False,
        },
        "leaf": {
            "subject":    "bu.edu",
            "issuer":     "DigiCert SHA2 Secure Server CA",
            "pubkey":     "CCCC3333...(bu.edu public key)",
            "san":        ["bu.edu", "www.bu.edu", "*.bu.edu"],
            "valid_days": 365,
            "in_root_store": False,
            "self_signed": False,
        },
    }

    def verify_chain(chain, hostname, verbose=True):
        if verbose:
            print(f"\n  Verifying certificate chain for '{hostname}':")
        errors = []

        leaf = chain["leaf"]
        inter = chain["intermediate"]
        root = chain["root"]

        # Step 1: hostname match
        sans = leaf.get("san", [leaf["subject"]])
        hostname_match = hostname in sans or any(
            s.startswith("*.") and hostname.endswith(s[1:]) for s in sans
        )
        if verbose:
            print(f"  [1] Hostname check: '{hostname}' in SAN {sans} → {hostname_match}")
        if not hostname_match:
            errors.append("Hostname mismatch")

        # Step 2: leaf signed by intermediate
        leaf_sig_valid = leaf["issuer"] == inter["subject"]
        if verbose:
            print(f"  [2] Leaf issuer '{leaf['issuer']}' == Intermediate '{inter['subject']}' → {leaf_sig_valid}")
        if not leaf_sig_valid:
            errors.append("Leaf cert not signed by intermediate")

        # Step 3: intermediate signed by root
        inter_sig_valid = inter["issuer"] == root["subject"]
        if verbose:
            print(f"  [3] Intermediate issuer '{inter['issuer']}' == Root '{root['subject']}' → {inter_sig_valid}")
        if not inter_sig_valid:
            errors.append("Intermediate cert not signed by root")

        # Step 4: root in trust store
        root_trusted = root["in_root_store"]
        if verbose:
            print(f"  [4] Root '{root['subject']}' in browser trust store → {root_trusted}")
        if not root_trusted:
            errors.append("Root CA not trusted")

        # Step 5: validity
        all_valid = all(c["valid_days"] > 0 for c in chain.values())
        if verbose:
            print(f"  [5] All certs within validity window → {all_valid}")

        result = len(errors) == 0
        if verbose:
            if result:
                print(f"  Chain verification: ✓ VALID — TLS proceeds")
            else:
                print(f"  Chain verification: ✗ INVALID — {errors}")
        return result

    verify_chain(cert_chain, "www.bu.edu")
    verify_chain(cert_chain, "evil.com")

    print("\n  CA failure case studies:")
    cases = [
        ("DigiNotar (2011)",
         "Attacker issued fraudulent *.google.com certs; used to intercept Gmail in Iran",
         "Removed from all root stores; company bankrupt within weeks"),
        ("Symantec (2017-18)",
         "Series of mis-issuance incidents; Google progressively distrusted hierarchy",
         "Sold CA business to DigiCert; Chrome distrusted old Symantec chain"),
    ]
    for name, incident, outcome in cases:
        print(f"\n  {name}:")
        print(f"    Incident: {incident}")
        print(f"    Outcome:  {outcome}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: TLS 1.3 Handshake Walkthrough
# ─────────────────────────────────────────────────────────────────────────────

def section6_tls_handshake():
    print("\n" + "=" * 65)
    print("SECTION 6: TLS 1.3 Handshake Walkthrough")
    print("=" * 65)

    print("\n  Characters: α (client), β (server), τ (adversary on wire)")

    # Step 1: ClientHello
    client_random = os.urandom(32)
    a_private = random.randint(2, 10**6)
    p, g = 2**521 - 1, 2  # simplified; real TLS uses NIST P-256 or X25519
    p_small = 2**19 - 1  # Use manageable prime for demo
    A_share = pow(g, a_private, p_small)  # g^a mod p
    print(f"\n  [→] ClientHello:")
    print(f"      Supported ciphers: TLS_AES_256_GCM_SHA384, TLS_AES_128_GCM_SHA256")
    print(f"      Ephemeral DH share: g^a mod p = {A_share}")
    print(f"      client_random: {client_random.hex()[:32]}...")

    # Step 2: ServerHello
    b_private = random.randint(2, 10**6)
    B_share = pow(g, b_private, p_small)   # g^b mod p
    server_cert_summary = "CN=example.com, issuer=Let's Encrypt, valid 365d"
    transcript_hash = hashlib.sha256(b"ClientHello||ServerHello||CertChain").hexdigest()
    print(f"\n  [←] ServerHello:")
    print(f"      Chosen cipher: TLS_AES_256_GCM_SHA384")
    print(f"      Ephemeral DH share: g^b mod p = {B_share}")
    print(f"      Certificate: {server_cert_summary}")
    print(f"      Signature over transcript (ECDSA): Sign_privkey(h(transcript))")

    # Step 3: Client verifies
    print(f"\n  [α] Client verification:")
    print(f"      1. Walk cert chain → root in trust store ✓")
    print(f"      2. Verify ECDSA signature over transcript hash:")
    print(f"         transcript_hash = {transcript_hash[:32]}...")
    print(f"         VerifyKpub(sig, transcript_hash) → True ✓")
    print(f"      Confirms: server holds the private key for the cert")

    # Step 4: Key derivation
    shared_secret = pow(B_share, a_private, p_small)
    shared_check = pow(A_share, b_private, p_small)
    assert shared_secret == shared_check
    session_key_material = hashlib.sha256(shared_secret.to_bytes(8, 'big')).hexdigest()
    print(f"\n  [α,β] Key derivation (HKDF):")
    print(f"      g^ab mod p = {shared_secret}")
    print(f"      Both compute same value: {shared_secret == shared_check} ✓")
    print(f"      HKDF(g^ab, handshake_context) → AES-256-GCM key + IV")
    print(f"      Key material (truncated): {session_key_material[:32]}...")
    print(f"      τ saw g^a={A_share} and g^b={B_share} — cannot compute g^ab (DL problem)")

    # Step 5: Application data
    print(f"\n  [↔] Application data (AES-GCM encrypted records):")
    print(f"      Each TLS record: AES-GCM(payload, AEAD tag over header+payload)")
    print(f"      Confidentiality: payload encrypted, τ sees ciphertext only")
    print(f"      Integrity:       any modification invalidates AEAD tag")
    print(f"      τ cannot read or modify any application data")

    # Summary table
    print(f"\n  Primitive map:")
    rows = [
        ("Ephemeral DH shares",      "Diffie-Hellman",    "Key agreement (forward secrecy)"),
        ("Certificate chain",         "PKI + signatures",  "Bind pubkey to identity"),
        ("Signature on transcript",   "RSA or ECDSA",      "Authenticate server"),
        ("Session key derivation",    "HKDF (SHA-384)",    "Expand g^ab into key material"),
        ("Application record crypto", "AES-256-GCM",       "Confidentiality + integrity"),
    ]
    print(f"  {'Step':<30} {'Primitive':<20} {'Purpose'}")
    print("  " + "-" * 70)
    for r in rows:
        print(f"  {r[0]:<30} {r[1]:<20} {r[2]}")

    # QUIC connection
    print(f"\n  QUIC vs TCP+TLS latency:")
    print(f"  TCP + TLS 1.3 (new session):   TCP SYN (1 RTT) + TLS (1 RTT) = 2 RTTs")
    print(f"  QUIC (new session):            Combined transport+crypto = 1 RTT")
    print(f"  QUIC (0-RTT resumption):       App data in first packet = 0 RTTs")
    print(f"  QUIC advantage: integrated TLS means less round-trip latency by default")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    section1_hash_properties()
    section2_rsa()
    section3_diffie_hellman()
    section4_hmac()
    section5_pki()
    section6_tls_handshake()

    print("\n" + "=" * 65)
    print("EC 441 Lecture 24 Lab complete.")
    print("=" * 65)