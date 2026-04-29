#!/usr/bin/env python3
"""
EC 441 — Lecture 23 Lab: Application Layer — DNS, HTTP, MIME, and Protocol Design
Covers: DNS resolution simulation, HTTP version comparison, MIME classification,
        BitTorrent mechanism analysis, WebSocket upgrade framing
"""

import socket
import struct
import hashlib
import time
import random
import urllib.request
import urllib.parse
import urllib.error
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Protocol Design Axis Classifier
# ─────────────────────────────────────────────────────────────────────────────

def section1_protocol_classifier():
    print("=" * 65)
    print("SECTION 1: Protocol Design Axis Classifier")
    print("=" * 65)

    protocols = {
        "HTTP/1.1": {
            "interaction":   "request/response",
            "state":         "stateless",
            "encoding":      "text (ASCII)",
            "direction":     "pull",
            "connection":    "semi-persistent (keep-alive)",
            "architecture":  "client-server",
        },
        "HTTP/2": {
            "interaction":   "request/response",
            "state":         "stateless",
            "encoding":      "binary (frames)",
            "direction":     "pull + server push",
            "connection":    "persistent (multiplexed)",
            "architecture":  "client-server",
        },
        "HTTP/3 (QUIC)": {
            "interaction":   "request/response",
            "state":         "stateless",
            "encoding":      "binary (QUIC frames)",
            "direction":     "pull",
            "connection":    "persistent (QUIC streams, UDP)",
            "architecture":  "client-server",
        },
        "DNS (UDP)": {
            "interaction":   "request/response",
            "state":         "stateless",
            "encoding":      "binary",
            "direction":     "pull",
            "connection":    "short-lived (single UDP)",
            "architecture":  "hierarchical",
        },
        "BitTorrent": {
            "interaction":   "request/response",
            "state":         "stateful (peer lists, chunks)",
            "encoding":      "binary",
            "direction":     "push + pull",
            "connection":    "persistent (swarm)",
            "architecture":  "peer-to-peer",
        },
        "WebSocket": {
            "interaction":   "pub-sub / push",
            "state":         "stateful",
            "encoding":      "binary or text frames",
            "direction":     "bidirectional (full-duplex)",
            "connection":    "long-lived",
            "architecture":  "client-server",
        },
        "SMTP": {
            "interaction":   "request/response",
            "state":         "stateful (session)",
            "encoding":      "text (ASCII)",
            "direction":     "push",
            "connection":    "persistent per relay",
            "architecture":  "client-server",
        },
    }

    axes = ["interaction", "state", "encoding", "direction", "connection", "architecture"]
    for name, attrs in protocols.items():
        print(f"\n  {name}")
        for axis in axes:
            print(f"    {axis:<16} {attrs[axis]}")

    print("\n  Key insight: 'stateless + cookie' pattern")
    print("  → HTTP wire is stateless; session lives in cookie jar + server DB")
    print("  → Any server replica can handle any request (enables load balancing)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: DNS Resolution Simulator
# ─────────────────────────────────────────────────────────────────────────────

def section2_dns_simulation():
    print("\n" + "=" * 65)
    print("SECTION 2: DNS Resolution Chain Simulator")
    print("=" * 65)

    # Simulated DNS hierarchy
    dns_tree = {
        "root": {
            "edu":    "a.edu-servers.net",
            "com":    "a.gtld-servers.net",
            "net":    "a.gtld-servers.net",
            "org":    "a.gtld-servers.net",
        },
        "edu": {
            "bu.edu":      "dns1.bu.edu",
            "mit.edu":     "auth-dns.mit.edu",
            "harvard.edu": "ns1.harvard.edu",
        },
        "bu.edu": {
            "www.bu.edu":    "128.197.1.10",
            "www.cs.bu.edu": "128.197.20.5",
            "mail.bu.edu":   "128.197.30.1",
        },
    }

    # Simulated TTL cache
    resolver_cache = {}

    def resolve(fqdn, cold_cache=True):
        if cold_cache:
            resolver_cache.clear()

        print(f"\n  Resolving: {fqdn}")
        print(f"  Stub resolver → recursive resolver (1.1.1.1)")
        steps = 0

        # Check leaf cache
        if fqdn in resolver_cache:
            print(f"  CACHE HIT: {fqdn} → {resolver_cache[fqdn]['value']} (TTL remaining: {resolver_cache[fqdn]['ttl']}s)")
            return resolver_cache[fqdn]["value"]

        # Walk the chain
        parts = fqdn.split(".")
        tld = parts[-1]
        sld = ".".join(parts[-2:])

        # Step 1: Root → TLD NS
        if tld in resolver_cache:
            print(f"  [Cache] TLD '{tld}' NS: {resolver_cache[tld]['value']}")
        else:
            ns = dns_tree["root"].get(tld, "NXDOMAIN")
            print(f"  [1] Resolver → a.root-servers.net  Q: NS {tld}")
            print(f"      Answer: {tld} NS → {ns}")
            resolver_cache[tld] = {"value": ns, "ttl": 518400}
            steps += 1

        # Step 2: TLD → Zone NS
        if sld in resolver_cache:
            print(f"  [Cache] Zone '{sld}' NS: {resolver_cache[sld]['value']}")
        else:
            ns = dns_tree["edu"].get(sld, "NXDOMAIN")
            print(f"  [2] Resolver → {resolver_cache[tld]['value']}  Q: NS {sld}")
            print(f"      Answer: {sld} NS → {ns}")
            resolver_cache[sld] = {"value": ns, "ttl": 172800}
            steps += 1

        # Step 3: Zone auth → A record
        auth_ns = resolver_cache[sld]["value"]
        a_record = dns_tree.get(sld, {}).get(fqdn, "NXDOMAIN")
        print(f"  [3] Resolver → {auth_ns}  Q: A {fqdn}")
        print(f"      Answer: {fqdn} A → {a_record}  TTL=300")
        resolver_cache[fqdn] = {"value": a_record, "ttl": 300}
        steps += 1

        print(f"  Total queries to authoritative servers: {steps}")
        print(f"  Result returned to stub: {a_record}")
        return a_record

    resolve("www.cs.bu.edu", cold_cache=True)
    print("\n  --- Second lookup (warm cache for TLD+zone NS) ---")
    resolve("mail.bu.edu", cold_cache=False)

    print("\n  TTL policy analysis:")
    ttl_data = [
        ("Root hint (NS .)", 518400, "6 days — root servers change once per decade"),
        ("TLD NS (edu)",     172800, "48 h — TLD server identity extremely stable"),
        ("Zone NS (bu.edu)", 172800, "48 h — BU nameserver identity stable"),
        ("A record (web)",   300,    "5 min — allows rapid failover/CDN changes"),
    ]
    for name, ttl, reason in ttl_data:
        print(f"  {name:<28} TTL={ttl:>7}s  {reason}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: HTTP Version Comparison
# ─────────────────────────────────────────────────────────────────────────────

def section3_http_comparison():
    print("\n" + "=" * 65)
    print("SECTION 3: HTTP Version Comparison — HOL Blocking Analysis")
    print("=" * 65)

    def simulate_http1_pipeline(n_resources, slow_index=0, slow_delay_ms=200, base_rtt_ms=30):
        """
        HTTP/1.1 pipelining: responses MUST arrive in request order.
        One slow response blocks all subsequent ones.
        """
        print(f"\n  HTTP/1.1 Pipelining — {n_resources} resources, slow at index {slow_index}")
        total_time = 0
        delivery_times = []
        for i in range(n_resources):
            if i == slow_index:
                delay = slow_delay_ms
            elif i > slow_index:
                # All resources after slow one are blocked until slow one completes
                delay = 0  # already waited
                total_time = max(total_time, slow_delay_ms + base_rtt_ms * slow_index)
            else:
                delay = base_rtt_ms
            total_time += delay if i <= slow_index else base_rtt_ms
            delivery_times.append(total_time)

        # In pipelining, we actually have to wait for all prior responses
        cum_time = 0
        actual_delivery = []
        running_max = 0
        for i in range(n_resources):
            if i == slow_index:
                t = slow_delay_ms
            else:
                t = base_rtt_ms
            cum_time += t
            running_max = max(running_max, cum_time)
            actual_delivery.append(running_max)

        print(f"  Resource delivery times (ms): {actual_delivery[:6]}{'...' if n_resources > 6 else ''}")
        print(f"  Total page load time: {actual_delivery[-1]} ms")
        print(f"  HOL penalty: resource 0 fast={base_rtt_ms}ms, but resource 1 blocked until {actual_delivery[0]}ms")
        return actual_delivery[-1]

    def simulate_http2_multiplex(n_resources, slow_index=0, slow_delay_ms=200, base_rtt_ms=30):
        """
        HTTP/2 multiplexing: independent streams, no HOL at app layer.
        All resources start in parallel; finish when their stream finishes.
        (TCP HOL still exists but ignored here.)
        """
        print(f"\n  HTTP/2 Multiplexing — {n_resources} resources, slow at index {slow_index}")
        delivery_times = []
        for i in range(n_resources):
            t = slow_delay_ms if i == slow_index else base_rtt_ms
            delivery_times.append(t)
        page_load = max(delivery_times)
        print(f"  All streams start simultaneously.")
        print(f"  Max delivery time (page load): {page_load} ms")
        print(f"  Slow resource ({slow_delay_ms}ms) does NOT block others.")
        return page_load

    t1 = simulate_http1_pipeline(10, slow_index=0, slow_delay_ms=200, base_rtt_ms=30)
    t2 = simulate_http2_multiplex(10, slow_index=0, slow_delay_ms=200, base_rtt_ms=30)
    print(f"\n  Speedup (HTTP/2 vs HTTP/1.1 pipelining): {t1/t2:.1f}x")

    print("\n  HTTP version comparison table:")
    rows = [
        ("HTTP/1.1", "TCP", "text",   "App-layer HOL",              "None (open 6+ TCP conns)"),
        ("HTTP/2",   "TCP", "binary", "App-layer HOL fixed (mux)",   "TCP-layer HOL on loss"),
        ("HTTP/3",   "QUIC/UDP", "binary", "TCP-layer HOL fixed",    "Middlebox compat; PQC"),
    ]
    print(f"  {'Version':<10} {'Transport':<10} {'Wire':<8} {'Solved':<30} {'Remaining'}")
    for r in rows:
        print(f"  {r[0]:<10} {r[1]:<10} {r[2]:<8} {r[3]:<30} {r[4]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: MIME Type Classifier and Content-Type Parser
# ─────────────────────────────────────────────────────────────────────────────

def section4_mime_types():
    print("\n" + "=" * 65)
    print("SECTION 4: MIME Type Reference and Parser")
    print("=" * 65)

    mime_db = {
        "text/html":                ("HTML document",        "web page"),
        "text/css":                 ("CSS stylesheet",       "web styling"),
        "text/plain":               ("Plain text",           "generic text"),
        "application/javascript":   ("JavaScript",           "browser scripting"),
        "application/json":         ("JSON",                 "REST APIs, configs"),
        "application/xml":          ("XML",                  "structured data"),
        "application/pdf":          ("PDF",                  "document"),
        "application/octet-stream": ("Binary blob",          "force download"),
        "image/png":                ("PNG image",            "lossless raster"),
        "image/jpeg":               ("JPEG image",           "lossy raster, photos"),
        "image/webp":               ("WebP image",           "modern lossy/lossless"),
        "image/avif":               ("AVIF image",           "AV1-based, high efficiency"),
        "video/mp4":                ("MP4 video",            "streaming, H.264/H.265"),
        "video/webm":               ("WebM video",           "open codec, VP8/VP9/AV1"),
        "audio/mpeg":               ("MP3 audio",            "music streaming"),
        "audio/ogg":                ("Ogg audio",            "open format"),
    }

    def parse_content_type(header_value):
        parts = [p.strip() for p in header_value.split(";")]
        mime = parts[0]
        params = {}
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                params[k.strip()] = v.strip()
        return mime, params

    print("\n  Full MIME reference:")
    print(f"  {'MIME type':<35} {'Description':<20} {'Use case'}")
    print("  " + "-" * 75)
    for mime, (desc, use) in mime_db.items():
        print(f"  {mime:<35} {desc:<20} {use}")

    print("\n  Content-Type header parser:")
    samples = [
        "text/html; charset=UTF-8",
        "application/json; charset=utf-8",
        "image/jpeg",
        "video/mp4; codecs=avc1.42E01E",
        "multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxk",
    ]
    for s in samples:
        mime, params = parse_content_type(s)
        info = mime_db.get(mime, ("Unknown", "—"))
        print(f"  Input:  {s}")
        print(f"  → MIME: {mime}  ({info[0]})")
        if params:
            print(f"  → Params: {params}")
        print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: BitTorrent Mechanism Simulation
# ─────────────────────────────────────────────────────────────────────────────

def section5_bittorrent():
    print("=" * 65)
    print("SECTION 5: BitTorrent Mechanism Simulation")
    print("=" * 65)

    N_CHUNKS = 12
    N_PEERS = 5

    # Simulate chunk availability across peers (0 = don't have, 1 = have)
    random.seed(42)
    peer_chunks = {
        f"peer_{i}": [random.choice([0, 1]) for _ in range(N_CHUNKS)]
        for i in range(N_PEERS)
    }
    # Seed has all chunks
    peer_chunks["seed"] = [1] * N_CHUNKS

    print(f"\n  Swarm: {N_PEERS} peers + 1 seed, {N_CHUNKS} chunks")
    print("\n  Chunk availability map (1=have, 0=missing):")
    for peer, chunks in peer_chunks.items():
        bar = "".join("█" if c else "░" for c in chunks)
        have = sum(chunks)
        print(f"  {peer:<8} [{bar}]  {have}/{N_CHUNKS} chunks")

    # Rarest-first selection
    chunk_counts = [sum(peer_chunks[p][c] for p in peer_chunks) for c in range(N_CHUNKS)]
    rarest_chunk = chunk_counts.index(min(chunk_counts))
    print(f"\n  Chunk popularity (number of peers that have each chunk):")
    print(f"  {chunk_counts}")
    print(f"  Rarest chunk: #{rarest_chunk} (held by {chunk_counts[rarest_chunk]} peers)")
    print(f"  Rarest-first rule: download chunk #{rarest_chunk} first to prevent it dying from swarm")

    # Tit-for-tat simulation
    print("\n  Tit-for-tat choking simulation:")
    upload_rates = {f"peer_{i}": random.randint(0, 100) for i in range(N_PEERS)}
    unchoke_slots = 3  # standard: 3 upload slots
    sorted_peers = sorted(upload_rates.items(), key=lambda x: -x[1])
    print(f"  Peer upload rates (KB/s): {upload_rates}")
    print(f"  Unchoked (top {unchoke_slots} uploaders): {[p for p, _ in sorted_peers[:unchoke_slots]]}")
    print(f"  Choked (free-riders throttled): {[p for p, _ in sorted_peers[unchoke_slots:]]}")
    print(f"  → Free-riders get throttled; incentive to upload is real")

    # Cryptographic chunk verification
    print("\n  Chunk verification via SHA-1 hash:")
    chunks = [f"chunk_{i}_data_bytes".encode() for i in range(3)]
    for i, chunk in enumerate(chunks):
        h = hashlib.sha1(chunk).hexdigest()
        print(f"  Chunk {i}: hash = {h[:20]}...  (stored in .torrent metadata)")
    print("  Any peer can verify any chunk from any source — trust replaced by verification")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: WebSocket Upgrade Framing
# ─────────────────────────────────────────────────────────────────────────────

def section6_websocket_upgrade():
    print("\n" + "=" * 65)
    print("SECTION 6: WebSocket Upgrade Handshake")
    print("=" * 65)

    import base64
    import hashlib

    def generate_ws_key():
        raw = bytes([random.randint(0, 255) for _ in range(16)])
        return base64.b64encode(raw).decode()

    def compute_ws_accept(key):
        MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        combined = (key + MAGIC).encode("utf-8")
        sha1 = hashlib.sha1(combined).digest()
        return base64.b64encode(sha1).decode()

    ws_key = generate_ws_key()
    ws_accept = compute_ws_accept(ws_key)

    print(f"\n  Simulating WebSocket upgrade to wss://game.example.com/positions")
    print(f"\n  Client → Server (HTTP Upgrade request):")
    upgrade_request = f"""GET /positions HTTP/1.1
Host: game.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: {ws_key}
Sec-WebSocket-Version: 13
Origin: https://game.example.com"""
    for line in upgrade_request.split("\n"):
        print(f"  > {line}")

    print(f"\n  Server → Client (101 Switching Protocols):")
    upgrade_response = f"""HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: {ws_accept}"""
    for line in upgrade_response.split("\n"):
        print(f"  < {line}")

    print(f"\n  Key derivation: SHA1(Sec-WebSocket-Key + MAGIC_UUID) → base64")
    print(f"  Key: {ws_key}")
    print(f"  Accept: {ws_accept}")
    print(f"\n  After 101: HTTP ends. RFC 6455 WebSocket frame protocol begins.")
    print(f"  Server can now push frames at any time without a prior client request.")
    print(f"  TLS still applies (wss:// = WebSocket over TLS, like https:// vs http://)")

    # Show a minimal WebSocket frame structure
    print("\n  WebSocket frame layout (RFC 6455):")
    frame_fields = [
        ("FIN (1 bit)",    "1 = last (or only) fragment"),
        ("RSV1-3 (3 bits)","Reserved for extensions"),
        ("Opcode (4 bits)","0x1=text, 0x2=binary, 0x8=close, 0x9=ping, 0xA=pong"),
        ("MASK (1 bit)",   "1 = payload is XOR-masked (required client→server)"),
        ("Payload len",    "7 bits; 126 → next 2 bytes; 127 → next 8 bytes"),
        ("Masking key",    "4 bytes, present if MASK=1"),
        ("Payload data",   "Application data (masked if client→server)"),
    ]
    for field, desc in frame_fields:
        print(f"  {field:<22} {desc}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    section1_protocol_classifier()
    section2_dns_simulation()
    section3_http_comparison()
    section4_mime_types()
    section5_bittorrent()
    section6_websocket_upgrade()

    print("\n" + "=" * 65)
    print("EC 441 Lecture 23 Lab complete.")
    print("=" * 65)