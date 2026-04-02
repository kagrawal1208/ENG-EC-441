#!/usr/bin/env python3
"""
EC 441 — Lecture 17 Lab: IPv4, IPv6, NAT, ICMP
================================================
Lab objectives:
  1. Parse and display every IPv4 header field with explanations
  2. Compute IP fragmentation (fragments, offsets, MF flags)
  3. Simulate a NAT translation table with PAT
  4. Expand/compress IPv6 addresses and classify address types
  5. Simulate the DHCP Discover/Offer/Request/Ack handshake
  6. Demonstrate ICMP type/code lookup

Usage:
    python3 ipv4_ipv6_nat_lab.py
"""

import ipaddress
import struct
import socket


# ─────────────────────────────────────────────────────────────
# SECTION 1: IPv4 Header Dissector
# ─────────────────────────────────────────────────────────────

PROTOCOL_NAMES = {1: "ICMP", 6: "TCP", 17: "UDP", 89: "OSPF"}

DSCP_NAMES = {
    0:  "Best Effort (default) — web browsing",
    10: "AF11 — Assured Forwarding",
    18: "AF21 — Assured Forwarding",
    26: "AF31 — Assured Forwarding",
    34: "AF41 — Assured Forwarding",
    46: "Expedited Forwarding (EF) — VoIP, highest priority",
    48: "CS6 — Network control",
    56: "CS7 — Network control (reserved)",
}


def dissect_ipv4_header(fields: dict):
    """Print a human-readable breakdown of an IPv4 header."""
    print(f"\n  IPv4 Header Dissection")
    print(f"  {'─'*52}")

    ihl     = fields.get("ihl", 5)
    dscp    = fields.get("dscp", 0)
    total   = fields.get("total_length", 1500)
    ttl     = fields.get("ttl", 64)
    proto   = fields.get("protocol", 6)
    src     = fields.get("src", "192.168.1.1")
    dst     = fields.get("dst", "8.8.8.8")
    df      = fields.get("df", 0)
    mf      = fields.get("mf", 0)
    offset  = fields.get("fragment_offset", 0)

    header_bytes = ihl * 4
    payload_bytes = total - header_bytes

    print(f"  Version         : 4")
    print(f"  IHL             : {ihl} ({header_bytes} bytes{' — standard, no options' if ihl == 5 else ' — options present'})")
    print(f"  DSCP            : {dscp} ({bin(dscp)[2:].zfill(6)}) → {DSCP_NAMES.get(dscp, 'Unknown')}")
    print(f"  Total Length    : {total} bytes")
    print(f"  Header size     : {header_bytes} bytes")
    print(f"  Payload size    : {payload_bytes} bytes")
    print(f"  DF flag         : {df} ({'Don\'t Fragment — PMTUD active' if df else 'May fragment'})")
    print(f"  MF flag         : {mf} ({'More fragments follow' if mf else 'Last (or only) fragment'})")
    print(f"  Fragment Offset : {offset} × 8 = {offset * 8} bytes into original payload")
    print(f"  TTL             : {ttl} (packet has traversed ~{64 - ttl if ttl <= 64 else 128 - ttl} hops, assuming default TTL)")
    print(f"  Protocol        : {proto} → {PROTOCOL_NAMES.get(proto, f'Unknown ({proto})')}")
    print(f"  Source          : {src}")
    print(f"  Destination     : {dst}")

    # Classify src and dst
    for label, addr_str in [("Source", src), ("Destination", dst)]:
        addr = ipaddress.IPv4Address(addr_str)
        kind = ("RFC 1918 private" if addr.is_private else
                "Loopback" if addr.is_loopback else
                "Link-local" if addr.is_link_local else
                "Multicast" if addr.is_multicast else
                "Public/global")
        print(f"  {label:<14}: {addr_str} ({kind})")


