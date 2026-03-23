# Why IP Addressing Looks the Way It Does: A History of the Network/Host Split

**EC 441 — Lecture 14 Report**  
*Topic: The design decisions behind IPv4 addressing, CIDR, and why IPv4 is still alive in 2026*

---

## Introduction

When you run `ip addr show` on any Linux machine and see something like `192.168.1.42/24`, you're looking at the result of four decades of engineering decisions, political compromises, and a few near-misses that almost broke the internet. The `/24` isn't arbitrary — it encodes a design philosophy about how routing should scale. This report traces why IPv4 addressing looks the way it does, why classful addressing collapsed, and why CIDR — a system from 1993 — is still the foundation of how every packet on earth gets routed.

---

## The Core Problem: Scale

An IPv4 address is 32 bits. In 1981, when RFC 791 was written, 4.3 billion addresses seemed essentially infinite. The engineers who designed the system were solving a different problem: how do you make routing work when the network might someday have *thousands* of nodes?

Their insight was that you can't have every router know about every machine. A router in Tokyo doesn't need to know that `128.197.10.42` is a workstation in BU's Photonics building — it only needs to know that anything starting with `128.197` should head toward Boston. The network/host split was the implementation of this idea: divide the 32 bits into a **network portion** (used for routing decisions) and a **host portion** (relevant only once the packet reaches its destination network).

This is the postal code analogy made literal. A mail sorting facility in Japan doesn't need every street address in the US — it just needs ZIP codes. The network bits are the ZIP code; the host bits are the street address.

---

## Classful Addressing: Simple, Then Catastrophic

The original implementation of the network/host split was "classful" — the first few bits of an address implicitly told routers how long the network prefix was:

- **Class A** (first bit = 0): 8-bit network, 24-bit host → 16 million addresses per network
- **Class B** (first bits = 10): 16-bit network, 16-bit host → 65,000 addresses per network
- **Class C** (first bits = 110): 24-bit network, 8-bit host → 254 usable addresses per network

This was elegant for 1981. No configuration needed — the address itself told you the class. But by the early 1990s, the system had a structural flaw that couldn't be patched: **the granularity was completely wrong for the organizations that needed addresses**.

A university with 5,000 students couldn't fit into a Class C (254 hosts) but was orders of magnitude smaller than what a Class B (65,534 hosts) provided. The result: BU received a Class B allocation (128.197.0.0/16) and over 60,000 of those addresses sat permanently unused. Multiply this across thousands of universities, corporations, and government agencies, and by 1993 approximately half of the entire IPv4 address space was wasted inside organizations with oversized allocations.

The second crisis was the routing table. A company with eight Class C blocks had eight routing table entries — one per block. Classful rules didn't allow summarization below /24 for Class C addresses, so you couldn't collapse them into one entry even if all eight were adjacent. By 1993, the global BGP routing table was doubling roughly every year, and router hardware was struggling to keep up.

---

## CIDR: The 1993 Fix That Still Runs Everything

RFC 1519, published in September 1993, introduced Classless Inter-Domain Routing. It made three changes that sound simple but had enormous consequences:

**1. Any prefix length is valid.** You can have a /19, a /22, a /27 — the split point is no longer encoded in the address itself.

**2. Prefix length is written explicitly.** `192.168.1.0/24` tells you everything; you no longer have to look at the first bits to determine the class.

**3. Aggregation is a first-class operation.** If an ISP holds `192.168.0.0/22`, it can advertise that single entry to the entire internet, regardless of how it subdivides that block internally.

The third point is the one that saved the routing table. Instead of each of four customers needing a separate global route entry, the ISP advertises one `/22` and handles the `/24` entries internally. This is *hierarchical delegation* — the same principle that makes the postal system work, now applied rigorously to routing.

CIDR's impact was immediate. The routing table growth rate flattened. Organizations could receive right-sized allocations — a startup gets a /27 (30 hosts), a medium company gets a /22 (1,022 hosts), an ISP gets a /16. No more choosing between "254 hosts" and "65,534 hosts."

---

## The Alignment Rule: Why CIDR Networks Have Funny Starting Addresses

One consequence of CIDR that confuses students is why subnets always seem to start at multiples of their block size. A /26 starts at .0, .64, .128, or .192 — never at .10 or .37.

This isn't arbitrary — it's the **alignment rule**, and it falls directly out of how the bitwise AND operation works. When a router ANDs an address with a subnet mask to find the network address, the result is only well-defined if the network address itself has all host bits set to zero. An address like 192.168.10.10/26 would be "invalid" because 10 in binary is `00001010`, and the /26 mask zeroes out the bottom 6 bits, giving you `00000000` = .0 — which is a *different* network. The alignment rule ensures there's no ambiguity: a /26 with block size 64 must start at a multiple of 64.

