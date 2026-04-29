#!/usr/bin/env python3
"""
EC 441 — Lecture 21 Lab: See the Network
Topics: CLI tool output parsing, pyshark pcap analysis, RTT estimation
        from live data, protocol hierarchy, DNS query extraction,
        TCP stream tracking, tcpdump filter reference

NOTE: Sections 1-4 parse *simulated* packet data so the lab runs
      without a live capture file. Section 5 shows the real pyshark
      code you would run against an actual .pcap file.
      To run against a real capture: replace SIMULATED_PACKETS with
      pyshark.FileCapture('your_capture.pcap', ...)
"""

import math
import random
import collections
import time

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: CLI Tool Output Reference and Field Mapping
# ─────────────────────────────────────────────────────────────────────────────

def section1_cli_reference():
    print("=" * 65)
    print("SECTION 1: CLI Tool → Protocol Concept Mapping")
    print("=" * 65)

    tool_map = [
        ("ping",       "ICMP Echo Req/Reply",    "L17 (ICMP), L19 (RTT)"),
        ("traceroute", "TTL decrement + ICMP TE", "L13 (fwd), L17 (ICMP TTL)"),
        ("ip addr",    "Interface IP + prefix",   "L14 (addressing)"),
        ("ip route",   "Forwarding table",         "L13 (routing)"),
        ("ip neigh",   "ARP cache (IP→MAC)",       "L08 (ARP)"),
        ("ss -t",      "TCP socket states",        "L19 (connections)"),
        ("ss -tipm",   "cwnd, ssthresh, rtt/rttvar","L19-L20 (CC internals)"),
        ("dig",        "DNS queries + TTLs",       "L18 (UDP), L23 (DNS)"),
        ("tcpdump",    "Raw packet capture",       "All layers"),
        ("wireshark",  "GUI protocol inspection",  "All layers"),
        ("pyshark",    "Programmatic pcap",        "All layers"),
    ]

    print(f"\n  {'Tool':<14} {'What it shows':<30} Concept (lecture)")
    print("  " + "-" * 70)
    for tool, what, concept in tool_map:
        print(f"  {tool:<14} {what:<30} {concept}")

    print("\n  Key ss -tipm fields:")
    ss_fields = [
        ("cwnd:N",        "Congestion window in MSS units (L20)"),
        ("ssthresh:N",    "Slow-start threshold; 2^31-1 = never had loss (L20)"),
        ("rtt:X/Y",       "SRTT ms / RTTVAR ms — Jacobson EWMA outputs (L19)"),
        ("rto:N",         "Retransmission timeout ms; floor=200ms per RFC (L19)"),
        ("retrans:N/M",   "In-flight retransmits / total retransmits (L19)"),
        ("app_limited:1", "App not writing fast enough; cwnd not the bottleneck"),
        ("cubic",         "Congestion control algorithm (CUBIC = Linux default)"),
        ("wscale:N,M",    "Window scale factors for sender/receiver (L19, L20)"),
    ]
    for field, desc in ss_fields:
        print(f"    {field:<20} {desc}")

    print("\n  tcpdump filter expressions:")
    filters = [
        ("port 53",                         "DNS traffic"),
        ("host 8.8.8.8",                    "To/from specific IP"),
        ("tcp and port 80",                 "HTTP traffic"),
        ("not port 22",                     "Exclude SSH"),
        ("tcp[tcpflags] & tcp-syn != 0",    "Any TCP SYN"),
        ("tcp[tcpflags] = tcp-syn",         "SYN only (not SYN-ACK)"),
        ("icmp",                            "All ICMP"),
        ("net 192.168.0.0/16",              "Subnet traffic"),
        ("ip[8] < 5",                       "TTL < 5 (traceroute first hops)"),
    ]
    print(f"\n  {'Filter':<40} {'Matches'}")
    print("  " + "-" * 65)
    for f, desc in filters:
        print(f"  {f:<40} {desc}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: TTL and Hop Count Analysis
# ─────────────────────────────────────────────────────────────────────────────

def section2_ttl_analysis():
    print("\n" + "=" * 65)
    print("SECTION 2: TTL Analysis — Estimating Hop Counts")
    print("=" * 65)

    print("\n  TTL starting values by OS:")
    os_ttl = [
        ("Linux / macOS",       64),
        ("Windows",             128),
        ("Cisco routers",       255),
        ("Solaris / AIX",       255),
    ]
    for os_name, ttl in os_ttl:
        print(f"    {os_name:<20} TTL={ttl}")

    print("\n  Observed TTL → hop count estimation:")
    samples = [
        (117, "Reply from 8.8.8.8"),
        (55,  "Reply from a university server"),
        (245, "Reply from a Cisco appliance"),
        (60,  "Reply from an unknown host"),
        (128, "Reply from a Windows server (direct neighbor)"),
    ]

    for obs_ttl, label in samples:
        candidates = []
        for initial in [64, 128, 255]:
            hops = initial - obs_ttl
            if 0 <= hops <= 30:
                candidates.append((initial, hops))
        if candidates:
            best = min(candidates, key=lambda x: x[1])
            init, hops = best
            print(f"    TTL={obs_ttl:3d}  ({label})")
            print(f"         Most likely: started at {init}, "
                  f"{hops} hop{'s' if hops != 1 else ''} away")
        else:
            print(f"    TTL={obs_ttl:3d}: ambiguous or corrupted")

    print("\n  How traceroute exploits TTL:")
    print("    Send probe with TTL=1 → first router decrements to 0 → drops")
    print("    → sends ICMP Time Exceeded → reveals router IP and RTT")
    print("    Repeat with TTL=2, 3, ... until destination replies")
    print("    (or max hops reached)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Jacobson RTT Estimator — Live Simulation
# ─────────────────────────────────────────────────────────────────────────────

def section3_rtt_estimator():
    print("\n" + "=" * 65)
    print("SECTION 3: Jacobson RTT Estimator on Simulated ping Data")
    print("=" * 65)

    alpha, beta = 1/8, 1/4
    rto_floor = 200  # ms, RFC 6298

    def update(srtt, rttvar, r):
        rttvar = (1-beta)*rttvar + beta*abs(srtt - r)
        srtt   = (1-alpha)*srtt  + alpha*r
        rto    = max(srtt + 4*rttvar, rto_floor)
        return srtt, rttvar, rto

    # Simulate realistic RTT sequence: stable with occasional spikes
    random.seed(42)
    base_rtt = 12.0
    rtts = []
    for i in range(20):
        if i in (5, 13):  # simulate two queue spikes
            rtts.append(base_rtt + random.uniform(30, 50))
        else:
            rtts.append(base_rtt + random.gauss(0, 1.2))
    rtts = [max(1.0, r) for r in rtts]

    srtt, rttvar = rtts[0], 0.0
    print(f"\n  α={alpha} β={beta}  (RTT samples from simulated ping)")
    print(f"  {'#':>4} {'R(ms)':>8} {'SRTT':>8} {'RTTVAR':>9} {'RTO':>9}  note")
    print("  " + "-" * 60)
    print(f"  {'init':>4} {rtts[0]:>8.1f} {srtt:>8.2f} {rttvar:>9.2f} {'—':>9}")

    for i, r in enumerate(rtts[1:], 1):
        srtt, rttvar, rto = update(srtt, rttvar, r)
        spike = "← SPIKE" if r > base_rtt + 20 else ""
        floor = " (floor)" if rto == rto_floor else ""
        print(f"  {i:>4} {r:>8.1f} {srtt:>8.2f} {rttvar:>9.2f} {rto:>7.1f}ms{floor}  {spike}")

    print(f"\n  Connection to TCP:")
    print(f"  • These RTT samples ARE what TCP's EWMA is filtering into srtt")
    print(f"  • The spread visible in the table = rttvar")
    print(f"  • RTO = srtt + 4×rttvar sits safely above nearly every sample")
    print(f"  • ss -tipm shows these exact values live: rtt:X/Y rto:Z")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Simulated Protocol Hierarchy (Wireshark-style)
# ─────────────────────────────────────────────────────────────────────────────

def section4_protocol_hierarchy():
    print("\n" + "=" * 65)
    print("SECTION 4: Protocol Hierarchy Analysis (Simulated)")
    print("=" * 65)

    # Simulate a realistic capture from a modern browsing session
    random.seed(7)
    protocols = {
        "Ethernet":  {"pkts": 1000, "bytes": 1_200_000},
        "  IPv4":    {"pkts":  850, "bytes": 1_050_000},
        "    TCP":   {"pkts":  750, "bytes":   950_000},
        "      TLS": {"pkts":  500, "bytes":   700_000},
        "      HTTP":{"pkts":   50, "bytes":    30_000},
        "    UDP":   {"pkts":  100, "bytes":   100_000},
        "      DNS": {"pkts":   60, "bytes":    12_000},
        "      QUIC":{"pkts":   40, "bytes":    88_000},
        "    ICMP":  {"pkts":   10, "bytes":     1_000},
        "  IPv6":    {"pkts":  150, "bytes":   150_000},
        "    UDP/v6":{"pkts":   80, "bytes":    80_000},
        "    TCP/v6":{"pkts":   70, "bytes":    70_000},
        "  ARP":     {"pkts":   10, "bytes":       600},
    }

    total_pkts  = 1000
    total_bytes = 1_200_000

    print(f"\n  Capture: {total_pkts} packets, {total_bytes:,} bytes")
    print(f"\n  {'Protocol':<18} {'Pkts':>8} {'%pkts':>8} {'Bytes':>12} {'%bytes':>9}")
    print("  " + "-" * 60)
    for proto, stats in protocols.items():
        p_pct = stats["pkts"] / total_pkts * 100
        b_pct = stats["bytes"] / total_bytes * 100
        print(f"  {proto:<18} {stats['pkts']:>8,} {p_pct:>7.1f}% "
              f"{stats['bytes']:>12,} {b_pct:>8.1f}%")

    print(f"\n  What to note:")
    print(f"  • TLS is the dominant TCP payload — most web is HTTPS (L19/L20)")
    print(f"  • QUIC (UDP) carries ~8% of traffic — HTTP/3 adoption (L20)")
    print(f"  • DNS is tiny in bytes but meaningful in packets — L23 preview")
    print(f"  • ARP is < 0.1% — only at startup and cache expiry (L08)")
    print(f"  • ICMP is minimal — only ping/traceroute in this capture (L17)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: pyshark Code Reference (runs against real .pcap file)
# ─────────────────────────────────────────────────────────────────────────────

def section5_pyshark_reference():
    print("\n" + "=" * 65)
    print("SECTION 5: pyshark Code Reference")
    print("=" * 65)

    print("""
  ─── Load and iterate ──────────────────────────────────────────
  import pyshark
  cap = pyshark.FileCapture('/home/ubuntu/capture.pcap')
  for pkt in cap:
      print(pkt.highest_layer, pkt.length)
  # highest_layer: topmost decoded protocol (DNS, TCP, TLS, QUIC...)
  # length: total frame length in bytes

  ─── Field-level access ────────────────────────────────────────
  pkt = next(iter(cap))
  print(pkt.layers)          # all protocol layers
  print(pkt.ip.src)          # source IP (L14, L17)
  print(pkt.ip.ttl)          # TTL field (L17)
  print(pkt.ip.len)          # IP total length
  print(pkt.tcp.seq)         # TCP sequence number (L19)
  print(pkt.tcp.ack)         # TCP ACK number (L19)
  print(pkt.tcp.flags)       # TCP flags as hex bitmask
  print(pkt.tcp.window_size) # advertised rwnd (L19)
  print(pkt.transport_layer) # 'TCP' or 'UDP'

  ─── DNS query extractor ───────────────────────────────────────
  cap = pyshark.FileCapture('capture.pcap', display_filter='dns')
  queries = collections.Counter()
  for pkt in cap:
      try:
          if hasattr(pkt.dns, 'qry_name'):
              queries[pkt.dns.qry_name] += 1
      except AttributeError:
          pass
  for name, count in queries.most_common(10):
      print(f"{count:4d}  {name}")

  ─── TCP RTT plotter ───────────────────────────────────────────
  import pyshark, matplotlib.pyplot as plt
  cap = pyshark.FileCapture('capture.pcap',
                            display_filter='tcp.analysis.ack_rtt')
  times, rtts = [], []
  for pkt in cap:
      try:
          times.append(float(pkt.sniff_timestamp))
          rtts.append(float(pkt.tcp.analysis_ack_rtt) * 1000)
      except AttributeError:
          pass
  plt.plot(times, rtts, '.', markersize=3)
  plt.xlabel('Time (s)'); plt.ylabel('RTT (ms)')
  plt.title('Per-segment TCP ACK RTT')
  plt.savefig('rtt_plot.png')
  # The resulting plot IS the raw signal that TCP's EWMA smooths into srtt.
  # Spikes = queuing delay or retransmissions (rttvar grows around them)

  ─── Protocol counter ──────────────────────────────────────────
  cap = pyshark.FileCapture('capture.pcap')
  counter = collections.Counter()
  for pkt in cap:
      counter[pkt.highest_layer] += 1
  for proto, count in counter.most_common():
      print(f"{count:6d}  {proto}")

  ─── TCP connection tracker (SYN → FIN) ───────────────────────
  cap = pyshark.FileCapture('capture.pcap',
                            display_filter='tcp.flags.syn == 1 or '
                                           'tcp.flags.fin == 1')
  conns = {}
  for pkt in cap:
      try:
          key = tuple(sorted([
              (pkt.ip.src, pkt.tcp.srcport),
              (pkt.ip.dst, pkt.tcp.dstport)
          ]))
          t = float(pkt.sniff_timestamp)
          flags = int(pkt.tcp.flags, 16)
          syn = bool(flags & 0x02)
          ack = bool(flags & 0x10)
          fin = bool(flags & 0x01)
          if syn and not ack and key not in conns:
              conns[key] = {'start': t}
          elif fin and key in conns and 'end' not in conns[key]:
              conns[key]['end'] = t
      except AttributeError:
          pass
  for key, times in conns.items():
      if 'start' in times and 'end' in times:
          dur = times['end'] - times['start']
          print(f"  {key}  duration={dur:.3f}s")
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: dig / DNS Output Parser
# ─────────────────────────────────────────────────────────────────────────────

def section6_dns_reference():
    print("=" * 65)
    print("SECTION 6: dig Output Field Reference")
    print("=" * 65)

    print("""
  Sample dig output:
  $ dig google.com

  ; <<>> DiG 9.18.1 <<>> google.com
  ;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 12345
  ;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0

  ;; QUESTION SECTION:
  ;google.com.    IN   A

  ;; ANSWER SECTION:
  google.com.   300  IN  A  142.250.80.46

  ;; Query time: 8 msec
  ;; SERVER: 192.168.1.1#53(192.168.1.1)
  ;; WHEN: ...
  ;; MSG SIZE rcvd: 55

  Field interpretation:
    status: NOERROR    → query succeeded; NXDOMAIN = not found
    flags: qr          → this is a response (not a query)
    flags: rd          → recursion desired (client wants full resolution)
    flags: ra          → recursion available (resolver supports it)
    google.com.  300   → TTL = 300 seconds; cache valid for 5 min
    IN A               → Internet class, A record (IPv4 address)
    SERVER: 192.168.1.1 → your recursive resolver (home router)

  Record types:
    A      → IPv4 address
    AAAA   → IPv6 address
    MX     → Mail exchanger
    CNAME  → Canonical name (alias)
    NS     → Name server
    TXT    → Text record (SPF, DKIM, etc.)
    PTR    → Reverse DNS (IP → name)

  Useful dig flags:
    +short      → just the answer IP
    +trace      → full resolution chain root→TLD→authoritative
    @8.8.8.8    → query specific resolver
    -x          → reverse DNS lookup
    +tcp        → force TCP instead of UDP
""")

    print("  DNS uses UDP (port 53) by default — connects to L18 (UDP, ports).")
    print("  Falls back to TCP when response > 512B or DNSSEC makes it large.")
    print("  TTL = DNS cache lifetime; when it expires, resolver re-queries.")
    print("  dig +trace reveals the L23 topic: root → TLD → authoritative.")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    section1_cli_reference()
    section2_ttl_analysis()
    section3_rtt_estimator()
    section4_protocol_hierarchy()
    section5_pyshark_reference()
    section6_dns_reference()
    print("\n" + "=" * 65)
    print("EC 441 Lecture 21 Lab complete.")
    print("=" * 65)