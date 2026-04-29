# EC 441 — Lecture 22 Problem Set: Scapy, Mininet, and Sockets

**Topic:** Touch the Network — Scapy, Mininet, Python socket API  
**Lecture:** 22  
**Covers:** Packet crafting with Scapy, topology emulation with Mininet, TCP/UDP socket programming, the read+write loop

---

## Problem 1: Scapy Packet Crafting

Consider the following Scapy code:

```python
from scapy.all import IP, TCP, sr1, RandShort

pkt = IP(dst="93.184.216.34", ttl=10) / TCP(dport=80, flags="S", sport=RandShort())
reply = sr1(pkt, timeout=2, verbose=0)
```

**(a)** What fields does Scapy fill in automatically when you build `IP(dst="93.184.216.34", ttl=10)`? Name at least four, and for each one state the default value and which lecture covered that field.

**(b)** The code sends a TCP SYN packet (`flags="S"`) to port 80. What two possible replies might come back, and what does each indicate about the server at that address? Refer to the TCP state machine from L19.

**(c)** The TTL is explicitly set to 10. If the actual path to 93.184.216.34 has 12 hops, what happens to the packet? What ICMP message is returned, and who sends it?

**(d)** `RandShort()` generates a random source port. Why does Scapy use a random port rather than a fixed one (e.g., sport=12345)?

**(e)** After receiving a SYN-ACK reply, what Scapy code would complete the 3-way handshake by sending an ACK? What values must the ACK's SEQ and ACK fields have?

### Solution

**(a)** Scapy fills in these IP header fields automatically:
- **version=4** (L17: IPv4 version field, always 4 for IPv4)
- **ihl=5** (L17: IP header length in 32-bit words; 5 = 20 bytes, no options)
- **proto=6** (L17: Protocol field; 6=TCP, set automatically from the stacked TCP layer)
- **src=<your IP>** (L17: source IP, pulled from the interface routing to the destination)
- **id=<random>** (L17: Identification field for reassembly, random per datagram)
- **len=<computed>** (L17: Total length, computed from header + payload size)
- **chksum=<computed>** (L17: IP header checksum, computed automatically)

**(b)** Two possible replies from TCP port 80:
1. **SYN-ACK** (`flags="SA"`): the server is listening on port 80 and accepted the connection attempt. The 3-way handshake proceeds — the server moved to SYN_RCVD state (L19 TCP state machine).
2. **RST** (`flags="R"` or `flags="RA"`): port 80 has no listener. The server's TCP stack sends RST immediately (L19: RST = abrupt close; sent when a connection request arrives at a port with no listener = "Connection refused").

**(c)** With TTL=10 and 12 hops to destination: the packet reaches the **10th router**, which decrements TTL from 1 to 0. That router **drops the packet** and sends an **ICMP Time Exceeded (Type 11, Code 0)** message back to the source. The destination (93.184.216.34) never receives the packet. This is exactly the mechanism traceroute exploits.

**(d)** Random source ports avoid **port collision** with any existing connection to the same destination. If multiple Scapy probes (or other applications) used fixed port 12345 while sending to 93.184.216.34:80, they would all share the same 4-tuple, making it impossible to match replies to their probes. More practically, if the OS has an existing socket on :12345→:80, a raw-socket SYN from Scapy with the same port would cause the OS to send an RST (because the reply's ACK won't match any expected sequence number). Random ephemeral ports avoid all these collisions.

