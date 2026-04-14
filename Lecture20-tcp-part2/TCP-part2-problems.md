# EC 441 — Lecture 20 Problem Set: TCP Part 2 — Congestion Control

**Topic:** TCP Congestion Control and the Modern Picture  
**Lecture:** 20  
**Covers:** cwnd vs rwnd, slow start, AIMD/congestion avoidance, fast recovery, TCP throughput formula, BDP + window scaling, TCP Reno vs CUBIC, ECN, AIMD fairness, QUIC

---

## Problem 1: Slow Start and Congestion Avoidance

A TCP connection starts with cwnd = 1 MSS, ssthresh = 16 MSS.

**(a)** Trace cwnd for the first 8 RTTs under slow start (no loss). At which RTT does TCP transition to congestion avoidance?

**(b)** In congestion avoidance, by how much does cwnd increase per RTT? Per ACK? Explain the formula `cwnd += MSS²/cwnd` per ACK and why it achieves +1 MSS/RTT.

**(c)** At RTT 12, a **timeout** occurs when cwnd = 20 MSS. What are the new values of ssthresh and cwnd immediately after the timeout? Describe what happens next.

**(d)** At RTT 20, a **3 duplicate ACK** event occurs when cwnd = 14 MSS. What are the new values of ssthresh and cwnd after fast recovery? Does TCP restart slow start?

### Solution

**(a)** Slow start trace:

| RTT | cwnd (MSS) | Phase        |
|-----|-----------|--------------|
| 0   | 1         | Slow Start   |
| 1   | 2         | Slow Start   |
| 2   | 4         | Slow Start   |
| 3   | 8         | Slow Start   |
| 4   | 16        | Slow Start → **transition** (cwnd = ssthresh) |
| 5   | 17        | Cong. Avoid. |
| 6   | 18        | Cong. Avoid. |
| 7   | 19        | Cong. Avoid. |

Transition at RTT 4 when cwnd reaches ssthresh = 16 MSS.

**(b)** In congestion avoidance, cwnd increases by +1 MSS **per RTT**. Per-ACK increment: each RTT sends cwnd segments; each ACK triggers `cwnd += MSS²/cwnd`. After a full window: cwnd × (MSS²/cwnd) = MSS total increase per RTT → exactly +1 MSS/RTT.

**(c)** Timeout at cwnd = 20 MSS:
- **ssthresh = cwnd/2 = 10 MSS**
- **cwnd = 1 MSS** (restart slow start)
- TCP resumes slow start from cwnd=1, growing exponentially until cwnd reaches ssthresh=10, then switching to congestion avoidance.

**(d)** 3 dup ACKs at cwnd = 14 MSS (fast recovery):
- **ssthresh = cwnd/2 = 7 MSS**
- **cwnd = ssthresh = 7 MSS** (skip slow start — dup ACKs prove later segments are flowing)
- TCP immediately enters congestion avoidance from cwnd=7. No slow start restart.

The key difference: timeout = severe congestion (nothing getting through, cwnd→1). 3 dup ACKs = mild congestion (later packets arriving, cwnd halved but stays productive).

---

## Problem 2: TCP Throughput Formula

Use the Mathis et al. steady-state approximation: `BW ≈ (MSS / RTT) × (1 / √p)`

**(a)** A TCP connection has RTT = 50ms, MSS = 1460B, loss rate p = 0.001 (0.1%). Compute the expected throughput.

**(b)** What loss rate would be required to sustain 1 Gb/s over the same path (RTT=50ms)?

**(c)** Two TCP flows share a bottleneck link. Flow A has RTT = 10ms, Flow B has RTT = 100ms. Both see the same loss rate p. What is the ratio of their throughputs? What does this imply about fairness?

**(d)** A 10 Gb/s fiber path has RTT = 100ms and MSS = 1460B. What is the required loss rate to achieve 10 Gb/s? Express in scientific notation and comment on what this means practically.

### Solution

**(a)** BW = (1460 / 0.05) × (1 / √0.001) = 29,200 × 31.62 = **923 kb/s ≈ 0.92 Mb/s**

**(b)** Rearrange: p = (MSS / (RTT × BW))² = (1460 / (0.05 × 10⁹))² = (2.92×10⁻⁵)² ≈ **8.5 × 10⁻¹⁰**  
Roughly 1 packet loss per billion transmitted — near-perfect delivery required.

**(c)** BW_A / BW_B = (MSS/RTT_A) / (MSS/RTT_B) = RTT_B / RTT_A = 100/10 = **10:1**  
Flow A gets 10× more bandwidth than Flow B despite seeing the same loss rate. This is **RTT unfairness** — TCP Reno is inherently biased toward short-RTT flows because they complete more AIMD cycles per second. CUBIC partially addresses this by using wall-clock time for growth, making it RTT-independent.

