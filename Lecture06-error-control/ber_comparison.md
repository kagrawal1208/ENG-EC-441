# Week 06 — Error Detection vs Error Correction vs Repetition (BER + Utilization)

This write-up compares three error-control strategies on a 1000-bit frame with channel bit error rate p = 10^-6. :contentReference[oaicite:12]{index=12}

---

## Setup

We compare:
1) Single-bit error correction  
2) Single-bit error detection + retransmission  
3) Rate 1/3 repetition code  

Given (from lecture):
- Frame size n = 1000 bits
- Channel BER p = 10^-6 :contentReference[oaicite:13]{index=13}

Metrics:
- **Utilization U** = fraction of channel carrying data (higher is better)
- **Residual BER Pe** = probability a bit is wrong after decoding (lower is better) :contentReference[oaicite:14]{index=14}

---

## Method Results (from lecture)

| Method | Utilization U | Residual BER Pe |
|---|---:|---:|
| Single-bit error detection | 0.998 | ~10^-9 |
| Single-bit error correction | 0.990 | ~10^-9 |
| Rate 1/3 repetition | 0.333 | ~3×10^-12 |

These are the “BER comparison results” for n=1000, p=10^-6. :contentReference[oaicite:15]{index=15}

---

## Key Explanation / Takeaways

### 1) Detection beats correction in networking
Detection + retransmission achieves about the **same residual error rate** (~10^-9) as correction, but better channel utilization (0.998 vs 0.990). :contentReference[oaicite:16]{index=16}

This makes sense for networking because retransmission is allowed/cheap compared to permanently adding more redundancy. :contentReference[oaicite:17]{index=17}

### 2) Repetition is extremely costly
Repetition coding improves Pe down to ~3×10^-12, but utilization collapses to **1/3**, meaning you sacrifice a huge amount of throughput. :contentReference[oaicite:18]{index=18}

### 3) When to use each
- Detection + retransmission: Ethernet/WiFi/TCP-style networking  
- Correction: real-time voice/video, deep space links (retransmission may not be feasible)  
- Repetition: ultra-reliable low-rate systems :contentReference[oaicite:19]{index=19}

---

## Bottom Line

For typical networks where retransmission is available, **error detection** gives near-best reliability while keeping utilization high. :contentReference[oaicite:20]{index=20}
