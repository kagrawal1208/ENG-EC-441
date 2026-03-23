# Problem Set: The Network Layer — Forwarding and Routing
**EC 441 - Intro to Computer Networking | Lecture 13**
**Topic:** Network Layer - Addressing, Forwarding, Routing, LPM, SDN

---

## Problem 1 - Network Layer Fundamentals

**(a)** Name the three responsibilities of the network layer and describe each in
one sentence.

**(b)** For each of the following functions, state whether it belongs to the
**data plane** or **control plane**, and give a one-line justification:

| Function | Plane | Why |
|----------|-------|-----|
| Running OSPF to exchange link-state advertisements | ? | ? |
| Decrementing TTL by 1 for an arriving packet | ? | ? |
| Installing a new route into the FIB | ? | ? |
| Performing longest-prefix match on a destination address | ? | ? |
| BGP selecting the best path to 8.8.0.0/16 | ? | ? |
| Dropping a packet whose header checksum fails | ? | ? |

**(c)** A router at a Tier-1 backbone exchange point processes 4 Tb/s of traffic.
A minimum-sized Ethernet frame carries a 64-byte IP packet. How many forwarding
decisions per second must the router make, assuming all traffic is minimum-sized?

**(d)** Why can't this router use a software lookup through a hash table in RAM
for each forwarding decision? What hardware does it use instead, and what is
the key property that makes it fast enough?

---

### Solution to Problem 1

**(a) Three responsibilities:**

- **Addressing:** assign every host a globally unique identifier (IPv4: 32-bit dotted
  decimal; IPv6: 128-bit colon-hex) so a packet can specify where it should go.
- **Forwarding:** at each individual router, examine the destination address and
  decide which output port to send the packet out on — a local, per-packet, data-plane
  operation taking nanoseconds.
- **Routing:** compute what the forwarding tables across the *entire network* should
  contain so packets reach their destinations efficiently — a network-wide, algorithmic,
  control-plane operation taking seconds to minutes.

**(b) Data plane vs. control plane:**

| Function | Plane | Why |
|----------|-------|-----|
| Running OSPF | **Control** | Routing protocol; computes routes over seconds/minutes |
| Decrementing TTL | **Data** | Per-packet operation at line rate |
| Installing route into FIB | **Control** | Control plane writes the table; happens occasionally |
| Longest-prefix match | **Data** | Executed per-packet in hardware for every forwarded packet |
| BGP path selection | **Control** | Network-wide routing decision; runs on routing processor |
| Dropping bad checksum | **Data** | Per-packet check at line rate in hardware |

**(c) Forwarding decisions per second at 4 Tb/s**

```
Frame size = 64 bytes = 512 bits
Frames/sec = 4 x 10^12 bits/s  /  512 bits/frame
           = 7.8 x 10^9 frames/second  (~7.8 billion/s)
```

Each frame requires one forwarding decision, so the router must make approximately
**7.8 billion forwarding decisions per second**.

**(d) Why not a RAM hash table?**

At 7.8 billion lookups/second, the time budget per lookup is:

```
1 / (7.8 x 10^9) ≈ 0.13 ns per lookup
```

A sequential DRAM access takes ~50-100 ns — roughly 400-800x too slow. Even SRAM
is ~1-2 ns per access, still too slow for multi-step hash lookups.

