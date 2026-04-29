# EC 441 — Lecture 21 Problem Set: CLI Tools, Wireshark, and pyshark

**Topic:** See the Network — ping, traceroute, ip, ss, dig, tcpdump, Wireshark, pyshark  
**Lecture:** 21  
**Covers:** Connecting live tool output to L13–L20 concepts; packet capture and analysis; programmatic pcap processing

---

## Problem 1: ping and RTT Interpretation

You run the following command and get this output:

```
$ ping -c 5 8.8.8.8
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 rtt=12.4 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=117 rtt=11.9 ms
64 bytes from 8.8.8.8: icmp_seq=3 ttl=117 rtt=45.2 ms
64 bytes from 8.8.8.8: icmp_seq=4 ttl=117 rtt=12.1 ms
64 bytes from 8.8.8.8: icmp_seq=5 ttl=117 rtt=12.3 ms
--- 8.8.8.8 ping statistics ---
5 packets transmitted, 5 received, 0% packet loss
rtt min/avg/max/mdev = 11.9/18.8/45.2/12.9 ms
```

**(a)** The TTL in the reply is 117. Assuming Google's Linux servers start with TTL=64, how many hops did the reply travel? Now assume the server actually runs with TTL=128 (Windows-style) — how many hops then? How would you determine which assumption is correct?

**(b)** Packet 3 has RTT=45.2ms while the others cluster around 12ms. Name two plausible causes. Which cause can ping alone distinguish between?

**(c)** Using the Jacobson RTT estimator from L19 (α=1/8, β=1/4), compute SRTT and RTTVAR after processing all five samples in order. Initial SRTT=12.4 (first sample), RTTVAR=0.

**(d)** What RTO would TCP set after processing these five samples? Is the RTO "too tight" or "reasonable" for this path? Explain using RTTVAR.

**(e)** The `mdev` (mean deviation) statistic in the output is 12.9ms. How does this compare to RTTVAR after your calculation? They measure similar things — why might they differ?

### Solution

**(a)** Assuming Linux server (initial TTL=64): hops = 64 − 117 = **−53** — impossible. So the Linux assumption is wrong. Assuming Windows (TTL=128): hops = 128 − 117 = **11 hops**. You can determine the initial TTL by running `traceroute` to find the destination: the last hop's reply TTL tells you what the server started with. Alternatively, TTL values are almost always 64, 128, or 255 — 117 is only consistent with a starting value of 128 (common Windows/Cisco devices).

**(b)** Two plausible causes: (1) **transient queuing delay** at a congested router, causing pkt 3 to wait in a queue; (2) **ICMP rate-limiting** at the destination — routers often deprioritize or rate-limit ICMP replies, so pkt 3 waited in a rate-limited queue. Ping alone **cannot distinguish** between these two causes: both produce a delayed RTT from the sender's perspective. Traceroute to the same destination while pinging might reveal which hop introduced the delay, but even that is not definitive.

**(c)** Jacobson trace (RTTVAR updated before SRTT each step):

| Sample | R     | RTTVAR (after)                      | SRTT (after)                   |
|--------|-------|-------------------------------------|--------------------------------|
| Init   | 12.4  | 0.00                                | 12.40                          |
| 11.9   | 11.9  | 0 + 0.25×|12.4−11.9| = 0.125       | 0.875×12.4 + 0.125×11.9 = 12.34 |
| 45.2   | 45.2  | 0.75×0.125 + 0.25×|12.34−45.2| = 8.30 | 0.875×12.34 + 0.125×45.2 = 16.45 |
| 12.1   | 12.1  | 0.75×8.30 + 0.25×|16.45−12.1| = 7.31 | 0.875×16.45 + 0.125×12.1 = 15.40 |
| 12.3   | 12.3  | 0.75×7.31 + 0.25×|15.40−12.3| = 6.26 | 0.875×15.40 + 0.125×12.3 = 14.98 |

**(d)** RTO = SRTT + 4×RTTVAR = 14.98 + 4×6.26 = **14.98 + 25.04 ≈ 40.0 ms**. This is **reasonable**: the spike to 45.2ms pushed RTTVAR high enough that RTO ≥ 40ms, which would accommodate another spike of similar magnitude without spurious retransmit. If we had only tracked SRTT ≈ 15ms and set RTO = 15ms (or 2×SRTT = 30ms), the next 45ms spike would fire a spurious retransmit. RTTVAR's role is precisely to absorb these spikes.

