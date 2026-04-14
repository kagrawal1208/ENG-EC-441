# EC 441 — Lecture 18 Problem Set: Transport Layer, UDP, and Reliable Data Transfer

**Topic:** Transport Layer, UDP, Reliable Data Transfer (Stop-and-Wait, GBN, SR)  
**Lecture:** 18  
**Covers:** Multiplexing/demultiplexing, ports/sockets, UDP header, link utilization, BDP/pipelining, Go-Back-N, Selective Repeat, GBN vs SR tradeoffs

---

## Problem 1: Multiplexing and Demultiplexing

Host A runs three processes simultaneously: a browser with an HTTPS connection to a server at 93.184.216.34:443, an SSH session to 128.197.20.200:22, and a DNS query to 8.8.8.8:53.

**(a)** For the HTTPS connection, what is the 5-tuple that uniquely identifies the TCP socket? What does the OS use as the demux key for incoming TCP segments?

**(b)** For the DNS query, what protocol is used at the transport layer, and what is the demux key for incoming UDP segments? Why is the key shorter for UDP than TCP?

**(c)** If a second browser tab opens another HTTPS connection to the same server (93.184.216.34:443), how does the OS distinguish between incoming segments for the two tabs?

**(d)** A student suggests: "If UDP's demux key is just (dst IP, dst port), couldn't two different clients accidentally share a UDP socket?" Explain whether this is a problem and how it is actually handled.

### Solution

**(a)** 5-tuple: **(TCP, HostA-IP, ephemeral-port, 93.184.216.34, 443)**. The ephemeral port is assigned by the OS from range 49152–65535. For incoming TCP segments, the demux key is the **full 5-tuple** — all five fields must match to identify the correct socket.

**(b)** DNS uses **UDP** (port 53 by default). The demux key for UDP is **(dst IP, dst port)** — just two fields. UDP's key is shorter because UDP has no connection state: any datagram destined for (HostA-IP, 53) is delivered to the same socket. TCP requires the full 5-tuple because thousands of separate connections can all have dst port 443 (e.g., a web server), and each must map to a distinct socket.

**(c)** Each browser tab gets a **different ephemeral source port** (e.g., tab 1 uses :54312, tab 2 uses :54313). Even though both connect to 93.184.216.34:443, their 5-tuples differ in the source port field. The OS uses the full 5-tuple to demultiplex, routing each ACK and data segment to the correct tab's socket.

**(d)** This is not a problem in practice because each client has a **different source IP address**. The UDP demux key is (dst IP, dst port) from the *receiver's* perspective — two different clients sending to the same UDP server port arrive at the same server socket, which is correct. The server then reads the source IP/port from the received datagram to know where to send the reply. The key difference from TCP: UDP has one server socket per port; TCP can have thousands of server sockets all on port 80 (one per accepted connection).

---

## Problem 2: UDP Header and Checksum

A UDP segment is sent with the following parameters:
- Source IP: 10.0.0.1, Destination IP: 10.0.0.2
- Source Port: 5000, Destination Port: 53
- Payload: 20 bytes of DNS query data

**(a)** What is the total length of the UDP datagram (header + payload)? What value appears in the Length field?

**(b)** The UDP checksum pseudo-header includes source IP, destination IP, a zero byte, the protocol number, and UDP length. Why are the IP addresses included in the checksum computation, even though they are in the IP header, not the UDP header?

**(c)** A router accidentally delivers this datagram to host 10.0.0.3 (wrong destination) due to a forwarding bug. The IP header has been updated with the correct destination, but the UDP checksum has not been recomputed. What happens when host 10.0.0.3 receives this segment?

**(d)** Is the UDP checksum optional in IPv6? Why or why not?

### Solution

**(a)** Header = 8 bytes, payload = 20 bytes → **total = 28 bytes**. The Length field contains **28** (covers header + data, in bytes).

**(b)** The IP addresses are included in the checksum pseudo-header to guard against **misdelivered datagrams**. If a packet is routed to the wrong host, the source/destination IP fields in the pseudo-header will no longer match the intended values, causing the checksum to fail at the receiver. Without IP addresses in the checksum, a packet routed to the wrong host might pass the UDP checksum check and be incorrectly delivered to an application.

