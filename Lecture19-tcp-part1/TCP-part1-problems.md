# EC 441 — Lecture 19 Problem Set: TCP Part 1

**Topic:** TCP Connections, Sequencing, Flow Control, and Reliable Delivery  
**Lecture:** 19  
**Covers:** TCP header fields, byte-stream model, 3-way handshake, ISN randomization, connection teardown (FIN/RST/TIME_WAIT), RTT estimation (EWMA + RTTVAR), fast retransmit, flow control (rwnd)

---

## Problem 1: TCP Header Fields

A TCP segment is captured with the following raw header values:

```
Source Port:      45678
Destination Port: 443
Sequence Number:  1000500
ACK Number:       8300201
Data Offset:      8 (32-bit words)
Flags:            ACK=1, PSH=1
Window Size:      65535
Checksum:         (valid)
```

There are 40 bytes of payload.

**(a)** What is the total header size in bytes? Is there an Options field present? If so, how large is it?

**(b)** What does ACK=1 mean? What does PSH=1 instruct the receiver to do?

**(c)** What does Sequence Number = 1000500 mean in TCP's byte-stream model? If this segment carries 40 bytes of payload, what will the receiver's next ACK number be?

**(d)** What does Window Size = 65535 mean? How does this interact with a Window Scale option value of 7?

**(e)** This connection is over HTTPS (port 443). The TCP segment carries TLS application data. A student argues "the TCP checksum is redundant because TLS also has integrity protection." Evaluate this argument.

### Solution

**(a)** Data Offset = 8 → header size = 8 × 4 = **32 bytes**. Standard TCP header is 20 bytes; 32 − 20 = **12 bytes of Options** are present (likely Timestamps + SACK-permitted options).

**(b)** ACK=1 means the **Acknowledgment Number field is valid** — the sender is acknowledging receipt of data from the other direction. PSH=1 instructs the receiver to **deliver this data to the application immediately**, without waiting to buffer more segments.

**(c)** Sequence Number = 1000500 means the **first byte of payload in this segment is byte 1,000,500** in the sender's byte stream. After the receiver processes this segment (40 bytes of data), the next expected byte is 1,000,500 + 40 = **1,000,540**. The receiver will send ACK Number = **1,000,540**.

**(d)** Window Size = 65535 bytes = the advertised receive window. Without Window Scale, this is the **raw available buffer space** (65535 bytes ≈ 64 KB). With Window Scale option of 7, the effective window is 65535 × 2^7 = 65535 × 128 = **8,388,480 bytes ≈ 8 MB**. The Window Scale multiplier is negotiated at SYN time and applied to every subsequent window advertisement.

**(e)** The argument is partially valid but misses the purpose of each checksum. The **TCP checksum** protects against bit errors in transit (hardware/software bugs on the path). **TLS integrity** (via HMAC or AEAD) protects against an adversary tampering with the content. They defend against different threats. In practice, neither is cryptographically strong (TCP's ones'-complement checksum has dmin=2), but they operate at different layers for different threat models. If TLS is present and verified end-to-end, the TCP checksum adds minimal security value — but it remains mandatory per spec.

---

## Problem 2: 3-Way Handshake and Sequence Numbers

A client at 10.0.0.1 connects to a server at 10.0.0.2 port 80. The client's ISN is x = 2000, the server's ISN is y = 5000.

**(a)** Write out the three handshake segments with their SEQ and ACK numbers (and flag bits).

**(b)** After the handshake, the client sends a 200-byte HTTP GET request. Write the segment fields (SEQ, ACK, flags, payload size).

**(c)** The server responds with a 1400-byte HTTP response. Write the server's segment fields.

**(d)** The client sends an ACK-only segment. Write its SEQ and ACK numbers.

**(e)** Why does TCP use a random Initial Sequence Number rather than starting at 0? Give two distinct reasons.

### Solution

**(a)** Three-way handshake:
```
Client → Server:  SEQ=2000, ACK=—,    SYN=1          (SYN)
Server → Client:  SEQ=5000, ACK=2001, SYN=1, ACK=1   (SYN-ACK)
Client → Server:  SEQ=2001, ACK=5001, ACK=1           (ACK)
```
SYN consumes one sequence number (2000 → next is 2001; 5000 → next is 5001). After handshake: client's next seq = 2001, server's next seq = 5001.

