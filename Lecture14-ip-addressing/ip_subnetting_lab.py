#!/usr/bin/env python3
"""
EC 441 — Lecture 14 Lab: IP Addressing & Subnetting with Python ipaddress
==========================================================================
Lab objectives:
  1. Use the ipaddress module to perform subnet arithmetic
  2. Implement a VLSM allocator that fits variable-sized subnets into a block
  3. Simulate an IP-to-subnet lookup (like a router's forwarding table check)
  4. Demonstrate route aggregation (supernetting)
  5. Identify special-purpose address ranges

Usage:
    python3 ip_subnetting_lab.py
"""

import ipaddress


# ─────────────────────────────────────────────────────────────
# SECTION 1: Basic Subnet Arithmetic
# ─────────────────────────────────────────────────────────────

def section1_subnet_arithmetic():
    print("=" * 60)
    print("SECTION 1: Basic Subnet Arithmetic")
    print("=" * 60)

    prefixes = [
        "192.168.10.0/24",
        "10.4.0.0/21",
        "172.16.32.0/20",
        "203.0.113.0/27",
    ]

    for cidr in prefixes:
        net = ipaddress.IPv4Network(cidr)
        usable = list(net.hosts())
        print(f"\nNetwork : {net}")
        print(f"  Mask         : {net.netmask}")
        print(f"  Network addr : {net.network_address}")
        print(f"  Broadcast    : {net.broadcast_address}")
        print(f"  Total addrs  : {net.num_addresses}")
        print(f"  Usable hosts : {len(usable)}")
        print(f"  First host   : {usable[0]}")
        print(f"  Last host    : {usable[-1]}")


# ─────────────────────────────────────────────────────────────
# SECTION 2: Equal Subnetting (borrowing k bits)
# ─────────────────────────────────────────────────────────────

def section2_equal_subnets():
    print("\n" + "=" * 60)
    print("SECTION 2: Equal Subnetting — dividing 192.168.50.0/24 into 8 /27s")
    print("=" * 60)

    net = ipaddress.IPv4Network("192.168.50.0/24")
    subnets = list(net.subnets(prefixlen_diff=3))  # borrow 3 bits → /27

    print(f"\nParent block : {net}  ({net.num_addresses} addresses)")
    print(f"Subnets      : {len(subnets)} × /{subnets[0].prefixlen}")
    print(f"Hosts/subnet : {subnets[0].num_addresses - 2} usable\n")

    labels = ["Engineering-A", "Engineering-B", "Sales", "HR",
              "IT", "Guest-WiFi", "IoT", "Management"]

    for label, subnet in zip(labels, subnets):
        hosts = list(subnet.hosts())
        print(f"  {label:<15} {str(subnet):<22} "
              f"hosts {hosts[0]} – {hosts[-1]}")

    # Verify full coverage
    total = sum(s.num_addresses for s in subnets)
    print(f"\nTotal addresses accounted for: {total} / {net.num_addresses} ✓")


# ─────────────────────────────────────────────────────────────
# SECTION 3: VLSM Allocator
# ─────────────────────────────────────────────────────────────

def next_power_of_two(n):
    """Return smallest power of 2 >= n."""
    p = 1
    while p < n:
        p <<= 1
    return p


def vlsm_allocate(parent_cidr: str, requirements: list[tuple[str, int]]) -> list[dict]:
    """
    Allocate variable-length subnets from parent_cidr.

    requirements: list of (label, host_count) sorted largest-first (caller's responsibility)
    Returns list of dicts with allocation details.
    """
    parent = ipaddress.IPv4Network(parent_cidr)
    current_start = int(parent.network_address)
    parent_end = int(parent.broadcast_address)
    allocations = []

    for label, hosts_needed in requirements:
        # Minimum block size: hosts + network + broadcast
        block_size = next_power_of_two(hosts_needed + 2)
        prefix_len = 32 - block_size.bit_length() + 1

        # Align current_start to block boundary
        if current_start % block_size != 0:
            current_start += block_size - (current_start % block_size)

        subnet_end = current_start + block_size - 1
        if subnet_end > parent_end:
            raise ValueError(f"Not enough space for '{label}' ({hosts_needed} hosts)")

        subnet = ipaddress.IPv4Network(f"{ipaddress.IPv4Address(current_start)}/{prefix_len}")
        hosts = list(subnet.hosts())
        allocations.append({
            "label": label,
            "hosts_needed": hosts_needed,
            "subnet": subnet,
            "usable": len(hosts),
            "first_host": hosts[0],
            "last_host": hosts[-1],
            "broadcast": subnet.broadcast_address,
        })
        current_start += block_size

    return allocations