**(c)** The checksum was computed with destination IP = 10.0.0.2 in the pseudo-header. Host 10.0.0.3 recomputes the checksum with its own IP (10.0.0.3) in the pseudo-header. The result **won't match** the checksum in the segment → the datagram is silently **dropped**. The misdelivery is caught.

**(d)** The UDP checksum is **mandatory in IPv6**. In IPv4, it was optional (value 0x0000 = "not computed") because IPv4 had its own header checksum providing some protection. IPv6 **removed the IP-layer header checksum entirely** (to reduce per-hop processing overhead), so the UDP checksum is the only integrity check available and must always be computed.

---

## Problem 3: Stop-and-Wait Link Utilization

A sender uses Stop-and-Wait to transmit over a trans-Atlantic fiber link with the following parameters:
- Link bandwidth: 10 Gb/s
- One-way propagation delay: 35 ms (RTT = 70 ms)
- Packet size: 9,000 bytes (jumbo Ethernet frame)

**(a)** Calculate the transmission time for one packet.

**(b)** Calculate the link utilization U under Stop-and-Wait.

**(c)** How many packets would need to be in flight simultaneously (window size) to achieve 100% utilization? What does this imply about the bandwidth-delay product?

**(d)** Suppose the link degrades and now has a 0.1% packet loss rate. What is the effective throughput of Stop-and-Wait over this link (accounting for retransmissions, ignoring the already-terrible utilization)?

### Solution

**(a)** Transmission time = (9,000 × 8 bits) / (10 × 10⁹ b/s) = 72,000 / 10,000,000,000 = **7.2 µs**

**(b)** U = t_tx / (RTT + t_tx) = 0.0072 ms / (70 + 0.0072) ms = **≈ 0.0103% ≈ 0.01%**  
The sender wastes 99.99% of its time waiting for the ACK.

**(c)** To achieve 100% utilization, the window must fill the pipe:  
BDP = 10 Gb/s × 70 ms = 700 Mb = 87.5 MB  
Packets needed = 87,500,000 bytes / 9,000 bytes ≈ **9,722 packets in flight**  
This is the bandwidth-delay product in packets — the number of packets that fit in the "pipe" end-to-end.

**(d)** With S&W, each packet loss requires a full RTT to recover (timeout + retransmit). Expected transmissions per successful packet = 1/(1-p) = 1/0.999 ≈ 1.001. So effective throughput ≈ 0.01% × (1/1.001) ≈ **0.01%** — the loss barely matters compared to the utilization catastrophe. S&W is so inefficient that its throughput is dominated by the wait time, not the loss rate.

---

## Problem 4: Go-Back-N Protocol Trace

A GBN sender has window size N = 4 and uses 3-bit sequence numbers (0–7). The following events occur in order: send packets 0, 1, 2, 3 → packet 1 is lost → ACK 0 arrives → timer fires on packet 1.

**(a)** After the sender sends packets 0–3, what is the state of the sender's window? Identify which packets are "sent but unACKed" vs "sendable."

**(b)** ACK 0 arrives (cumulative). What does this mean? How does the window slide?

**(c)** The timer fires on packet 1. What does GBN retransmit? Why is this considered wasteful when loss rate is high?

**(d)** During the retransmission, the receiver gets packets 1, 2, 3, 4 in order. Trace the ACK sequence the receiver sends.

**(e)** What is the maximum window size for GBN with k=3 bit sequence numbers? Why can't the window be 2^k = 8?

### Solution

**(a)** Window = [0, 1, 2, 3]. Packets 0–3 all "sent but unACKed." Sendable: none (window full). Not yet usable: 4, 5, 6, 7.

**(b)** ACK 0 (cumulative) means: "I have received all packets through 0 correctly." Window slides by 1: window becomes [1, 2, 3, 4]. Packet 4 is now sendable. Packet 0 is freed from the sender's buffer.

