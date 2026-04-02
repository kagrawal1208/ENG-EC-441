# EC 441 — Lecture 17 Problem Set: IPv4, IPv6, NAT, and ICMP

**Topic:** The network layer's protocols — IPv4 header, ICMP, fragmentation, NAT, IPv6, DHCP  
**Lecture:** 17  
**Covers:** IPv4 header fields, TTL mechanics, ICMP types, fragmentation, NAT translation tables, IPv6 vs IPv4 comparison, IPv6 address notation, DHCP

---

## Problem 1: IPv4 Header Fields

A packet is captured with the following IPv4 header values:
- Version: 4, IHL: 5, DSCP: 101110, Total Length: 1500
- Identification: 0x4321, Flags: 010 (DF=1, MF=0), Fragment Offset: 0
- TTL: 63, Protocol: 6, Header Checksum: (valid)
- Source: 192.168.1.100, Destination: 93.184.216.34

**(a)** What is the total header size in bytes? How many bytes of payload does this packet carry?

**(b)** Which upper-layer protocol carries the payload? What well-known application does this suggest?

**(c)** The DSCP value is `101110`. What per-hop behavior does this correspond to, and what traffic class is it typically used for?

**(d)** The TTL is 63. Assuming the sender started with a default TTL of 64 (Linux default), how many hops has this packet traversed? What would a router do if it received this packet with TTL=1?

**(e)** The DF bit is set. The next hop link has MTU 576 bytes. What happens to this packet? What ICMP message is generated?

### Solution

**(a)** IHL = 5 → header size = 5 × 4 = **20 bytes** (minimum, no options).  
Payload = Total Length − Header = 1500 − 20 = **1480 bytes**.

**(b)** Protocol = 6 → **TCP**. TCP carries virtually all web traffic, SSH, email, and other connection-oriented applications. Port 80 (HTTP) or 443 (HTTPS) is the most likely application.

**(c)** DSCP `101110` = binary 46 = **Expedited Forwarding (EF)**. This is the highest-priority DSCP class, used for **VoIP calls** and other real-time traffic requiring low latency, low jitter, and low packet loss.

**(d)** TTL 63 = 64 − 1 → the packet has traversed **1 hop**. If TTL = 1 when received, the router decrements it to 0, **drops the packet**, and sends an **ICMP Time Exceeded (Type 11, Code 0)** message back to the source address. This is the exact mechanism that `traceroute` exploits to discover intermediate hops.

**(e)** Since DF=1, the router **cannot fragment** this 1500-byte packet to fit the 576-byte MTU. The router drops the packet and sends **ICMP Fragmentation Needed (Type 3, Code 4)** back to the source, including the MTU of the bottleneck link (576). The source then reduces its packet size and retries — this is Path MTU Discovery (PMTUD) in action.

---

## Problem 2: IP Fragmentation

A host sends a 3,980-byte IP datagram (including the 20-byte header, so 3,960 bytes of payload) over a network with MTU = 1,500 bytes.

**(a)** How many fragments are produced? What is the total length and payload of each fragment?

**(b)** Fill in a table showing: fragment number, Total Length, MF flag, Fragment Offset (in 8-byte units), and payload range (byte offsets into the original payload).

**(c)** Fragment 2 is lost in transit. The destination receives fragments 1 and 3. What happens?

**(d)** Why does the Fragment Offset field use 8-byte units rather than byte offsets? What constraint does this impose on fragment sizes?

### Solution

**(a)** Each fragment can carry at most 1500 − 20 = **1480 bytes** of payload.  
- Fragment 1: 1480 bytes payload → Total Length 1500 ✓  
- Fragment 2: 1480 bytes payload → Total Length 1500 ✓  
- Fragment 3: remaining = 3960 − 1480 − 1480 = **1000 bytes** → Total Length 1020

**3 fragments produced.**

**(b)** Fragment offsets in 8-byte units (1480 / 8 = 185):

| Frag | Total Length | MF Flag | Offset (8-byte units) | Payload Bytes (original) |
|------|--------------|---------|-----------------------|--------------------------|
| 1    | 1500         | 1       | 0                     | 0 – 1,479                |
| 2    | 1500         | 1       | 185                   | 1,480 – 2,959            |
| 3    | 1020         | 0       | 370                   | 2,960 – 3,959            |

Check: 3 × 1480 − 1480 = 3960 total payload ✓. Last fragment has MF=0 (no more fragments).

**(c)** Reassembly happens **only at the destination**. The destination buffers fragments 1 and 3, starts a reassembly timer, and waits for fragment 2. When the timer expires (typically 30–60 seconds), the destination **discards all received fragments** and the entire original datagram is lost. Fragment 1 and 3's data is wasted. The sender gets no direct notification — it will eventually time out at the transport layer (TCP retransmit, or application timeout for UDP).