The solution is **TCAM (Ternary Content-Addressable Memory)**. Each TCAM entry
stores a (value, mask) pair where each bit can be 0, 1, or **X (don't care)** —
the X bits represent the host portion of a prefix. TCAM performs a **parallel search
across all entries simultaneously in a single clock cycle**, returning all matching
entries at once. A priority encoder then selects the longest match.
The cost: TCAM is expensive in power and die area, and capacity is limited — the full
BGP table (~900,000 prefixes) barely fits in commodity TCAM chips.

---

## Problem 2 - TTL and Traceroute

A packet leaves a Linux host (initial TTL = 64) destined for a server 9 hops away.

**(a)** What TTL value does the server receive?

**(b)** The server sends a reply. Assuming the server also uses Linux (TTL = 64)
and the reverse path is also 9 hops, what TTL does the original sender observe
in the reply?

**(c)** A network engineer runs traceroute to a host and sees:

```
1   192.168.1.1      1.1 ms
2   10.24.0.1        8.3 ms
3   * * *
4   72.14.200.1     14.1 ms
5   142.250.80.46   14.9 ms
```

What does hop 3 (`* * *`) mean? Does it mean the packet was dropped at
hop 3 for all traffic? Is the end-to-end path broken?

**(d)** Explain precisely what traceroute does to discover each hop. Why do routers
reveal themselves without any special traceroute protocol?

**(e)** A packet arrives at a router with TTL = 1. What does the router do?
What message does it send, to whom?

---

### Solution to Problem 2

**(a)** Each of the 9 routers along the path decrements TTL by 1:

```
TTL at destination = 64 - 9 = 55
```

**(b)** The server starts a new packet with TTL = 64 and it traverses 9 hops:

```
TTL observed by original sender = 64 - 9 = 55
```

**(c)** `* * *` means the router at hop 3 **silently dropped the TTL-expired probe**
instead of sending an ICMP Time Exceeded reply. This is a common firewall policy —
many routers are configured not to respond to TTL-expired probes to avoid revealing
internal topology.

It does **not** mean packets are dropped at hop 3 for regular traffic. The router is
still forwarding normal traffic normally. The end-to-end path is **not broken** —
we can see hop 4 responding, which proves packets are passing through hop 3.

**(d)** traceroute sends a series of probes (UDP datagrams or ICMP Echo Requests)
with TTL = 1, 2, 3, ... in sequence:

- Probe with TTL=1: the first router decrements to 0, drops the packet, and sends
  back an **ICMP Time Exceeded** message — revealing its own IP address.
- Probe with TTL=2: passes the first router (TTL decremented to 1), hits the second
  router which decrements to 0 and replies — and so on.

Routers reveal themselves because **TTL decrement and ICMP Time Exceeded generation
is normal required IP behavior** (RFC 791/792). They are not doing anything special
for traceroute — traceroute exploits the TTL mechanism as an emergent behavior.

**(e)** The router decrements TTL from 1 to 0. It **drops the packet** and sends an
**ICMP Time Exceeded (Type 11, Code 0)** message back to the **original source host**
(the IP source address in the dropped packet's header). The packet is not forwarded.

---

## Problem 3 - Longest-Prefix Match

A router has the following forwarding table:

| Prefix | Next Hop | Interface |
|--------|----------|-----------|
| 0.0.0.0/0 | 203.0.113.1 | eth0 |
| 10.0.0.0/8 | 10.255.0.1 | eth1 |
| 10.1.0.0/16 | 10.1.255.1 | eth2 |
| 10.1.2.0/24 | 10.1.2.254 | eth3 |
| 10.1.2.128/25 | 10.1.2.129 | eth4 |
| 192.168.0.0/16 | 192.168.0.1 | eth5 |

For each destination address below, list **all matching prefixes** (with lengths),
identify the **longest match**, and state the **output interface**.

**(a)** `10.1.2.200`

**(b)** `10.1.2.50`

**(c)** `10.1.5.1`

**(d)** `192.168.100.1`

**(e)** `172.16.0.1`

**(f)** `10.1.2.128` (the network address itself — does it match /25?)

---

### Solution to Problem 3

The rule: convert each prefix to its range, check if the destination falls in that
range. Among all matches, pick the one with the longest prefix length.

**(a) 10.1.2.200**

- `0.0.0.0/0` — matches everything ✓ (length 0)
- `10.0.0.0/8` — 10.x.x.x ✓ (length 8)
- `10.1.0.0/16` — 10.1.x.x ✓ (length 16)
- `10.1.2.0/24` — 10.1.2.0–10.1.2.255 ✓ (length 24)
- `10.1.2.128/25` — 10.1.2.128–10.1.2.255: 200 ≥ 128 ✓ (length 25)
- `192.168.0.0/16` — no ✗

**Longest match: `10.1.2.128/25` (length 25) → forward out eth4**

**(b) 10.1.2.50**

- `0.0.0.0/0` ✓ (0)
- `10.0.0.0/8` ✓ (8)
- `10.1.0.0/16` ✓ (16)
- `10.1.2.0/24` ✓ (24)
- `10.1.2.128/25` — 50 < 128 ✗

**Longest match: `10.1.2.0/24` (length 24) → forward out eth3**

**(c) 10.1.5.1**

- `0.0.0.0/0` ✓ (0)
- `10.0.0.0/8` ✓ (8)
- `10.1.0.0/16` — 10.1.x.x: 10.1.5.1 ✓ (16)
- `10.1.2.0/24` — 10.1.2.x only: 5 ≠ 2 ✗
- `10.1.2.128/25` ✗

**Longest match: `10.1.0.0/16` (length 16) → forward out eth2**

**(d) 192.168.100.1**

- `0.0.0.0/0` ✓ (0)
- `10.x.x.x` prefixes ✗
- `192.168.0.0/16` — 192.168.x.x: 100 is a valid third octet ✓ (16)

**Longest match: `192.168.0.0/16` (length 16) → forward out eth5**

**(e) 172.16.0.1**

- `0.0.0.0/0` ✓ (0)
- All others ✗ (wrong first octet)

**Longest match: `0.0.0.0/0` (length 0, default route) → forward out eth0**

**(f) 10.1.2.128 (network address)**

- `0.0.0.0/0` ✓ (0)
- `10.0.0.0/8` ✓ (8)
- `10.1.0.0/16` ✓ (16)
- `10.1.2.0/24` ✓ (24)
- `10.1.2.128/25` — range is 10.1.2.128–10.1.2.255; 128 = 128 ✓ (25)

Yes, the network address itself falls within the range.
**Longest match: `10.1.2.128/25` (length 25) → forward out eth4**

---

## Problem 4 - Router Architecture

A router has 8 input ports and 8 output ports, each running at 100 Gb/s.

**(a)** What is the minimum throughput the switching fabric must support to avoid
being a bottleneck?

**(b)** Describe head-of-line (HOL) blocking. Give a concrete example with 2 input
ports and 2 output ports showing how it causes a packet to be delayed even
though its target output port is free.

**(c)** What is Virtual Output Queuing (VOQ) and how does it solve HOL blocking?

**(d)** Packets arrive at an output port faster than the link can drain them.
Describe what happens under **tail drop** vs. **RED (Random Early Detection)**.
Which is better for TCP performance and why?

**(e)** A routing protocol crash freezes the control plane for 30 seconds. What
happens to traffic being forwarded during this time? Why?

---

### Solution to Problem 4

**(a) Minimum switching fabric throughput**

```
8 ports x 100 Gb/s = 800 Gb/s aggregate input rate
```

The fabric must support at least **800 Gb/s** to forward all inputs simultaneously
without becoming a bottleneck. High-end routers use a crossbar fabric that can
connect any input to any output simultaneously, providing full non-blocking throughput.

**(b) HOL blocking example**

Setup: 2 input ports (I1, I2), 2 output ports (O1, O2).

```
I1 queue (FIFO): [pkt-A -> O1, pkt-B -> O2]
I2 queue (FIFO): [pkt-C -> O1]
```

Round 1: I1's head packet (pkt-A) needs O1. I2's head packet (pkt-C) also needs O1.
O1 can only accept one packet — say pkt-A wins. pkt-C waits.

Meanwhile: pkt-B in I1's queue needs O2, which is **completely free**. But pkt-B is
stuck behind pkt-A in I1's FIFO queue — it cannot advance even though O2 is idle.

**pkt-B is blocked by a packet ahead of it that wants a different output port.**
This is HOL blocking: O2 sits idle while pkt-B waits unnecessarily.

**(c) Virtual Output Queuing (VOQ)**

Instead of one FIFO queue per input port, maintain **one queue per (input, output)
pair**. With N ports, each input port maintains N separate queues.

In the example above:
```
I1 has: queue-for-O1: [pkt-A], queue-for-O2: [pkt-B]
I2 has: queue-for-O1: [pkt-C]
```

Now pkt-B in I1's O2-queue is never blocked by pkt-A. When O1 is busy, pkt-B
can be scheduled to O2 immediately. HOL blocking is eliminated. The tradeoff is
more complex scheduling logic (the fabric scheduler must select a conflict-free
matching across all input-output pairs each cycle).

**(d) Tail drop vs. RED**

**Tail drop:** when the output queue is full, every newly arriving packet is discarded.
All TCP senders whose packets hit the full queue experience loss simultaneously,
triggering simultaneous congestion window reductions — "global synchronization."
After all senders back off together, the link goes underutilized briefly, then they all
ramp up together again, causing oscillation.

**RED (Random Early Detection):** begins dropping (or marking) packets
*probabilistically* before the queue is full, based on the average queue length. Early
loss signals reach individual TCP senders at different times, staggering their
backoff responses and avoiding global synchronization. The queue never fills
completely, so delay stays lower and link utilization stays higher.

RED is better for TCP performance because it provides gradual, spread-out congestion
signals rather than a sudden cliff that hits all flows at once.

**(e) Control plane crash — effect on forwarding**

**Traffic continues to be forwarded normally.** The data plane operates independently
of the control plane. It consults the last-installed FIB, which remains in TCAM/memory
unchanged. The FIB is not cleared when the routing protocol crashes.

This is a key benefit of the data/control plane separation: **failure isolation**. The
routing processor can restart and recompute routes without interrupting the forwarding
of packets already in flight. Only if routes change during the 30-second outage (e.g.,
a link goes down) would traffic be misrouted, because the FIB cannot be updated
until the control plane recovers.

---

## Problem 5 - SDN and the End-to-End Argument

**(a)** State the end-to-end argument in your own words. Use it to explain why
IP was designed as best-effort rather than building reliability into every router.

**(b)** X.25 and ATM both tried to build reliability and QoS into the network.
Both lost to IP. Give two concrete reasons from the lecture why IP won.

**(c)** What is SDN? How does it differ from traditional distributed routing?

**(d)** Google's B4 network uses SDN to achieve ~100% WAN link utilization vs.
30-40% with OSPF. Explain why central control enables higher utilization.

**(e)** SDN is widely deployed inside cloud data centers but does not run the open
internet. Why not? What fundamental constraint prevents an internet-wide SDN
controller?

---

### Solution to Problem 5

**(a) End-to-end argument**

If a function requires application-specific knowledge to implement correctly, it must
live at the endpoints — not inside the network. Even if the network provided
reliable delivery hop-by-hop, the application would *still* need to verify that the
data arrived at the right process, was interpreted correctly, and the session is still
valid. The network cannot know what "received correctly" means for an arbitrary
application.

Therefore: building reliability into every router adds cost and complexity but does
not eliminate the endpoint check. IP remains best-effort; reliability is implemented
once, in TCP, at the endpoints — where it has to be anyway.

**(b) Two reasons IP won over X.25/ATM**

1. **No per-connection state:** IP routers are stateless — they hold forwarding
   table entries, not per-flow state. X.25 and ATM required every switch to maintain
   state for every active connection, which is expensive and fragile at scale. IP scales
   to billions of hosts because adding a new host doesn't require updating state in
   every router between it and the rest of the internet.

2. **Commodity hardware and Moore's Law:** IP's simplicity meant it could be
   implemented cheaply on any new link technology. As hardware costs fell, IP
   routers became cheap enough to deploy everywhere. ATM's complex QoS
   machinery required expensive specialized hardware that couldn't ride the same
   cost curve. The IETF also deployed working systems faster than ITU/ISO
   standardized ATM.

**(c) SDN vs. traditional routing**

**Traditional routing:** control plane is distributed — every router independently
runs OSPF/BGP, exchanges advertisements, and computes its own forwarding tables
with only a local view of the network.

**SDN:** control plane is logically centralized in a controller with a global view of the
entire network. Data-plane devices (switches) are simple forwarding engines that
match packets against rules pushed down by the controller (via OpenFlow or similar).
No routing protocol runs in the switch itself.

The separation that enables SDN is the data/control plane split: once those are
cleanly separated, the control plane can run anywhere — including a server farm
with full topology visibility.

**(d) Why central control enables higher utilization**

OSPF computes shortest paths — it does not consider current link load or make
traffic-engineering decisions. If the shortest path between two data centers is
congested while a longer path is idle, OSPF keeps sending traffic down the congested
path. Link utilization is uneven; the network is dimensioned for peak, not average load.

An SDN controller with global topology and traffic-demand visibility can compute
traffic-engineered paths that spread load across all available links, rebalancing in
real time as demands shift. Google B4 achieves ~100% utilization because the
controller actively fills every link to its capacity, whereas OSPF's distributed,
shortest-path-only model leaves many links underloaded.

**(e) Why no internet-wide SDN controller**

The internet is owned and operated by **thousands of independent organizations**
(ISPs, enterprises, universities, governments). No single entity can be given control
over all their routing — it is a political, legal, and trust problem as much as a
technical one. Each organization must maintain sovereignty over its own network.

SDN works inside a single organization's infrastructure (a data center, a campus,
an enterprise WAN) precisely because one entity controls all the switches and
can trust a central controller. Across organizational boundaries, BGP's distributed,
policy-based model — where each AS makes its own routing decisions — is the only
architecture that works at internet scale with independent operators.

---

*Generated with assistance from Claude (Anthropic). Covers all EC 441 Lecture 13
learning objectives: network layer responsibilities, data vs. control plane,
forwarding vs. routing, router architecture, longest-prefix match, TTL/traceroute,
and SDN.*