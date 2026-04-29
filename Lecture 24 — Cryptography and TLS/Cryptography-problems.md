# EC 441 — Lecture 24 Problem Set: Cryptography and Security — From Primitives to TLS

**Topic:** Cryptography and Security: From Primitives to TLS
**Lecture:** 24
**Covers:** Threat model, symmetric crypto (AES-GCM), hash functions, RSA, Diffie-Hellman, MACs, digital signatures, PKI, TLS 1.3 handshake

---

## Problem 1: Threat Model and Primitives Mapping

**(a)** Alice (α) wants to send a message to Bob (β). Trudy (τ) sits on the network path. For each of the five attacks below, name the security requirement it violates and the cryptographic primitive that addresses it:

| Attack | Requirement violated | Primitive |
|--------|---------------------|-----------|
| Trudy reads the plaintext of Alice's message | | |
| Trudy flips bits in transit; Bob receives corrupted data | | |
| Trudy pretends to be Alice when sending to Bob | | |
| Trudy records a valid login message and replays it later | | |
| Alice sends a fraudulent transfer; later claims she didn't | | |

**(b)** A MAC (HMAC) and a digital signature both provide integrity and authentication. Explain the one capability a signature has that a MAC cannot provide, and explain *why* the MAC cannot provide it even in principle.

**(c)** AES-GCM is described as an "authenticated encryption" primitive. What does this mean precisely? Which two rows from the threat model table does a single AES-GCM operation address, and how?

### Solution

**(a)**