**(e)** `mdev` in ping is the **sample standard deviation** of all five RTTs; RTTVAR is an **exponentially-weighted mean absolute deviation** updated sample-by-sample. They differ because: (1) mdev treats all samples equally while RTTVAR weights recent samples more heavily; (2) mdev is computed over the final set while RTTVAR is updated online. Both measure spread around the mean RTT, but they use different formulas and reflect different windows of history.

---

## Problem 2: traceroute Analysis

You run `traceroute -m 20 8.8.8.8` and see:

```
 1  10.0.0.1      0.8 ms   0.7 ms   0.8 ms    (home gateway)
 2  100.64.5.1    8.2 ms   8.1 ms   8.3 ms    (ISP edge)
 3  192.0.2.10   10.4 ms  10.3 ms  10.5 ms
 4  * * *
 5  72.14.215.1  11.2 ms  11.1 ms  11.3 ms
 6  8.8.8.8      12.4 ms  12.1 ms  12.3 ms
```

**(a)** Hop 4 shows `* * *`. Does this mean the path is broken? Explain what actually causes this output.

**(b)** The RTT jumps from 10.4ms (hop 3) to 11.2ms (hop 5). Is this a meaningful latency increase? What kinds of topology changes would cause a sudden large RTT jump (e.g., 10ms → 80ms)?

**(c)** Traceroute sends three probes per TTL value. Why might the three RTTs at a single hop differ significantly from each other, even when all three probes reach the same router?

**(d)** The address 100.64.5.1 is in the 100.64.0.0/10 range. What is this address range, and what does its appearance in a traceroute output suggest about this network?

**(e)** A student says: "traceroute shows the exact path my packets take to the destination." Identify two reasons this statement is incorrect or incomplete.

### Solution

**(a)** The path is **not broken** — hop 6 (8.8.8.8) replies successfully, proving traffic flows through hop 4. The `* * *` means the **router at hop 4 does not send ICMP Time Exceeded messages** — it either has ICMP response generation disabled (common on backbone routers to prevent amplification attacks) or rate-limits ICMP. The probe packets pass through this router normally; only the ICMP response is suppressed.

**(b)** The 0.8ms increase from hop 3 to hop 5 is **not significant** — it is within normal jitter. Meaningful latency jumps (e.g., 10ms → 80ms between adjacent hops) typically indicate: (1) **intercontinental fiber links** (transatlantic ≈ +70ms, transpacific ≈ +120ms); (2) **AS boundary crossings** where the packet transitions from a local network to a long-haul backbone; (3) a hop that introduces significant **queuing delay** or traffic-shapes ICMP replies.

**(c)** The three probes at a single hop may differ because: **IP load balancing** (the path from source to that hop may use ECMP, sending probe 1 and probe 3 via different routers); **queuing delay** (each probe sees different queue depth); **ICMP rate limiting** (the router queues or deprioritizes ICMP generation); **kernel scheduling jitter** at the router. Load balancing is the most common cause of dramatically different RTTs at a single hop.

**(d)** 100.64.0.0/10 is **Carrier-Grade NAT (CGNAT) shared address space** (RFC 6598). Its appearance means the ISP is using CGNAT — multiple subscriber connections share a single public IPv4 address. The subscriber's home gateway (10.0.0.1) is behind an additional layer of NAT at the ISP. This is a consequence of IPv4 exhaustion and is extremely common with residential broadband providers.

**(e)** Two reasons traceroute does not show the exact path: (1) **Asymmetric routing** — traceroute shows only the forward path; return packets (ICMP Time Exceeded) may travel entirely different routers. The path shown is the forward path only. (2) **Load balancing and per-flow routing** — successive probes with different TTLs may take different paths through ECMP routers. Some hops in the output may be from different physical routers on different paths, not a single sequential chain.

---

## Problem 3: ss Output Interpretation

You run `ss -tipm` while an iperf3 transfer is running and see:

```
tcp   ESTAB  0      0     127.0.0.1:5201  127.0.0.1:43210
    cubic wscale:7,7 rto:204 rtt:0.03/0.01 ato:40 mss:65495
    cwnd:10 ssthresh:2147483647
    send 174.7Gb/s lastsnd:6 lastrcv:6 lastack:6
    app_limited:1
```

