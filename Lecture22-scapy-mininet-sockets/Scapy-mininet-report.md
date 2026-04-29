# Touch the Network: Scapy, Mininet, and Sockets

**EC 441 — Lecture 22 Report**  
*Topic: Moving from observation to participation — crafting packets, emulating topologies, writing networked applications*

---

## Introduction

Lecture 21 taught you to read the network. Lecture 22 teaches you to write to it. The distinction matters: observation is forensic — you watch what already exists and try to understand it. Participation is generative — you make things happen and watch the consequences. Three tools, one arc: Scapy lets you craft a single packet byte by byte. Mininet lets you own a complete network topology. The socket API is the interface every real application uses. Together, they close the loop: write code, generate traffic, capture it, explain every field.

---

## Scapy: Wireshark in Reverse

Wireshark takes bytes off the wire and presents them as structured Python objects. Scapy does the inverse: you build Python objects, and Scapy writes the bytes onto the wire. The core idiom is the `/` operator for layer stacking — `IP(dst="8.8.8.8") / ICMP()` means "an ICMP message encapsulated inside an IP datagram destined for 8.8.8.8." Every field not specified is filled with a sensible default: `version=4`, `ihl=5`, `ttl=64`, `proto=1` (ICMP). Every one of those defaults was covered in L14 and L17.

The power of Scapy is in what it exposes. When you call `pkt.show()`, you see every field of the IP header and the ICMP message, with their values. When you do `bytes(pkt)`, you get the actual 28 bytes that would appear on the wire. The abstraction layers from the OSI model are not just pedagogical — they are directly visible as Python objects stacked with `/`.

The `sr1()` function ("send and receive one") is where Scapy transitions from crafting to participation. It sends a packet and waits for a reply. The TTL of the reply reveals the hop count from the destination. The flags of a TCP reply reveal the server's state: SYN-ACK means a listener is present and the 3-way handshake is proceeding; RST means no listener and the OS is rejecting the connection. These are exactly the TCP state machine transitions from L19.

The traceroute implementation in 10 lines is one of the most instructive pieces of code in the lecture. Traceroute is not a protocol — it is a technique that exploits the TTL decrement behavior of normal IP forwarding and the ICMP Time Exceeded response that every router is required to send. Any tool with raw socket access can implement it. The Scapy implementation exposes the mechanism completely: loop TTL from 1 to N, send an ICMP Echo Request at each value, inspect the reply type (0 = reached, 11 = Time Exceeded, None = filtered). In 10 lines, the L13 forwarding mechanism, the L17 TTL field, and the L17 ICMP message types are all directly visible.

The ethics note in the lecture is not boilerplate. Raw sockets bypass the OS kernel's normal socket layer. Scapy can forge source addresses, craft malformed packets, and send floods. The technical capability and the legal permission are different things. `scanme.nmap.org` exists precisely because the nmap project wanted to give learners a legal target.

---

## Mininet: A Real Network in Miniature

Mininet is not a simulator. It uses Linux network namespaces to create isolated network stacks for each virtual host, connected by virtual Ethernet pairs. Every "host" in a Mininet topology is a real Linux process with its own routing table, socket layer, and ARP cache. When `h1 ping -c 3 h2` runs in a Mininet shell, those are real ICMP packets traversing real kernel network stacks. The packets are virtualized, but the protocol machinery is not.

This distinction matters for the `ss -tipm` experiment. In L21, the iperf3 demo ran over loopback. Loopback has RTT ≈ 30 microseconds and never drops packets. The congestion control state machine from L20 was invisible: cwnd grew to the initial window limit (typically 10 MSS) and stayed there, because there was no delay to make pipelining necessary and no loss to trigger AIMD. Mininet adds real delay and real loss. With `delay='20ms'` on the bottleneck link, the RTT becomes 42ms — long enough that cwnd must grow beyond 10 MSS to fill the pipe. With `loss=1`, packets drop at 1% rate — frequent enough to trigger fast retransmit and AIMD cwnd reduction. The abstract diagrams from L20 become live numbers in `ss` output: slow start visible as cwnd doubling per RTT, ssthresh visible as the threshold where growth switches from exponential to linear, multiplicative decrease visible when a loss event halves cwnd.

