#!/usr/bin/env python3
"""
EC 441 — Lecture 22 Lab: Touch the Network
Topics: Scapy packet crafting reference, Mininet topology simulation,
        TCP/UDP socket server+client, the full read+write loop,
        setsockopt reference, framing patterns

NOTE: Scapy and Mininet sections show reference code that requires
      root and the respective libraries. Socket sections run directly.
      Run the TCP/UDP echo demos in two terminals:
        Terminal 1: python3 this_file.py server
        Terminal 2: python3 this_file.py client
"""

import socket
import sys
import collections
import time
import threading
import struct

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Scapy Packet-Crafting Reference
# ─────────────────────────────────────────────────────────────────────────────

def section1_scapy_reference():
    print("=" * 65)
    print("SECTION 1: Scapy Packet-Crafting Reference")
    print("=" * 65)

    print("""
  Core Scapy idiom: layer stacking with /
    pkt = IP(dst="8.8.8.8") / ICMP()   # "ICMP encapsulated in IP"
    pkt = IP(dst="X") / TCP(dport=80)  # "TCP encapsulated in IP"
    pkt = Ether() / IP() / TCP()       # full stack from L2

  Scapy fills defaults for unspecified fields:
    IP: version=4, ihl=5, ttl=64, proto=auto (from stacked layer)
    IP: src=auto (from routing table), len=auto, chksum=auto
    TCP: seq=0, ack=0, dataofs=auto, chksum=auto

  ─── Build and inspect ───────────────────────────────────────
  from scapy.all import IP, ICMP, TCP
  pkt = IP(dst="8.8.8.8") / ICMP()
  pkt.show()          # pretty-print all fields with values
  bytes(pkt)          # raw wire bytes
  pkt.summary()       # one-line description
  hexdump(pkt)        # hex dump of bytes

  ─── Send and receive ────────────────────────────────────────
  sr1(pkt, timeout=2) # send + receive ONE reply
  sr(pkt, timeout=2)  # send + receive (multiple)
  send(pkt)           # send only, no wait
  sendp(pkt)          # send at L2 (Ethernet frame)
  sniff(filter="icmp", count=5)  # capture (like tcpdump)

  ─── ICMP ping from scratch ──────────────────────────────────
  from scapy.all import IP, ICMP, sr1
  req = IP(dst="8.8.8.8") / ICMP()
  reply = sr1(req, timeout=2, verbose=0)
  if reply:
      print(f"TTL={reply.ttl}, hops≈{128-reply.ttl} (if Windows start)")
      print(f"RTT estimated from sniff_time delta")

  ─── TCP SYN probe ───────────────────────────────────────────
  from scapy.all import IP, TCP, sr1, RandShort
  r = sr1(IP(dst="scanme.nmap.org") /
          TCP(dport=80, flags="S", sport=RandShort()),
          timeout=2, verbose=0)
  if r and r[TCP].flags == "SA":
      print("Port 80 OPEN (got SYN-ACK)")
  elif r and "R" in r[TCP].flags:
      print("Port 80 CLOSED (got RST)")
  else:
      print("No reply (filtered)")

  ─── Minimal traceroute ──────────────────────────────────────
  from scapy.all import IP, ICMP, sr1
  for ttl in range(1, 16):
      r = sr1(IP(dst="8.8.8.8", ttl=ttl)/ICMP(), timeout=2, verbose=0)
      if r is None:   print(f"{ttl:2d} *")
      elif r.type==0: print(f"{ttl:2d} {r.src} (reached)"); break
      else:           print(f"{ttl:2d} {r.src}")

  ─── Sniff (passive capture) ─────────────────────────────────
  from scapy.all import sniff
  pkts = sniff(filter="icmp", count=5, iface="any")
  pkts.summary()       # print one-line per packet
  pkts.nsummary()      # numbered summary

  ─── Ethics reminder ─────────────────────────────────────────
  Scapy opens raw sockets (root required).
  Scanning hosts you don't own may violate CFAA.
  Legal targets: scanme.nmap.org, your own VMs.
  Any other target requires written permission.
""")

    print("  TCP flags reference:")
    flags = [
        ("S",  "SYN — connection initiation"),
        ("A",  "ACK — acknowledgment"),
        ("SA", "SYN-ACK — server handshake reply"),
        ("F",  "FIN — connection close"),
        ("R",  "RST — abrupt close / connection refused"),
        ("PA", "PSH+ACK — data push with acknowledgment"),
        ("FA", "FIN+ACK — graceful close with ACK"),
    ]
    for flag, desc in flags:
        print(f"    flags='{flag}'  →  {desc}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Mininet Topology Reference
# ─────────────────────────────────────────────────────────────────────────────

def section2_mininet_reference():
    print("\n" + "=" * 65)
    print("SECTION 2: Mininet Topology Reference")
    print("=" * 65)

    print("""
  Mininet creates virtual hosts using Linux network namespaces.
  Each host is a real Linux process with its own network stack.
  Links are Linux veth (virtual Ethernet) pairs.
  This is NOT simulation — it is a real miniature network.

  ─── CLI hello world ─────────────────────────────────────────
  sudo mn --topo single,3 --link tc
  mininet> h1 ping -c 3 h2   # real ICMP across virtual link
  mininet> pingall            # all-pairs reachability test
  mininet> h1 iperf -s &; h2 iperf -c h1   # bandwidth test
  mininet> exit

  ─── Python API: bottleneck topology ─────────────────────────
  from mininet.net import Mininet
  from mininet.link import TCLink
  from mininet.node import OVSController

  net = Mininet(controller=OVSController, link=TCLink)
  net.addController('c0')
  h1 = net.addHost('h1')
  h2 = net.addHost('h2')
  s1 = net.addSwitch('s1')
  net.addLink(h1, s1, bw=100, delay='1ms')       # fast access link
  net.addLink(s1, h2, bw=10, delay='20ms', loss=1) # bottleneck
  net.start()

  h2.cmd('iperf3 -s -D')                # start server on h2
  print(h1.cmd('iperf3 -c %s -t 20' % h2.IP()))  # run for 20s
  print(h1.cmd('ss -tipm'))             # TCP internals during transfer
  net.stop()

  ─── Link parameters and their protocol effects ──────────────
  bw=10    → 10 Mb/s bottleneck; governs max throughput
  delay='20ms' → 20ms one-way → RTT ≈ 42ms; BDP = 10M×0.042=52.5KB
  loss=1   → 1% drop rate; triggers fast retransmit, cwnd halving (L20)

  ─── Why Mininet where loopback failed ───────────────────────
  Loopback: RTT ≈ 0.03ms, no loss → cwnd stays at iw=10, no AIMD arc
  Mininet: RTT = 42ms, loss = 1% → slow start → ssthresh → AIMD sawtooth
  ss -tipm on a Mininet transfer shows meaningful cwnd dynamics.

  ─── CLI tools inside Mininet hosts ──────────────────────────
  print(h1.cmd('ip route show'))   # routing table for this namespace
  print(h1.cmd('ss -tipm'))        # cwnd for THIS host's connections
  print(h1.cmd('ping -c 3 %s' % h2.IP()))  # ping across virtual link
""")

    # Simulate the BDP calculation for the lecture topology
    print("  BDP calculation for bw=10, delay=20ms:")
    bw_bps = 10e6
    rtt = 0.042  # 2 × 21ms
    mss = 1460
    bdp_bytes = bw_bps * rtt / 8
    pkts_needed = bdp_bytes / mss
    print(f"    BDP = {bw_bps/1e6:.0f}Mb/s × {rtt*1e3:.0f}ms = "
          f"{bdp_bytes:.0f}B ≈ {bdp_bytes/1024:.1f}KB")
    print(f"    Window needed = {bdp_bytes:.0f}B / {mss}B = "
          f"{pkts_needed:.1f} MSS")
    print(f"    Without Window Scale: max=64KB {'OK' if 64*1024 >= bdp_bytes else 'INSUFFICIENT'}")

    import math
    p = 0.01
    formula_bw = mss / (rtt * math.sqrt(p))
    print(f"\n  Throughput formula with p={p*100:.0f}% loss:")
    print(f"    BW ≈ MSS/(RTT×√p) = {mss}/({rtt}×{math.sqrt(p):.2f})")
    print(f"       = {formula_bw/1e3:.0f} kb/s ≈ {formula_bw/1e6:.2f} Mb/s")
    print(f"    vs bottleneck: {bw_bps/1e6:.0f} Mb/s  → loss severely limits TCP Reno")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: TCP Echo Server (runnable)
# ─────────────────────────────────────────────────────────────────────────────

TCP_HOST = '127.0.0.1'
TCP_PORT = 5001
UDP_PORT = 5002

def tcp_echo_server():
    """Minimal TCP echo server — mirrors the lecture code exactly."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((TCP_HOST, TCP_PORT))
    srv.listen(5)
    print(f"[TCP server] Listening on {TCP_HOST}:{TCP_PORT}")
    while True:
        conn, addr = srv.accept()
        print(f"[TCP server] Connection from {addr}")
        with conn:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                conn.sendall(data)
        print(f"[TCP server] Connection from {addr} closed")


def tcp_echo_client():
    """Minimal TCP echo client."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((TCP_HOST, TCP_PORT))
        messages = [b'hello from ec441\n', b'transport layer\n', b'goodbye\n']
        for msg in messages:
            s.sendall(msg)
            echo = recv_exact(s, len(msg))
            print(f"[TCP client] Sent: {msg.strip()!r}  Echo: {echo.strip()!r}")
    print("[TCP client] Connection closed")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: UDP Echo Server/Client (runnable)
# ─────────────────────────────────────────────────────────────────────────────

def udp_echo_server():
    """Minimal UDP echo server — stateless, no accept/listen."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind((TCP_HOST, UDP_PORT))
    print(f"[UDP server] Listening on {TCP_HOST}:{UDP_PORT}")
    while True:
        data, addr = srv.recvfrom(1024)
        print(f"[UDP server] Datagram from {addr}: {data.strip()!r}")
        srv.sendto(data, addr)


def udp_echo_client():
    """Minimal UDP echo client."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    messages = [b'hello udp\n', b'ec441 transport\n', b'stateless!\n']
    for msg in messages:
        s.sendto(msg, (TCP_HOST, UDP_PORT))
        data, addr = s.recvfrom(1024)
        print(f"[UDP client] Sent: {msg.strip()!r}  Echo: {data.strip()!r}")
    s.close()
    print("[UDP client] Done")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Framing Patterns
# ─────────────────────────────────────────────────────────────────────────────

def recv_exact(sock, n):
    """Read exactly n bytes from a TCP socket. Core framing primitive."""
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(f"connection closed: got {len(buf)}/{n} bytes")
        buf += chunk
    return buf


def send_length_prefixed(sock, msg: bytes):
    """Length-prefix framing: 4-byte big-endian length header + payload."""
    header = struct.pack('>I', len(msg))
    sock.sendall(header + msg)


def recv_length_prefixed(sock) -> bytes:
    """Receive a length-prefixed message from a TCP socket."""
    header = recv_exact(sock, 4)
    length = struct.unpack('>I', header)[0]
    return recv_exact(sock, length)


def section5_framing():
    print("\n" + "=" * 65)
    print("SECTION 5: TCP Framing Patterns")
    print("=" * 65)

    print("""
  TCP is a byte stream — recv(N) may return 1..N bytes.
  Applications must implement framing to reconstruct messages.

  ─── Pattern 1: Fixed-length messages ───────────────────────
  def recv_exact(sock, n):
      buf = b''
      while len(buf) < n:
          chunk = sock.recv(n - len(buf))
          if not chunk: raise ConnectionError("closed early")
          buf += chunk
      return buf

  ─── Pattern 2: Length-prefix framing ───────────────────────
  # Sender:
  header = struct.pack('>I', len(msg))   # 4-byte big-endian length
  sock.sendall(header + msg)

  # Receiver:
  length = struct.unpack('>I', recv_exact(sock, 4))[0]
  msg = recv_exact(sock, length)

  ─── Pattern 3: Delimiter framing ───────────────────────────
  # HTTP uses \\r\\n\\r\\n to end headers; Content-Length for body
  # Simple newline protocol:
  buf = b''
  while b'\\n' not in buf:
      buf += sock.recv(1024)
  line, rest = buf.split(b'\\n', 1)

  ─── Three socket traps (from lecture) ──────────────────────
  1. SO_REUSEADDR: always set on servers or port stuck in TIME_WAIT
  2. recv(N) is a hint: may return fewer bytes; always use recv_exact
  3. sendall vs send: send() may partial-write; sendall() loops for you
""")

    # Demo the length-prefix framing with a loopback socket pair
    print("  Demo: length-prefix framing over loopback socket pair")

    messages = [b"hello", b"world from EC441", b"transport layer protocol"]

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(('127.0.0.1', 15001))
    server_sock.settimeout(3)
    server_sock.listen(1)

    results = []

    def server_thread():
        try:
            conn, _ = server_sock.accept()
            conn.settimeout(2)
            received = []
            for _ in messages:
                msg = recv_length_prefixed(conn)
                received.append(msg)
            results.extend(received)
            conn.close()
        except Exception as e:
            results.append(f"server error: {e}".encode())
        finally:
            server_sock.close()

    t = threading.Thread(target=server_thread, daemon=True)
    t.start()

    time.sleep(0.1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(('127.0.0.1', 15001))
    for msg in messages:
        send_length_prefixed(client, msg)
    client.close()
    t.join(timeout=3)

    for sent, received in zip(messages, results):
        ok = "✓" if sent == received else "✗"
        print(f"    {ok} sent={sent!r} received={received!r}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: setsockopt Reference
# ─────────────────────────────────────────────────────────────────────────────

def section6_setsockopt():
    print("\n" + "=" * 65)
    print("SECTION 6: setsockopt Reference")
    print("=" * 65)

    options = [
        ("SO_REUSEADDR",  "socket",  "SOL_SOCKET",  "Allow rebind after close/TIME_WAIT. Always set on servers."),
        ("TCP_NODELAY",   "socket",  "IPPROTO_TCP", "Disable Nagle's algorithm. Required for interactive/RPC apps."),
        ("SO_KEEPALIVE",  "socket",  "SOL_SOCKET",  "Periodic probes on idle connections. Detects dead peers."),
        ("SO_RCVBUF",     "bytes",   "SOL_SOCKET",  "Receive buffer size. Increase for high-BDP paths (TCP window)."),
        ("SO_SNDBUF",     "bytes",   "SOL_SOCKET",  "Send buffer size. Limits how much can be in-flight."),
        ("SO_BROADCAST",  "socket",  "SOL_SOCKET",  "Allow sending to broadcast address. UDP only."),
        ("IP_TTL",        "int",     "IPPROTO_IP",  "Set IP TTL for outgoing packets. Affects traceroute."),
    ]

    print(f"\n  {'Option':<18} {'Level':<14} {'Use when'}")
    print("  " + "-" * 72)
    for opt, arg, level, desc in options:
        print(f"  {opt:<18} {level:<14} {desc}")

    print("""
  ─── Nagle's algorithm ───────────────────────────────────────
  If unACKed data is in flight, buffer small writes until ACK arrives,
  then flush everything accumulated as one segment.

  Benefit: reduces header overhead on slow links (40 bytes per 1-byte write!)
  Cost:    adds latency equal to one RTT for the first small write

  Disable with TCP_NODELAY for:
    - SSH / interactive terminals (each keystroke must echo immediately)
    - RPC / database clients (request can't sit waiting for an ACK)
    - Real-time games (position updates must go out immediately)

  Enable (default) for:
    - Bulk file transfers (large writes aren't affected)
    - Any app where bandwidth efficiency > latency

  ─── setsockopt usage ────────────────────────────────────────
  import socket
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

  # Disable Nagle
  s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

  # Allow address reuse
  s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

  # Enlarge receive buffer (useful for satellite / high-BDP links)
  s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: TCP vs UDP Socket API Comparison
# ─────────────────────────────────────────────────────────────────────────────

def section7_tcp_vs_udp():
    print("\n" + "=" * 65)
    print("SECTION 7: TCP vs UDP Socket API Comparison")
    print("=" * 65)

    comparison = [
        ("Socket type",     "SOCK_STREAM",     "SOCK_DGRAM"),
        ("Connection setup","listen/accept",   "none"),
        ("Per-conn socket", "yes (accept)",    "no (one socket)"),
        ("send data",       "send/sendall",    "sendto(data, addr)"),
        ("recv data",       "recv(N)",         "recvfrom(N)"),
        ("Message boundary","none (stream)",   "preserved per datagram"),
        ("Ordering",        "guaranteed",      "none"),
        ("Reliability",     "kernel handles",  "app's responsibility"),
        ("Framing needed",  "yes (app layer)", "no (datagrams preserved)"),
        ("Typical use",     "HTTP SSH Git",    "DNS QUIC games video"),
    ]

    print(f"\n  {'Aspect':<22} {'TCP':<26} {'UDP'}")
    print("  " + "-" * 70)
    for aspect, tcp, udp in comparison:
        print(f"  {aspect:<22} {tcp:<26} {udp}")

    print("""
  ─── The full read+write loop ────────────────────────────────
  # shell 1: capture
  sudo tcpdump -i lo -w /tmp/sockets.pcap 'port 5001 or port 5002'

  # shell 2: servers
  python3 this_file.py tcp-server &
  python3 this_file.py udp-server &

  # shell 3: clients
  python3 this_file.py tcp-client
  python3 this_file.py udp-client

  # shell 1: stop capture
  sudo pkill tcpdump

  # Analyze:
  import pyshark
  cap = pyshark.FileCapture('/tmp/sockets.pcap')
  for p in cap:
      print(p.highest_layer, p.length, p.transport_layer)

  The resulting pcap contains:
    Ethernet frame (L08) carrying
    IP datagram (L14-L17) carrying
    TCP/UDP segment (L18-L20) carrying
    bytes written by your own Python code.
  You wrote the app. You captured the traffic. You can explain every field.
""")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "tcp-server":
            tcp_echo_server()
        elif mode == "tcp-client":
            time.sleep(0.3)
            tcp_echo_client()
        elif mode == "udp-server":
            udp_echo_server()
        elif mode == "udp-client":
            time.sleep(0.3)
            udp_echo_client()
        else:
            print(f"Unknown mode: {mode}")
            print("Usage: python3 lab.py [tcp-server|tcp-client|udp-server|udp-client]")
    else:
        # Reference mode: print all sections
        section1_scapy_reference()
        section2_mininet_reference()
        section5_framing()
        section6_setsockopt()
        section7_tcp_vs_udp()
        print("\n" + "=" * 65)
        print("EC 441 Lecture 22 Lab complete.")
        print("To run the echo servers/clients:")
        print("  python3 this_file.py tcp-server   (in terminal 1)")
        print("  python3 this_file.py tcp-client   (in terminal 2)")
        print("  python3 this_file.py udp-server   (in terminal 1)")
        print("  python3 this_file.py udp-client   (in terminal 2)")
        print("=" * 65)