def section3_vlsm():
    print("\n" + "=" * 60)
    print("SECTION 3: VLSM Allocator — 10.20.0.0/22")
    print("=" * 60)

    # Requirements sorted largest-first (best practice for VLSM)
    requirements = [
        ("Engineering",     300),
        ("Marketing",       100),
        ("HR",               50),
        ("P2P Link",          2),
    ]

    allocations = vlsm_allocate("10.20.0.0/22", requirements)

    parent = ipaddress.IPv4Network("10.20.0.0/22")
    print(f"\nParent block: {parent}  ({parent.num_addresses} addresses)\n")
    print(f"  {'Segment':<12} {'Needed':>7}  {'Subnet':<22} {'Usable':>7}  "
          f"{'First Host':<17} {'Last Host':<17} {'Broadcast'}")
    print("  " + "-" * 105)

    total_used = 0
    for a in allocations:
        print(f"  {a['label']:<12} {a['hosts_needed']:>7}  {str(a['subnet']):<22} "
              f"{a['usable']:>7}  {str(a['first_host']):<17} {str(a['last_host']):<17} "
              f"{a['broadcast']}")
        total_used += a['subnet'].num_addresses

    print(f"\n  Total used   : {total_used}")
    print(f"  Total avail  : {parent.num_addresses}")
    print(f"  Remaining    : {parent.num_addresses - total_used} addresses free for future use")


# ─────────────────────────────────────────────────────────────
# SECTION 4: Subnet Membership Lookup (Router Simulation)
# ─────────────────────────────────────────────────────────────

def section4_lookup():
    print("\n" + "=" * 60)
    print("SECTION 4: Subnet Membership Lookup")
    print("=" * 60)

    # Simulate the four /26 subnets from the lecture example
    subnets = {
        "Engineering": ipaddress.IPv4Network("192.168.10.0/26"),
        "Sales":       ipaddress.IPv4Network("192.168.10.64/26"),
        "HR":          ipaddress.IPv4Network("192.168.10.128/26"),
        "IT":          ipaddress.IPv4Network("192.168.10.192/26"),
    }

    test_hosts = [
        "192.168.10.1",
        "192.168.10.75",
        "192.168.10.100",
        "192.168.10.130",
        "192.168.10.200",
        "192.168.10.255",
    ]

    print("\nSubnet table:")
    for name, net in subnets.items():
        print(f"  {name:<12} → {net}")

    print("\nLookup results:")
    for addr_str in test_hosts:
        addr = ipaddress.IPv4Address(addr_str)
        found = None
        for name, net in subnets.items():
            if addr in net:
                found = name
                break
        if found:
            print(f"  {addr_str:<20} → {found}")
        else:
            print(f"  {addr_str:<20} → No match (network/broadcast addr)")

    # Demonstrate same-subnet check
    print("\nSame-subnet checks (/26 mask):")
    pairs = [
        ("192.168.10.75",  "192.168.10.100"),
        ("192.168.10.75",  "192.168.10.130"),
        ("192.168.10.65",  "192.168.10.126"),
    ]
    for a, b in pairs:
        net_a = ipaddress.IPv4Interface(f"{a}/26").network
        net_b = ipaddress.IPv4Interface(f"{b}/26").network
        same = net_a == net_b
        verdict = "same subnet (no router needed)" if same else "different subnets (router required)"
        print(f"  {a} vs {b} → {verdict}")


# ─────────────────────────────────────────────────────────────
# SECTION 5: Route Aggregation (Supernetting)
# ─────────────────────────────────────────────────────────────

