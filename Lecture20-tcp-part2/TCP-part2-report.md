# TCP Part 2: Congestion Control and the Modern Picture

**EC 441 — Lecture 20 Report**  
*Topic: How TCP regulates its sending rate to avoid collapsing the network it depends on*

---

## Introduction

Lecture 19 left one variable undefined: `cwnd`, the congestion window. Flow control — the receive window `rwnd` — ensures the sender doesn't overwhelm the *receiver's* buffer. But the receiver's buffer is not the only resource at stake. Between sender and receiver lies a network of routers with finite queue capacity. If every TCP sender probes for maximum throughput simultaneously, routers' queues fill, packets drop, and retransmissions flood the network — each one consuming bandwidth, requiring more retransmissions, causing more drops. In 1986, this feedback loop caused "congestion collapse" on the internet, reducing throughput on some paths by a factor of 1000.

Congestion control is TCP's self-regulation mechanism: the protocol backs off when it detects network stress, and probes cautiously when things seem calm. The elegance of the design is that no router ever explicitly signals congestion. TCP infers it from packet loss — a dropped packet means a queue somewhere overflowed, which means the network is overloaded, which means the sender should slow down.

---

## The Two Limits on Sending Rate

TCP's effective sending rate is bounded by two independent constraints:

```
effective window = min(cwnd, rwnd)
```

`rwnd` (receive window) is set by the receiver based on its available buffer space. It protects the receiver from being overwhelmed. `cwnd` (congestion window) is maintained by the sender based on its inference about network capacity. It protects the network from being overwhelmed.

Flow control is **explicit**: the receiver directly advertises `rwnd` in every ACK. Congestion control is **implicit**: no router says "I am congested." The sender watches for lost packets as a proxy for queue overflow, and adjusts `cwnd` accordingly. This end-to-end inference is what makes TCP remarkable — it achieves network-wide stability through purely local decisions at each sender, without any coordination protocol between them.

---

## Slow Start: Exponential Growth by Design

When a TCP connection starts (or after a timeout), the sender has no information about the available bandwidth. Sending at full window size immediately might flood the bottleneck link. TCP starts conservatively at `cwnd = 1 MSS` and probes the network by increasing `cwnd` exponentially.

The mechanism: for every ACK received, `cwnd` increases by 1 MSS. Since a window of N segments produces N ACKs in one RTT, `cwnd` doubles each RTT — exponential growth. Despite the name, "slow start" is not slow; it reaches large windows quickly. "Slow" refers to the starting point (1 MSS), not the growth rate.

Slow start continues until `cwnd` reaches `ssthresh` (slow-start threshold). At that point, TCP switches to **congestion avoidance**: `cwnd` increases by only 1 MSS per RTT (implemented as `+MSS²/cwnd` per ACK). The transition from exponential to linear growth reflects the intuition that once the window is large enough to fill the pipe, aggressive probing risks loss.

`ssthresh` is initialized to a large value (effectively unlimited) and set to `cwnd/2` on the first loss event, encoding the estimate of where congestion began.

---

## AIMD: The Sawtooth and Why It Works

Congestion avoidance implements **Additive Increase, Multiplicative Decrease (AIMD)**:

- **Additive increase**: `cwnd += 1 MSS` per RTT during normal operation.
- **Multiplicative decrease**: `cwnd = ssthresh = cwnd/2` on a loss event (3 dup ACKs) or `cwnd = 1` on timeout.

This produces the characteristic sawtooth: cwnd grows linearly, hits a congestion signal, drops sharply, grows again. The asymmetry between increase and decrease is deliberate. Slow growth (additive) prevents overshooting the available bandwidth. Sharp decrease (multiplicative) quickly frees queue space, allowing competing flows to recover.

The fairness of AIMD emerges from a geometric argument. Consider two flows sharing a bottleneck. Both receive the same loss signal at the same time and halve simultaneously — moving along a ray toward the origin. Both increase linearly and by equal amounts — moving parallel to the equal-share line. The combination of these two movements produces a spiral toward the intersection of the equal-share line and the full-utilization line. Neither flow dominates in the long run, and together they fill the link.

This is AIMD's theoretical elegance: it is the unique simple linear policy that achieves both efficiency (uses available bandwidth) and fairness (equal-share convergence) without any coordination between flows.

---

## Fast Recovery: Not All Loss Is Equal

When a timeout fires, nothing is getting through. The network is severely congested — the sender resets `cwnd = 1 MSS` and restarts slow start. This is appropriate for complete network failure, but excessive for a minor hiccup.

When 3 duplicate ACKs arrive, the picture is different. Later segments are still being received (hence the dup ACKs). One packet was lost, but the network is still functioning. Treating this as a timeout — restarting from cwnd=1 — would be needlessly conservative.