**(d)** The Fragment Offset field is 13 bits wide. Using 8-byte units instead of bytes gives 13-bit × 8 = **65,528-byte maximum datagram offset**, which is sufficient for the 65,535-byte maximum IP datagram size. The constraint is that **all fragments except the last must have a payload that is a multiple of 8 bytes** — otherwise the next fragment's offset would be non-integer in 8-byte units. This is automatically satisfied when MTUs are multiples of 8, which all standard link MTUs are.

---

## Problem 3: NAT Translation Table

A home network (10.0.0.0/24) sits behind a NAT router with public IP 203.0.113.5.

Three hosts initiate connections simultaneously:
- Host A (10.0.0.2) connects to 93.184.216.34:443 from source port 50001
- Host B (10.0.0.3) connects to 93.184.216.34:443 from source port 50001  
- Host C (10.0.0.4) connects to 8.8.8.8:53 from source port 50002

**(a)** The NAT router must distinguish A and B since they use the same source port. Fill in the NAT translation table (WAN side → LAN side).

**(b)** A reply arrives at the NAT router: `Src: 93.184.216.34:443, Dst: 203.0.113.5:40002`. Which host does it get forwarded to? Rewrite the packet headers for delivery to the LAN host.

**(c)** Host A behind NAT tries to run a web server on port 80. An external host at 1.2.3.4 tries to connect to 203.0.113.5:80. What happens and why?

**(d)** Name two protocols that are broken by NAT (other than simple TCP/UDP flows) and explain why.

### Solution

**(a)** The NAT router assigns unique WAN-side ports to differentiate flows:

| WAN Side (public)          | LAN Side (private)     | Dest                   |
|----------------------------|------------------------|------------------------|
| 203.0.113.5:**40001**      | 10.0.0.2:50001         | 93.184.216.34:443      |
| 203.0.113.5:**40002**      | 10.0.0.3:50001         | 93.184.216.34:443      |
| 203.0.113.5:**40003**      | 10.0.0.4:50002         | 8.8.8.8:53             |

Note: A and B both used source port 50001, but the NAT router assigns different WAN ports (40001 vs 40002) to distinguish them. This is Port Address Translation (PAT).

**(b)** Reply `Src: 93.184.216.34:443, Dst: 203.0.113.5:40002`:  
NAT table lookup: WAN port 40002 → LAN host **10.0.0.3:50001**.

Rewritten packet delivered to LAN:
- Source: 93.184.216.34:443 (unchanged)
- Destination: **10.0.0.3:50001** (was 203.0.113.5:40002)
- IP and TCP/UDP checksums recomputed.

**(c)** The connection **fails silently** from the external host's perspective. NAT translation tables are populated by **outbound** connections only — the NAT router creates an entry when a LAN host initiates a connection. There is no entry for inbound connections to port 80 on 203.0.113.5. The NAT router has no idea which LAN host (if any) should receive this SYN packet, so it **drops** it. The fix is manual port forwarding: configure the NAT router to forward inbound traffic on port 80 to 10.0.0.2:80.

**(d)** Two protocols broken by NAT:

1. **FTP (active mode)**: In active mode FTP, the client sends the server a PORT command containing the client's private IP address and port number embedded *in the application payload*. The server then opens a connection back to that IP:port. The NAT router rewrites the IP header but not the payload, so the server receives the private (non-routable) IP address, which it cannot connect back to. (Passive mode FTP works around this.)

2. **SIP/VoIP**: SIP signaling embeds IP addresses in the SDP session description inside the packet payload (e.g., `c=IN IP4 10.0.0.2`). The NAT router rewrites the IP header but not the payload, so the remote endpoint receives a private address it cannot reach. STUN/TURN/ICE were developed specifically to work around this for WebRTC and VoIP.

---

## Problem 4: IPv6 Address Notation and Header Comparison

**(a)** Expand the following compressed IPv6 addresses to full 128-bit notation:
1. `::1`
2. `fe80::a1b2:3c4d`
3. `2001:db8::1:0:0:1`

**(b)** Compress the following full IPv6 address: `2001:0db8:0000:0000:0001:0000:0000:0001`

**(c)** A host has the IPv6 address `2001:db8:cafe:1::42/64`. What is the network prefix? How many host addresses can this /64 support?

**(d)** List three fields present in the IPv4 header that were **removed** in IPv6, and explain the rationale for each removal.

### Solution

**(a)** Expanding compressed addresses (fill zeros to make 8 groups of 4 hex digits):

1. `::1` = 7 groups of zeros + one group of 1:  
   `0000:0000:0000:0000:0000:0000:0000:0001`

2. `fe80::a1b2:3c4d` — 2 explicit groups + :: + 2 explicit groups = 4 groups present, :: expands to 4 zero groups:  
   `fe80:0000:0000:0000:0000:0000:a1b2:3c4d`