**(d)** p = (1460 / (0.1 × 10¹⁰))² = (1.46×10⁻⁷)² ≈ **2.1 × 10⁻¹⁴**  
Approximately 1 drop per 50 trillion packets. This is **physically impossible** on any real network — packet loss from cosmic rays alone exceeds this rate. This shows why TCP Reno cannot achieve 10 Gb/s over wide-area paths; specialized protocols (CUBIC, BBR, QUIC) are required.

---

## Problem 3: cwnd and ssthresh Trace

Trace the following cwnd/ssthresh evolution. Start: cwnd=1, ssthresh=32.

Events (in order):
1. Slow start until first loss (3 dup ACKs) at cwnd = 32
2. Congestion avoidance for 5 RTTs
3. Timeout occurs
4. Slow start to new ssthresh, then congestion avoidance for 3 RTTs

**(a)** Fill in the table tracking cwnd and ssthresh at each event.

**(b)** Sketch the sawtooth shape of cwnd over time (RTTs).

**(c)** What is the long-run average cwnd in the congestion avoidance phase between the first loss event and the timeout? (Assume the sawtooth is symmetric around 3W/4 where W is the max cwnd.)

### Solution

**(a)** Trace:

| Phase                   | Event           | cwnd (MSS) | ssthresh |
|-------------------------|-----------------|------------|----------|
| Slow Start              | Start           | 1          | 32       |
| Slow Start              | RTT 1           | 2          | 32       |
| Slow Start              | RTT 2           | 4          | 32       |
| Slow Start              | RTT 3           | 8          | 32       |
| Slow Start              | RTT 4           | 16         | 32       |
| Slow Start              | RTT 5 (=ssthresh)| 32        | 32       |
| **3 dup ACK at cwnd=32**| **loss event**  | **16**     | **16**   |
| Cong. Avoid.            | +1/RTT          | 17         | 16       |
| Cong. Avoid.            | +1/RTT          | 18         | 16       |
| Cong. Avoid.            | +1/RTT          | 19         | 16       |
| Cong. Avoid.            | +1/RTT          | 20         | 16       |
| Cong. Avoid.            | +1/RTT          | 21         | 16       |
| **Timeout at cwnd=21**  | **severe loss** | **1**      | **10**   |
| Slow Start              | RTT 1           | 2          | 10       |
| Slow Start              | RTT 2           | 4          | 10       |
| Slow Start              | RTT 3           | 8          | 10       |
| Slow Start→CA           | RTT 4 (=ssthresh)| 10        | 10       |
| Cong. Avoid.            | +1/RTT          | 11         | 10       |
| Cong. Avoid.            | +1/RTT          | 12         | 10       |
| Cong. Avoid.            | +1/RTT          | 13         | 10       |

**(b)** Sawtooth sketch:
```
cwnd
 32 |    *
 24 |   *         *
 16 |  * \    * *
  8 | *   \ *
  1 |*     *
    └─────────────────────────────── RTTs
     SS→CA  3dup CA    timeout SS→CA
```

**(c)** In the CA phase between 3-dup-ACK and timeout: cwnd oscillates between W/2=16 and the timeout value (21). Average ≈ (16 + 21) / 2 ≈ **18.5 MSS**. Per the formula, average ≈ 3W/4 = 3×21/4 ≈ 15.75 MSS (theoretical, slightly different from this short trace).

---

## Problem 4: ECN and Congestion Signaling

**(a)** Describe the end-to-end sequence of events when a congestion-aware router uses ECN to signal congestion rather than dropping a packet. Include all parties: router, receiver, sender.

**(b)** What are two advantages of ECN over loss-based congestion signaling?

**(c)** ECN requires cooperation from both endpoints and all routers on the path. Why is ECN widely deployed in datacenters but less universal on the public Internet?

**(d)** The TCP throughput formula is BW ≈ MSS/(RTT × √p). If a router uses ECN instead of drops, p in the formula no longer measures *loss* — what does it measure, and does the formula still hold?

### Solution

**(a)** ECN sequence:
1. **Router**: Queue begins to fill (not yet overflow). Router **sets the CE (Congestion Experienced) bit** in the IP header of a packet in transit — the packet is NOT dropped.
2. **Receiver**: Receives the CE-marked packet. Echoes the congestion signal by setting the **ECE (ECN-Echo) flag** in the next TCP ACK sent to the sender.
3. **Sender**: Receives the ACK with ECE=1. Reduces cwnd **as if a loss event (3 dup ACKs) had occurred** — halves cwnd and sets ssthresh. Sends CWR (Congestion Window Reduced) flag in next segment to tell receiver the signal was received.

