# TCP Part 1: How Reliability Is Actually Built

**EC 441 — Lecture 19 Report**  
*Topic: TCP's connection model, byte-stream sequencing, RTT estimation, and flow control*

---

## Introduction

Lecture 18 established the building blocks of reliable transfer: sequence numbers, acknowledgments, timers, and pipelining. TCP is the deployed protocol that assembles these pieces into a full-duplex, byte-stream service used by virtually every application that needs reliability — HTTP, SSH, email, database protocols, file transfer. TCP's genius is not in any single mechanism but in the integration: a careful marriage of connection management, adaptive timing, and flow control that has been refined over four decades and still runs correctly on a global network with millions of simultaneously active connections.

This report walks through the core mechanisms of TCP Part 1: why connections matter, how TCP sequences bytes rather than packets, why initial sequence numbers must be random, and how TCP adapts its retransmission timer to changing network conditions.

---

## The Segment Header: 40 Years of Backward Compatibility

The TCP header is 20 bytes minimum — 10 two-byte fields packed tightly. Every field earns its place. The Source and Destination Port fields provide multiplexing (one IP address, many simultaneous connections). The Sequence Number and Acknowledgment Number fields implement the byte-stream model. The Window Size field enables flow control. The six flag bits encode the connection state machine.

Two fields deserve particular attention: the Data Offset and the Options.

Data Offset, like IP's IHL field, specifies the header length in 32-bit words. The minimum is 5 (20 bytes); the maximum is 15 (60 bytes), leaving 40 bytes for options. This extensibility mechanism has been crucial: the Window Scale option (for large windows), the SACK option (for selective acknowledgment), and the Timestamps option (for precise RTT measurement) were all added without changing the base protocol. Any TCP implementation that doesn't recognize an option can simply ignore it.

---

## The Byte-Stream Model: Why Sequence Numbers Count Bytes

TCP is not a packet-based protocol at the application layer. It is a byte-stream protocol. The application writes bytes and reads bytes; TCP has no concept of message boundaries. Two 100-byte writes by the sender might be read as one 200-byte read by the receiver, or as four 50-byte reads, or as any other subdivision. This is fundamentally different from UDP, where each send produces exactly one datagram.

The byte-stream model dictates the sequencing scheme. TCP sequence numbers are **byte offsets**, not packet numbers. If the initial sequence number is 1000 and the first segment carries 500 bytes of data, those bytes are numbered 1000–1499. The second segment starts at 1500. An ACK of 1500 means "I have received all bytes through 1499; send me byte 1500 next." One ACK can acknowledge a thousand bytes or a million bytes — it doesn't matter how many segments carried them.

This has a practical implication: the ACK from the receiver is "your sequence number + bytes received = my next expected byte." The mnemonic from the slides captures it cleanly: "your SEQ is my ACK." SYN and FIN each consume one sequence number, even though they carry no data, because the connection-setup and teardown events themselves need to be reliably acknowledged.

---

## The 3-Way Handshake: Why Three Messages?

Before TCP can exchange data, both sides must agree on initial sequence numbers and negotiate options. The minimum number of messages to achieve **mutual** agreement is three. Two messages only let one side confirm the other's ISN.

The handshake serves multiple functions simultaneously: it establishes ISNs for both directions, exchanges MSS and Window Scale options, signals SACK support, and negotiates Timestamps. The SYN-ACK is the server's confirmation of the client's ISN *plus* the server's own ISN in a single segment — the protocol's elegance in minimizing round trips.

Why must SYN and SYN-ACK consume sequence space even though they carry no payload? Because if the SYN is lost and retransmitted, the receiver needs to distinguish the retransmit from a subsequent new connection. SYN occupying sequence number x means ACK x+1 unambiguously acknowledges the SYN itself, not just the absence of data.

---

## ISN Randomization: Two Problems, One Solution

Starting every connection at sequence number 0 would be a security and correctness disaster. The lecture identifies two distinct problems, and ISN randomization solves both.

The **correctness problem** is stale segments. TCP connections are identified by 5-tuples (protocol, source IP, source port, destination IP, destination port). When a connection closes, the OS may immediately reuse the source port for a new connection to the same destination. Any segment from the old connection still in transit — delayed in a router's queue, perhaps — now arrives with a sequence number. If the new connection also starts at 0, that old segment may fall within the new connection's window and be accepted as valid data, silently corrupting the application's byte stream.

Randomizing the ISN makes the probability of overlap negligible. Even with the same 5-tuple, a retransmitted segment from a previous connection will almost certainly have a sequence number outside the new connection's window.