3. `2001:db8::1:0:0:1` — 2 groups before :: + 3 groups after = 5 groups, :: expands to 3 zero groups:  
   `2001:0db8:0000:0000:0001:0000:0000:0001`

**(b)** Starting with `2001:0db8:0000:0000:0001:0000:0000:0001`:
- Step 1 (drop leading zeros): `2001:db8:0:0:1:0:0:1`
- Step 2 (find longest consecutive zero run): groups 3–4 are `0:0` (2 zeros), groups 6–7 are `0:0` (2 zeros) — tie, choose first by convention
- Result: **`2001:db8::1:0:0:1`**

**(c)** Network prefix: **`2001:db8:cafe:1::/64`** (first 64 bits).  
Host addresses in a /64: 2^(128−64) = 2^64 ≈ **18.4 × 10^18 addresses** (18.4 quintillion). In practice, all modern /64 subnets have this many addresses — address exhaustion within a subnet is impossible.

**(d)** Three removed IPv4 fields and rationale:

| Removed Field | Rationale |
|---------------|-----------|
| **Header Checksum** | Redundant: link-layer CRCs (Ethernet FCS) catch per-hop bit errors; TCP/UDP checksums cover end-to-end integrity. Recomputing the checksum at every router wastes CPU cycles for no additional error detection. |
| **Fragmentation fields** (Identification, Flags, Fragment Offset) | IPv6 moves fragmentation to endpoints only — routers never fragment. Endpoints use Path MTU Discovery. Removing these fields simplifies the base header and eliminates fragmentation-based attacks (Ping of Death, Teardrop). |
| **IHL (Internet Header Length)** | IPv4 IHL was needed because the Options field made the header variable length. IPv6 has a fixed 40-byte base header; optional features go in extension headers via the Next Header chain. With a fixed header size, IHL is unnecessary. |

---

## Problem 5: DHCP and Protocol Integration

**(a)** Trace the four DHCP messages (Discover, Offer, Request, Ack) for a new host joining a network. For each message, specify: source IP, destination IP, source port, destination port, and what information is carried.

**(b)** A host receives DHCP Offer with lease time 3600 seconds (1 hour). At what time does the client typically attempt to renew? What happens if renewal fails but the lease hasn't expired?

**(c)** Why does DHCP use UDP rather than TCP? Why does the Discover message use 0.0.0.0 as source and 255.255.255.255 as destination?

**(d)** A ping to a remote host shows `TTL=54` in the reply. The remote host runs Linux (default TTL=64). How many hops away is the remote host? Is this definitive?

### Solution

**(a)** DHCP four-way handshake:

| Message  | Src IP    | Dst IP            | Src Port | Dst Port | Carries |
|----------|-----------|-------------------|----------|----------|---------|
| Discover | 0.0.0.0   | 255.255.255.255   | 68       | 67       | Client MAC, requested lease time |
| Offer    | (DHCP server IP) | 255.255.255.255 or client | 67 | 68 | Offered IP, subnet mask, gateway, DNS, lease time |
| Request  | 0.0.0.0   | 255.255.255.255   | 68       | 67       | Requested IP (from Offer), selected server ID |
| Ack      | (DHCP server IP) | client's new IP | 67 | 68 | Confirmed IP, all configuration parameters |

Note: Discover and Request use 0.0.0.0 source because the client doesn't yet have an IP. Broadcast destination reaches all servers on the subnet, including multiple DHCP servers if present.

**(b)** The client attempts renewal at **T/2 = 1800 seconds** (50% of lease time) via unicast to the server that granted the lease. If that fails, it retries at **T×7/8 = 3150 seconds** via broadcast (in case the original server is down). If the lease expires without renewal, the client must release the address and restart the full Discover process — it loses its IP.

**(c)** **UDP instead of TCP**: TCP requires a connection setup (SYN/SYN-ACK/ACK), which requires both endpoints to have IP addresses. The client has no IP address yet, so TCP connection establishment is impossible. UDP allows sending a single broadcast datagram before any addressing is configured.

**0.0.0.0 source**: The client has no assigned IP yet — using 0.0.0.0 signals "this host" in the pre-configuration state. **255.255.255.255 destination**: The client doesn't know the DHCP server's address, so it broadcasts to all hosts on the local subnet. Routers don't forward 255.255.255.255 broadcasts (limited broadcast), so this only reaches the local segment. DHCP relay agents handle multi-subnet environments by forwarding the broadcast as a unicast to a known DHCP server.

**(d)** TTL in reply = 54. Linux default starting TTL = 64. Hops = 64 − 54 = **10 hops**.

This is **not definitive** for two reasons: (1) the remote host might not use Linux — Windows uses TTL=128, network equipment uses TTL=255. If the remote host used Windows with TTL=128, the calculation would be 128−54=74 hops, a completely different answer. (2) Some routers decrement TTL by more than 1 (non-standard but observed). Without knowing the source OS and its default TTL, the calculation is an estimate.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 17 notes.*