| Attack | Requirement violated | Primitive |
|--------|---------------------|-----------|
| Trudy reads plaintext | Confidentiality | AES-GCM (symmetric encryption) or RSA (asymmetric) |
| Trudy flips bits | Integrity | MAC (HMAC) or AEAD (AES-GCM) or digital signature |
| Trudy impersonates Alice | Authentication (peer) | Digital signature (Alice's private key) or MAC (shared key) |
| Trudy replays a message | Freshness | Nonces / timestamps embedded in protocol |
| Alice denies sending | Non-repudiation | Digital signature (only Alice holds her private key) |

**(b)** A MAC can prove **"someone who knows the shared key k made this message"** — but both Alice and Bob know k. Neither can prove to a third party that the *other* party sent a specific message, because either could have generated the same MAC. A digital signature is produced with a **private key that only one party holds**; any third party who has the corresponding public key can verify the signature without knowing the private key. This asymmetry is why non-repudiation is only achievable with signatures. The MAC limitation is fundamental, not a weakness in HMAC's construction — no MAC scheme over a shared key can solve this, because the verifier holds exactly the same capability as the signer.

**(c)** AES-GCM (Galois/Counter Mode) is an **Authenticated Encryption with Associated Data (AEAD)** scheme: it simultaneously encrypts the payload (providing confidentiality) and computes an authentication tag over the ciphertext and associated data (providing integrity). A single AES-GCM operation addresses **confidentiality** (Trudy cannot read the plaintext) and **integrity** (Trudy cannot modify the ciphertext without the tag verification failing). Decryption and authentication verification happen atomically — the plaintext is never released if the tag is invalid.

---

## Problem 2: Hash Functions

**(a)** A hash function h maps arbitrary-length input to a fixed-length digest. State the three security properties of a cryptographic hash function, define each precisely, and explain which is hardest to achieve.

**(b)** SHA-256 produces a 256-bit digest. By the birthday paradox, how many hash evaluations does an attacker need (on average) to find a collision? Express as a power of 2.

**(c)** A developer stores user passwords as `h(password)` in the database. Explain two distinct attacks this enables and how the correct construction `h(salt || password)` — with a per-user random salt — defends against each.

**(d)** Explain the commitment scheme: α computes `c = h(nonce || bid)` and publishes c, then later reveals (nonce, bid). What does this achieve, and what property of h makes it work?

### Solution

**(a)** Three security properties:

1. **Preimage resistance**: Given `y = h(m)`, it must be computationally infeasible to find *any* `m'` such that `h(m') = y`. The hash is one-way — knowing the output reveals nothing about the input.

2. **Second-preimage resistance**: Given a specific message `m`, it must be infeasible to find a different `m' ≠ m` such that `h(m') = h(m)`. An attacker cannot forge a second message that matches an existing one's hash.

3. **Collision resistance**: It must be infeasible to find *any* pair `m ≠ m'` such that `h(m) = h(m')`. Note that this is strictly stronger than second-preimage resistance — here the attacker can choose *both* messages freely.

Collision resistance is hardest to achieve: the birthday paradox means the search space is only `2^(n/2)` for an n-bit hash, compared to `2^n` for preimage attacks. For SHA-256, collision resistance gives ~`2^128` security; preimage resistance gives ~`2^256`.

**(b)** By the birthday paradox, ~`2^(n/2) = 2^(256/2) = 2^128` evaluations are needed on average to find a collision in SHA-256.

**(c)** Two attacks on `h(password)` storage:

- **Rainbow table / precomputed dictionary attack**: An attacker precomputes `h(word)` for every word in a large dictionary or character space and stores (hash, password) pairs. A stolen database can then be cracked offline by table lookup in O(1) per hash. With per-user random salts, the attacker must recompute the dictionary for every individual user's salt — the precomputation is useless.

- **Identical password detection**: If two users choose the same password, `h(password)` is identical in both rows. An attacker who compromises one account can immediately identify all users with the same password. With unique per-user salts, `h(salt_A || password)` and `h(salt_B || password)` are completely different even for identical passwords.

**(d)** α binds herself to a bid without revealing it: she publishes `c = h(nonce || bid)` before the auction closes. When the auction ends she reveals `(nonce, bid)`. Anyone can verify `h(nonce || bid) == c`. This achieves two things: α cannot **change her bid** after publication (preimage resistance prevents finding a different `(nonce', bid')` that hashes to c), and no one learns her bid until she reveals it (preimage resistance prevents recovering `bid` from `c`). The scheme works because of preimage resistance and second-preimage resistance together.

---

## Problem 3: RSA

**(a)** Walk through RSA key generation with `p = 7, q = 11`. Compute n, φ(n). Choose `e = 13` and verify it is a valid choice. Compute d. State the public and private keys.

**(b)** Encrypt `m = 5` with the public key from (a). Show the computation.

**(c)** Decrypt the ciphertext from (b) with the private key. Verify you recover m = 5.

**(d)** Explain *why* RSA decryption recovers the original message. Cite the theorem used and show the algebraic step.

**(e)** An attacker has (n, e) but not d. What is the computationally hard problem they must solve to find d? Why is this believed to be hard?

### Solution

**(a)** Key generation:
- `n = p × q = 7 × 11 = 77`
- `φ(n) = (p-1)(q-1) = 6 × 10 = 60`
- Choose `e = 13`. Check: `gcd(13, 60) = 1` ✓ (13 is coprime to 60; 13 is prime and does not divide 60)
- Compute `d = e^(-1) mod 60`. We need `13d ≡ 1 (mod 60)`. Extended Euclidean: `13 × 37 = 481 = 8 × 60 + 1`, so `d = 37`. Check: `13 × 37 = 481 = 8 × 60 + 1 ≡ 1 (mod 60)` ✓
- **Public key:** `(n=77, e=13)`. **Private key:** `(n=77, d=37)`.

**(b)** Encrypt `m = 5`:
- `c = m^e mod n = 5^13 mod 77`
- `5^2 = 25; 5^4 = 625 mod 77 = 625 - 8×77 = 625 - 616 = 9`
- `5^8 = 9^2 = 81 mod 77 = 4`
- `5^{13} = 5^8 × 5^4 × 5^1 = 4 × 9 × 5 = 180 mod 77 = 180 - 2×77 = 26`
- **Ciphertext: c = 26**

**(c)** Decrypt `c = 26`:
- `m = c^d mod n = 26^{37} mod 77`
- Compute via repeated squaring: `26^2 = 676 mod 77 = 676 - 8×77 = 60`
- `26^4 = 60^2 = 3600 mod 77 = 3600 - 46×77 = 3600 - 3542 = 58`
- `26^8 = 58^2 = 3364 mod 77 = 3364 - 43×77 = 3364 - 3311 = 53`
- `26^{16} = 53^2 = 2809 mod 77 = 2809 - 36×77 = 2809 - 2772 = 37`
- `26^{32} = 37^2 = 1369 mod 77 = 1369 - 17×77 = 1369 - 1309 = 60`
- `37 = 32 + 4 + 1`, so `26^{37} = 26^{32} × 26^4 × 26^1 = 60 × 58 × 26 mod 77`
- `60 × 58 = 3480 mod 77 = 3480 - 45×77 = 3480 - 3465 = 15`
- `15 × 26 = 390 mod 77 = 390 - 5×77 = 390 - 385 = 5`
- **Decrypted: m = 5 ✓**

**(d)** RSA decryption works by **Euler's theorem**: if `gcd(m, n) = 1`, then `m^φ(n) ≡ 1 (mod n)`. We chose `ed ≡ 1 (mod φ(n))`, so `ed = 1 + kφ(n)` for some integer k. Therefore:

```
c^d = (m^e)^d = m^(ed) = m^(1 + kφ(n)) = m · (m^φ(n))^k ≡ m · 1^k ≡ m (mod n)
```

The exponent wraps around via Euler's theorem, leaving only the original message.

**(e)** The attacker needs `d = e^(-1) mod φ(n)`. Computing `φ(n) = (p-1)(q-1)` requires knowing the prime factorization of n (i.e., finding p and q). **Integer factorization** of a 2048-bit semiprime (product of two large primes) is believed to require ~`2^112` operations with the best known classical algorithms (General Number Field Sieve). No efficient classical algorithm for factoring is known. Note: Shor's algorithm on a quantum computer solves this in polynomial time, which motivates post-quantum cryptography research.

---

## Problem 4: Diffie-Hellman Key Exchange

Public parameters: prime `p = 23`, generator `g = 5`.

**(a)** Alice chooses private value `a = 6`. Compute her public share A.

**(b)** Bob chooses private value `b = 15`. Compute his public share B.

**(c)** Compute the shared secret that Alice derives (from B and a) and the shared secret Bob derives (from A and b). Verify they are equal.

**(d)** Trudy observes A = 8 and B = 19 on the wire. She knows p = 23, g = 5. What problem must she solve to recover the shared secret? Why is this believed to be hard?

**(e)** Explain forward secrecy. In TLS 1.3, ephemeral DH is used for key agreement and the server's RSA/ECDSA key is used only to sign the DH share. Why does this provide forward secrecy while the old TLS 1.2 RSA key-transport mode does not?

### Solution

**(a)** `A = g^a mod p = 5^6 mod 23`
- `5^2 = 25 mod 23 = 2`
- `5^4 = 2^2 = 4`
- `5^6 = 5^4 × 5^2 = 4 × 2 = 8`
- **A = 8**

**(b)** `B = g^b mod p = 5^15 mod 23`
- `5^1=5, 5^2=2, 5^4=4, 5^8=4^2=16, 5^15 = 5^8 × 5^4 × 5^2 × 5^1 = 16×4×2×5 = 640 mod 23`
- `640 / 23 = 27 remainder 19`
- **B = 19**

**(c)**
- Alice: `B^a mod p = 19^6 mod 23`
  - `19^2 = 361 mod 23 = 361 - 15×23 = 361 - 345 = 16`
  - `19^4 = 16^2 = 256 mod 23 = 256 - 11×23 = 256 - 253 = 3`
  - `19^6 = 19^4 × 19^2 = 3 × 16 = 48 mod 23 = 2`
- Bob: `A^b mod p = 8^{15} mod 23`
  - `8^2 = 64 mod 23 = 64 - 2×23 = 18`
  - `8^4 = 18^2 = 324 mod 23 = 324 - 14×23 = 324 - 322 = 2`
  - `8^8 = 2^2 = 4`
  - `8^{15} = 8^8 × 8^4 × 8^2 × 8^1 = 4 × 2 × 18 × 8 = 1152 mod 23`
  - `1152 / 23 = 50 r 2`
- **Shared secret: 2 (both derive g^ab = 5^90 mod 23 = 2)** ✓

**(d)** Trudy must solve the **discrete logarithm problem**: given `A = g^a mod p`, find `a`. Equivalently, she sees `g^a` and `g^b` and needs `g^ab` — the **Diffie-Hellman problem**, which is believed to be as hard as discrete log. No efficient classical algorithm for discrete log in large prime-order groups is known; the best classical algorithms (index calculus) are sub-exponential but infeasible for 2048-bit primes.

**(e)** **Forward secrecy**: if a long-term private key is compromised in the future, previously recorded sessions cannot be decrypted. In TLS 1.3 with ephemeral DH: the session key is derived from ephemeral DH shares (`g^a`, `g^b`) generated fresh for each connection and discarded immediately after use. Even if the server's RSA/ECDSA long-term key leaks, an attacker cannot recover the ephemeral `a` or `b` values (discrete log), so recorded traffic remains secure. In the old TLS 1.2 RSA key-transport mode, the client encrypted the session key directly with the server's long-term RSA public key. If the server's RSA private key is later compromised, an attacker who recorded the handshake can now decrypt the session key and the entire session. There is no forward secrecy because the session key's protection is permanently tied to the long-term key.

---

## Problem 5: TLS 1.3 Handshake

**(a)** List the five steps of the TLS 1.3 handshake. For each step, identify which cryptographic primitive from the lecture is exercised.

**(b)** After the handshake, application data is protected by AES-GCM. What is AES-GCM protecting against in each record? What additional data (besides the payload) is authenticated?

**(c)** A browser connects to `bank.com`. Explain, step by step, how the browser verifies that the TLS certificate presented is legitimate. What is the browser checking at each step, and what attack does each check prevent?

**(d)** Let's Encrypt launched in 2016 and made TLS certificates free and automated. What was the measurable effect on HTTPS adoption? Why was cost and friction the bottleneck, not technical difficulty?

**(e)** QUIC "integrates" TLS 1.3 rather than running it on top. What does this mean concretely? What latency benefit does it provide compared to TLS over TCP?

### Solution

**(a)** TLS 1.3 handshake steps and primitives:

| Step | Action | Primitive |
|------|--------|-----------|
| 1. ClientHello | Client sends supported ciphers + ephemeral DH share `g^a` | Diffie-Hellman |
| 2. ServerHello | Server sends cipher choice + ephemeral DH share `g^b` + cert chain + signature over transcript | DH (key agreement) + RSA/ECDSA signature + PKI (cert) |
| 3. Client verifies | Client walks cert chain to root store; verifies server's signature on handshake transcript | Digital signatures + PKI trust chain |
| 4. Key derivation | Both compute `g^ab`; run through HKDF to produce AES-GCM session keys | DH shared secret + HKDF (hash-based KDF) |
| 5. Application data | All records encrypted+authenticated with session keys | AES-GCM (AEAD) |

**(b)** AES-GCM protects each TLS record against: **confidentiality** (payload encrypted with AES in counter mode) and **integrity** (GCM authentication tag covers ciphertext + associated data). The authentication tag covers both the encrypted payload and the **associated data** — the TLS record header (content type, version, length). This prevents an attacker from reordering records, truncating the stream, or modifying header fields even though the header itself is not encrypted.

**(c)** Certificate verification:

1. **Receive leaf certificate**: contains `bank.com`'s public key, signed by an intermediate CA. Check that the certificate's `CN` or `SAN` matches the hostname `bank.com` exactly. Prevents serving a cert for `bankk.com` or a different domain.

2. **Verify leaf signature**: using the intermediate CA's public key, verify the CA's signature on the leaf cert. Confirms the leaf cert was issued by the intermediate CA and has not been tampered with.

3. **Walk the chain**: the intermediate CA cert is itself signed by another intermediate or a root CA. Repeat signature verification up the chain.

4. **Check root anchor**: confirm the root CA at the top of the chain is in the browser's preinstalled root store. Roots are trusted by being preinstalled by the OS/browser vendor after vetting; they are the trust anchors for the entire PKI.

5. **Check validity window**: confirm the current timestamp falls within each certificate's `notBefore` and `notAfter` fields. Expired certs are rejected.

6. **Check revocation**: query OCSP or check CRL to confirm no cert in the chain has been revoked. Protects against a compromised cert whose key has leaked.

**(d)** HTTPS adoption went from ~30% of web traffic in 2015 to ~95% today, with most of the increase following Let's Encrypt's launch. The bottleneck was not technical: TLS itself had been available for decades, and the cryptographic implementation was mature. The barriers were cost ($100–$300/year per cert), manual renewal (certs expire; missed renewals cause outages), and operational complexity (CSR generation, CA verification workflows). Let's Encrypt (ACME protocol) reduced the cost to zero and automated renewal to a single cron job. Once the operational friction matched the friction of *not* using HTTPS, operators adopted it by default.

**(e)** In TLS over TCP, two separate handshakes occur: first the TCP three-way handshake (1 RTT), then the TLS 1.3 handshake (1 RTT). New connections require 2 RTTs before application data flows. QUIC integrates the TLS 1.3 key exchange into the QUIC transport handshake — the DH shares and crypto negotiation travel in the same packets as the QUIC connection establishment. New connections require only **1 RTT** before application data. On 0-RTT resumption (returning to a known server), the client can send application data in the **first packet**, before receiving any server response. The integration also means packet headers and stream data are encrypted at the QUIC layer, not just the payload — even more metadata is protected than in TLS over TCP.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 24 notes.*