def section1_header_dissect():
    print("=" * 60)
    print("SECTION 1: IPv4 Header Dissector")
    print("=" * 60)

    examples = [
        {
            "label": "Normal TCP HTTPS packet (no fragmentation)",
            "ihl": 5, "dscp": 0, "total_length": 1500, "ttl": 63, "protocol": 6,
            "df": 1, "mf": 0, "fragment_offset": 0,
            "src": "192.168.1.100", "dst": "93.184.216.34",
        },
        {
            "label": "VoIP packet (EF/Expedited Forwarding)",
            "ihl": 5, "dscp": 46, "total_length": 200, "ttl": 56, "protocol": 17,
            "df": 1, "mf": 0, "fragment_offset": 0,
            "src": "10.0.1.5", "dst": "172.16.5.10",
        },
        {
            "label": "Second fragment of a fragmented datagram",
            "ihl": 5, "dscp": 0, "total_length": 1500, "ttl": 60, "protocol": 6,
            "df": 0, "mf": 1, "fragment_offset": 185,
            "src": "10.0.0.1", "dst": "8.8.8.8",
        },
    ]

    for ex in examples:
        print(f"\n  ── Example: {ex['label']}")
        dissect_ipv4_header(ex)


# ─────────────────────────────────────────────────────────────
# SECTION 2: IP Fragmentation Calculator
# ─────────────────────────────────────────────────────────────