**(b)** Client sends 200-byte HTTP GET:
```
SEQ=2001, ACK=5001, ACK=1, PSH=1, payload=200B
```
**(c)** Server sends 1400-byte response:
```
SEQ=5001, ACK=2201, ACK=1, PSH=1, payload=1400B
```
Server ACK = 2001 + 200 = 2201 (acknowledges all 200 bytes of the GET request).

**(d)** Client ACK-only:
```
SEQ=2201, ACK=6401, ACK=1, payload=0B
```
Client's SEQ doesn't change (ACK-only segments carry no data). ACK = 5001 + 1400 = 6401.

**(e)** Two reasons for ISN randomization:
1. **Stale segment protection:** If a connection closes and a new connection reuses the same 5-tuple, a delayed segment from the old connection might have a low sequence number that falls within the new connection's window. Random ISNs make the probability of overlap negligible.
2. **Security:** Predictable ISNs allow an off-path attacker to guess the correct ACK value for a connection they cannot observe, enabling injection of forged data. Modern Linux computes ISN = MD5(src IP, dst IP, ports, secret key, timestamp), making it cryptographically unpredictable.

---

## Problem 3: Connection Teardown

A client closes a connection to a server. The client's sequence number is u = 10000. The server's sequence number is v = 20000. The server still has 500 bytes of data to send after receiving the FIN.

**(a)** Trace the full teardown sequence: who sends what, with SEQ/ACK numbers and flag bits? The server should send its remaining data before closing.

**(b)** After the client sends its final ACK, it enters TIME_WAIT. How long does TIME_WAIT last (in terms of MSL)? Give two reasons this state must exist.

**(c)** What happens if the server sends RST instead of FIN? What does the client do upon receiving RST? Does it enter TIME_WAIT?

**(d)** A high-traffic web server shows hundreds of sockets in TIME_WAIT state when you run `ss -t -a`. Is this a problem? What do these sockets represent?

### Solution

**(a)** Full teardown with server sending remaining 500 bytes:
```
Client → Server:  SEQ=10000, ACK=20000, FIN=1, ACK=1    (client half-close)
Server → Client:  SEQ=20000, ACK=10001, ACK=1           (ACK client's FIN)
Server → Client:  SEQ=20000, ACK=10001, payload=500B    (server sends remaining data)
Server → Client:  SEQ=20500, ACK=10001, FIN=1, ACK=1   (server half-close)
Client → Server:  SEQ=10001, ACK=20501, ACK=1           (final ACK)
Client enters TIME_WAIT
```
FIN consumes one sequence number: client's FIN is seq 10000, acknowledged with ACK 10001. Server's FIN is seq 20500 (after 500 bytes), acknowledged with ACK 20501.

**(b)** TIME_WAIT lasts **2 × MSL** (Maximum Segment Lifetime), typically 2–4 minutes. Two reasons:
1. **Final ACK may be lost:** If the client's last ACK is dropped, the server will retransmit its FIN. The client must remain alive to re-ACK it. Without TIME_WAIT, the client would have no socket and the server would hang.
2. **Prevent 5-tuple reuse confusion:** Delayed segments from the old connection must expire before a new connection can reuse the same (src IP, src port, dst IP, dst port). TIME_WAIT ensures any in-flight "ghost" segments die before the same 5-tuple is reused.

**(c)** RST (reset) causes an **abrupt close**. The client immediately discards all buffered data, closes the socket, and does **not** enter TIME_WAIT — RST is never acknowledged. RST is sent when a connection request arrives at a port with no listener ("Connection refused"), when one side crashes and restarts, or when a firewall terminates a connection.

**(d)** Not a problem — this is **normal and expected behavior**. Each TIME_WAIT socket corresponds to a recently closed TCP connection that the OS is holding for 2×MSL to prevent stale segment confusion. On a busy web server handling thousands of short-lived HTTP connections, having hundreds of TIME_WAIT sockets at any moment is healthy. They represent connections that were properly closed, not errors.

---

## Problem 4: RTT Estimation and RTO

A TCP connection measures the following sequence of RTT samples: 80, 120, 90, 200, 85, 95 ms.
Initial SRTT = 80, initial RTTVAR = 0, α = 1/8, β = 1/4.

**(a)** Compute SRTT and RTTVAR after each sample. Use the Jacobson formulas:
```
RTTVAR = (1 - β) * RTTVAR + β * |SRTT - R|
SRTT   = (1 - α) * SRTT   + α * R
```
(Update RTTVAR before SRTT for each sample.)

**(b)** Compute RTO = SRTT + 4 × RTTVAR after each sample.