The **security problem** is sequence prediction attacks. An off-path attacker cannot see the SYN-ACK (they're not on the network path), so they don't know the server's ISN. But if the server's ISN is predictable — if it increments by a known amount on each connection — the attacker can guess the ACK value needed to forge a valid TCP segment. A predictable ISN enables injection of arbitrary data into a connection the attacker cannot observe. This was a real attack in the early internet (the Kevin Mitnick attack in 1994 exploited it). Modern Linux generates ISNs as MD5(source IP, destination IP, source port, destination port, secret key, timestamp) — cryptographically unpredictable.

---

## Connection Teardown: Half-Close and TIME_WAIT

TCP's teardown is asymmetric. Each direction closes independently. When an application calls close(), TCP sends FIN — "I have no more data to send." But the other side may still have data in flight. The receiver of a FIN must ACK it, but can continue sending data until it is ready to close its own direction (the "half-close" state).

TIME_WAIT is one of TCP's most misunderstood features. After the active closer (the side that sent the first FIN) receives the final FIN and sends the last ACK, it does not immediately close the socket. It waits for 2 × MSL (Maximum Segment Lifetime, typically 2 minutes) before the socket is freed. Two reasons:

First, the final ACK might be lost. If it is, the remote side will retransmit its FIN. The active closer must still be alive to re-ACK it. Without TIME_WAIT, the retransmitted FIN would arrive at a closed socket, triggering a RST — leaving the remote side uncertain whether the connection was cleanly closed.

Second, any delayed segments from this connection must expire before the 5-tuple can be reused. TCP guarantees that old segments from a previous connection on the same 5-tuple cannot corrupt a new connection. TIME_WAIT enforces this guarantee by preventing 5-tuple reuse for long enough that any in-flight ghosts from the old connection will have been dropped by their TTL.

A busy web server seeing hundreds of TIME_WAIT sockets is normal and correct — not a bug.

---

## RTT Estimation: The EWMA as a Low-Pass Filter

TCP must set a retransmission timeout that is neither too short (spurious retransmits, wasted bandwidth) nor too long (slow loss recovery). The right value depends on the network's round-trip time — which varies over time and must be estimated from observed samples.

Van Jacobson's 1988 algorithm uses two Exponentially Weighted Moving Averages:

```
RTTVAR ← (1 − β) × RTTVAR + β × |SRTT − R|    (β = 1/4)
SRTT   ← (1 − α) × SRTT   + α × R             (α = 1/8)
RTO    = SRTT + 4 × RTTVAR
```

Expanding the SRTT recursion shows that past samples are weighted by a geometrically decaying envelope with ratio (1 − α). This is a first-order IIR low-pass filter — the SRTT tracks the slowly-varying mean of the RTT signal while suppressing high-frequency noise. The time constant is approximately 1/α = 8 RTT measurements.

RTTVAR tracks the *variability* of the RTT — roughly the mean absolute deviation from the smoothed mean. The RTO formula is "mean plus four times variability" — a confidence interval that adapts to the network. On a stable LAN, RTTVAR is small and RTO tracks SRTT closely. On a congested or variable path, RTTVAR grows and RTO provides safety margin.

The choice α = 1/8 = 2^(−3) makes the update computable as a right bit-shift — no floating-point required. This was critical for 1980s router hardware and remains computationally trivial today. The same formula runs in Linux's TCP stack unchanged since 1988.

---

## Fast Retransmit: Not Waiting for the Timer

The retransmission timer provides correctness but is slow. On a 100ms RTT path, a timeout might fire after 200–400ms (with backoff). But loss can often be detected much sooner.

When a receiver gets an out-of-order segment, it immediately sends an ACK for the last in-order byte — a **duplicate ACK**. The sender collects these: one or two duplicate ACKs can arise from normal IP reordering (packets taking slightly different paths). Three duplicate ACKs is a statistically reliable loss signal — by that point, three later packets have arrived in order after the gap, and reordering of that magnitude is extremely unlikely on modern networks.

Three duplicate ACKs trigger **fast retransmit**: the sender retransmits the lost segment immediately, without waiting for the RTO. This can cut loss recovery time from hundreds of milliseconds to one RTT.

---

## Flow Control: Telling the Sender to Slow Down

Even if the network is perfect, the receiver can be overwhelmed. The application might read data slowly; the receive buffer might fill. Without flow control, the sender would keep transmitting, the buffer would overflow, and data would be silently discarded — requiring retransmission of data the network delivered correctly.

TCP's solution is the **receive window** (`rwnd`), advertised in every ACK. `rwnd` = free bytes in the receiver's buffer. The sender keeps bytes-in-flight ≤ rwnd. As the application reads data and frees buffer space, `rwnd` grows, and the receiver advertises the larger value — opening the window and allowing more data in.

When `rwnd = 0`, the sender pauses and enters a "persist" state, periodically sending one-byte probes to check whether space has reopened. Without this, the window-open notification from the receiver might be lost, creating a deadlock where the sender is waiting for permission and the receiver is waiting for data.

Flow control answers one of the two critical resource questions: "is the receiver ready?" The other question — "is the network ready?" — is answered by congestion control, which uses the `cwnd` variable introduced in Lecture 20.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 19 notes.*