Fast recovery (introduced with TCP Reno) handles 3-dup-ACK loss events more gently:
1. `ssthresh = cwnd/2`
2. `cwnd = ssthresh` (skip slow start entirely — dup ACKs prove the network is working)
3. Retransmit the missing segment immediately, without waiting for RTO
4. Each additional dup ACK during recovery: `cwnd += 1 MSS` (inflation: each dup ACK represents one more segment delivered to the receiver)
5. New ACK (recovering from loss): `cwnd = ssthresh`, return to congestion avoidance

The asymmetry is correct: timeout means "restart from scratch"; 3 dup ACKs means "back off by half and stay productive."

---

## The Throughput Formula: RTT and Loss Are Expensive

Mathis et al. (1997) derived a steady-state approximation for TCP Reno's throughput:

```
BW ≈ (MSS / RTT) × (1 / √p)
```

This formula reveals two fundamental constraints. Throughput scales as **1/RTT** — connections with longer round-trip times systematically get less bandwidth than shorter-RTT connections, even if both see the same loss rate. This is TCP Reno's RTT unfairness: a datacenter connection (RTT=1ms) and an intercontinental connection (RTT=150ms) sharing a bottleneck will split bandwidth 150:1 in favor of the short-RTT flow.

Throughput scales as **1/√p** — very sensitive to loss. To achieve 10 Gb/s over a 100ms RTT path with 1460B MSS, the required loss rate is approximately 2×10⁻¹⁴ — fewer than one drop per trillion segments. This is physically impossible on any real network. The formula explains why TCP Reno cannot achieve high throughput on high-BDP paths with any realistic loss rate, motivating the development of CUBIC and BBR.

---

## CUBIC: Time-Based Rather Than ACK-Based

TCP Reno's growth is **RTT-clocked**: cwnd increases by 1 MSS per RTT. This creates RTT unfairness — flows with shorter RTTs grow faster.

CUBIC (the default in Linux since kernel 2.6.19) replaces RTT-clocked linear growth with a **cubic function of wall-clock time**:

```
W(t) = C(t − K)³ + Wmax
```

where `Wmax` is the window at the last congestion event, and `K` is chosen so that `W(0) = Wmax/2`. Growth is slow near `Wmax` (cautious probing near the last congestion point) and fast when far from it (rapid recovery of available bandwidth).

Because CUBIC's growth rate is clocked by wall time rather than RTTs, it is **RTT-independent** — a 10ms flow and a 100ms flow grow at the same absolute rate in windows/second, rather than the same relative rate in windows/RTT. This substantially improves fairness on networks with mixed-RTT flows. CUBIC also recovers faster than Reno on high-BDP paths, where the RTT-paced linear growth of Reno takes many seconds to reclaim available bandwidth after a loss event.

---

## ECN: Signaling Without Dropping

TCP's default congestion signal is a dropped packet: router queue overflows, packet discarded, sender detects loss, reduces cwnd. This works, but it is lossy by design — the very mechanism that signals congestion destroys the packet that triggered it, requiring a retransmission.

Explicit Congestion Notification (ECN) replaces the drop with a mark: when a router's queue begins to build (before overflow), it sets the CE (Congestion Experienced) bit in the IP header of a packet it is forwarding. The packet arrives at the receiver. The receiver echoes the CE signal via the ECE flag in its next ACK. The sender receives the ECE-flagged ACK and reduces cwnd exactly as it would for a 3-dup-ACK loss event.

ECN's advantages are clear: no packet is dropped (no retransmission needed), and the congestion signal fires *before* the queue overflows rather than after. Earlier signaling means smaller queues, lower latency, and less sawtooth amplitude. ECN is widely deployed in datacenters where all equipment is controlled. On the public Internet, deployment is incomplete — legacy middleboxes clear ECN bits, some endpoints don't support it — but progress continues.

---

## QUIC: Redesigning the Transport Layer

TCP's problems are well-known: head-of-line blocking in multiplexed streams, multi-RTT connection setup, protocol ossification from middlebox interference, connection disruption on network handoffs. The challenge is that fixing TCP requires updating every middlebox in the internet — effectively impossible.

QUIC's approach is architectural bypass. By running over UDP, QUIC's payload is opaque to middleboxes — they see UDP, pass it through, and cannot inspect or tamper with the QUIC header. QUIC implements all of TCP's reliability, ordering, and congestion control in user space, plus additional features: per-stream reliability (no HOL blocking), built-in TLS 1.3 (1 RTT new, 0 RTT resumed connections), and connection IDs (survives IP address changes).

The progression from UDP's eight bytes to QUIC's encrypted variable-length header represents fifty years of learning what the transport layer needs to do, and what it can safely leave out. QUIC now carries approximately 25% of internet traffic, powering HTTP/3, YouTube, and Google's infrastructure — demonstrating that the transport layer is not frozen, even if TCP itself appears to be.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 20 notes.*