def fragment_datagram(total_length: int, mtu: int, ip_header: int = 20):
    """
    Fragment a datagram of total_length bytes into fragments fitting mtu.
    Returns list of fragment dicts.
    """
    payload_total = total_length - ip_header
    max_payload_per_frag = ((mtu - ip_header) // 8) * 8   # must be multiple of 8

    fragments = []
    offset = 0   # in bytes
    remaining = payload_total

    while remaining > 0:
        payload_size = min(max_payload_per_frag, remaining)
        is_last = (payload_size == remaining)
        fragments.append({
            "total_length": payload_size + ip_header,
            "mf_flag": 0 if is_last else 1,
            "offset_8units": offset // 8,
            "payload_start": offset,
            "payload_end": offset + payload_size - 1,
            "payload_size": payload_size,
        })
        offset += payload_size
        remaining -= payload_size

    return fragments


def section2_fragmentation():
    print("\n" + "=" * 60)
    print("SECTION 2: IP Fragmentation Calculator")
    print("=" * 60)

    scenarios = [
        ("4,000-byte datagram over Ethernet (MTU=1500)", 4000, 1500),
        ("3,980-byte datagram over Ethernet (MTU=1500)", 3980, 1500),
        ("3,000-byte datagram over PPPoE (MTU=1492)",    3000, 1492),
        ("1,000-byte datagram (no fragmentation needed)", 1000, 1500),
    ]

    for label, total, mtu in scenarios:
        frags = fragment_datagram(total, mtu)
        print(f"\n  {label}")
        print(f"  Datagram: {total} bytes | MTU: {mtu} bytes | → {len(frags)} fragment(s)")
        print(f"  {'Frag':<5} {'Tot Len':<9} {'MF':<4} {'Offset':<8} {'Payload Bytes'}")
        print("  " + "-" * 45)
        for i, f in enumerate(frags):
            print(f"  {i+1:<5} {f['total_length']:<9} {f['mf_flag']:<4} "
                  f"{f['offset_8units']:<8} {f['payload_start']} – {f['payload_end']}")

        total_payload = sum(f["payload_size"] for f in frags)
        total_overhead = sum(20 for _ in frags)
        print(f"  Total payload reassembled: {total_payload} bytes")
        print(f"  Total header overhead:     {total_overhead} bytes ({total_overhead/(total_payload+total_overhead)*100:.1f}% overhead)")


# ─────────────────────────────────────────────────────────────
# SECTION 3: NAT Translation Table Simulator
# ─────────────────────────────────────────────────────────────

class NATRouter:
    def __init__(self, public_ip: str, port_start: int = 40000):
        self.public_ip = public_ip
        self.next_port = port_start
        # WAN side → LAN side
        self.table = {}   # (public_ip, wan_port) → (lan_ip, lan_port, dst_ip, dst_port)

    def outbound(self, lan_ip: str, lan_port: int, dst_ip: str, dst_port: int) -> tuple:
        """Record an outbound connection, return (wan_ip, wan_port)."""
        wan_port = self.next_port
        self.next_port += 1
        self.table[(self.public_ip, wan_port)] = (lan_ip, lan_port, dst_ip, dst_port)
        return self.public_ip, wan_port

    def inbound(self, dst_ip: str, dst_port: int) -> tuple | None:
        """Look up a return packet. Returns (lan_ip, lan_port) or None."""
        key = (dst_ip, dst_port)
        entry = self.table.get(key)
        if entry:
            return entry[0], entry[1]
        return None

    def print_table(self):
        print(f"\n  {'WAN Side':<28} {'LAN Side':<22} {'Destination'}")
        print("  " + "-" * 65)
        for (wan_ip, wan_port), (lan_ip, lan_port, dst_ip, dst_port) in self.table.items():
            print(f"  {wan_ip}:{wan_port:<6}  →  {lan_ip}:{lan_port:<8}  {dst_ip}:{dst_port}")


def section3_nat():
    print("\n" + "=" * 60)
    print("SECTION 3: NAT Translation Table (PAT)")
    print("=" * 60)

    router = NATRouter("203.0.113.5")

    # Three hosts initiate connections
    flows = [
        ("10.0.0.2", 50001, "93.184.216.34", 443, "Host A — HTTPS"),
        ("10.0.0.3", 50001, "93.184.216.34", 443, "Host B — HTTPS (same src port as A!)"),
        ("10.0.0.4", 50002, "8.8.8.8",       53,  "Host C — DNS"),
    ]

    print("\n  Outbound connections (LAN → WAN):")
    for lan_ip, lan_port, dst_ip, dst_port, label in flows:
        wan_ip, wan_port = router.outbound(lan_ip, lan_port, dst_ip, dst_port)
        print(f"\n  {label}")
        print(f"    Original:  {lan_ip}:{lan_port} → {dst_ip}:{dst_port}")
        print(f"    Rewritten: {wan_ip}:{wan_port} → {dst_ip}:{dst_port}")

    print("\n  NAT Translation Table:")
    router.print_table()

    # Simulate return packet
    print("\n  Inbound return packet lookup:")
    returns = [
        ("203.0.113.5", 40001, "Reply to Host A"),
        ("203.0.113.5", 40002, "Reply to Host B"),
        ("203.0.113.5", 40003, "Reply to Host C"),
        ("203.0.113.5", 40099, "Unknown WAN port — no entry"),
    ]
    for wan_ip, wan_port, label in returns:
        result = router.inbound(wan_ip, wan_port)
        if result:
            lan_ip, lan_port = result
            print(f"  {label}: Dst {wan_ip}:{wan_port} → forward to {lan_ip}:{lan_port}")
        else:
            print(f"  {label}: Dst {wan_ip}:{wan_port} → DROPPED (no mapping)")

    print("""
  Key observations:
  - A and B both used source port 50001, but NAT assigned different WAN ports (40001/40002)
  - PAT: one public IP supports ~65,000 simultaneous connections via port differentiation
  - Inbound connections without an existing entry are DROPPED (no mapping)
  - NAT modifies IP header (src address) + TCP/UDP header (src port) + recomputes checksums
    """)


# ─────────────────────────────────────────────────────────────
# SECTION 4: IPv6 Address Utilities
# ─────────────────────────────────────────────────────────────

def expand_ipv6(addr: str) -> str:
    return str(ipaddress.IPv6Address(addr).exploded)


def compress_ipv6(addr: str) -> str:
    return str(ipaddress.IPv6Address(addr).compressed)


def classify_ipv6(addr_str: str) -> str:
    addr = ipaddress.IPv6Address(addr_str)
    if addr.is_loopback:          return "Loopback (::1)"
    if addr.is_link_local:        return "Link-local (fe80::/10) — auto-configured"
    if addr.is_multicast:         return "Multicast (ff00::/8)"
    if addr.is_private:           return "Unique Local (fc00::/7) — like RFC 1918"
    if addr.is_global:            return "Global Unicast (2000::/3) — publicly routable"
    return "Unknown"


def section4_ipv6():
    print("=" * 60)
    print("SECTION 4: IPv6 Address Notation and Classification")
    print("=" * 60)

    # Expand compressed addresses
    print("\n  4a. Expanding compressed addresses:")
    compressed = [
        "::1",
        "fe80::a1b2:3c4d",
        "2001:db8::1:0:0:1",
        "2001:db8:cafe::42",
        "ff02::1",
    ]
    for addr in compressed:
        print(f"  {addr:<30} → {expand_ipv6(addr)}")

    # Compress full addresses
    print("\n  4b. Compressing full addresses:")
    full = [
        "2001:0db8:0000:0000:0001:0000:0000:0001",
        "fe80:0000:0000:0000:0000:0000:0000:0001",
        "0000:0000:0000:0000:0000:0000:0000:0001",
        "ff02:0000:0000:0000:0000:0000:0000:0001",
    ]
    for addr in full:
        print(f"  {addr}  →  {compress_ipv6(addr)}")

    # Classify addresses
    print("\n  4c. Address classification:")
    test_addrs = [
        "::1",
        "fe80::a1b2:3c4d",
        "2001:db8::1",
        "fc00::1",
        "ff02::1",
        "2607:f8b0:4006:80e::200e",   # Google
        "2001:4860:4860::8888",         # Google DNS
    ]
    print(f"  {'Address':<40} {'Type'}")
    print("  " + "-" * 70)
    for addr in test_addrs:
        print(f"  {addr:<40} {classify_ipv6(addr)}")

    # IPv6 vs IPv4 header comparison
    print("\n  4d. IPv4 vs IPv6 Header Comparison:")
    rows = [
        ("Address size",    "32 bits (4.3B)",              "128 bits (3.4 × 10³⁸)"),
        ("Header size",     "20–60 bytes (variable)",      "40 bytes (fixed)"),
        ("Header checksum", "Yes (recomputed every hop)",  "Removed (redundant)"),
        ("Fragmentation",   "Routers may fragment",        "Source only; DF always set"),
        ("Options",         "In base header (IHL varies)", "Extension headers"),
        ("TTL",             "Time to Live",                "Hop Limit (same semantics)"),
        ("Broadcast",       "Yes (255.255.255.255)",       "No — multicast only"),
        ("Auto-config",     "Requires DHCP",               "SLAAC (stateless)"),
    ]
    print(f"  {'Feature':<20} {'IPv4':<35} {'IPv6'}")
    print("  " + "-" * 80)
    for feature, v4, v6 in rows:
        print(f"  {feature:<20} {v4:<35} {v6}")


# ─────────────────────────────────────────────────────────────
# SECTION 5: DHCP Handshake Simulation
# ─────────────────────────────────────────────────────────────

def section5_dhcp():
    print("\n" + "=" * 60)
    print("SECTION 5: DHCP Handshake Simulation")
    print("=" * 60)

    print("""
  Scenario: New host with MAC aa:bb:cc:dd:ee:ff joins 192.168.1.0/24 network.
  DHCP server at 192.168.1.1 has pool: 192.168.1.100 – 192.168.1.200.
    """)

    messages = [
        {
            "step": 1,
            "name": "DISCOVER",
            "src_ip": "0.0.0.0",
            "dst_ip": "255.255.255.255",
            "src_port": 68,
            "dst_port": 67,
            "payload": "Client MAC=aa:bb:cc:dd:ee:ff, requested lease=3600s",
            "note": "No IP yet → src=0.0.0.0. Broadcast to find any DHCP server."
        },
        {
            "step": 2,
            "name": "OFFER",
            "src_ip": "192.168.1.1",
            "dst_ip": "255.255.255.255",
            "src_port": 67,
            "dst_port": 68,
            "payload": "Offered IP=192.168.1.105, mask=/24, gateway=192.168.1.1, DNS=8.8.8.8, lease=3600s",
            "note": "Server offers address from pool. Still broadcasts (client has no IP yet)."
        },
        {
            "step": 3,
            "name": "REQUEST",
            "src_ip": "0.0.0.0",
            "dst_ip": "255.255.255.255",
            "src_port": 68,
            "dst_port": 67,
            "payload": "Requested IP=192.168.1.105, Server ID=192.168.1.1",
            "note": "Client formally requests the offered address. Broadcast so other servers see it."
        },
        {
            "step": 4,
            "name": "ACK",
            "src_ip": "192.168.1.1",
            "dst_ip": "192.168.1.105",
            "src_port": 67,
            "dst_port": 68,
            "payload": "Confirmed: IP=192.168.1.105, mask=/24, gateway=192.168.1.1, DNS=8.8.8.8, lease=3600s",
            "note": "Server confirms. Client now has a fully configured IP stack."
        },
    ]

    for msg in messages:
        print(f"  Step {msg['step']}: DHCP {msg['name']}")
        print(f"    Src IP:Port   : {msg['src_ip']}:{msg['src_port']}")
        print(f"    Dst IP:Port   : {msg['dst_ip']}:{msg['dst_port']}")
        print(f"    Payload       : {msg['payload']}")
        print(f"    Note          : {msg['note']}")
        print()

    print("  After ACK, client configures:")
    print("    IP address : 192.168.1.105/24")
    print("    Gateway    : 192.168.1.1  (default route)")
    print("    DNS        : 8.8.8.8")
    print("    Lease      : 3600 seconds (renew attempt at T/2 = 1800s)")
    print()
    print("  Transport: UDP (can't use TCP — no IP yet for connection setup)")
    print("  DHCP relay agents forward broadcast across subnets as unicast to server")


# ─────────────────────────────────────────────────────────────
# SECTION 6: ICMP Type/Code Reference
# ─────────────────────────────────────────────────────────────

ICMP_TYPES = {
    (0,  0): ("Echo Reply",                   "Response to ping"),
    (3,  0): ("Dest Unreachable: Net",        "No route to network"),
    (3,  1): ("Dest Unreachable: Host",       "Can reach net, not host"),
    (3,  3): ("Dest Unreachable: Port",       "Host reached, port closed"),
    (3,  4): ("Frag Needed / DF Set",         "Packet too big → PMTUD signal"),
    (8,  0): ("Echo Request",                 "Ping — sent by source"),
    (11, 0): ("Time Exceeded: TTL",           "TTL decremented to 0 → traceroute"),
    (11, 1): ("Time Exceeded: Reassembly",    "Fragment reassembly timeout"),
}


def section6_icmp():
    print("=" * 60)
    print("SECTION 6: ICMP Type/Code Reference and Protocol Mechanics")
    print("=" * 60)

    print("\n  ICMP messages used in this course:")
    print(f"  {'Type':<5} {'Code':<5} {'Name':<35} {'Purpose'}")
    print("  " + "-" * 75)
    for (t, c), (name, purpose) in ICMP_TYPES.items():
        print(f"  {t:<5} {c:<5} {name:<35} {purpose}")

    print("\n  How ping works (ICMP protocol level):")
    print("  1. Host A sends ICMP Echo Request (Type 8, Code 0) to B")
    print("     → IP header: Protocol=1, Src=A, Dst=B")
    print("  2. Host B receives it, sends ICMP Echo Reply (Type 0, Code 0)")
    print("     → IP header: Protocol=1, Src=B, Dst=A")
    print("  3. A measures RTT from send to receive")
    print("  Note: ping does NOT use TCP or UDP — it uses raw ICMP directly over IP")

    print("\n  How traceroute works (TTL exploitation):")
    for ttl in range(1, 5):
        if ttl < 4:
            print(f"  TTL={ttl}: Packet reaches router R{ttl} → R{ttl} sends ICMP Time Exceeded (11,0) → A learns R{ttl}")
        else:
            print(f"  TTL={ttl}: Packet reaches destination → dest sends ICMP Port Unreachable (3,3) → done")

    print("\n  Fragmentation and ICMP:")
    print("  DF=1 + oversized packet → router sends ICMP Type 3 Code 4 (Frag Needed)")
    print("  Includes bottleneck MTU in ICMP body → source reduces size (PMTUD)")
    print("  Caution: firewalls blocking all ICMP break PMTUD → 'black hole' effect")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    section1_header_dissect()
    section2_fragmentation()
    section3_nat()
    section4_ipv6()
    section5_dhcp()
    section6_icmp()

    print("\n" + "=" * 60)
    print("Lab complete.")
    print("=" * 60)
    