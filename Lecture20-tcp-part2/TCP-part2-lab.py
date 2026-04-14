#!/usr/bin/env python3
"""
EC 441 — Lecture 20 Lab: TCP Part 2 — Congestion Control
Topics: Slow start, AIMD sawtooth, fast recovery, cwnd trace,
        TCP throughput formula, BDP + window scaling,
        AIMD fairness visualization, CUBIC vs Reno comparison, QUIC overview
"""

import math
import random

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Slow Start and Congestion Avoidance — Step-by-Step Trace
# ─────────────────────────────────────────────────────────────────────────────

def section1_slow_start():
    print("=" * 65)
    print("SECTION 1: Slow Start and Congestion Avoidance Trace")
    print("=" * 65)

    def trace_cwnd(ssthresh_init, events, n_rtts=20):
        """
        events: list of (rtt, type) where type = 'timeout' | '3dup'
        Returns list of (rtt, cwnd, ssthresh, phase, note)
        """
        cwnd    = 1
        ssthresh = ssthresh_init
        results = []
        ev_dict = {rtt: t for rtt, t in events}

        for rtt in range(n_rtts + 1):
            phase = "Slow Start" if cwnd < ssthresh else "Cong. Avoid."
            note  = ""

            if rtt in ev_dict:
                ev = ev_dict[rtt]
                if ev == "timeout":
                    note = "TIMEOUT → cwnd=1, ssthresh=cwnd/2"
                    ssthresh = max(cwnd // 2, 1)
                    cwnd = 1
                    phase = "Slow Start"
                elif ev == "3dup":
                    note = "3 DUP ACK → fast recovery"
                    ssthresh = max(cwnd // 2, 1)
                    cwnd = ssthresh
                    phase = "Cong. Avoid."

            results.append((rtt, cwnd, ssthresh, phase, note))

            # Advance cwnd for next RTT
            if cwnd < ssthresh:
                cwnd = min(cwnd * 2, ssthresh)  # slow start: doubles up to ssthresh
            else:
                cwnd += 1  # congestion avoidance: +1/RTT

        return results

    print("\n  Scenario: ssthresh=16, 3-dup ACK at RTT 8, timeout at RTT 15")
    results = trace_cwnd(16, events=[(8, "3dup"), (15, "timeout")], n_rtts=22)

    print(f"\n  {'RTT':>5} {'cwnd':>6} {'ssthresh':>9} {'Phase':<16} Note")
    print("  " + "-" * 72)
    for rtt, cwnd, ssth, phase, note in results:
        bar = "█" * min(cwnd, 40)
        print(f"  {rtt:>5} {cwnd:>6} {ssth:>9} {phase:<16} {note or bar}")

    # ASCII sawtooth
    print("\n  cwnd sawtooth (each █ = 1 MSS, capped at 40):")
    for rtt, cwnd, _, phase, _ in results:
        bar = "█" * min(cwnd, 40)
        print(f"  {rtt:>3}| {bar}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: TCP Throughput Formula
# ─────────────────────────────────────────────────────────────────────────────

def section2_throughput():
    print("\n" + "=" * 65)
    print("SECTION 2: TCP Throughput Formula  BW ≈ MSS/(RTT×√p)")
    print("=" * 65)

    mss = 1460  # bytes

    scenarios = [
        ("LAN",              0.001, 1e-4),
        ("Campus WAN",       0.010, 1e-4),
        ("Trans-Atlantic",   0.100, 1e-4),
        ("Satellite",        0.600, 1e-4),
        ("Lossy cellular",   0.050, 1e-2),
        ("Good cellular",    0.050, 1e-4),
    ]

    print(f"\n  {'Scenario':<18} {'RTT':>8} {'p':>10} {'BW':>14}  {'% of 1Gbps'}")
    print("  " + "-" * 68)
    for name, rtt, p in scenarios:
        bw = (mss / rtt) / math.sqrt(p)  # bytes/sec
        pct = bw / 1e9 * 100
        bw_str = f"{bw/1e9:.4f}Gb/s" if bw >= 1e9 else \
                 f"{bw/1e6:.2f}Mb/s"  if bw >= 1e6 else \
                 f"{bw/1e3:.1f}kb/s"
        print(f"  {name:<18} {rtt*1e3:>6.0f}ms {p:>10.0e} {bw_str:>14}  {pct:.4f}%")

    print("\n  Solve for required p to achieve target throughput:")
    targets = [(1e8, 0.050), (1e9, 0.050), (1e10, 0.050)]
    for target_bw, rtt in targets:
        # p = (MSS / (RTT * BW))^2
        p_req = (mss / (rtt * target_bw)) ** 2
        bw_str = f"{target_bw/1e9:.0f}Gb/s" if target_bw >= 1e9 else \
                 f"{target_bw/1e6:.0f}Mb/s"
        print(f"    {bw_str} over RTT={rtt*1e3:.0f}ms → p < {p_req:.2e}  "
              f"({'near-impossible' if p_req < 1e-10 else 'achievable'})")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: BDP and Window Scaling
# ─────────────────────────────────────────────────────────────────────────────

def section3_bdp():
    print("\n" + "=" * 65)
    print("SECTION 3: BDP and Window Scaling")
    print("=" * 65)

    scenarios = [
        ("100Mb LAN",           100e6, 0.001, 1500),
        ("1Gb campus",          1e9,   0.010, 1500),
        ("1Gb trans-atlantic",  1e9,   0.150, 1500),
        ("10Gb datacenter",     10e9,  0.0005,9000),
        ("Geostationary sat",   1e9,   0.600, 1500),
    ]

    MAX_WINDOW_NO_SCALE = 64 * 1024  # 64 KB

    print(f"\n  {'Scenario':<25} {'BW':>10} {'RTT':>7} {'BDP':>12} {'wscale':>8} {'eff window'}")
    print("  " + "-" * 80)
    for name, bw, rtt, mss in scenarios:
        bdp = bw * rtt  # bits
        bdp_bytes = bdp / 8
        win_pkts  = math.ceil(bdp_bytes / mss)

        # Find required window scale
        needed = bdp_bytes
        scale  = 0
        while MAX_WINDOW_NO_SCALE * (2 ** scale) < needed and scale < 14:
            scale += 1
        eff_win = MAX_WINDOW_NO_SCALE * (2 ** scale)

        bw_str  = f"{bw/1e9:.0f}Gb/s" if bw >= 1e9 else f"{bw/1e6:.0f}Mb/s"
        rtt_str = f"{rtt*1e3:.0f}ms"
        bdp_str = f"{bdp_bytes/1e6:.1f}MB" if bdp_bytes >= 1e6 else f"{bdp_bytes/1e3:.0f}KB"
        win_str = f"{eff_win/1e6:.1f}MB" if eff_win >= 1e6 else f"{eff_win/1e3:.0f}KB"

        print(f"  {name:<25} {bw_str:>10} {rtt_str:>7} {bdp_str:>12} "
              f"  ×2^{scale:<2} {win_str:>10}")

    print(f"\n  Without Window Scale: max window = 64KB (16-bit field, no multiplier)")
    print(f"  With Window Scale n:  max window = 64KB × 2^n, up to 1GB (n=14)")
    print(f"  Negotiated at SYN time. Required for any high-BDP path.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Fast Recovery — cwnd/ssthresh Trace
# ─────────────────────────────────────────────────────────────────────────────

def section4_fast_recovery():
    print("\n" + "=" * 65)
    print("SECTION 4: Fast Recovery — cwnd Trace Through a Loss Event")
    print("=" * 65)

    def fast_recovery_trace(cwnd_at_loss):
        ssthresh = cwnd_at_loss // 2
        cwnd_after = ssthresh
        print(f"\n  3 dup ACKs at cwnd = {cwnd_at_loss} MSS:")
        print(f"    ssthresh = cwnd/2 = {ssthresh} MSS")
        print(f"    cwnd     = ssthresh = {cwnd_after} MSS  (skip slow start!)")
        print(f"    → retransmit missing segment immediately")
        print(f"    → each additional dup ACK while in recovery: cwnd += 1 MSS")
        print(f"    → new ACK arrives → cwnd = ssthresh → back to Cong. Avoid.")

        print(f"\n  Compare to timeout at same cwnd:")
        print(f"    ssthresh = cwnd/2 = {ssthresh} MSS  (same)")
        print(f"    cwnd     = 1 MSS  (full restart, exponential slow start)")
        print(f"\n  Key difference: 3 dup ACKs = network partly working,")
        print(f"  data is flowing. Timeout = nothing getting through.")

    fast_recovery_trace(20)

    print("\n  Fast recovery dup-ACK inflation:")
    print("  During recovery, each additional dup ACK = one more segment")
    print("  arrived at receiver. cwnd is temporarily inflated to keep")
    print("  the pipe full while the lost segment is retransmitted.")
    print("  RTT=5: cwnd=10, 3 dup ACKs → ssthresh=5, cwnd=5+3=8 during recovery")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: AIMD Fairness Simulation
# ─────────────────────────────────────────────────────────────────────────────

def section5_aimd_fairness():
    print("\n" + "=" * 65)
    print("SECTION 5: AIMD Fairness — Two Flows Sharing a Link")
    print("=" * 65)

    capacity   = 20   # Mbps (shared)
    mss        = 1    # normalized to 1 Mbps unit

    print("\n  Two TCP flows sharing a 20-unit link.")
    print("  Both start at 1 unit. Additive increase +1/RTT.")
    print("  Multiplicative decrease ÷2 on loss (when sum > capacity).")

    x1, x2 = 1.0, 1.0
    print(f"\n  {'RTT':>5} {'x1':>8} {'x2':>8} {'sum':>8} {'fair?':>8}")
    print("  " + "-" * 45)

    for rtt in range(25):
        total = x1 + x2
        fair  = abs(x1 - x2) < 0.5 * capacity
        print(f"  {rtt:>5} {x1:>8.2f} {x2:>8.2f} {total:>8.2f} "
              f"{'≈ fair' if fair and total >= capacity * 0.9 else ''}")
        x1 += mss
        x2 += mss
        if x1 + x2 > capacity:
            x1 /= 2
            x2 /= 2

    print("\n  Convergence proof (AIMD):")
    print("  Additive increase: both +Δ → move parallel to x1=x2 line")
    print("  Multiplicative decrease: both ÷2 → move toward origin")
    print("  Net: spiral toward (capacity/2, capacity/2)")
    print("  AIMD is the unique simple policy that achieves both efficiency")
    print("  and fairness through this geometric argument.")

    print("\n  AIMD fairness caveats:")
    caveats = [
        ("RTT unfairness",     "Reno gives more BW to short-RTT flows (more steps/sec)"),
        ("UDP unfriendliness", "UDP flows ignore AIMD → crowd out TCP"),
        ("N connections",      "Opening N connections captures N× the AIMD share"),
        ("CUBIC fix",          "Wall-clock growth is RTT-independent → better fairness"),
    ]
    for c, desc in caveats:
        print(f"  • {c:<20} {desc}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: TCP Reno vs CUBIC
# ─────────────────────────────────────────────────────────────────────────────

def section6_cubic():
    print("\n" + "=" * 65)
    print("SECTION 6: TCP Reno vs TCP CUBIC")
    print("=" * 65)

    def cubic_window(t, wmax, C=0.4):
        """CUBIC window function: W(t) = C(t-K)^3 + Wmax"""
        K = (wmax * 0.5 / C) ** (1/3)
        return C * (t - K) ** 3 + wmax

    print("\n  CUBIC: W(t) = C(t-K)³ + Wmax")
    print("  K = (Wmax×0.5/C)^(1/3)  — time to recover to Wmax")
    print("  Growth is slow near Wmax (cautious probe) and fast when far from it")

    wmax = 40
    print(f"\n  After loss event (Wmax={wmax} MSS), CUBIC window recovery:")
    print(f"  {'t (sec)':>10} {'CUBIC cwnd':>12} {'Reno cwnd (linear)':>20}")
    print("  " + "-" * 46)

    reno_cwnd  = wmax / 2
    rtt = 0.05  # 50ms

    for t_ms in [0, 50, 100, 200, 400, 600, 800, 1000, 1500, 2000]:
        t_sec = t_ms / 1000
        c_cwnd = max(wmax / 2, cubic_window(t_sec, wmax))
        r_cwnd = reno_cwnd + t_sec / rtt  # +1 MSS per RTT
        print(f"  {t_ms:>8}ms {c_cwnd:>12.1f} {r_cwnd:>20.1f}")

    print(f"\n  CUBIC key advantages over Reno:")
    rows = [
        ("Growth clock",    "RTT-clocked",    "Wall-clock time"),
        ("Growth shape",    "Linear (AIMD)",  "Cubic (slow near Wmax, fast when far)"),
        ("High-BDP",        "Slow recovery",  "Fast recovery"),
        ("RTT fairness",    "Short RTT wins", "RTT-independent growth"),
        ("Linux default",   "No (old)",       "Yes (since kernel 2.6.19)"),
    ]
    print(f"\n  {'':22} {'Reno':<22} {'CUBIC'}")
    print("  " + "-" * 66)
    for row, reno, cubic in rows:
        print(f"  {row:<22} {reno:<22} {cubic}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: QUIC — Protocol Stack Comparison
# ─────────────────────────────────────────────────────────────────────────────

def section7_quic():
    print("\n" + "=" * 65)
    print("SECTION 7: QUIC — What TCP Gets Wrong and How QUIC Fixes It")
    print("=" * 65)

    print("""
  Classic HTTP/2 stack:        QUIC / HTTP/3 stack:
  ┌─────────────────────┐      ┌─────────────────────┐
  │    HTTP/1.1          │      │       HTTP/3         │
  ├─────────────────────┤      ├─────────────────────┤
  │       TLS           │      │  QUIC + TLS 1.3     │
  ├─────────────────────┤      ├─────────────────────┤
  │       TCP           │      │       UDP            │
  ├─────────────────────┤      ├─────────────────────┤
  │        IP           │      │        IP            │
  └─────────────────────┘      └─────────────────────┘
  Handshake: 2-3 RTTs           Handshake: 1 RTT (0 RTT resumed)
""")

    problems = [
        ("HOL Blocking",
         "HTTP/2 streams over one TCP byte-stream. One lost packet\n"
         "  blocks ALL streams. QUIC: each stream independent."),
        ("Slow Setup",
         "TCP 3WHS + TLS = 2-3 RTTs before data. QUIC + TLS1.3:\n"
         "  1 RTT new, 0 RTT resumed (cached session)."),
        ("Ossification",
         "Middleboxes inspect/modify TCP headers. Can't change TCP.\n"
         "  QUIC: header fully encrypted over UDP; middleboxes pass-through."),
        ("Connection Migration",
         "TCP is 4-tuple. Switch WiFi→cellular: connection breaks.\n"
         "  QUIC: uses Connection ID; survives IP address changes."),
    ]

    for problem, fix in problems:
        print(f"  TCP Problem: {problem}")
        print(f"  QUIC Fix:    {fix}")
        print()

    print("  Feature comparison:")
    rows = [
        ("Connection setup", "None",          "3WHS (1 RTT)",     "1 RTT / 0 RTT"),
        ("Reliability",      "None",          "Byte stream",      "Per stream"),
        ("HOL blocking",     "N/A",           "Yes",              "No"),
        ("Encryption",       "App layer",     "TLS separate",     "TLS 1.3 built-in"),
        ("Migration",        "N/A",           "No (4-tuple)",     "Yes (conn ID)"),
        ("Runs over",        "IP",            "IP",               "UDP"),
    ]
    print(f"\n  {'Feature':<22} {'UDP':<16} {'TCP':<18} {'QUIC'}")
    print("  " + "-" * 72)
    for row in rows:
        print(f"  {row[0]:<22} {row[1]:<16} {row[2]:<18} {row[3]}")

    print(f"\n  QUIC usage (2024): ~25% of Internet traffic")
    print(f"  Powers: HTTP/3, YouTube, Google Search, Cloudflare")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Transport Layer Summary L18–L20
# ─────────────────────────────────────────────────────────────────────────────

def section8_summary():
    print("\n" + "=" * 65)
    print("SECTION 8: Transport Layer Summary — L18 through L20")
    print("=" * 65)

    summary = [
        ("L18", "Mux/demux",          "Port numbers identify processes on a host"),
        ("L18", "UDP",                "Best-effort, 8B header, app controls reliability"),
        ("L18", "Stop-and-Wait",      "Correct; utilization = t_tx/(RTT+t_tx) ≈ 0"),
        ("L18", "Pipelining",         "Window ≥ BDP/pkt to fill the pipe"),
        ("L18", "GBN",                "Cumulative ACK; retransmit all in window on loss"),
        ("L18", "SR",                 "Individual ACK; buffer OOO; retransmit only lost"),
        ("L19", "TCP header",         "20B min; SEQ/ACK are byte offsets not packet #s"),
        ("L19", "3-way handshake",    "SYN/SYN-ACK/ACK; ISN randomized for safety"),
        ("L19", "Teardown",           "FIN half-close; TIME_WAIT = 2×MSL; RST = abort"),
        ("L19", "RTT estimation",     "EWMA (SRTT) + RTTVAR; RTO = SRTT + 4×RTTVAR"),
        ("L19", "Fast retransmit",    "3 dup ACKs → retransmit immediately (before RTO)"),
        ("L19", "Flow control",       "rwnd = receiver free buffer; sender ≤ rwnd"),
        ("L20", "cwnd",               "Sender-side limit; protects network from overload"),
        ("L20", "Slow start",         "Exponential growth (doubles/RTT) until ssthresh"),
        ("L20", "AIMD",               "+1 MSS/RTT; halve on loss → sawtooth + fairness"),
        ("L20", "Fast recovery",      "3 dup ACKs → ssthresh=cwnd/2, cwnd=ssthresh (no SS)"),
        ("L20", "Throughput formula", "BW ≈ MSS/(RTT×√p); penalizes high RTT and loss"),
        ("L20", "CUBIC",              "Cubic W(t), wall-clock, RTT-fair; Linux default"),
        ("L20", "ECN",                "Mark not drop; earlier, lossless congestion signal"),
        ("L20", "QUIC",               "UDP-based; fixes HOL, ossification, migration"),
    ]

    print(f"\n  {'Lec':>4} {'Concept':<22} Key idea")
    print("  " + "-" * 72)
    for lec, concept, desc in summary:
        print(f"  {lec:>4} {concept:<22} {desc}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    section1_slow_start()
    section2_throughput()
    section3_bdp()
    section4_fast_recovery()
    section5_aimd_fairness()
    section6_cubic()
    section7_quic()
    section8_summary()
    print("\n" + "=" * 65)
    print("EC 441 Lecture 20 Lab complete.")
    print("=" * 65)