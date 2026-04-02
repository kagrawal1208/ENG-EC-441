# What's Inside Every Packet: The IPv4 Header and Its Consequences

**EC 441 — Lecture 17 Report**  
*Topic: IPv4 datagram design, ICMP, NAT, IPv6, and DHCP — the protocols that make routing concrete*

---

## Introduction

Lectures 13 through 16 built the routing machinery — how forwarding tables are constructed, how routing algorithms compute paths, how BGP governs inter-domain traffic. All of that machinery operates on packets. This lecture examines the packet itself: what fields the IPv4 header contains, what each router actually looks at on every hop, and what auxiliary protocols (ICMP, DHCP) make the system work.

The IPv4 header is a 20-byte structure that has been transmitted hundreds of billions of times every day for over 40 years. Its design reflects a series of careful tradeoffs made in 1981, some of which turned out to be mistakes. Understanding those tradeoffs — and why IPv6 changed them — is the point of this lecture.

---

## The Header as a Contract Between Routers

The IPv4 header is not primarily for the sender or receiver — it is for the routers in between. Its fields are a protocol: a contract specifying what each intermediate device must do to move the packet forward.

Every router examines exactly four fields in the IPv4 header at each hop. The **Destination Address** drives the forwarding decision via longest-prefix match. The **TTL** is decremented by one; if it reaches zero, the packet is dropped and an ICMP message is sent back to the source. The **Header Checksum** is verified and recomputed (because TTL changed, the checksum changes too). The **Total Length** determines where the packet ends in a stream of bytes.

Everything else — Source Address, Protocol, DSCP, fragmentation fields — either passes through unchanged or is only examined under specific circumstances. NAT is a conspicuous exception: NAT routers modify the Source Address (and sometimes the Source Port), which is why NAT breaks the end-to-end design that IP was built around.

The Protocol field (8 bits) is the demultiplexing key that tells the destination which upper-layer module should receive the payload: 1 for ICMP, 6 for TCP, 17 for UDP, 89 for OSPF. This is directly analogous to the EtherType field in Ethernet frames, which identifies whether the payload is IPv4, IPv6, or ARP. Each layer has a field that names the protocol above it.

---

## TTL: Solving a Problem That Shouldn't Exist

The TTL field exists to solve routing loops. If forwarding tables are consistent — every router making the correct decision — packets always reach their destination and TTL never matters. But during convergence, or when tables are misconfigured, a packet can loop: A forwards to B, B forwards to C, C forwards to A, indefinitely. Without TTL, a looping packet would consume bandwidth forever.

TTL is set by the sender (Linux uses 64, Windows uses 128, network equipment uses 255) and decremented by every router. When it reaches zero, the router drops the packet and sends an ICMP Time Exceeded message (Type 11, Code 0) back to the source. The traceroute utility exploits this mechanism deliberately: by sending packets with TTL=1, 2, 3, ... in sequence, it causes each router along the path to generate an ICMP Time Exceeded, revealing the full path from source to destination. The "protocol underneath traceroute" is ICMP — not TCP, not UDP, not some application-layer mechanism.