**(c)** GBN retransmits **all packets in the window: 1, 2, 3** (and possibly 4 if it was sent). Even though packets 2 and 3 arrived correctly at the receiver, GBN discards out-of-order packets — the receiver has no buffer. So those correctly-delivered packets must be re-sent. Under high loss rates, this creates a multiplicative retransmission overhead: one loss causes N retransmissions.

**(d)** Receiver sends: **ACK 1, ACK 2, ACK 3, ACK 4** (one per packet received in order). Each ACK is cumulative — ACK 3 means "received everything through packet 3."

**(e)** Maximum window size = 2^k − 1 = 2^3 − 1 = **7**. With 8 packets in flight and 3-bit sequence numbers, after the sender sends 0–7 and all ACKs are lost, the receiver can't distinguish whether a retransmitted "pkt 0" is a retransmit of the old sequence 0 or a new packet 8 (which also has sequence number 0 mod 8). Limiting to N ≤ 2^k − 1 ensures the unACKed window and the next new-packet range never overlap in sequence number space.

---

## Problem 5: Selective Repeat vs. Go-Back-N

A 4-bit sequence number space (seqnums 0–15) is used. For each protocol, answer the following:

**(a)** What is the maximum window size for GBN? For SR? Explain the difference in the constraint.

**(b)** With SR and N = 8, packet 5 is lost but packets 6, 7, 8, 9, 10, 11, 12 all arrive. Describe the state at the receiver: what is buffered, what is delivered to the application, and what ACKs are sent for packets 6–12?

**(c)** When packet 5 is retransmitted and arrives, what happens at the SR receiver? Walk through the buffer delivery carefully.

**(d)** Under a 5% loss rate with window size 8, which protocol has higher throughput? Give a brief quantitative argument.

**(e)** A student says: "SR requires a stricter sequence number constraint than GBN because SR receivers buffer packets." Explain *why* the buffer creates the stricter constraint — what ambiguity does it prevent?

### Solution

**(a)** 4-bit sequence numbers → 2^4 = 16 sequence numbers.  
**GBN**: N ≤ 2^k − 1 = **15**  
**SR**: N ≤ 2^(k-1) = **8**  
The SR constraint is half as large because SR receivers buffer out-of-order packets and ACK them individually. If N > 2^(k-1), a receiver can't distinguish a new packet from a retransmit of an already-delivered packet (see part e).

**(b)** Receiver base = 5. Packets 6–12 are in the window [5, 12]. All arrive, but packet 5 (the base) is missing. Since 5 hasn't arrived, the window can't slide. State: **packets 6–12 are buffered**. None are delivered to the application yet (delivery requires in-order). ACKs sent: **ACK 6, ACK 7, ACK 8, ACK 9, ACK 10, ACK 11, ACK 12** (individual, not cumulative).

**(c)** Packet 5 arrives. rcv_base = 5, packet 5 = rcv_base → deliver. Then check buffer: 6 is buffered → deliver, 7 → deliver, ..., 12 → deliver. **All 8 packets (5–12) delivered to application in order**. Window slides to rcv_base = 13.

**(d)** With SR, only the lost packet is retransmitted. Expected retransmissions per window ≈ N × p = 8 × 0.05 = 0.4 retransmits per window. Effective throughput ≈ (1 − 0.05) × effective send rate.  
With GBN, each loss retransmits the entire window. If packet i is lost, packets i through i+N-1 are retransmitted → N × p retransmissions, but *each* wastes N−1 good transmissions. Wasted bandwidth per loss event ≈ N−1 = 7 packets. **SR has substantially higher throughput** at 5% loss with N=8; GBN wastes ~7× more bandwidth per loss event.

**(e)** Suppose SR uses N = 9 with 4-bit sequence numbers (16 values). After the receiver delivers packets 0–7 and ACKs them, its window slides to [8, 16] — but 16 mod 16 = 0. Now if packets 8–15 are all lost and the sender retransmits packet 0 (the retransmit of the original window start), the receiver sees sequence number 0 in its new window [8, 0, 1, ...]. It **cannot tell** if this is a new packet (the next after 15) or a retransmit it already delivered. Limiting N ≤ 2^(k-1) = 8 ensures the sender's retransmit window and the receiver's new window never overlap in sequence number space.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 18 notes.*