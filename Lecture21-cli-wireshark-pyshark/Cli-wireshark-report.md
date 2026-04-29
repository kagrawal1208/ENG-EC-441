# See the Network: CLI Tools, Wireshark, and pyshark

**EC 441 — Lecture 21 Report**  
*Topic: How standard Linux tools make semester-long protocol theory directly observable*

---

## Introduction

For twenty lectures, the protocols of the internet have lived in diagrams and equations. IP datagrams, TCP sequence numbers, ICMP Time Exceeded messages, congestion windows — these exist as abstract constructs, useful for answering exam questions and building mental models. Lecture 21 changes the register. These protocols are running right now, on the machine in front of you, producing output that standard tools can read in real time.

This report connects each tool to the concepts it makes visible, explains what the output fields mean in protocol terms, and frames pyshark as the bridge between packet observation and data analysis. The central message: the tools are not new content — they are a lens through which the entire semester becomes measurable.

---

## ping: The RTT Signal in Its Rawest Form

ping sends ICMP Echo Request messages and reports the time until an ICMP Echo Reply arrives. From L17, we know ICMP is IP's control-message protocol — the mechanism by which the network reports errors and status conditions. From L19, we know TCP uses a continuously-updated RTT estimate to set its retransmission timer.

What ping prints are exactly the individual RTT samples that feed TCP's Jacobson EWMA. The per-packet RTT values are the signal; SRTT is the smoothed estimate of its mean; RTTVAR tracks its variance. The `mdev` statistic in ping's summary is a rough approximation of what RTTVAR quantifies: the spread of RTT measurements around the mean. A high-`mdev` path forces TCP to set a conservative RTO — without the safety margin of RTTVAR, any packet that takes slightly longer than the smooth mean would trigger a spurious retransmit.

The TTL field in ping's output connects to L17's IP header discussion. The TTL reported is from the *reply* packet. If Google's servers start replies at TTL=128 (common for Windows or some network appliances) and a reply arrives with TTL=117, the hop count is 128−117=11. The initial TTL is almost always 64, 128, or 255 — knowing which one lets you infer whether the destination runs Linux, Windows, or a network appliance.

---

## traceroute: Exploiting a Protocol Side Effect

traceroute is one of the most instructive tools in networking because it works entirely by exploiting a side effect of normal IP forwarding. TTL is not a traceroute mechanism — it is an anti-looping safety feature. Every router that forwards a packet decrements the TTL field. When TTL reaches zero, the router drops the packet and sends back an ICMP Time Exceeded message.

traceroute sends a series of probes with TTL=1, TTL=2, TTL=3, and so on. The probe with TTL=1 is dropped by the first router, which reveals itself via ICMP Time Exceeded. TTL=2 reveals the second router. This continues until a probe reaches the destination and returns an ICMP Echo Reply (or TCP RST, in TCP-mode traceroute).

Several observations connect directly to earlier lectures. The `* * *` entries at some hops do not mean the path is broken — they mean the router at that hop suppresses ICMP Time Exceeded responses (common on backbone routers to prevent amplification attacks). Subsequent hops still respond, proving the path is intact. Large RTT jumps between adjacent hops mark either AS boundary crossings — where packets transition from one autonomous system to another — or intercontinental links. A 10ms → 80ms jump often indicates a transatlantic cable: 10ms is local, 80ms is the round-trip to Europe. Asymmetric routing is a subtler point: traceroute only shows the forward path. The ICMP Time Exceeded messages travel a return path that may use entirely different routers, so the RTTs in traceroute output include both the forward delay to each hop and whatever return path the ICMP reply takes.

---

## ip and ss: The Kernel's Internal State

The `ip` command exposes three data structures that are otherwise invisible: the interface table (`ip addr`), the forwarding table (`ip route`), and the ARP cache (`ip neigh`). These map directly to L14 (IP addressing), L13 (IP forwarding), and L08 (ARP/Ethernet).

The forwarding table visible in `ip route` is the exact data structure a router walks when making forwarding decisions. The default route (`default via X.X.X.X`) is the entry matched when no more-specific prefix applies — the gateway of last resort. The ARP cache in `ip neigh` shows the resolved IP-to-MAC mappings that populate the Ethernet destination field; the STALE state means an entry was valid but hasn't been used or confirmed recently, and will be re-probed before being evicted.

