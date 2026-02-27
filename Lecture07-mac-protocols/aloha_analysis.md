# Week 07 — Why CSMA Improves on ALOHA + Minimum Ethernet Frame Size

This report explains why CSMA outperforms ALOHA and derives the minimum Ethernet frame size constraint for CSMA/CD. :contentReference[oaicite:34]{index=34}

---

## 1) Why ALOHA is inefficient

ALOHA transmits without checking if the channel is already in use, so collisions are common and waste full frame time T. :contentReference[oaicite:35]{index=35}

The fundamental weakness: nodes do not “listen” before sending. :contentReference[oaicite:36]{index=36}

---

## 2) CSMA: Carrier Sense Multiple Access

CSMA rule: before transmitting, listen to the channel.

- If idle → transmit
- If busy → defer :contentReference[oaicite:37]{index=37}

Why this helps:
Signals propagate at ~2×10^8 m/s, so propagation delay τ is usually much smaller than transmission time T on a LAN.  
Collisions then only happen when two nodes start within τ of each other (much smaller “vulnerable” period than ALOHA). :contentReference[oaicite:38]{index=38}

---

## 3) CSMA/CD: Collision Detection

CSMA/CD improves further:

While transmitting, a node listens. If what it hears != what it sent, collision is happening → abort early. :contentReference[oaicite:39]{index=39}

Key benefit:
Instead of wasting a full frame time T, collision waste is bounded by about **2τ** (round-trip propagation). :contentReference[oaicite:40]{index=40}

---

## 4) Minimum Frame Size for CSMA/CD (Important Constraint)

A sender must still be transmitting when the collision signal returns; otherwise it could finish sending and never realize a collision happened.

So we require:

T ≥ 2τ :contentReference[oaicite:41]{index=41}

Since T = L/R (frame length / link rate):

L/R ≥ 2τ  
=> **L ≥ 2τR** :contentReference[oaicite:42]{index=42}

### Classic Ethernet Example (from lecture)

Given:
- R = 10 Mb/s
- max segment = 2500 m
- propagation speed ≈ 2×10^8 m/s → τ ≈ 25 μs

Then:

Lmin = 2 × 25 μs × 10^7 bps = 500 bits ≈ 64 bytes :contentReference[oaicite:43]{index=43}

✅ This is where the **64-byte minimum Ethernet frame size** comes from (physics-driven). :contentReference[oaicite:44]{index=44}

---

## 5) Modern Ethernet Note

Modern Ethernet uses switched, full-duplex links, so collisions are essentially impossible on those links, and CSMA/CD is not exercised in practice (even though it remains in the standard). :contentReference[oaicite:45]{index=45}
