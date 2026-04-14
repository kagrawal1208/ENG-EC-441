# The Transport Layer: From Best-Effort to Reliable Delivery

**EC 441 — Lecture 18 Report**  
*Topic: How the transport layer bridges the gap between unreliable IP and the reliable streams applications expect*

---

## Introduction

The internet's network layer makes one promise: it will try to deliver your packet. It offers no guarantees about whether the packet arrives, in what order, or even once. This "best-effort" model is deliberate — it keeps routers simple and fast. But it creates a problem for applications. A web browser, an SSH session, a file transfer — none of these can tolerate missing data or out-of-order bytes. Someone has to fill the gap between "I'll try" and "I guarantee."

That someone is the transport layer. Lecture 18 introduces two transport protocols that represent opposite answers to the question of how much work the transport layer should do: UDP, which adds almost nothing to IP, and the mechanisms behind TCP (Stop-and-Wait, GBN, SR), which add reliable delivery. Understanding why both exist, and why reliable delivery is harder than it first appears, is the foundation for everything TCP does in the next two lectures.

---

## What the Transport Layer Actually Adds

IP delivers datagrams from host to host. But a host is not an endpoint — a *process* is. Multiple applications run simultaneously on the same machine, all sharing a single IP address. The first job of the transport layer is to extend host-to-host delivery into process-to-process delivery. It does this through **ports** and **sockets**.

A port is a 16-bit number that identifies an endpoint within a host. Ports 0–1023 are reserved for well-known services (SSH on 22, DNS on 53, HTTP on 80). Ports 49152–65535 are ephemeral — assigned by the OS to client-side sockets on demand. The combination of a transport-layer header's source and destination ports with the IP layer's source and destination addresses gives a **5-tuple** that uniquely identifies one end of a communication.

**Multiplexing** is what the sender does: collect data from multiple sockets, add port headers, hand everything to IP. **Demultiplexing** is what the receiver does: read the arriving segment's port fields and route it to the right socket. UDP and TCP demultiplex differently. For UDP, the demultiplexing key is just (destination IP, destination port) — all datagrams to the same address:port go to the same socket. For TCP, the key is the full 5-tuple — which is why a web server can have thousands of simultaneous TCP connections all on port 80, each routed to its own socket.

---

## UDP: Deliberate Minimalism

UDP adds exactly eight bytes to IP: source port, destination port, length, and checksum. That's it. No connection setup, no delivery guarantee, no ordering, no congestion control. The application gets raw datagram delivery with process demultiplexing.

This sounds like a list of deficiencies. It is actually a list of choices. UDP is the right tool when:

**Latency matters more than completeness.** VoIP and online games cannot wait for a retransmission. A retransmitted audio packet arrives too late to be useful — a small gap in audio is less disruptive than hearing yesterday's speech today. The application would rather skip the packet than wait for it.

**Each transaction fits in one datagram.** DNS queries and responses are typically one packet each. Using TCP for DNS would add at least 1.5 RTTs of handshake overhead before the first byte of query could be sent — a 150% latency penalty for a round-trip that might itself be only a few milliseconds.

**Multicast or broadcast is needed.** TCP requires a point-to-point connection. UDP can address groups.

**The application controls reliability.** QUIC, WebRTC, and similar protocols implement their own loss recovery, congestion control, and encryption on top of UDP. By building above the transport layer rather than inside it, they can innovate without modifying the OS kernel — and they avoid TCP's head-of-line blocking problem.

The UDP checksum deserves a note. It is computed over a pseudo-header that includes both endpoint IP addresses, even though IP addresses are in the IP header, not the UDP header. The reason is subtle: if a datagram is routed to the wrong host, the IP addresses in the pseudo-header will not match the intended ones, and the checksum will fail. This catches misdelivery that would otherwise be invisible to UDP.

---

## Why Reliable Transfer Is Harder Than It Looks

The naïve approach to reliability is: "if something goes wrong, retransmit." But this immediately raises four harder questions:

1. **How does the sender know something went wrong?** The network doesn't send a "your packet was dropped" notification. The sender must detect loss indirectly — either by waiting for an acknowledgment that never comes (timer-based detection) or by seeing the receiver signal a gap (duplicate ACK detection).

2. **Which packet needs retransmission?** When a timeout fires, the sender must know which packets are unacknowledged. **Sequence numbers** label packets so the sender can track exactly what's been received.