`ss -tipm` is the most intellectually satisfying tool in this lecture, because it exposes the congestion control state machine from L19–L20 in real time. The `rtt:X/Y` field is exactly SRTT and RTTVAR from Jacobson's algorithm. The `cwnd` field is the current congestion window in MSS units. The `ssthresh` field is the slow-start threshold; a value of 2^31−1 means the connection has never experienced loss. `app_limited:1` reveals when the sender is not writing data fast enough to fill the window — the network is idle not because of congestion but because the application isn't generating traffic fast enough.

Running `watch -n 0.5 'ss -tipm | grep iperf'` while iperf3 is running shows the congestion control state machine in real time: cwnd grows exponentially during slow start, switches to linear growth when it crosses ssthresh, and halves sharply if packet loss occurs. The abstract diagrams from L20 become live numbers updating twice per second.

---

## dig: DNS Queries in Real Time

dig sends DNS queries and displays the full server response, including the record type, TTL, and which server answered. The `+trace` flag follows the complete resolution chain from root servers to TLD nameservers to authoritative servers — a preview of L23's topic.

The TTL in a DNS response is not the IP TTL — it is the cache lifetime in seconds. When a client receives a DNS response with TTL=300, the resolver may cache this mapping for up to 300 seconds before re-querying. Low TTLs are common for CDN resources that need to direct clients to different servers rapidly; high TTLs are common for stable infrastructure where rapid updates are not needed.

Running `dig` while `tcpdump port 53` is capturing in another window confirms the UDP transport visible in L18: DNS queries travel as UDP datagrams to port 53, and the entire round-trip (query out, response back) is visible in the packet capture. If the DNS response is truncated (the TC bit is set in the DNS header), the client retries the query over TCP — a rare but observable fallback.

---

## tcpdump: The Universal Capture Tool

tcpdump's filter language is the same BPF (Berkeley Packet Filter) engine used by Wireshark and pyshark — the same expression in all three tools. Understanding the filter syntax pays dividends across all packet analysis work. Compound filters (`tcp and port 80`, `host 8.8.8.8 and port 53`) combine cleanly with boolean operators. Field offsets like `ip[8] < 5` access raw bytes in the IP header, enabling filters that the high-level syntax doesn't cover directly.

The output of a live tcpdump session shows fields from every protocol covered in the course simultaneously: the timestamp, source/destination IPs (L14), TTL in some contexts, the protocol (TCP/UDP/ICMP), port numbers (L18), TCP flags (L19), and sequence numbers. Reading a tcpdump trace is the operational skill that corresponds to the theoretical knowledge of all those lectures combined.

---

## pyshark: A Packet Capture Is a Dataset

Wireshark is optimized for deep inspection of individual packets and conversations. pyshark is optimized for asking questions across thousands of packets: which domains did this host look up? How did RTT evolve over a ten-minute transfer? What fraction of traffic is QUIC?

The conceptual shift is important. tcpdump and Wireshark present packets sequentially — you scroll through and look. pyshark treats the capture as a dataset and lets you write Python against it. The attribute namespace mirrors Wireshark exactly: `pkt.ip.src`, `pkt.tcp.seq`, `pkt.dns.qry_name`, `pkt.tcp.analysis_ack_rtt`. Any field visible in the Wireshark GUI is accessible as a Python attribute.

The TCP RTT plot from Demo 4 is the most theoretically rich output in the lecture. The plot shows individual per-segment RTTs as computed by tshark (from ACK timestamps). This is the raw signal. The SRTT from L19 is a smoothed version of this signal — an EWMA that tracks its mean while filtering transient spikes. RTTVAR is a smoothed estimate of the spread visible in the plot. The RTO formula `SRTT + 4×RTTVAR` is a confidence bound designed to sit above nearly every point in the plot without being unnecessarily large. Visualizing the actual data makes the motivation for Jacobson's two-filter design immediately obvious in a way that formulas alone cannot.

---

## The Unified View

The tools covered in this lecture form a complete observability stack for the protocols studied all semester. ping shows ICMP and RTT. traceroute shows TTL, ICMP, and AS topology. ip shows addressing, forwarding tables, and ARP. ss shows live TCP congestion state. dig shows DNS. tcpdump captures everything. Wireshark dissects it. pyshark analyzes it programmatically.

None of this is theoretical. The same commands — ping, traceroute, tcpdump, ss — run on Juniper JunOS, on Arista EOS, on every Linux-based router and switch in production networks. What the course called "protocol concepts" the industry calls "what you read when something breaks." The tools are not a supplement to the theory. They are what the theory looks like when it runs.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 21 notes.*