def section5_aggregation():
    print("\n" + "=" * 60)
    print("SECTION 5: Route Aggregation (Supernetting)")
    print("=" * 60)

    customer_blocks = [
        "192.168.0.0/24",
        "192.168.1.0/24",
        "192.168.2.0/24",
        "192.168.3.0/24",
    ]

    networks = [ipaddress.IPv4Network(b) for b in customer_blocks]

    print(f"\nISP has {len(networks)} customer /24 blocks:")
    for net in networks:
        print(f"  {net}")

    # collapse() finds the minimal set of prefixes covering all input networks
    aggregated = list(ipaddress.collapse_addresses(networks))
    print(f"\nAfter collapse_addresses():")
    for agg in aggregated:
        print(f"  {agg}  ← single entry advertised to the internet")

    print(f"\nRouting table savings: {len(networks)} entries → {len(aggregated)} entry")
    print("(Internal ISP routers still hold the /24 entries for each customer)")

    # Demonstrate what happens with a non-contiguous block (can't fully aggregate)
    print("\nNon-contiguous example (3 out of 4 /24s — cannot fully aggregate):")
    partial = [
        "192.168.0.0/24",
        "192.168.1.0/24",
        "192.168.3.0/24",   # gap: .2.0/24 is missing
    ]
    partial_nets = [ipaddress.IPv4Network(b) for b in partial]
    partial_agg = list(ipaddress.collapse_addresses(partial_nets))
    print(f"  Input: {[str(n) for n in partial_nets]}")
    print(f"  After collapse: {[str(n) for n in partial_agg]}")
    print("  → Gap prevents full aggregation; two entries required")


# ─────────────────────────────────────────────────────────────
# SECTION 6: Special-Purpose Address Classifier
# ─────────────────────────────────────────────────────────────

SPECIAL_RANGES = [
    (ipaddress.IPv4Network("10.0.0.0/8"),         "RFC 1918 private (large enterprise/cloud VPCs)"),
    (ipaddress.IPv4Network("172.16.0.0/12"),       "RFC 1918 private (medium enterprise)"),
    (ipaddress.IPv4Network("192.168.0.0/16"),      "RFC 1918 private (home/small office)"),
    (ipaddress.IPv4Network("127.0.0.0/8"),         "Loopback (localhost / never leaves host)"),
    (ipaddress.IPv4Network("169.254.0.0/16"),      "Link-local APIPA (DHCP failed)"),
    (ipaddress.IPv4Network("224.0.0.0/4"),         "Multicast (Class D)"),
    (ipaddress.IPv4Network("100.64.0.0/10"),       "Carrier-Grade NAT / RFC 6598 (ISP internal)"),
    (ipaddress.IPv4Network("0.0.0.0/8"),           "This-host or unspecified"),
    (ipaddress.IPv4Network("240.0.0.0/4"),         "Reserved (Class E)"),
]


def classify_address(addr_str: str) -> str:
    addr = ipaddress.IPv4Address(addr_str)
    if addr == ipaddress.IPv4Address("255.255.255.255"):
        return "Limited broadcast"
    for net, description in SPECIAL_RANGES:
        if addr in net:
            return description
    return "Public / globally routable"


def section6_classify():
    print("\n" + "=" * 60)
    print("SECTION 6: Special-Purpose Address Classifier")
    print("=" * 60)

    test_addresses = [
        "192.168.1.42",
        "10.0.5.1",
        "172.17.0.5",       # Docker default bridge
        "127.0.0.1",
        "169.254.23.45",
        "100.78.14.3",
        "8.8.8.8",
        "224.0.0.5",        # OSPF Hello
        "255.255.255.255",
        "128.197.10.42",    # BU address
        "203.0.113.1",      # TEST-NET (documentation range)
    ]

    print(f"\n  {'Address':<20} Classification")
    print("  " + "-" * 70)
    for addr in test_addresses:
        print(f"  {addr:<20} {classify_address(addr)}")

    # Show Python's built-in flags
    print("\n  Python ipaddress built-in flags:")
    flag_addrs = ["192.168.1.1", "10.0.0.1", "8.8.8.8", "127.0.0.1", "169.254.1.1", "224.0.0.1"]
    for addr_str in flag_addrs:
        addr = ipaddress.IPv4Address(addr_str)
        flags = []
        if addr.is_private:   flags.append("is_private")
        if addr.is_loopback:  flags.append("is_loopback")
        if addr.is_link_local: flags.append("is_link_local")
        if addr.is_multicast: flags.append("is_multicast")
        if addr.is_global:    flags.append("is_global")
        print(f"  {addr_str:<18} {', '.join(flags) if flags else '(no special flags)'}")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    section1_subnet_arithmetic()
    section2_equal_subnets()
    section3_vlsm()
    section4_lookup()
    section5_aggregation()
    section6_classify()

    print("\n" + "=" * 60)
    print("Lab complete.")
    print("=" * 60)