**(e)** To complete the handshake after receiving SYN-ACK:
```python
# reply is the SYN-ACK received from the server
ack = IP(dst="93.184.216.34") / TCP(
    dport=80,
    sport=pkt[TCP].sport,         # same source port we used
    flags="A",                    # ACK only
    seq=reply[TCP].ack,           # our next seq = server's ACK (= our ISN+1)
    ack=reply[TCP].seq + 1        # acknowledge server's SYN (seq+1)
)
send(ack)
```
The SEQ must equal the server's ACK number from the SYN-ACK (= our ISN+1). The ACK must equal the server's SYN SEQ + 1 (acknowledging the SYN's sequence number consumed).

---

## Problem 2: Scapy Traceroute Implementation

The lecture shows a minimal traceroute in 10 lines using Scapy:

```python
from scapy.all import IP, ICMP, sr1
for ttl in range(1, 16):
    reply = sr1(IP(dst="8.8.8.8", ttl=ttl) / ICMP(), timeout=2, verbose=0)
    if reply is None:
        print(f"{ttl:2d} *")
    elif reply.type == 0:     # ICMP Echo Reply
        print(f"{ttl:2d} {reply.src} (reached)")
        break
    else:                      # ICMP Time Exceeded
        print(f"{ttl:2d} {reply.src}")
```

**(a)** Which ICMP message type is `reply.type == 0`? Which is returned by intermediate routers? Give the type numbers and names from L17.

**(b)** The code sends **one** probe per TTL. Real traceroute sends three. Why might a single probe at each TTL give a misleading or incomplete picture?

**(c)** The destination is `8.8.8.8` but the code sends ICMP rather than UDP. Real traceroute uses UDP probes by default. What functional difference does it make? When would you prefer `traceroute -T` (TCP mode) instead?

**(d)** Modify the logic: instead of breaking when the destination is reached, continue for two more hops. What would you observe, and why is this useful?

**(e)** A student runs this code and sees the same IP address at hops 6, 7, and 8, but different RTTs. How is this possible? What does it reveal about the network topology?

### Solution

**(a)** ICMP message types:
- **Type 0**: ICMP Echo Reply — sent by the destination in response to a successful probe. This is the "reached" condition.
- **Type 11**: ICMP Time Exceeded — sent by intermediate routers when TTL decrements to 0. Code 0 = "TTL exceeded in transit."
- Type 3 (Destination Unreachable) is also possible but not shown in this code — would appear if no listener is present (for UDP-based traceroute).

**(b)** A single probe is unreliable because: (1) **transient loss** — the probe may be dropped by a congested queue even though the path is normally intact; a single `*` doesn't tell you whether the hop is filtered or the probe was lost; (2) **load balancing** — ECMP routers may send each probe to different next hops, so one probe might miss a relevant hop entirely; (3) **RTT variance** — a single measurement provides no estimate of variability; real traceroute's three probes give you min/avg/max and show outliers.

**(c)** UDP probes: traceroute sends UDP to high, unlikely-to-be-used destination ports. When the packet reaches the destination, the port probably has no listener → returns ICMP Port Unreachable (Type 3, Code 3), signaling arrival. **ICMP probes** (as in the code): destination returns an ICMP Echo Reply (Type 0). Functionally equivalent for hop discovery; difference is in the arrival signal. **TCP mode (`traceroute -T -p 80`)** sends TCP SYN packets. Use this when firewalls on the path **block ICMP or UDP** but pass TCP to common ports (80/443). Most firewalls allow TCP/80 for web traffic, making TCP mode better at penetrating enterprise firewall rules.

**(d)** Continuing two hops past the destination would try TTL values that reach beyond 8.8.8.8. The responses would be: either no reply (`*`), or ICMP packets from infrastructure near Google's edge (routers on Google's side of 8.8.8.8). This is useful because it reveals the internal Google network topology, confirms the destination is not the last hop in the BGP path, and can expose anycast routing — if the next probe after 8.8.8.8 reaches a different server entirely, it means 8.8.8.8 is anycast and your traffic terminated at a geographically different PoP than the continuing path.

**(e)** The same IP appearing at multiple consecutive hops with different RTTs indicates a **routing loop** — the packet is being forwarded in a cycle through the same router. Each traversal decrements TTL, so each TTL value eventually times out at the same router. The router reports its own IP for TTLs 6, 7, and 8 because all three probes loop back through it. Different RTTs reflect different queue depths on each probe's arrival. This reveals a temporary misconfiguration in the routing tables of the routers surrounding this node.

---

## Problem 3: Mininet Topology and TCP Behavior

Consider this Mininet setup:

```python
net.addLink(h1, s1, bw=100, delay='1ms')
net.addLink(s1, h2, bw=10,  delay='20ms', loss=1)
```

**(a)** What is the bottleneck bandwidth for a flow from h1 to h2? Explain why.

**(b)** Calculate the RTT for this path (assuming symmetric delay). What is the Bandwidth-Delay Product (BDP) in bytes? How many MSS (1460B) does the sender need in flight to fill the pipe?

**(c)** With 1% loss on the h1→h2 direction and Reno congestion control, use the throughput formula `BW ≈ MSS/(RTT × √p)` to estimate the expected throughput. How does this compare to the 10 Mb/s bottleneck?

**(d)** You run iperf3 and see actual throughput of 7.2 Mb/s — lower than both the bottleneck and the formula's prediction. Name two TCP mechanisms from L19–L20 that incur overhead under 1% loss, reducing effective throughput below the raw bottleneck rate.

**(e)** You change the h1-s1 link to `bw=1, delay='1ms'` (1 Mb/s instead of 100 Mb/s). Now where is the bottleneck? Predict whether the ss output's `cwnd` will be large or small, and explain why.

### Solution