3. **How does the receiver avoid delivering duplicates?** If the sender retransmits packet 0 because an ACK was lost, the receiver might see packet 0 again after already delivering it. Without sequence numbers, it would deliver a duplicate to the application. With sequence numbers, it recognizes the retransmit and discards it.

4. **How does the sender stay busy while waiting for ACKs?** This is the performance crisis of Stop-and-Wait.

The four building blocks that answer these questions — sequence numbers, acknowledgments, timers, and checksums — appear in every reliable data transfer protocol, from the simplest academic ARQ to TCP running on a 400Gb/s datacenter interconnect.

---

## Stop-and-Wait: Correct but Catastrophically Slow

Stop-and-Wait is the simplest possible reliable protocol: send one packet, wait for the ACK, then send the next. With one-bit alternating sequence numbers (the "Alternating Bit Protocol"), the receiver can always distinguish a new packet from a retransmit.

The correctness is elegant. The performance is disastrous. Consider a 1 Gb/s geostationary satellite link with a 600 ms RTT. Transmitting a 1500-byte packet takes 12 microseconds. The sender then idles for 600 milliseconds waiting for the ACK. Link utilization:

```
U = t_transmit / (RTT + t_transmit) = 0.012ms / 600ms ≈ 0.002%
```

A 1 Gb/s link delivers approximately 20 kilobits per second. The problem is not the link — it's that Stop-and-Wait keeps only one packet in the pipe at a time, and the pipe is enormous. The bandwidth-delay product of this link is 600 megabits — the number of bits that could be "in flight" on a fully utilized link. Stop-and-Wait sends 12,000 bits, then waits. 99.998% of the capacity is wasted.

The fix is **pipelining**: send multiple packets before waiting for ACKs. The window size needed to fill the pipe is BDP / packet_size ≈ 50,000 packets. Pipelining introduces a new problem: what happens when a packet in the middle of the pipeline is lost? This is the design choice that separates Go-Back-N from Selective Repeat.

---

## Go-Back-N: Simple Receiver, Costly Loss Recovery

GBN allows the sender to have up to N unacknowledged packets in flight at once. ACKs are **cumulative**: ACK n means "I have received all packets through n correctly." The receiver needs no buffer — any out-of-order packet is discarded immediately.

When the timer fires for the oldest unacknowledged packet, the sender retransmits **every packet in the window**. This is the "go back N" — retransmit from the point of loss forward. The receiver simplicity (no buffer) trades off against transmission efficiency under loss: one dropped packet triggers retransmission of N packets. Under a 10% loss rate with window N=40, each loss event wastes 39 unnecessary retransmissions.

GBN's sequence number constraint is N ≤ 2^k − 1. Allowing N = 2^k would mean the unacknowledged window wraps around to overlap with new packet sequence numbers — the receiver couldn't distinguish a retransmit from a new packet.

---

## Selective Repeat: Efficient But Complex

SR fixes GBN's retransmission waste: the receiver **buffers** out-of-order packets and ACKs each one **individually**. The sender keeps a per-packet timer and retransmits **only** the lost packet when its timer fires.

The cost is receiver complexity. SR needs a buffer of size N at the receiver. The sequence number constraint tightens to N ≤ 2^(k-1) — half the sequence space. The reason is subtle: if the window were larger, the receiver couldn't tell whether a packet with sequence number 0 is a new packet (just past the end of the window) or a retransmit of an old packet (from the beginning of the window) after all ACKs were lost.

Under high loss rates, SR substantially outperforms GBN. Under low loss rates, the difference is negligible and GBN's simpler receiver may be preferred.

---

## What TCP Inherits from Each

TCP is not a clean implementation of either GBN or SR. It borrows the useful pieces from both:

From GBN: **cumulative ACKs** (the default TCP ACK behavior), which allow a single ACK to acknowledge a large burst of data. From SR: **receiver buffering** (the TCP receive buffer, advertised as `rwnd`) and the SACK option (an explicit add-on that provides SR-style individual ACK ranges). From neither: TCP's fast retransmit mechanism, which uses three duplicate ACKs as an early loss signal — a hybrid that doesn't wait for a timer but also doesn't require a full SR receiver.

The progression from Stop-and-Wait through GBN and SR is not just academic history. It is the design space that every reliable transport protocol must navigate, and the choices TCP made in 1981 — and the refinements added over the following decades — are still visible in every TCP segment on the internet today.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 18 notes.*