**(c)** Sample 4 (R = 200ms) is anomalously high. How does RTTVAR protect against a spurious retransmission that would occur if the RTO were set to just SRTT?

**(d)** Why does TCP use α = 1/8 rather than α = 1/2? What is the engineering tradeoff?

### Solution

**(a)/(b)** Trace (RTTVAR updated before SRTT per RFC 6298):

| Sample | R    | RTTVAR (before) | RTTVAR (after)           | SRTT (after)              | RTO               |
|--------|------|-----------------|--------------------------|---------------------------|-------------------|
| Init   | —    | 0.00            | 0.00                     | 80.00                     | —                 |
| R=120  | 120  | 0.00→|80−120|/4=10.0 | 10.00              | (7/8)×80+(1/8)×120=85.00  | 85+40=125ms       |
| R=90   | 90   | (3/4)×10+(1/4)×|85−90|=8.75 | 8.75       | (7/8)×85+(1/8)×90=85.63  | 85.63+35=120.6ms  |
| R=200  | 200  | (3/4)×8.75+(1/4)×|85.63−200|=34.47 | 34.47 | (7/8)×85.63+(1/8)×200=99.93 | 99.93+138=237.9ms |
| R=85   | 85   | (3/4)×34.47+(1/4)×|99.93−85|=29.58 | 29.58 | (7/8)×99.93+(1/8)×85=97.94 | 97.94+118=215.9ms |
| R=95   | 95   | (3/4)×29.58+(1/4)×|97.94−95|=22.92 | 22.92 | (7/8)×97.94+(1/8)×95=97.57 | 97.57+92=189.6ms  |

**(c)** After sample 3 (R=90), SRTT ≈ 85ms and RTO ≈ 120ms. If the next RTT were 200ms and RTO were just SRTT (≈85ms), the timer would fire at 85ms even though the ACK is legitimately in flight. This is a **spurious retransmission** — unnecessary bandwidth waste and potential congestion signal. RTTVAR tracks variance: the spike to 200ms pushes RTTVAR to 34ms, making RTO ≈ 238ms, which safely exceeds the 200ms RTT and avoids the spurious retransmit.

**(d)** α = 1/8 = 2^(-3) makes the smoothing a **right bit-shift** — extremely cheap on 1980s hardware with no floating-point unit. The tradeoff: small α means the EWMA "time constant" ≈ 1/α = 8 RTT measurements, making SRTT slow to respond to changes (good for filtering noise, bad for tracking rapid RTT changes). Large α responds faster but is noisier. 1/8 was empirically found to be a good balance for internet RTT distributions, and the hardware efficiency made it an easy choice. It's still used today because changing it would risk unknown effects on congestion behavior.

---

## Problem 5: Flow Control

A TCP receiver has a 32 KB receive buffer. The application is reading data slowly (2 KB every 200ms). The sender is transmitting at full speed.

**(a)** Sender transmits three full-MSS segments (1460 B each). How much data is buffered? What rwnd value does the receiver advertise in the ACK?

**(b)** The application reads 4380 bytes (all three segments' worth) from the buffer. What rwnd does the receiver advertise now?

**(c)** The sender fills the buffer to exactly 32 KB. What rwnd does the receiver advertise? What does the sender do?

**(d)** The application reads 1 byte from the full buffer. What problem arises if the receiver immediately sends an ACK with rwnd = 1? What is the "silly window syndrome" and how is it avoided?

### Solution

**(a)** 3 × 1460 = 4380 bytes buffered. Free space = 32768 − 4380 = 28388 bytes.  
**rwnd = 28388 bytes** advertised in the ACK.

**(b)** Application reads 4380 bytes → buffer = 0 bytes. Free space = 32768 bytes.  
**rwnd = 32768 bytes** advertised.

**(c)** Buffer full: free space = 0. **rwnd = 0** advertised. The sender must **pause** — it cannot send more data. The sender starts a **persist timer** and periodically sends a **1-byte zero-window probe** to check whether the window has reopened. This prevents deadlock if the rwnd-open notification is lost.

**(d)** If the receiver sends ACK with rwnd=1 after the application reads 1 byte, the sender transmits a 1-byte segment — but a 1-byte payload requires 40+ bytes of headers (20 IP + 20 TCP). The segment is **97% overhead**. This is **silly window syndrome**. Avoidance (Clark's algorithm): the receiver waits to advertise a non-zero window until it has either a full MSS of free space or half its buffer is free — whichever is smaller. This batches small window updates into meaningful ones.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 19 notes.*