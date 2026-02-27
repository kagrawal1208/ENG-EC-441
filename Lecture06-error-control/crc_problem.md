# Week 06 — CRC Encoding + Decoding (Worked Problem)

This problem is based on CRC encoding/decoding using modulo-2 (GF(2)) polynomial division. CRC is an error **detection** code where valid transmitted frames are divisible by the generator polynomial. :contentReference[oaicite:0]{index=0}

---

## Problem Statement

Given:
- Message bits **M = 1101**
- Generator bits **G = 1011**
- Degree of G is **r = 3** (since G has 4 bits = r+1)

Tasks:
1. Compute the CRC remainder **R** and transmitted frame **T**
2. Verify at the receiver that **T mod G = 0**
3. Flip one bit and show the CRC detects the error

CRC rules used:
- Multiply message by x^r (append r zeros)
- Divide by G using **mod-2 division**
- Remainder is the CRC checksum appended to the message :contentReference[oaicite:1]{index=1}

---

## 1) CRC Encoding (Compute R and T)

### Step 1: Append r zeros to M
Since r = 3:

M = 1101  
x^r M → append 3 zeros → **1101000** :contentReference[oaicite:2]{index=2}

### Step 2: Modulo-2 long division of 1101000 by 1011

We divide like normal long division, but subtraction is XOR (because arithmetic is in GF(2)). :contentReference[oaicite:3]{index=3}

Dividend: 1101000  
Divisor:  1011

Perform XOR steps (same as lecture example):

- Take first 4 bits: 1101
  - 1101 XOR 1011 = 0110
  - Bring down next bit (0) → 1100
- 1100 XOR 1011 = 0111
  - Bring down next bit (0) → 1110
- 1110 XOR 1011 = 0101
  - Bring down next bit (0) → 1010
- 1010 XOR 1011 = 0001
  - Bring down next bit (last 0 already accounted in length) → remainder is **001**

So the remainder is:

**R = 001** :contentReference[oaicite:4]{index=4}

### Step 3: Form the transmitted frame T
Transmit:

T = (x^r M) + R  
= 1101000 + 001  
= **1101001** :contentReference[oaicite:5]{index=5}

✅ Final Answer (Encoding):
- **R = 001**
- **T = 1101001**

---

## 2) CRC Decoding (Verify remainder is 0)

Receiver divides the received frame by G:

1101001 ÷ 1011

From the lecture verification, the remainder is:

**1101001 mod 1011 = 000** :contentReference[oaicite:6]{index=6}

✅ Since remainder = 0, the receiver **accepts** the frame (no detected error). :contentReference[oaicite:7]{index=7}

---

## 3) Error Detection Demo (Flip a bit)

Suppose one bit flips in transmission. Example used in lecture:

Original: 1101001  
Error frame: **1001001** (a bit is flipped) :contentReference[oaicite:8]{index=8}

Now divide:

1001001 ÷ 1011 → remainder ≠ 0 (nonzero)

✅ Therefore CRC **detects** the error and the receiver rejects + requests retransmission. :contentReference[oaicite:9]{index=9}

---

## Concept Link: Why CRC detects errors

Let received frame be:

T̂(x) = T(x) + E(x)

Since valid T(x) is divisible by G(x), an error is undetected only if:

G(x) divides E(x). :contentReference[oaicite:10]{index=10}

So CRC works by choosing a generator polynomial that makes common error patterns very unlikely (or impossible) to be divisible by G(x). :contentReference[oaicite:11]{index=11}
