#!/usr/bin/env python3
"""
EC 441 — Lecture 18 Lab: Transport Layer, UDP, and Reliable Data Transfer
Topics: Port/socket analysis, UDP header, Stop-and-Wait utilization,
        BDP calculation, GBN simulation, SR simulation, GBN vs SR comparison
"""

import random
import math
import time

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Port Ranges and Well-Known Services
# ─────────────────────────────────────────────────────────────────────────────

def section1_ports():
    print("=" * 65)
    print("SECTION 1: Port Ranges and Well-Known Services")
    print("=" * 65)

    ranges = [
        (0,     1023,  "Well-known", "IANA-assigned"),
        (1024,  49151, "Registered", "Convention"),
        (49152, 65535, "Ephemeral",  "OS (client side)"),
    ]
    print(f"\n{'Range':<18} {'Name':<14} {'Assigned By'}")
    print("-" * 45)
    for lo, hi, name, who in ranges:
        print(f"{lo}–{hi:<12}  {name:<14} {who}")

    services = [
        (22,    "TCP",      "SSH"),
        (53,    "UDP/TCP",  "DNS"),
        (67,    "UDP",      "DHCP (server→client)"),
        (68,    "UDP",      "DHCP (client→server)"),
        (80,    "TCP",      "HTTP"),
        (443,   "TCP",      "HTTPS"),
        (5353,  "UDP",      "mDNS (Bonjour/Avahi)"),
        (6379,  "TCP",      "Redis"),
        (9092,  "TCP",      "Apache Kafka"),
    ]
    print(f"\n{'Port':<8} {'Proto':<10} Service")
    print("-" * 40)
    for port, proto, svc in services:
        print(f"{port:<8} {proto:<10} {svc}")

    print("\nDemux key comparison:")
    print("  UDP: (dst IP, dst port)          — 2 fields")
    print("  TCP: (proto, src IP, src port, dst IP, dst port) — 5 fields")
    print("  Why? TCP needs full 5-tuple because many connections share dst port 80.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: UDP Header Layout
# ─────────────────────────────────────────────────────────────────────────────

def section2_udp_header():
    print("\n" + "=" * 65)
    print("SECTION 2: UDP Header Layout and Checksum")
    print("=" * 65)

    def format_udp_header(src_port, dst_port, payload_bytes):
        length = 8 + payload_bytes  # header + data
        print(f"\n  UDP Header for src={src_port} → dst={dst_port}, payload={payload_bytes}B")
        print("  ┌────────────────────┬────────────────────┐")
        print(f"  │  Src Port: {src_port:<9}│  Dst Port: {dst_port:<9}│")
        print("  ├────────────────────┼────────────────────┤")
        print(f"  │  Length: {length:<11}│  Checksum: 0xXXXX  │")
        print("  ├────────────────────┴────────────────────┤")
        print(f"  │  Data ({payload_bytes} bytes)                       │")
        print("  └─────────────────────────────────────────┘")
        print(f"  Total datagram: {length} bytes  (header always 8 bytes)")
        print(f"  Overhead ratio: {8/length*100:.1f}%")

    format_udp_header(54312, 53,   20)   # DNS query
    format_udp_header(12345, 5005, 1400) # large UDP payload

    print("\n  UDP checksum pseudo-header fields:")
    print("    [src IP 4B] [dst IP 4B] [zero 1B] [proto=17 1B] [UDP len 2B]")
    print("  + UDP header (8 bytes) + UDP data")
    print("  Ones'-complement sum → dmin=2 (detects all single-bit errors)")
    print("  Optional in IPv4 (0x0000 = 'not computed')")
    print("  Mandatory in IPv6 (IPv6 dropped the IP-layer checksum)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Stop-and-Wait Link Utilization Calculator
# ─────────────────────────────────────────────────────────────────────────────

def section3_utilization():
    print("\n" + "=" * 65)
    print("SECTION 3: Stop-and-Wait Link Utilization")
    print("=" * 65)

    scenarios = [
        ("LAN",          1e9,   0.2e-3,  1500),
        ("Campus WAN",   1e9,   10e-3,   1500),
        ("Trans-atlantic fiber", 10e9, 70e-3, 9000),
        ("Geostationary satellite", 1e9, 600e-3, 1500),
    ]

    print(f"\n{'Scenario':<30} {'BW':>8} {'RTT':>8} {'Pkt':>6} "
          f"{'t_tx':>10} {'U':>10} {'Eff BW':>12}")
    print("-" * 88)

    for name, bw, rtt, pkt_bytes in scenarios:
        t_tx = (pkt_bytes * 8) / bw
        U = t_tx / (rtt + t_tx)
        eff_bw = U * bw

        bw_str  = f"{bw/1e9:.0f}Gb/s" if bw >= 1e9 else f"{bw/1e6:.0f}Mb/s"
        rtt_str = f"{rtt*1e3:.0f}ms"
        ttx_str = f"{t_tx*1e6:.2f}µs"
        u_str   = f"{U*100:.4f}%"
        eff_str = f"{eff_bw/1e3:.1f}kb/s" if eff_bw < 1e6 else f"{eff_bw/1e6:.2f}Mb/s"

        print(f"{name:<30} {bw_str:>8} {rtt_str:>8} {pkt_bytes:>6}B "
              f"{ttx_str:>10} {u_str:>10} {eff_str:>12}")

    print("\n→ Lesson: S&W is catastrophically wasteful on high-BDP links.")
    print("  A 1Gb/s satellite link delivers ~20kb/s. Pipelining is essential.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Bandwidth-Delay Product and Window Size
# ─────────────────────────────────────────────────────────────────────────────

def section4_bdp():
    print("\n" + "=" * 65)
    print("SECTION 4: Bandwidth-Delay Product and Required Window Size")
    print("=" * 65)

    scenarios = [
        ("100Mb LAN",           100e6,  0.5e-3,  1500),
        ("1Gb campus",          1e9,    10e-3,   1500),
        ("1Gb intercontinental",1e9,    150e-3,  1500),
        ("10Gb datacenter",     10e9,   0.5e-3,  9000),
        ("Geostationary sat",   1e9,    600e-3,  1500),
    ]

    print(f"\n{'Scenario':<28} {'BW':>10} {'RTT':>8} {'BDP':>12} {'Window (pkts)':>14}")
    print("-" * 76)

    for name, bw, rtt, pkt in scenarios:
        bdp_bits  = bw * rtt
        bdp_bytes = bdp_bits / 8
        win_pkts  = math.ceil(bdp_bytes / pkt)

        bw_str  = f"{bw/1e9:.0f}Gb/s" if bw >= 1e9 else f"{bw/1e6:.0f}Mb/s"
        rtt_str = f"{rtt*1e3:.0f}ms"
        bdp_str = f"{bdp_bytes/1e6:.2f}MB" if bdp_bytes >= 1e6 else f"{bdp_bytes/1e3:.1f}KB"

        print(f"{name:<28} {bw_str:>10} {rtt_str:>8} {bdp_str:>12} {win_pkts:>14,}")

    print("\n→ Filling the pipe requires keeping BDP/MSS packets in flight simultaneously.")
    print("  Stop-and-Wait keeps exactly 1 packet in flight — always starving the pipe.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Go-Back-N Simulator
# ─────────────────────────────────────────────────────────────────────────────

def section5_gbn():
    print("\n" + "=" * 65)
    print("SECTION 5: Go-Back-N Simulator")
    print("=" * 65)

    def simulate_gbn(total_pkts, window, seq_bits, loss_prob, seed=42):
        random.seed(seed)
        seq_mod   = 2 ** seq_bits
        max_win   = seq_mod - 1
        assert window <= max_win, f"GBN window must be ≤ 2^k-1 = {max_win}"

        sent      = 0        # next seq to send
        base      = 0        # oldest unACKed
        delivered = 0        # pkts delivered to application
        tx_count  = 0        # total transmissions (including retransmits)
        events    = []

        print(f"\n  GBN: total={total_pkts} pkts, window={window}, "
              f"seq_bits={seq_bits} (mod {seq_mod}), loss_prob={loss_prob}")

        while delivered < total_pkts:
            # Fill the window
            while sent < base + window and sent < total_pkts:
                seq = sent % seq_mod
                tx_count += 1
                if not events or len(events) < 20:
                    events.append(f"    SEND pkt {seq} (pkt #{sent})")
                sent += 1

            # Simulate ACK for base packet
            if random.random() < loss_prob:
                # Base packet lost → timeout → retransmit window
                retx_start = base
                retx_end   = min(sent - 1, base + window - 1)
                if len(events) < 20:
                    events.append(f"    LOSS pkt {base % seq_mod} → TIMEOUT → "
                                  f"retransmit [{retx_start % seq_mod}..{retx_end % seq_mod}]")
                for i in range(retx_start, min(sent, base + window)):
                    tx_count += 1
            else:
                if len(events) < 20:
                    events.append(f"    ACK  {base % seq_mod} → window slides to base={base+1}")
                base      += 1
                delivered += 1

        for e in events[:15]:
            print(e)
        if len(events) > 15:
            print(f"    ... ({len(events) - 15} more events) ...")

        overhead = (tx_count - total_pkts) / total_pkts * 100
        print(f"\n  Results: delivered={delivered}, total_tx={tx_count}, "
              f"overhead={overhead:.1f}%")
        return tx_count, delivered

    simulate_gbn(total_pkts=20, window=4, seq_bits=3, loss_prob=0.10)
    print()
    simulate_gbn(total_pkts=20, window=4, seq_bits=3, loss_prob=0.30)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Selective Repeat Simulator
# ─────────────────────────────────────────────────────────────────────────────

def section6_sr():
    print("\n" + "=" * 65)
    print("SECTION 6: Selective Repeat Simulator")
    print("=" * 65)

    def simulate_sr(total_pkts, window, seq_bits, loss_prob, seed=42):
        random.seed(seed)
        seq_mod    = 2 ** seq_bits
        max_win    = seq_mod // 2
        assert window <= max_win, f"SR window must be ≤ 2^(k-1) = {max_win}"

        base       = 0
        sent       = 0
        buffer     = {}        # seq_num → received bool
        acked      = set()     # individually ACKed
        delivered  = 0
        tx_count   = 0
        events     = []

        print(f"\n  SR: total={total_pkts} pkts, window={window}, "
              f"seq_bits={seq_bits} (mod {seq_mod}), loss_prob={loss_prob}")

        while delivered < total_pkts:
            # Fill the window
            while sent < base + window and sent < total_pkts:
                seq = sent % seq_mod
                tx_count += 1
                lost = random.random() < loss_prob
                if not lost:
                    buffer[sent] = True
                    acked.add(seq)
                    if len(events) < 20:
                        events.append(f"    SEND pkt {seq} → ACK {seq}")
                else:
                    if len(events) < 20:
                        events.append(f"    SEND pkt {seq} → LOST (will retransmit only {seq})")
                sent += 1

            # Deliver consecutive from base
            while base in buffer and buffer[base]:
                del buffer[base]
                delivered += 1
                base += 1

            # Retransmit only missing packets in window
            for i in range(base, min(sent, base + window)):
                if i not in buffer:
                    seq = i % seq_mod
                    tx_count += 1
                    buffer[i] = True
                    acked.add(seq)
                    if len(events) < 20:
                        events.append(f"    RETX pkt {seq} (pkt #{i}) → ACK {seq}")

        for e in events[:15]:
            print(e)
        if len(events) > 15:
            print(f"    ... ({len(events) - 15} more events) ...")

        overhead = (tx_count - total_pkts) / total_pkts * 100
        print(f"\n  Results: delivered={delivered}, total_tx={tx_count}, "
              f"overhead={overhead:.1f}%")
        return tx_count, delivered

    simulate_sr(total_pkts=20, window=4, seq_bits=3, loss_prob=0.10)
    print()
    simulate_sr(total_pkts=20, window=4, seq_bits=3, loss_prob=0.30)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: GBN vs SR Comparison
# ─────────────────────────────────────────────────────────────────────────────

def section7_comparison():
    print("\n" + "=" * 65)
    print("SECTION 7: GBN vs SR — Overhead Comparison Across Loss Rates")
    print("=" * 65)

    def gbn_overhead(n_pkts, window, loss_p, seed=0):
        random.seed(seed)
        base = sent = delivered = tx = 0
        while delivered < n_pkts:
            while sent < base + window and sent < n_pkts:
                tx += 1; sent += 1
            if random.random() < loss_p:
                for _ in range(base, min(sent, base + window)):
                    tx += 1
            else:
                base += 1; delivered += 1
        return (tx - n_pkts) / n_pkts * 100

    def sr_overhead(n_pkts, window, loss_p, seed=0):
        random.seed(seed)
        base = sent = delivered = tx = 0
        buf = {}
        while delivered < n_pkts:
            while sent < base + window and sent < n_pkts:
                lost = random.random() < loss_p
                if not lost:
                    buf[sent] = True
                tx += 1; sent += 1
            while base in buf and buf[base]:
                del buf[base]; delivered += 1; base += 1
            for i in range(base, min(sent, base + window)):
                if i not in buf:
                    buf[i] = True; tx += 1
        return (tx - n_pkts) / n_pkts * 100

    loss_rates = [0.01, 0.05, 0.10, 0.20, 0.30]
    window = 8
    n_pkts = 500

    print(f"\n  Window size N={window}, {n_pkts} packets")
    print(f"\n  {'Loss %':>8}  {'GBN overhead':>14}  {'SR overhead':>13}  {'GBN/SR ratio':>13}")
    print("  " + "-" * 54)
    for p in loss_rates:
        g = gbn_overhead(n_pkts, window, p)
        s = sr_overhead(n_pkts, window, p)
        ratio = g / s if s > 0 else float('inf')
        print(f"  {p*100:>7.0f}%  {g:>13.1f}%  {s:>12.1f}%  {ratio:>12.1f}x")

    print("\n  GBN vs SR summary table:")
    rows = [
        ("Receiver buffer",      "None needed",        "Must buffer OOO pkts"),
        ("Retransmit on loss",   "All in window",      "Only lost packet"),
        ("ACK type",             "Cumulative",         "Individual"),
        ("Timers",               "One (oldest unACK)", "One per unACKed pkt"),
        ("Seq num limit",        "N ≤ 2^k − 1",       "N ≤ 2^(k-1)"),
        ("Good when",            "Loss rate is low",   "Loss rate is high"),
    ]
    print(f"\n  {'':30} {'GBN':<25} {'SR'}")
    print("  " + "-" * 80)
    for row, gbn, sr in rows:
        print(f"  {row:<30} {gbn:<25} {sr}")

    print("\n  TCP borrows from BOTH:")
    print("    - Cumulative ACKs (GBN) + SACK option (SR-style)")
    print("    - Receiver buffer (SR) + one retransmit timer (GBN-style)")
    print("    - Fast retransmit (3 dup ACKs) = SR insight without full SR machinery")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    section1_ports()
    section2_udp_header()
    section3_utilization()
    section4_bdp()
    section5_gbn()
    section6_sr()
    section7_comparison()
    print("\n" + "=" * 65)
    print("EC 441 Lecture 18 Lab complete.")
    print("=" * 65)