**(a)** The connection shows `cubic` as the congestion control algorithm. What does this tell you about the OS? From L20, what is CUBIC's key departure from TCP Reno?

**(b)** `rtt:0.03/0.01` means SRTT=0.03ms and RTTVAR=0.01ms. What RTO does the Jacobson formula compute? The output shows `rto:204` — why is the actual RTO so much larger?

**(c)** `cwnd:10` and `ssthresh:2147483647`. What phase of congestion control is this connection in? What does ssthresh = 2^31 − 1 mean in practice?

**(d)** `app_limited:1` — what does this mean? Is this connection limited by the network or by the application? What does this imply about the "send 174.7Gb/s" figure?

**(e)** `wscale:7,7` — what does this mean? Without Window Scale, what would the maximum effective window be? Why is scaling necessary for this connection?

### Solution

**(a)** CUBIC is the default congestion control in **Linux since kernel 2.6.19** — this confirms a Linux OS. CUBIC's key departure: growth is governed by a **cubic function of wall-clock time** (`W(t) = C(t−K)³ + Wmax`) rather than RTT-clocked linear increase. This makes CUBIC's growth RTT-independent — short and long RTT flows grow at the same absolute rate — and allows faster recovery on high-BDP paths.

**(b)** RTO = SRTT + 4×RTTVAR = 0.03 + 4×0.01 = 0.07ms. The actual RTO is 204ms because **RFC 6298 specifies a minimum RTO of 1 second** (implementations often use 200ms as a practical floor). The computed value (0.07ms) is physically unreasonable — any interrupt latency or kernel scheduling delay would exceed it and cause spurious retransmits. The floor prevents timer thrashing on ultra-low-latency paths like loopback.

**(c)** ssthresh = 2,147,483,647 = 2^31 − 1 is effectively **infinity** — the **initial value** set before any loss event has occurred. This means the connection has **never seen a loss event** and is still in **slow start** (cwnd < ssthresh). With cwnd=10 and ssthresh=∞, every ACK increments cwnd by 1 MSS — exponential growth. However, the connection is app_limited (see d), so cwnd isn't actually growing.

**(d)** `app_limited:1` means the **application is not providing data fast enough** to fill the congestion window. The network could handle more data but the sender's write() calls are the bottleneck. The "send 174.7Gb/s" figure is the **theoretical bandwidth** given the current cwnd and RTT — not the actual throughput. Actual throughput is limited by how fast the application generates data. This is why cwnd stays at 10: the sender never has a full window's worth of data to send.

**(e)** `wscale:7,7` — both sender and receiver advertise Window Scale = 7, meaning the 16-bit window field is multiplied by 2^7 = 128. Max effective window = 65,535 × 128 = **8,388,480 bytes ≈ 8MB**. Without scaling: max = **65,535 bytes = 64 KB**. On this loopback connection the RTT is 0.03ms and BDP = 174Gb/s × 0.03ms ≈ 650MB — so even the scaled window is the bottleneck on a fully saturated loopback, though app_limited means it doesn't matter here.

---

## Problem 4: pyshark and Packet Analysis

A student captures traffic while visiting a website and writes this pyshark script:

```python
import pyshark
cap = pyshark.FileCapture('capture.pcap', display_filter='dns')
queries = {}
for pkt in cap:
    try:
        if hasattr(pkt.dns, 'qry_name'):
            name = pkt.dns.qry_name
            queries[name] = queries.get(name, 0) + 1
    except AttributeError:
        pass
for name, count in sorted(queries.items(), key=lambda x: -x[1]):
    print(f"{count:3d} {name}")
```

The top 5 results are:
```
 12 fonts.googleapis.com
  8 www.google-analytics.com
  6 cdn.example.com
  4 www.example.com
  3 api.stripe.com
```

**(a)** Why does `fonts.googleapis.com` appear 12 times? DNS queries are cached — shouldn't the second and subsequent lookups be free?

**(b)** The student notices that DNS queries travel over UDP (port 53) but a few DNS packets use TCP. Under what conditions does DNS fall back to TCP? What response characteristic triggers this?

**(c)** The student adds `pkt.dns.a` to extract resolved IP addresses for each query. When they run it, they get `AttributeError` for many packets. Explain why the `.a` attribute is missing for those packets, and how to safely handle this.