**(a)** Bottleneck = **10 Mb/s** (h1→s1 is 100 Mb/s, h1→h2 via s1 is limited to 10 Mb/s at the second link). Max-flow min-cut: the minimum capacity link governs the end-to-end rate.

**(b)** RTT = 2 × (1ms + 20ms) = **42ms** (one way = 21ms).  
BDP = 10 Mb/s × 0.042s = 420,000 bits = 52,500 bytes.  
Window size = 52,500 / 1460 ≈ **36 MSS** needed to fill the pipe.

**(c)** BW = MSS / (RTT × √p) = 1460 / (0.042 × √0.01) = 1460 / (0.042 × 0.1) = 1460 / 0.0042 ≈ **347 kb/s ≈ 0.35 Mb/s**.  
This is far below the 10 Mb/s bottleneck — the formula predicts Reno will be severely degraded by 1% loss. A 1% loss rate on a 42ms RTT path crushes TCP Reno's throughput because AIMD reacts to each loss event by halving cwnd, and with 1% loss, loss events occur frequently.

**(d)** Two TCP overhead sources:
1. **Fast retransmit and recovery time**: each 1% loss event triggers fast retransmit (3 dup ACKs), followed by cwnd halving and a recovery period. During recovery, the effective window is smaller than the BDP, leaving the pipe underutilized. With 1% loss and 36 MSS needed to fill the pipe, roughly 1 in 3600 bytes is dropped — frequent cwnd reductions accumulate.
2. **Retransmission bandwidth**: the lost segments themselves must be retransmitted, consuming link capacity without delivering new data. At 1% loss on the bottleneck link, ~1% of all transmissions are retransmits — wasted capacity that the formula's clean math doesn't fully capture with realistic ack-clocking behavior.

**(e)** Now h1-s1 is 1 Mb/s and h1-s1 becomes the new bottleneck (1 Mb/s < 10 Mb/s). **cwnd will be small**: the BDP on the new bottleneck = 1 Mb/s × 42ms = 42,000 bits = 5,250 bytes ≈ 3.6 MSS. The sender only needs ~4 MSS in flight to fill the pipe; cwnd will stabilize around 4 MSS once fully ramped. Compare to the original 36 MSS — a much smaller window because the bottleneck bandwidth dropped by 10×.

---

## Problem 4: TCP Socket Programming

Consider this TCP echo server:

```python
import socket
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(('127.0.0.1', 5001))
srv.listen(1)
while True:
    conn, addr = srv.accept()
    with conn:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            conn.sendall(data)
```

**(a)** Explain the `SO_REUSEADDR` socket option. Without it, what error occurs when you restart the server within 60 seconds of stopping it, and why?

**(b)** The server calls `conn.recv(1024)`. A client sends the string `"hello from ec441\n"` (18 bytes). Is it guaranteed that `recv(1024)` returns all 18 bytes at once? Explain using TCP's byte-stream model from L19.

**(c)** The server uses `conn.sendall(data)` rather than `conn.send(data)`. What is the difference? When would `send()` return without writing all the data?

**(d)** The inner `while True` loop breaks when `if not data`. When does `recv()` return an empty bytes object `b""`? What TCP event caused this?

**(e)** A second client connects while the server is busy handling the first. What happens? How would you modify the server to handle multiple simultaneous clients?

### Solution

**(a)** `SO_REUSEADDR` allows the server to bind to a port that still has sockets in TIME_WAIT state (L19). Without it, restarting within the TIME_WAIT period (2×MSL ≈ 60–120 seconds) produces **"OSError: [Errno 98] Address already in use"**. The OS refuses the bind because the previous socket is still in TIME_WAIT — waiting to ensure any delayed segments from the old connection expire before allowing a new bind. `SO_REUSEADDR` tells the OS to allow the rebind anyway, since the new server is the same process/application.

**(b)** **Not guaranteed**. TCP is a byte stream, not a message-preserving channel (L19). The 18 bytes may arrive as one segment, but `recv(1024)` might return only 9 bytes if that's all that arrived in the kernel buffer by the time recv() is called. The remaining 9 bytes arrive in the next recv() call. Applications must implement their own **framing** — a length prefix, a delimiter (like `\n`), or a fixed message size — to reconstruct complete messages from the stream.

**(c)** `send(data)` sends as many bytes as the kernel can accept into its send buffer and returns the count actually written — which may be less than `len(data)` if the buffer is full. `sendall(data)` loops internally, calling `send()` repeatedly until all bytes are written. Use `sendall` whenever you need to ensure the complete data is written (which is almost always). `send()` is appropriate only when you handle partial writes explicitly, which is rare and error-prone.