**(b)** Two advantages:
1. **No goodput loss**: The packet is delivered, not dropped. The application data gets through; there is no retransmission needed for the marked packet.
2. **Earlier signal**: ECN fires when the queue is *building*, before it overflows. Loss-based signaling fires only *after* overflow. Earlier feedback means smaller queues, lower latency, and less overshoot.

**(c)** ECN requires ECT (ECN-Capable Transport) bits to be set by the sender, CE marking by intermediate routers, and ECE/CWR flag support in both TCP stacks. Datacenters control the entire path (their own switches, known endpoint OS versions) and can enable ECN universally. The public Internet has billions of unmanaged endpoints, legacy devices that clear ECN bits, and middleboxes that don't forward ECN marks — making universal deployment effectively impossible without years of gradual rollout.

**(d)** With ECN, *p* measures the **mark rate** (fraction of packets that receive CE marking), not the loss rate. The throughput formula still holds mathematically — the sender's AIMD behavior is triggered by marks at the same rate as it would be triggered by losses. The practical difference is that marks carry no goodput cost (the marked packet arrives), so the effective throughput for a given *p* is slightly higher with ECN than with loss-based signaling.

---

## Problem 5: QUIC and TCP Limitations

**(a)** Explain HTTP/2's head-of-line blocking problem at the TCP layer. Why does running multiple HTTP/2 streams over one TCP connection not fully solve HOL blocking?

**(b)** A mobile user switches from WiFi (10.0.0.5:54321) to cellular (192.168.100.1:54321). Their ongoing TCP connection to a server at 93.184.216.34:443 breaks. Explain why using a QUIC connection ID would prevent this disruption.

**(c)** TCP has existed for 50 years and runs on billions of devices. Why is it effectively impossible to change TCP's wire format to fix its known problems?

**(d)** QUIC runs over UDP rather than TCP. A student asks: "Doesn't that mean QUIC is unreliable?" Explain why this is incorrect.

**(e)** Fill in the comparison table:

| Feature | UDP | TCP | QUIC |
|---------|-----|-----|------|
| Connection setup | | | |
| Reliability | | | |
| HOL blocking | | | |
| Encryption | | | |
| Connection migration | | | |

### Solution

**(a)** HTTP/2 multiplexes multiple streams (requests/responses) over a single TCP connection. TCP delivers data as a byte stream — it doesn't know about HTTP/2 stream boundaries. If one packet is lost, TCP's reliability mechanism holds back **all** subsequent data until that packet is retransmitted and acknowledged. All HTTP/2 streams are blocked, even those whose bytes are already buffered in the OS. This is HOL blocking at the TCP layer — unavoidable because TCP doesn't understand stream multiplexing above it.

**(b)** A TCP connection is identified by a 4-tuple (src IP, src port, dst IP, dst port). When the client's IP address changes (WiFi → cellular), the src IP changes, and the 4-tuple no longer matches. The server has no connection with the new source IP — the connection is broken, requiring a new handshake (and new TLS handshake). QUIC uses a **Connection ID** — a randomly chosen identifier independent of IP addresses. When the client switches networks, it sends packets with the same Connection ID from the new address. The server recognizes the Connection ID and **continues the connection** without interruption, renegotiating the path transparently.

**(c)** **Protocol ossification**: middleboxes (firewalls, NAT boxes, load balancers, deep packet inspection appliances) throughout the internet inspect and modify TCP headers based on the current wire format. Any change to TCP semantics — new flags, new option interpretations — risks breaking these devices. Millions of middleboxes would need to be updated simultaneously. This is impossible in practice; even small TCP extensions have taken 10–15 years for widespread deployment. QUIC bypasses this by running over UDP with an encrypted payload — middleboxes see UDP, pass it through, and cannot inspect or modify the QUIC header.

**(d)** QUIC is not unreliable because it **implements its own reliability layer** on top of UDP. QUIC has its own sequence numbers, ACKs, retransmission logic, and congestion control — everything TCP provides — but implemented in user space rather than the OS kernel. QUIC *uses* UDP's datagram delivery (bypassing TCP's stream abstraction) but provides all the reliability guarantees TCP offers, plus additional features like per-stream reliability and 0-RTT connection resumption.

**(e)** Comparison table:

| Feature | UDP | TCP | QUIC |
|---------|-----|-----|------|
| Connection setup | None | 3-way handshake (1 RTT) | 1 RTT new, 0 RTT resumed |
| Reliability | None | Yes (byte stream) | Yes (per stream) |
| HOL blocking | N/A | Yes (one byte stream) | No (independent streams) |
| Encryption | None (app layer) | TLS separate (+1 RTT) | TLS 1.3 built-in |
| Connection migration | N/A | No (4-tuple bound) | Yes (connection ID) |

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 20 notes.*