**(d)** `api.stripe.com` appears in the capture. What does this reveal about the webpage visited? Is this information available to anyone who can capture traffic on the network path?

**(e)** The student wants to find all TCP connections and their durations (time from SYN to FIN). Describe the logic they would need to implement in pyshark (no code required).

### Solution

**(a)** DNS queries repeat 12 times for several reasons: (1) **DNS TTL expiry** — each record has a TTL (commonly 300s–3600s); if the page is visited across TTL boundaries, the resolver re-queries; (2) **multiple processes/tabs** — different browser tabs, background extensions, or the OS resolver each maintain separate caches; (3) **negative caching failure** — if a query fails and the result isn't cached; (4) **subresource loads** — a page may request `fonts.googleapis.com` for different font variants, each potentially triggering a separate query; (5) **DNS prefetching** — browsers pre-resolve links on the page. The high count suggests multiple page loads or cross-tab activity within the capture window.

**(b)** DNS falls back to TCP when: (1) the **UDP response is truncated** at 512 bytes (classic DNS limit) or at the path MTU; (2) the response exceeds even the EDNS0-extended UDP limit; (3) **DNSSEC signatures** make responses large enough to exceed UDP limits; (4) **zone transfers** (AXFR) which are always TCP. The TC (Truncated) bit in the DNS response header signals the client to retry over TCP.

**(c)** The `.a` attribute is present only in **DNS response packets containing an A record** (IPv4 address answer). DNS queries (not responses) have no answer field; responses to AAAA, MX, TXT, or CNAME queries have no `.a` field; error responses (NXDOMAIN, SERVFAIL) have no answer. Safe handling:
```python
try:
    ip = pkt.dns.a  # present only in A record responses
except AttributeError:
    pass  # query, non-A response, or error
```
Also check `pkt.dns.flags_response == '1'` to filter only responses.

**(d)** The DNS query for `api.stripe.com` reveals that the webpage **processes payments via Stripe** — a specific third-party payment processor was contacted during the page load. This is metadata: the URL or page content may be encrypted (HTTPS/TLS), but DNS queries are **unencrypted by default** (plaintext UDP/TCP to port 53). Anyone who can capture traffic on the local network (e.g., a home router, ISP, or network observer) can read DNS queries and infer which services and sites the user interacts with. This is the privacy motivation for DNS-over-HTTPS (DoH) and DNS-over-TLS (DoT).

**(e)** Logic for tracking TCP connection durations:
1. **Maintain a dictionary** keyed by 4-tuple `(src_ip, src_port, dst_ip, dst_port)`.
2. **On SYN packet** (flags contain SYN, no ACK): record the timestamp as `start_time` for that 4-tuple.
3. **On FIN or RST packet**: record the timestamp as `end_time`. Duration = end_time − start_time.
4. Handle **normalization**: TCP is bidirectional, so `(A→B)` SYN and `(B→A)` FIN need to be matched to the same connection — use the canonical form `(min(src,dst), ..., max(src,dst), ...)` or track both directions.
5. Handle **missing SYN/FIN**: captures often start mid-connection (no SYN seen) or end before teardown (no FIN seen) — skip connections without both endpoints.

---

## Problem 5: tcpdump Filters

Write a `tcpdump` filter expression for each of the following requirements:

**(a)** Capture only DNS traffic (UDP or TCP) to or from 8.8.8.8.

**(b)** Capture all TCP SYN packets (connection initiation only, not SYN-ACK).

**(c)** Capture all traffic except SSH (port 22).

**(d)** Capture HTTP or HTTPS traffic to or from the subnet 192.168.1.0/24.

**(e)** Capture ICMP packets with TTL less than 5 (e.g., from a traceroute tool scanning local hops).

### Solution

**(a)** `host 8.8.8.8 and port 53`

**(b)** `tcp[tcpflags] & (tcp-syn|tcp-ack) = tcp-syn`  
This matches packets with SYN=1 and ACK=0 — pure SYN, not SYN-ACK. The SYN-ACK would have both bits set; this expression requires SYN set AND ACK clear.

**(c)** `not port 22`  
Or equivalently: `port not 22`

**(d)** `(port 80 or port 443) and net 192.168.1.0/24`

**(e)** `icmp and ip[8] < 5`  
`ip[8]` is byte offset 8 in the IP header, which is the TTL field. This captures ICMP packets where TTL < 5.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 21 notes.*