**(d)** `recv()` returns `b""` (empty bytes) when the **remote peer has closed its side of the connection** — specifically, when the peer sent a TCP FIN and the kernel has delivered all remaining data to the application. This is the application-layer notification that the peer called `close()` (L19: FIN teardown). An empty recv() does NOT indicate a network error — that raises an exception instead.

**(e)** The second client's `connect()` call **queues** in the kernel's accept backlog (size 1 in this code, set by `listen(1)`). The second client will block waiting for `accept()` to be called. Since the server's main loop is busy in the inner `recv/sendall` loop, the second client waits until the first disconnects. To handle multiple clients simultaneously: (1) **Threading**: spawn a thread per `accept()` call; (2) **multiprocessing**: fork a child process per connection; (3) **async I/O**: use `asyncio` with non-blocking sockets; (4) **select/poll**: multiplex multiple sockets in a single-threaded event loop. Real servers use async I/O (nginx) or threading/processes (Apache) depending on expected load.

---

## Problem 5: TCP vs UDP Socket API

**(a)** Explain why UDP's `sendto()` always requires an address argument but TCP's `send()` does not.

**(b)** A UDP client sends a message before the UDP server has started. What happens? Compare to TCP's behavior in the same scenario.

**(c)** The lecture calls TCP `recv(N)` "a hint, not a guarantee." Write a simple framing loop that reassembles a complete fixed-length message of exactly 100 bytes from a TCP stream.

**(d)** `TCP_NODELAY` disables Nagle's algorithm. Explain Nagle's algorithm from L19 in one sentence, then give two specific applications that must use `TCP_NODELAY` and explain why.

**(e)** A student is building a multiplayer game server. They ask: "Should I use TCP or UDP?" Give a complete recommendation, including protocol choice, the specific setsockopt option most important to set, and the main tradeoff they accept with their choice.

### Solution

**(a)** TCP's `send()` doesn't need an address because the socket is already **bound to a specific peer** via `connect()` — the connection is established at the 3-way handshake, and all subsequent data flows between the fixed endpoints. UDP is **connectionless**: there is no handshake, no bound peer, and each `sendto()` can go to a different address. The address is part of every UDP send because UDP treats each datagram independently.

**(b)** The first datagram from the UDP client is simply **lost** — no error is raised at the client, no connection refused. UDP is fire-and-forget; if no one is listening, the datagram is discarded by the OS and the sender is never notified. With TCP: the client's `connect()` call either receives a SYN-ACK (if the server is up) or an ICMP Port Unreachable / RST (if no listener), which causes `connect()` to raise `ConnectionRefusedError`. TCP provides **explicit rejection notification**; UDP does not.

**(c)** Framing loop for exactly 100 bytes:
```python
def recv_exact(sock, n):
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed before full message received")
        buf += chunk
    return buf

message = recv_exact(conn, 100)
```
Each `recv()` call is asked for the remaining bytes (`n - len(buf)`). The loop continues until exactly 100 bytes have accumulated. The empty-recv check catches premature connection close.

**(d)** Nagle's algorithm: if there is unacknowledged data in flight, buffer small writes until an ACK arrives, then send all accumulated data as one segment — trading latency for efficiency. Two applications requiring `TCP_NODELAY`:
1. **Interactive SSH**: each keystroke is 1 byte. Nagle would buffer it waiting for an ACK, delaying echo by up to one RTT. At 50ms RTT, this makes the terminal feel laggy and unresponsive.
2. **RPC / microservice calls** (gRPC, Redis): a request-response call sends a small request and waits for a reply. Nagle would hold the request, waiting for an ACK that can't arrive until the server receives the request and replies — a deadlock that adds one RTT of latency to every call.

**(e)** **Recommendation: UDP with `TCP_NODELAY`-equivalent behavior (i.e., use UDP and implement your own protocol).**

Use **UDP** (`SOCK_DGRAM`). Most important option: none required, but you should set `SO_RCVBUF` to a larger buffer if you expect bursts. Key tradeoff accepted: **no delivery guarantee** — packets can be lost, duplicated, or reordered. The game must tolerate this (e.g., use sequence numbers, drop stale position updates, extrapolate missing frames).

Rationale: games send position updates at 20–60 Hz. A lost position packet from 50ms ago is worthless — retransmitting it (TCP) means the correction arrives late, making the game stutter. UDP lets you send the *current* state without waiting for the old lost packet. TCP's head-of-line blocking means one lost packet blocks all subsequent updates until retransmit, which is exactly what causes game lag. UDP sidesteps this entirely. QUIC is an emerging alternative that provides similar properties with encryption; raw UDP is still the dominant choice for game engines (Unreal, Unity) as of 2026.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 22 notes.*