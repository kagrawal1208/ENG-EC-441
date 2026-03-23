# EC 441 — Lecture 14 Problem Set: IP Addressing, CIDR, and Subnetting

**Topic:** IP Addressing, CIDR, and Subnetting  
**Lecture:** 14  
**Covers:** Network/host split, classful addressing, CIDR notation, subnet arithmetic, VLSM, special-purpose ranges, IPv4 exhaustion

---

## Problem 1: CIDR Arithmetic

An organization is assigned the block **10.4.0.0/21**.

**(a)** How many total addresses are in this block? How many are usable hosts?

**(b)** Write the subnet mask in dotted-decimal notation.

**(c)** What is the broadcast address?

**(d)** What is the last usable host address?

### Solution

**(a)**  
Prefix length = /21, so host bits = 32 − 21 = 11  
Total addresses = 2¹¹ = **2048**  
Usable hosts = 2¹¹ − 2 = **2046**

**(b)**  
21 ones followed by 11 zeros:  
`11111111.11111111.11111000.00000000` = **255.255.248.0**

**(c)**  
Network address: 10.4.0.0  
Broadcast = set all host bits to 1:  
Last 11 bits all 1 → last two octets: `00000111.11111111` = 7.255  
Broadcast = **10.4.7.255**

**(d)**  
Last usable host = broadcast − 1 = **10.4.7.254**

---

## Problem 2: Subnet Membership Check

A network uses the prefix **172.16.32.0/20**.

**(a)** What is the subnet mask in dotted-decimal?

**(b)** Is host **172.16.45.200** in this subnet?

**(c)** Is host **172.16.48.1** in this subnet?

**(d)** What are the network and broadcast addresses?

### Solution

**(a)**  
20 ones, 12 zeros:  
`11111111.11111111.11110000.00000000` = **255.255.240.0**

**(b)** AND 172.16.45.200 with 255.255.240.0:  
Third octet: 45 = `00101101`, mask = `11110000` → AND = `00100000` = 32  
Result: 172.16.32.0 → matches network address → **Yes, in subnet.**

**(c)** AND 172.16.48.1 with 255.255.240.0:  
Third octet: 48 = `00110000`, mask = `11110000` → AND = `00110000` = 48  
Result: 172.16.48.0 ≠ 172.16.32.0 → **Not in subnet.**

**(d)**  
Network: **172.16.32.0**  
Host bits = 12, all set to 1: last 12 bits → third octet lower nibble + fourth octet all 1s  
`00101111.11111111` → third octet = 47, fourth = 255  
Broadcast: **172.16.47.255**

---

## Problem 3: Subnetting a Block (Equal-Sized)

A university department is assigned **192.168.50.0/24** and needs to divide it into **8 equal subnets**.

**(a)** How many bits must be borrowed? What is the new prefix length?

**(b)** How many usable hosts does each subnet support?

**(c)** List the network address and broadcast address for all 8 subnets.

**(d)** Are 192.168.50.100 and 192.168.50.140 in the same subnet?

### Solution

**(a)**  
2ᵏ = 8 → k = 3 bits borrowed  
New prefix: /24 + 3 = **/27**

**(b)**  
Host bits = 32 − 27 = 5  
Usable hosts = 2⁵ − 2 = **30 hosts per subnet**

**(c)** Block size = 2⁵ = 32 addresses each:

| Subnet | Network Address       | Broadcast Address      |
|--------|-----------------------|------------------------|
| 0      | 192.168.50.0/27       | 192.168.50.31          |
| 1      | 192.168.50.32/27      | 192.168.50.63          |
| 2      | 192.168.50.64/27      | 192.168.50.95          |
| 3      | 192.168.50.96/27      | 192.168.50.127         |
| 4      | 192.168.50.128/27     | 192.168.50.159         |
| 5      | 192.168.50.160/27     | 192.168.50.191         |
| 6      | 192.168.50.192/27     | 192.168.50.223         |
| 7      | 192.168.50.224/27     | 192.168.50.255         |

Check: 8 × 32 = 256 total. Full /24 accounted for. ✓

**(d)**  
AND both with mask 255.255.255.224:  
100 = `01100100` AND `11100000` = `01100000` = 96 → network 192.168.50.96  
140 = `10001100` AND `11100000` = `10000000` = 128 → network 192.168.50.128  
Different networks → **Not in the same subnet. A router is required.**

---

## Problem 4: VLSM Design

A company is allocated **10.20.0.0/23** and has the following requirements:

