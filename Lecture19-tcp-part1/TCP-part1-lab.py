#!/usr/bin/env python3
"""
EC 441 — Lecture 19 Lab: TCP Part 1
Topics: TCP header layout, 3-way handshake trace, SEQ/ACK arithmetic,
        ISN randomization, RTT estimation (EWMA + RTTVAR), Karn's algorithm,
        fast retransmit, flow control (rwnd) simulator
"""

import math
import random
import hashlib
import struct
import time

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: TCP Segment Header Layout
# ─────────────────────────────────────────────────────────────────────────────

def section1_header():
    print("=" * 65)
    print("SECTION 1: TCP Segment Header Layout")
    print("=" * 65)

    def show_tcp_header(src_port, dst_port, seq, ack, flags, window,
                        payload_bytes=0, options_bytes=0):
        data_offset = (20 + options_bytes) // 4
        flag_str = ", ".join(f for f, v in flags.items() if v)
        print(f"\n  TCP Segment: {src_port} → {dst_port}  flags=[{flag_str}]")
        print("  ┌──────────────────────┬──────────────────────┐")
        print(f"  │ Src Port: {src_port:<11}│ Dst Port: {dst_port:<11}│")
        print("  ├──────────────────────┴──────────────────────┤")
        print(f"  │ Sequence Number: {seq:<28}│")
        print("  ├─────────────────────────────────────────────┤")
        print(f"  │ ACK Number: {'(not valid)' if not flags.get('ACK') else str(ack):<33}│")
        print("  ├────────┬────────┬────────────────────────────┤")
        print(f"  │Off={data_offset:<4}│Flags   │ Window={window:<22}│")
        print("  ├────────┴────────┴────────────────────────────┤")
        print(f"  │ Checksum + Urgent Ptr (4 bytes)              │")
        if options_bytes:
            print(f"  ├─────────────────────────────────────────────┤")
            print(f"  │ Options ({options_bytes} bytes)                        │")
        if payload_bytes:
            print(f"  ├─────────────────────────────────────────────┤")
            print(f"  │ Data ({payload_bytes} bytes)                           │")
        print("  └─────────────────────────────────────────────┘")
        print(f"  Header: {20+options_bytes}B | Payload: {payload_bytes}B | "
              f"Total segment: {20+options_bytes+payload_bytes}B")

    print("\n  --- 3-way handshake segments ---")
    show_tcp_header(54312, 80, seq=1000, ack=0,
                    flags={"SYN": True, "ACK": False},
                    window=65535, options_bytes=12)
    show_tcp_header(80, 54312, seq=5000, ack=1001,
                    flags={"SYN": True, "ACK": True},
                    window=65535, options_bytes=12)
    show_tcp_header(54312, 80, seq=1001, ack=5001,
                    flags={"ACK": True},
                    window=65535)

    print("\n  Key flags reference:")
    flags_ref = [
        ("SYN", "Connection initiation; carries ISN"),
        ("ACK", "ACK number field is valid"),
        ("FIN", "Sender has no more data to send"),
        ("RST", "Abort connection immediately"),
        ("PSH", "Deliver to app without buffering"),
        ("CWR/ECE", "Congestion signals (L20)"),
    ]
    for flag, desc in flags_ref:
        print(f"    {flag:<8} {desc}")

    print("\n  TCP Options negotiated at SYN:")
    opts = [
        ("MSS",          "Max segment size (typically 1460B on Ethernet)"),
        ("Window Scale", "Multiplies window by 2^n; needed for BDP > 64KB"),
        ("SACK",         "SR-style selective ACK for specific byte ranges"),
        ("Timestamps",   "Precise RTT measurement; removes Karn ambiguity"),
    ]
    for opt, desc in opts:
        print(f"    {opt:<16} {desc}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: SEQ/ACK Arithmetic Tracer
# ─────────────────────────────────────────────────────────────────────────────

def section2_seq_ack():
    print("\n" + "=" * 65)
    print("SECTION 2: SEQ/ACK Byte-Stream Arithmetic")
    print("=" * 65)

    print("\n  TCP models data as a continuous byte stream.")
    print("  SEQ = offset of first byte in this segment")
    print("  ACK = next byte expected from the other side")
    print("  SYN and FIN each consume 1 sequence number\n")

    class TCPEndpoint:
        def __init__(self, name, isn):
            self.name    = name
            self.seq     = isn + 1  # after SYN
            self.exp_ack = None

        def send_data(self, n_bytes, other, label=""):
            print(f"  {self.name:6} → {other.name:6}  SEQ={self.seq:<10} "
                  f"ACK={other.seq:<10} payload={n_bytes}B  {label}")
            other.exp_ack = self.seq + n_bytes
            self.seq += n_bytes

        def send_ack(self, other):
            print(f"  {self.name:6} → {other.name:6}  SEQ={self.seq:<10} "
                  f"ACK={other.seq:<10} [ACK only]")

    client = TCPEndpoint("Client", 2000)
    server = TCPEndpoint("Server", 5000)

    print("  After handshake: client next_seq=2001, server next_seq=5001\n")

    print("  --- Data exchange ---")
    client.send_data(500, server, "HTTP GET")
    server.send_data(1400, client, "HTTP 200 OK")
    client.send_ack(server)
    server.send_data(1400, client, "HTTP body (cont.)")
    client.send_ack(server)

    print("\n  Lesson: ACK-only segments don't advance SEQ.")
    print("  Only data bytes, SYN, and FIN consume sequence space.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: ISN Randomization Demo
# ─────────────────────────────────────────────────────────────────────────────

def section3_isn():
    print("\n" + "=" * 65)
    print("SECTION 3: ISN Randomization")
    print("=" * 65)

    def linux_isn(src_ip, dst_ip, src_port, dst_port, secret_key, timestamp):
        """Simplified Linux ISN: MD5 hash of 5-tuple + key + timestamp."""
        data = f"{src_ip}:{dst_ip}:{src_port}:{dst_port}:{secret_key}:{timestamp}"
        h = hashlib.md5(data.encode()).digest()
        # Take first 4 bytes as ISN
        isn = struct.unpack(">I", h[:4])[0]
        return isn

    secret = "ec441_secret_key_do_not_share"

    print("\n  Same 5-tuple, different timestamps → wildly different ISNs:")
    src_ip, dst_ip = "10.0.0.1", "93.184.216.34"
    src_port, dst_port = 54312, 80

    for t in range(5):
        isn = linux_isn(src_ip, dst_ip, src_port, dst_port, secret, t * 1000)
        print(f"    t={t*1000:5}ms → ISN = {isn:>12,} (0x{isn:08X})")

    print("\n  Different 5-tuples at same time → different ISNs:")
    for sp in [54312, 54313, 54314]:
        isn = linux_isn(src_ip, dst_ip, sp, dst_port, secret, 5000)
        print(f"    src_port={sp} → ISN = {isn:>12,} (0x{isn:08X})")

    print("\n  Why ISN randomization matters:")
    print("  1. STALE SEGMENTS: Old connection closes, new one starts with same")
    print("     5-tuple. Without random ISN, delayed packets from old connection")
    print("     fall into new connection's window → data corruption.")
    print("  2. SECURITY: Predictable ISN → off-path attacker guesses ACK value")
    print("     → injects forged data into a connection they can't observe.")
    print("  Modern Linux: ISN = MD5(src_ip, dst_ip, ports, key, timestamp)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: RTT Estimation (Jacobson EWMA + RTTVAR)
# ─────────────────────────────────────────────────────────────────────────────

def section4_rtt():
    print("\n" + "=" * 65)
    print("SECTION 4: RTT Estimation — Jacobson EWMA + RTTVAR")
    print("=" * 65)

    alpha = 1/8   # SRTT smoothing
    beta  = 1/4   # RTTVAR smoothing
    rto_floor = 200  # RFC 6298 minimum RTO (ms)

    def update_rto(srtt, rttvar, r):
        # Update RTTVAR before SRTT (RFC 6298 §2.3)
        rttvar = (1 - beta) * rttvar + beta * abs(srtt - r)
        srtt   = (1 - alpha) * srtt   + alpha * r
        rto    = max(srtt + 4 * rttvar, rto_floor)
        return srtt, rttvar, rto

    samples = [80, 120, 90, 200, 85, 95, 100, 110, 88]
    srtt, rttvar = samples[0], 0.0

    print(f"\n  α={alpha}(=1/8), β={beta}(=1/4), RTO floor={rto_floor}ms")
    print(f"\n  {'Sample':>8} {'R(ms)':>8} {'SRTT':>8} {'RTTVAR':>9} {'RTO':>9}  Note")
    print("  " + "-" * 65)
    print(f"  {'init':>8} {'—':>8} {srtt:>8.2f} {rttvar:>9.2f} {'—':>9}")

    for i, r in enumerate(samples[1:], 1):
        srtt_old = srtt
        srtt, rttvar, rto = update_rto(srtt, rttvar, r)
        note = ""
        if r > srtt_old * 1.5:
            note = "← spike! RTTVAR grows"
        if rto == rto_floor:
            note = "← RTO floor active"
        print(f"  {i:>8} {r:>8.0f} {srtt:>8.2f} {rttvar:>9.2f} {rto:>9.2f}  {note}")

    print(f"\n  SRTT = signal mean (slow-moving, smooth)")
    print(f"  RTTVAR = noise power (grows when RTT spikes)")
    print(f"  RTO = SRTT + 4×RTTVAR  ≈ mean + 4σ confidence bound")
    print(f"\n  Engineering insight:")
    print(f"    α=1/8=2^(-3), β=1/4=2^(-2) → implemented as right-shifts.")
    print(f"    Efficient on 1980s hardware without floating-point units.")
    print(f"    Time constant ≈ 1/α = 8 RTT measurements.")

    print(f"\n  Karn's Algorithm:")
    print(f"    When a retransmit occurs, DO NOT update SRTT/RTTVAR from")
    print(f"    the subsequent ACK — we don't know which transmission it ACKs.")
    print(f"    (Timestamps option removes this ambiguity entirely.)")

    print(f"\n  Exponential Backoff:")
    rto_ex = 200.0
    print(f"  {'Timeout #':<12} {'RTO':>10}")
    print("  " + "-" * 24)
    for i in range(6):
        print(f"  {i+1:<12} {rto_ex:>9.0f}ms")
        rto_ex = min(rto_ex * 2, 60000)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Fast Retransmit Simulation
# ─────────────────────────────────────────────────────────────────────────────

def section5_fast_retransmit():
    print("\n" + "=" * 65)
    print("SECTION 5: Fast Retransmit — 3 Dup ACKs")
    print("=" * 65)

    print("\n  Fast retransmit detects loss BEFORE the RTO fires.")
    print("  When receiver gets out-of-order segment, it sends dup ACK")
    print("  for the last in-order byte. 3 dup ACKs = reliable loss signal.\n")

    def simulate_fast_retransmit(lost_seg=3, window=6):
        print(f"  Window={window}, segment {lost_seg} is lost:\n")
        print(f"  {'Event':<35} {'Sender Action'}")
        print("  " + "-" * 65)

        dup_count = 0
        for seg in range(1, window + 3):
            if seg == lost_seg:
                print(f"  Send seg {seg} → LOST in network         —")
                continue
            if seg > lost_seg:
                dup_count += 1
                note = f"dup ACK #{dup_count} for seg {lost_seg-1}"
                if dup_count == 3:
                    print(f"  Recv dup ACK for seg {lost_seg-1} (#{dup_count})          "
                          f"→ FAST RETRANSMIT seg {lost_seg}!")
                    continue
                else:
                    print(f"  Send seg {seg} → ACK={lost_seg-1} ({note})  "
                          f"  waiting ({dup_count}/3)")
            else:
                print(f"  Send seg {seg} → ACK={seg}                    cumulative ACK")

        print(f"\n  After fast retransmit of seg {lost_seg}:")
        print(f"    → New ACK for seg {lost_seg} arrives → window resumes from seg {lost_seg+1}")
        print(f"\n  Why 3 dup ACKs and not 1?")
        print(f"    1–2 dup ACKs can occur from IP reordering (normal, no loss).")
        print(f"    3 dup ACKs is statistically reliable evidence of loss.")

    simulate_fast_retransmit(lost_seg=3, window=7)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Flow Control (rwnd) Simulator
# ─────────────────────────────────────────────────────────────────────────────

def section6_flow_control():
    print("\n" + "=" * 65)
    print("SECTION 6: Flow Control — Receive Window (rwnd)")
    print("=" * 65)

    buffer_size = 32 * 1024  # 32 KB
    mss         = 1460

    class RecvBuffer:
        def __init__(self, size):
            self.size   = size
            self.filled = 0

        @property
        def rwnd(self):
            return self.size - self.filled

        def receive(self, n):
            actual = min(n, self.rwnd)
            self.filled += actual
            return actual

        def app_read(self, n):
            actual = min(n, self.filled)
            self.filled -= actual
            return actual

    buf = RecvBuffer(buffer_size)

    print(f"\n  Buffer size: {buffer_size//1024} KB, MSS: {mss}B")
    print(f"\n  {'Event':<40} {'Buffered':>10} {'rwnd':>10}")
    print("  " + "-" * 62)

    steps = [
        ("initial state",             "recv", 0),
        ("3 segments arrive (3×1460B)", "recv", 3 * mss),
        ("app reads 4380B",            "read", 4380),
        ("2 more segments arrive",     "recv", 2 * mss),
        ("app reads 1460B",            "read", 1460),
        ("sender floods buffer",       "recv", buffer_size),
        ("rwnd = 0, sender pauses",    "recv", 0),
        ("app reads 5000B",            "read", 5000),
    ]

    for label, action, n in steps:
        if action == "recv":
            buf.receive(n)
        elif action == "read":
            buf.app_read(n)

        rwnd_str = f"{buf.rwnd}B" if buf.rwnd > 0 else "0 → sender PAUSES"
        print(f"  {label:<40} {buf.filled:>9}B {rwnd_str:>12}")

    print(f"\n  When rwnd=0:")
    print(f"    Sender enters 'persist' state.")
    print(f"    Periodically sends 1-byte ZERO-WINDOW PROBE to check for space.")
    print(f"    This prevents deadlock if the rwnd-open notification is lost.")

    print(f"\n  Silly window syndrome:")
    print(f"    App reads 1B → receiver advertises rwnd=1B → sender sends 1B segment")
    print(f"    → 41B on the wire for 1B of data (97% overhead!)")
    print(f"    Clark's algorithm: wait to advertise until min(MSS, buffer/2) is free.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: TCP State Machine
# ─────────────────────────────────────────────────────────────────────────────

def section7_state_machine():
    print("\n" + "=" * 65)
    print("SECTION 7: TCP State Machine (key states)")
    print("=" * 65)

    states = """
  CLOSED
    │ passive open (server)     │ connect() (client)
    ▼                           ▼
  LISTEN                     SYN_SENT
    │ recv SYN                  │ recv SYN-ACK
    ▼                           ▼
  SYN_RCVD ──── send ACK ──► ESTABLISHED ◄──────────────────────┐
    │                           │                                │
    │ recv ACK                  │ close() → send FIN             │
    ▼                           ▼                                │
  ESTABLISHED             FIN_WAIT_1 ──── recv ACK ──► FIN_WAIT_2
                               │                                │
                               │ recv FIN → send ACK            │
                               ▼                                │
                           TIME_WAIT ◄─────────────────────────┘
                               │ 2×MSL
                               ▼
                           CLOSED

  Server path (passive close):
    ESTABLISHED → recv FIN → send ACK → CLOSE_WAIT
    → close() → send FIN → LAST_ACK → recv ACK → CLOSED
"""
    print(states)

    print("  Key states explained:")
    state_info = [
        ("LISTEN",      "Server waiting for incoming SYN"),
        ("SYN_SENT",    "Client sent SYN, waiting for SYN-ACK"),
        ("ESTABLISHED", "Normal data transfer state"),
        ("FIN_WAIT_1",  "Active closer sent FIN, waiting for ACK"),
        ("FIN_WAIT_2",  "Got ACK for FIN; waiting for remote FIN"),
        ("TIME_WAIT",   "Wait 2×MSL before allowing 5-tuple reuse"),
        ("CLOSE_WAIT",  "Passive closer got FIN; app can still send"),
        ("LAST_ACK",    "Passive closer sent FIN; waiting for final ACK"),
    ]
    for state, desc in state_info:
        print(f"    {state:<14} {desc}")

    print("\n  ss -t -a   # show all TCP sockets with states")
    print("  Many TIME_WAIT on a busy server = normal; not an error.")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    section1_header()
    section2_seq_ack()
    section3_isn()
    section4_rtt()
    section5_fast_retransmit()
    section6_flow_control()
    section7_state_machine()
    print("\n" + "=" * 65)
    print("EC 441 Lecture 19 Lab complete.")
    print("=" * 65)