The bottleneck topology in the lecture (`bw=100` on the first link, `bw=10` with `loss=1` on the second) illustrates a principle from the throughput formula: `BW ≈ MSS / (RTT × √p)`. With RTT=42ms and p=0.01, the formula predicts throughput of approximately 0.35 Mb/s — far below the 10 Mb/s bottleneck capacity. TCP Reno is so sensitive to loss that even 1% loss on a 42ms path reduces throughput by more than 97% of theoretical capacity. Running this experiment in Mininet and comparing the iperf3 output to the formula's prediction makes the mathematics concrete in a way that no classroom derivation can.

---

## The Socket API: What Applications Actually Use

Every networked program you have ever used — browsers, SSH clients, database drivers, streaming services — speaks to the network through the socket API. Below sockets is the OS kernel; above sockets is application code. The socket API is the contract between them.

The TCP server flow is asymmetric: `socket() → bind() → listen() → accept() → recv/send → close()`. The accept() call blocks until a client connects and returns a new socket representing that specific connection. The original listening socket continues accepting new connections. The UDP flow is symmetric and stateless: `socket() → bind() → recvfrom/sendto → close()`. There is no connection, no accept, no per-client socket — every datagram stands alone.

Three traps trip programmers who understand the API intellectually but haven't written enough code to feel them:

**SO_REUSEADDR** is the most common first bug in server code. Without it, restarting a server within the TIME_WAIT period fails with "Address already in use." The port is occupied by a socket in TIME_WAIT state — waiting to ensure delayed segments from the previous connection expire. SO_REUSEADDR tells the OS to allow rebinding anyway. Every production server sets this option; omitting it wastes developer time every time the server is tested.

**recv(N) is a hint, not a guarantee.** This is perhaps the most dangerous misconception in network programming. TCP is a byte stream. A call to `recv(1024)` may return 1 byte, or 512 bytes, or 1024 bytes — depending on when the kernel's receive buffer was checked relative to packet arrival. Applications that assume recv() returns one complete message will corrupt data silently. The fix is explicit framing: either read a known number of bytes with a loop (`recv_exact`), or use a length prefix, or use a delimiter. HTTP uses `\r\n\r\n` plus `Content-Length`. Most protocols use length-prefix framing. The choice matters; the consistency matters more.

**sendall vs send.** `send()` writes as many bytes as the kernel can currently accept and returns the count written — which may be less than requested if the send buffer is full. `sendall()` loops internally until everything is written. In practice, `send()` partial-writes are rare on modern systems with generous buffers, which is why they produce such confusing bugs: the code works 99.9% of the time and mysteriously loses data under load.

---

## Nagle's Algorithm: A Feature That Becomes a Bug

Nagle's algorithm coalesces small writes into larger TCP segments: if there is unacknowledged data in flight, buffer additional small writes until an ACK arrives, then send everything at once. On a slow network with many tiny writes (each keystroke in a Telnet session producing a 41-byte segment — 1 byte of data, 40 bytes of headers), Nagle's algorithm reduces traffic by an order of magnitude.

The same feature is a latency disaster for interactive applications. An SSH session sending one keystroke must wait for an ACK from the server before the buffered keystroke is flushed. At 50ms RTT, this makes typing feel like shouting into a canyon. An RPC client sending a small request payload must wait for an ACK — which cannot arrive until the server receives the request and begins processing it, making Nagle's delay a deadlock-like stall before every call.

`TCP_NODELAY` disables Nagle's algorithm per-socket. It is the most commonly cited setsockopt option in production application code. The pattern is consistent: bulk transfer → Nagle on (default); interactive or request-response → TCP_NODELAY.

---

## Closing the Loop

The lecture's final exercise brings together everything from both L21 and L22 and, implicitly, the entire semester. A tcpdump capture runs on the loopback interface while Python TCP and UDP echo clients and servers exchange messages. The resulting .pcap file contains packets that you generated, traversing a network path you controlled, using protocols you have spent a semester studying.

Opening that pcap in pyshark, the layers are all present: Ethernet frames from L08, IP datagrams from L14–L17, TCP segments with sequence numbers and ACKs from L18–L20, UDP datagrams from L18, and the application bytes written in Python above the socket API. The protocol stack is not a textbook diagram. It is a file on disk, generated minutes ago by code you wrote.

This is what the semester has been building toward: not just the ability to describe how protocols work, but the ability to observe them running, to generate traffic and analyze it, and to connect every byte on the wire to the design decisions that put it there.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 22 notes.*