The TTL field also has a diagnostic use: the TTL value in a received packet (combined with knowledge of the sender's default TTL) reveals approximately how many hops the packet traversed. A packet arriving with TTL=54 from a Linux host (which started at 64) has crossed roughly 10 hops.

---

## ICMP: The Internet's Error Reporting Layer

The Internet Control Message Protocol (ICMP) is the network layer's feedback mechanism. It operates inside IP datagrams (Protocol = 1) and provides two categories of functionality: error reporting and diagnostics.

Error reporting covers the failures that IP itself cannot communicate. When a router drops a packet because TTL expired, it can't just silently discard it — the sender needs to know. ICMP carries that notification. When a packet can't be delivered because there's no route to the network (Type 3, Code 0), no route to the specific host (Code 1), or the destination port is closed (Code 3), ICMP carries the error back to the sender. In each case, the ICMP message body includes the original IP header plus the first 8 bytes of the failed packet's payload — enough to identify the source port and destination port that caused the failure, so the sending application can correlate the error with a specific connection.

Diagnostics are the ping and traceroute tools. Ping sends ICMP Echo Request (Type 8, Code 0) and receives ICMP Echo Reply (Type 0, Code 0), measuring RTT. Traceroute exploits ICMP Time Exceeded, as described above. Both of these tools work directly at the network layer without any transport-layer involvement — a common misconception is that ping uses UDP; it does not.

The fragmentation-related ICMP message (Type 3, Code 4 — Fragmentation Needed) deserves special attention because it enables Path MTU Discovery (PMTUD). When a sender sets the DF (Don't Fragment) bit and a router encounters a link with insufficient MTU, the router drops the packet and sends ICMP Type 3 Code 4 back, including the MTU of the bottleneck link. The sender reduces its packet size and retries. This iterative process converges on the path MTU — the minimum MTU across all links on the path — without requiring any router to know the full path.

Firewalls that block all ICMP traffic break PMTUD. The result is a "black hole": connections appear to establish (small packets like TCP SYN get through) but stall when large data packets are sent (the ICMP Fragmentation Needed message is blocked, so the sender never learns to reduce its packet size). This is a well-known operational problem that argues strongly against blanket ICMP blocking.

---

## Fragmentation: A Design Mistake

IP fragmentation allows a router to split an oversized datagram into smaller pieces when the outgoing link's MTU is smaller than the datagram. The pieces (fragments) share the same Identification value and are reassembled — only at the destination, never at intermediate routers — using the Fragment Offset field (in 8-byte units) and the More Fragments (MF) flag.

In theory, fragmentation is elegant: it allows the network to handle datagrams that don't fit on some links. In practice, it has several serious problems.

Losing a single fragment loses the entire original datagram — the destination buffers all fragments, and if any one is missing when the reassembly timer expires, all buffered fragments are discarded. The sender gets no notification at the IP layer; the loss surfaces only when a transport-layer retransmit timer fires. This means fragmentation amplifies the impact of any packet loss.

Reassembly is complex and creates state at the destination that can be exploited. Historical attacks like "Ping of Death" (oversized fragments that overflow reassembly buffers) and "Teardrop" (overlapping fragment offsets that cause buffer management errors) exploited fragmentation to crash or exploit systems.

Each fragment carries its own 20-byte IP header, adding overhead. For a datagram fragmented into three pieces, three headers are transmitted instead of one.

The modern solution is Path MTU Discovery: senders set DF=1 and reduce packet size based on ICMP feedback, eliminating in-network fragmentation entirely. IPv6 removes fragmentation from the base header completely — routers never fragment, and endpoints handle MTU via PMTUD.

---

## NAT: The Hack That Saved the Internet, At a Cost

NAT's premise is simple: an entire private network shares one public IP address. When a private host sends a packet, the NAT router rewrites the source IP (and source port) to the router's public IP and a freshly assigned port number, records the mapping in a translation table, and forwards the packet. When the reply arrives, the NAT router consults its table, rewrites the destination back to the private host's IP and port, and forwards it inward.

This Port Address Translation (PAT) allows a single public IP to support up to ~65,000 simultaneous TCP/UDP connections (the range of available port numbers). It's why a household with five devices and one public IP can all browse the internet simultaneously.

NAT fundamentally violates the end-to-end principle — the original design axiom that intelligence should sit at the endpoints, not in the middle of the network. Several important consequences follow.

**Incoming connections fail by default.** NAT tables are populated by outbound connections. An external host trying to reach a private server gets dropped because there's no table entry. Manual port forwarding ("open port 80 and forward it to 192.168.1.10:80") is the workaround.

**Peer-to-peer communication requires workarounds.** Two hosts both behind NAT cannot directly communicate without a third party to relay connections (TURN) or coordinate the NAT traversal (STUN/ICE). The technology behind WebRTC, VoIP, and multiplayer gaming relies on elaborate hole-punching techniques to work around NAT.

**Protocols that embed IP addresses in payloads break.** FTP's active mode embeds the client's private IP in an application-layer command. The NAT router rewrites the IP header but doesn't parse the FTP payload, so the server receives a private address it can't reach. This is why FTP active mode doesn't work through NAT, and why VoIP requires ALGs (Application Layer Gateways) or STUN.

Despite these costs, NAT extended IPv4's operational life by roughly 20 years. Without it, IPv6 would have been a hard requirement much earlier. With it, IPv4 remained "good enough" for long enough that a smooth transition became permanently deferred.

---

## IPv6: Correcting the Mistakes

IPv6's header design reflects lessons learned from 20 years of IPv4 deployment. The changes are mostly subtractions.

The header checksum was removed. IPv4 required every router to verify and recompute the checksum on every packet. With link-layer CRCs catching per-hop bit errors and TCP/UDP checksums providing end-to-end integrity, the IP header checksum added CPU overhead at every router for essentially no additional error detection. IPv6 routers can process headers faster as a result.

Fragmentation was removed from the base header. IPv6 routers never fragment. Path MTU Discovery is mandatory, and fragmentation can only be performed by source endpoints using an extension header. This eliminates the security vulnerabilities and reassembly complexity associated with IPv4 fragmentation.

Options were removed from the base header. IPv4's variable-length options field required routers to determine the header length using the IHL field and handle various option types in software. IPv6 uses a fixed 40-byte base header with optional extension headers chained via the Next Header field. The base header is always the same size, enabling faster hardware processing.

Broadcast was eliminated. IPv4 broadcasts (255.255.255.255) cause all hosts on a subnet to receive and process every broadcast packet. IPv6 replaces broadcast with targeted multicast — each functional group (all routers, all DHCP servers, etc.) has its own multicast address.

IPv6's 128-bit address space makes the address exhaustion problem moot. With 2^128 addresses — enough to assign billions of addresses to every square millimeter of Earth's surface — there is no scenario in which IPv6 exhausts its address space.

The irony is that IPv6 has been "almost ready" for 25 years. Its deployment has been largely driven by mobile carriers (who ran out of IPv4 first) and has remained uneven globally. NAT's effectiveness at working around IPv4 exhaustion removed the urgency. The transition continues, slowly.

---

## DHCP: Bootstrapping Without an Address

DHCP solves a circular problem: a host needs an IP address to communicate, but it needs to communicate to get an IP address. The solution is to use broadcasts before any address is configured.

The four-message exchange (Discover, Offer, Request, Ack) uses UDP — not TCP, because TCP connection establishment requires an IP address at both endpoints. The client sends from 0.0.0.0 (no address assigned) to 255.255.255.255 (limited broadcast). The server responds with an offer. The client requests the offered address. The server confirms.

The use of UDP broadcast for Discover and Request is notable: multiple DHCP servers may exist on a subnet, and broadcasting allows all of them to see the request and respond. The client selects one offer (typically the first received) and broadcasts the Request message so all other servers know their offers were declined. Only the Ack goes unicast — by that point, the client's IP is known.

DHCP leases are time-limited. A client must renew before the lease expires (typically attempting renewal at the 50% mark). If the DHCP server is unreachable and the lease expires, the client must release its address and restart the process — a constraint that matters for long-running servers and services that can't tolerate address changes.

IPv6's SLAAC (Stateless Address Auto-Configuration) eliminates the need for a DHCP server for address assignment: hosts generate their own addresses from the network prefix (advertised by routers in Router Advertisement messages) and their interface identifier. DHCPv6 still provides DNS server addresses and other options, but the core address assignment is self-contained.

---

## Conclusion

The IPv4 header is simultaneously elegant and flawed. It's elegant in that 20 bytes contain everything a network needs to forward a packet across a planet. It's flawed in that the header checksum adds per-hop overhead, fragmentation creates security vulnerabilities and complexity, the lack of a large address space required NAT, and NAT broke the end-to-end model.

IPv6 is the considered response — a redesign that removes the overhead, eliminates fragmentation from the network interior, restores end-to-end addressing, and provides an address space that will never be exhausted. Its slow adoption is a consequence of NAT being "good enough" for long enough that the economic incentive to upgrade disappeared.

ICMP, DHCP, and NAT are all products of the same dynamic: IP's original design didn't anticipate certain problems, and these protocols were developed to work around the gaps. Understanding them together — the original design, the gaps, and the workarounds — gives a complete picture of the network layer that every packet traverses.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 17 notes.*