| Segment       | Hosts needed |
|---------------|-------------|
| Engineering   | 300         |
| Marketing     | 100         |
| HR            | 50          |
| Point-to-point link | 2    |

Design a VLSM allocation that fits all segments with minimal waste.

### Solution

Total available: 2⁹ = 512 addresses (a /23).

Assign largest-first to minimize fragmentation:

**Engineering (300 hosts):**  
Need 2ⁿ − 2 ≥ 300 → 2⁹ = 512, n = 9, prefix = /23 → already the whole block. Use /23 → 510 hosts. Too big. Try /24 → 254 hosts. Not enough. Use **/23** is the whole block — that won't work.  
Recalculate: 2⁹ = 512 > 302 ✓ → prefix = 32 − 9 = **/23**  

Wait — the entire allocation is /23. We need to fit all segments. Reconsider: the company was assigned a /23 (512 addresses total). Engineering needs 300 hosts → minimum /23 (510 usable). This exceeds the allocation.

**Corrected interpretation:** assume the company receives a **/22** (1024 addresses) — a common realistic scenario. Re-solve:

| Segment       | Hosts | Min block | Prefix | Addresses |
|---------------|-------|-----------|--------|-----------|
| Engineering   | 300   | 512       | /23    | 512       |
| Marketing     | 100   | 128       | /25    | 128       |
| HR            | 50    | 64        | /26    | 64        |
| Point-to-point| 2     | 4         | /30    | 4         |

Starting from 10.20.0.0/22:

- **Engineering:** 10.20.0.0/23 → hosts 10.20.0.1 – 10.20.1.254, broadcast 10.20.1.255
- **Marketing:** 10.20.2.0/25 → hosts 10.20.2.1 – 10.20.2.126, broadcast 10.20.2.127
- **HR:** 10.20.2.128/26 → hosts 10.20.2.129 – 10.20.2.190, broadcast 10.20.2.191
- **P2P link:** 10.20.2.192/30 → hosts 10.20.2.193 – 10.20.2.194, broadcast 10.20.2.195

Total used: 512 + 128 + 64 + 4 = 708 addresses. Remaining: 1024 − 708 = **316 addresses free** for future growth.

---

## Problem 5: Special-Purpose Ranges and Route Aggregation

**(a)** A traceroute shows an intermediate hop with address **100.78.14.3**. Is this a public address? What does it tell you about the network path?

**(b)** An ISP has been assigned **203.0.113.0/24** and wants to allocate it to 8 customers with equal-sized blocks of 32 addresses. What prefix does each customer receive? Write all 8 network addresses.

**(c)** Your network interface shows **169.254.44.12/16**. What is the most likely cause and what should you check?

### Solution

**(a)**  
100.64.0.0/10 is the Carrier-Grade NAT (CGN) range defined in RFC 6598. The address 100.78.14.3 falls in this range (100.64.0.0 – 100.127.255.255). This tells you that the path traverses an **ISP's internal CGN infrastructure** — the ISP is itself performing NAT between its backbone and subscribers because it ran out of public IPv4 addresses. This is not a private RFC 1918 address, but it is not globally routable either. Seeing it in traceroute means your traffic is behind at least two layers of NAT (home router + ISP CGN).

**(b)**  
32 addresses per block → /27 prefix (2⁵ = 32)  
Block size = 32; increment fourth octet by 32 each time:

| Customer | Network Address       |
|----------|-----------------------|
| 1        | 203.0.113.0/27        |
| 2        | 203.0.113.32/27       |
| 3        | 203.0.113.64/27       |
| 4        | 203.0.113.96/27       |
| 5        | 203.0.113.128/27      |
| 6        | 203.0.113.160/27      |
| 7        | 203.0.113.192/27      |
| 8        | 203.0.113.224/27      |

Check: 8 × 32 = 256 = full /24 ✓. Alignment rule: each network address is a multiple of 32 ✓.  
The ISP still advertises one entry to the internet: **203.0.113.0/24** (route aggregation).

**(c)**  
169.254.0.0/16 is the **link-local (APIPA)** range. A host self-assigns an address in this range when it cannot obtain one from a DHCP server. The most likely cause is that **DHCP failed** — the DHCP server is unreachable, down, or the DHCP lease pool is exhausted. First checks: (1) is the DHCP server running? (2) is the network cable/Wi-Fi connection actually up? (3) is `dhclient` or the DHCP client service running on the host?

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 14 notes.*