This is also why VLSM (Variable-Length Subnet Masking) requires careful bookkeeping. When you're carving up a /24 into differently-sized subnets, you must place larger blocks first and ensure each new block starts at an aligned boundary. The Python `ipaddress` module handles this automatically, but understanding why helps you debug VLSM designs by hand.

---

## RFC 1918 and the NAT Miracle

By 2011, IANA had exhausted its free pool of IPv4 addresses. The last five /8 blocks (each containing 16 million addresses) were handed to the five Regional Internet Registries on February 3, 2011. APNIC exhausted two months later. The projections from the early 1990s had come true.

What the projections hadn't accounted for was NAT — Network Address Translation. RFC 1918 (1996) had designated three blocks as permanently "private": `10.0.0.0/8`, `172.16.0.0/12`, and `192.168.0.0/16`. These addresses would never be assigned to public internet hosts, so they could be reused freely by any organization. The tradeoff: they're not routable on the public internet. Traffic from a RFC 1918 address must pass through a NAT gateway that rewrites the source address to a public IP before the packet crosses the ISP boundary.

NAT extended IPv4 life by roughly 20 years beyond what would otherwise have been necessary. One public IP address, shared by hundreds or thousands of private hosts behind a home router or enterprise gateway, reduced public IP demand by orders of magnitude. Your laptop's address (almost certainly `192.168.x.x` or `10.x.x.x`) has never needed to be globally unique — only the WAN interface of your router does.

The cost of this convenience is visible every time you try to host a server at home, run peer-to-peer applications, or debug why two devices on different private networks can't communicate directly. NAT breaks the end-to-end model that IP was designed around. IPv6 exists partly to restore it.

---

## What /32 and /0 Tell You About Prefix Length Semantics

Two edge cases reveal the full meaning of the prefix length:

A **/32** prefix — a single host — seems strange: a "network" with exactly one address. But it's used constantly in routing: host routes, loopback addresses, BGP next-hop advertisements. It means "the network *is* the host." No host portion exists.

A **/0** prefix matches every possible address. It's the default route — `0.0.0.0/0` — the entry that says "if nothing more specific matches, send it here." This is how home routers work: your ISP assigns you a default route pointing toward their infrastructure, and that route catches all traffic not destined for your local LAN.

Together, /0 and /32 are the boundaries of the prefix length spectrum, and understanding them clarifies what the prefix length actually means: **the number of bits that must match for this entry to apply.** Zero bits must match for a /0 (everything matches); all 32 must match for a /32 (only that exact address matches). Longest-prefix match selects the most specific applicable entry — /32 beats /30 beats /24 beats /0.

---

## IPv6: The Long-Term Answer to a Problem CIDR Delayed

IPv6 allocates 128 bits — 2¹²⁸ addresses, approximately 3.4 × 10³⁸. The design retained everything useful about CIDR (prefix notation, hierarchical allocation, longest-prefix match) while solving the fundamental scarcity problem. There are enough addresses to assign trillions to every device ever manufactured, plus every device that will be manufactured over the coming centuries.

Yet as of 2026, IPv4 remains dominant for most enterprise traffic. The transition has been slow and uneven — driven primarily by mobile networks (where carrier IPv4 exhaustion made IPv6 economical) and major cloud providers. The reason IPv4 has persisted despite exhaustion in 2011 is exactly the system examined in this lecture: a secondary market for IPv4 addresses (now priced at approximately $30–50 per address), carrier-grade NAT at the ISP level, and a global installed base of devices, software, and operational knowledge so large that replacement happens incrementally, over decades.

CIDR bought the internet roughly 15 additional years of IPv4 runway. NAT bought another 20. IPv6 is the permanent fix — but the history of addressing shows that "permanent" in networking often means "durable enough to be somebody else's problem."

---

## Conclusion

The `192.168.1.42/24` on your laptop is the visible end of a design history stretching from 1981 to today. Classful addressing solved hierarchical routing but created catastrophic waste. CIDR solved the waste problem with a deceptively simple change — making the split point explicit — and introduced aggregation as a first-class operation. RFC 1918 and NAT extended IPv4 life by decades at the cost of end-to-end transparency. And IPv6, designed in the late 1990s, has been deploying ever since to address the problem that everyone knew was coming but no one could afford to solve all at once.

Understanding this history makes the technical details stick. The alignment rule exists because bitwise AND requires it. The /30 for point-to-point links exists because every additional bit of prefix doubles the waste. The default route is /0 because zero bits need to match for it to apply. None of this is arbitrary — it's all the same idea, applied consistently: **represent network identity in bits, aggregate by prefix, and route by the longest match.**

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 14 notes, RFC 791, RFC 1519, RFC 1918, and RFC 6598.*