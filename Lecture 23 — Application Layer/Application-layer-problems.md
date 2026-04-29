# EC 441 — Lecture 23 Problem Set: Application Layer — Design Patterns, DNS, HTTP, and QUIC

**Topic:** Application Layer: Design Patterns, DNS, HTTP, and QUIC
**Lecture:** 23
**Covers:** Protocol design axes, client–server vs P2P, DNS resolution chain, HTTP/1.1 → HTTP/2 → HTTP/3, MIME types, WebSocket, email protocols

---

## Problem 1: Protocol Design Axes

Characterize each protocol below by naming it along all six design axes: interaction model, state, encoding, direction, connection lifetime, and architecture.

| Protocol     | Interaction | State | Encoding | Direction | Connection | Architecture |
|-------------|-------------|-------|----------|-----------|------------|--------------|
| HTTP/1.1    |             |       |          |           |            |              |
| HTTP/2      |             |       |          |           |            |              |
| HTTP/3/QUIC |             |       |          |           |            |              |
| DNS (UDP)   |             |       |          |           |            |              |
| BitTorrent  |             |       |          |           |            |              |
| WebSocket   |             |       |          |           |            |              |
| SMTP        |             |       |          |           |            |              |

**(b)** HTTP is stateless on the wire, yet users stay "logged in" across many requests and across browser restarts. Explain the full mechanism — who stores what, where — and why this design decision is critical for load balancing.

**(c)** A student claims "DNS is distributed, therefore it is P2P." Identify the flaw. How does DNS actually distribute authority, and why does that distinction matter?

### Solution

**(a)**

| Protocol     | Interaction       | State    | Encoding | Direction    | Connection    | Architecture      |
|-------------|-------------------|----------|----------|--------------|---------------|-------------------|
| HTTP/1.1    | request/response  | stateless| text     | pull         | semi-persistent (keep-alive) | client–server |
| HTTP/2      | request/response  | stateless| binary   | pull + server push | persistent (mux) | client–server |
| HTTP/3/QUIC | request/response  | stateless| binary   | pull         | persistent (mux, UDP) | client–server |
| DNS (UDP)   | request/response  | stateless| binary   | pull         | short-lived (single UDP) | hierarchical |
| BitTorrent  | request/response  | stateful (peer lists) | binary | push+pull | persistent (swarm) | peer-to-peer |
| WebSocket   | push/pub-sub      | stateful | binary   | bidirectional| long-lived    | client–server     |
| SMTP        | request/response  | stateful (session) | text | push | persistent per relay | client–server |

**(b)** HTTP itself carries no session memory — each TCP exchange is independent. Session state is stored in two complementary places: the **client** holds a cookie (a short opaque token set by the server via `Set-Cookie`), and the **server** (or a shared database/cache) stores the session record keyed on that token. On every subsequent request, the browser automatically appends the cookie; the server looks up the session record and reconstructs identity. The critical architectural consequence: because the wire protocol is stateless, **any server replica can handle any request** — no stickiness required. A load balancer can send request N to server A and request N+1 to server B; both find the same session in the shared database. This is the foundational design decision that makes horizontal scaling possible.

**(c)** The flaw is conflating "distributed" with "peer-to-peer." DNS is **hierarchically delegated**, not a P2P mesh. Authority flows down a strict tree: root servers → TLD servers → second-level zone servers → sub-zone servers. Each level is operated by a small, known set of entities, and delegation is explicit (NS records). A P2P system has no authority hierarchy and no single coordinator — nodes are symmetric. DNS has the opposite structure: every delegation step has a single authoritative source (even if that source is replicated for availability). The distinction matters for trust and consistency: DNS gives deterministic answers with a clear chain of responsibility; a P2P system cannot guarantee a canonical answer.

---

## Problem 2: DNS Resolution

A browser on a laptop running in Boston opens `www.cs.bu.edu`. The laptop's DNS cache is cold (empty), but the recursive resolver at 1.1.1.1 has the `.edu` TLD servers cached.

**(a)** List every DNS query and response that occurs, naming the sender, receiver, query type, and query name for each exchange. Indicate which steps the laptop participates in and which it does not.

**(b)** The authoritative zone for `bu.edu` sets the A record TTL for `www.cs.bu.edu` to 300 seconds. The TLD server's NS record for `bu.edu` has TTL 172800 seconds. Explain why the difference exists and what would change operationally if both were set to 30 seconds.

**(c)** A sysadmin runs `dig +trace www.cs.bu.edu` and sees the following in the output:
```
.             518400  IN  NS  a.root-servers.net.
edu.          172800  IN  NS  a.edu-servers.net.
bu.edu.       172800  IN  NS  dns1.bu.edu.
www.cs.bu.edu. 300    IN  A   128.197.x.x
```
Identify the record type, TTL policy, and caching implication for each line. At what level does caching give the most performance benefit, and why?

**(d)** A company wants DNS lookups from employees to be private from their ISP. Name two protocols that address this, explain how they differ technically, and identify a scenario where each is the better choice.

### Solution

**(a)** Exchange sequence:

| # | Sender | Receiver | Type | Name | Direction |
|---|--------|----------|------|------|-----------|
| 1 | Laptop (stub) | 1.1.1.1 (recursive resolver) | A | www.cs.bu.edu | Laptop → Resolver |
| 2 | 1.1.1.1 | a.root-servers.net | NS | edu | Resolver → Root |
| 3 | a.root-servers.net | 1.1.1.1 | NS referral | bu.edu | Root → Resolver |
| 4 | 1.1.1.1 | a.edu-servers.net | NS | bu.edu | Resolver → TLD (SKIPPED — cached) |
| 5 | a.edu-servers.net | 1.1.1.1 | NS referral | cs.bu.edu/www | TLD → Resolver (SKIPPED — cached) |
| 6 | 1.1.1.1 | dns1.bu.edu | A | www.cs.bu.edu | Resolver → Auth |
| 7 | dns1.bu.edu | 1.1.1.1 | A answer | 128.197.x.x | Auth → Resolver |
| 8 | 1.1.1.1 | Laptop | A answer | 128.197.x.x | Resolver → Laptop |

The laptop participates only in steps 1 and 8. Steps 2–7 are between the recursive resolver and authoritative servers; the laptop never sees them. Because the resolver has `.edu` TLD servers cached, steps 4–5 may be skipped entirely.

**(b)** The A record TTL is short (300 s = 5 min) because web server IPs change: failover events, CDN reconfiguration, and load balancer updates require rapid propagation. A short TTL means DNS caches stale the old address for at most 5 minutes. The NS TTL is long (48 hours) because the identity of BU's authoritative name servers is extremely stable — changing them requires deliberate admin action and wide propagation time. If both were 30 seconds: every 30 seconds, resolvers worldwide would re-query root and TLD servers for `bu.edu` delegation — a massive amplification of query load on stable infrastructure. Root servers serve ~10^12 queries/day already; eliminating caching at the NS level would overwhelm them.

**(c)** Line analysis:

- **`.` NS a.root-servers.net, TTL 518400 (6 days):** Root hints change extremely rarely (once every few years); a 6-day cache is safe and dramatically reduces root server load.
- **`edu. NS a.edu-servers.net, TTL 172800 (48 hours):** TLD server identity is stable; 48-hour cache avoids constant re-querying of root servers.
- **`bu.edu. NS dns1.bu.edu, TTL 172800 (48 hours):** Zone NS records stable; cached at the resolver so repeated lookups for any `*.bu.edu` name skip root/TLD entirely.
- **`www.cs.bu.edu A 128.197.x.x, TTL 300 (5 min):** Leaf record; short TTL allows rapid failover.

The largest performance benefit comes from caching the **NS records** (TLD and zone levels). Once a resolver has `bu.edu NS dns1.bu.edu` cached, *every* subsequent lookup for any `bu.edu` name skips root and TLD queries entirely — potentially millions of root queries avoided per day for a popular domain.

**(d)** **DNS over TLS (DoT, port 853):** wraps DNS in TLS before sending. Network-visible as a TLS stream on a non-standard port. **Best for:** corporate networks with a known, trusted DoT resolver — network admins can easily configure and audit it; its non-443 port makes it distinguishable for monitoring. **DNS over HTTPS (DoH, port 443):** wraps DNS in an HTTPS connection, indistinguishable from regular web traffic to a network observer. **Best for:** individual users who want privacy even from their own network operator (e.g., on a hostile or monitored Wi-Fi); the HTTPS camouflage prevents ISP-level filtering. DoH is controversial in enterprise settings because it bypasses local DNS policy.

---

## Problem 3: HTTP Evolution

**(a)** Explain precisely what "head-of-line blocking at the application layer" means in HTTP/1.1. What workaround did browsers adopt, and what was its cost?

**(b)** HTTP/2 fixes application-layer HOL blocking. Describe the mechanism (multiplexing + binary framing). Then explain why HTTP/2 does *not* fix HOL blocking entirely, and at which layer the remaining problem lives.

**(c)** A page loads 1 HTML document plus 200 sub-resources (images, CSS, JS). Estimate, qualitatively, the number of TCP connections required under HTTP/1.1 (no pipelining), HTTP/2, and HTTP/3. Explain the key difference.

**(d)** QUIC runs over UDP, not TCP. Explain three concrete things QUIC provides that vanilla UDP does not, and why building them on UDP (rather than modifying TCP) was the right architectural choice.

**(e)** Fill in the table:

| Version | Transport | Wire | Problem solved | Problem left |
|---------|-----------|------|----------------|--------------|
| HTTP/1.1 | | | | |
| HTTP/2  | | | | |
| HTTP/3  | | | | |

### Solution

**(a)** HTTP/1.1 pipelining allows sending multiple requests on one TCP connection before receiving responses, but **responses must be delivered in request order**. If the first-requested resource is slow to generate (e.g., a database query), every faster resource queued behind it is blocked — it cannot be delivered out of order. This is HOL blocking at the **application layer** (distinct from TCP-level HOL). Browsers abandoned pipelining in practice and instead opened **6+ parallel TCP connections per origin**. Cost: 6× the connection overhead (SYN/SYN-ACK/ACK, TLS handshakes), increased server load, and port exhaustion at scale.

**(b)** HTTP/2 sends all requests and responses as small **binary frames** tagged with a stream ID. Many streams share one TCP connection; frames from different streams interleave freely. A slow stream's response frames do not block other streams — the client reassembles each stream independently. This eliminates app-level HOL. The remaining problem is **TCP-level HOL blocking**: TCP delivers bytes in order. A single lost TCP segment causes the OS to withhold all subsequent bytes from the application — including bytes from completely unrelated HTTP/2 streams — until the missing segment is retransmitted and received. HTTP/2 cannot fix this because the problem is below the HTTP layer, inside the kernel's TCP implementation.

**(c)** 
- **HTTP/1.1:** Browsers open ~6 TCP connections per origin. 200 sub-resources → resources pipeline in groups of 6 with HOL degradation; realistic: ~6 simultaneous connections, sub-resources queued.
- **HTTP/2:** 1 TCP connection per origin, all 200 sub-resources as concurrent streams. Zero additional handshakes after the first connection.
- **HTTP/3:** 1 QUIC connection per origin. Same 1-connection-for-all model as HTTP/2, but each stream is independently reliable — a lost packet stalls only its stream, not all 200.

**(d)** Three things QUIC adds over raw UDP: **(1) Reliable, ordered delivery per stream** — QUIC implements its own retransmission and acknowledgment logic, so application data is guaranteed to arrive in order, just like TCP, but independently per stream. **(2) Built-in TLS 1.3** — QUIC integrates the cryptographic handshake into the transport handshake; one round-trip establishes both the connection and encryption. **(3) Connection migration** — QUIC identifies connections by a connection ID, not by (src IP, src port); a client moving from WiFi to cellular keeps the same QUIC connection alive. Why UDP: TCP semantics are baked into every router, NAT, and middlebox on the internet — a "modified TCP" would be dropped or mangled by middleboxes that enforce TCP assumptions. UDP is a thin datagram service that middleboxes leave alone. Building reliability in user space on top of UDP means a browser update can deploy new transport behavior to a billion users overnight, with no kernel patches required.

**(e)**

| Version | Transport | Wire | Problem solved | Problem left |
|---------|-----------|------|----------------|--------------|
| HTTP/1.1 | TCP | text (ASCII) | — (baseline); keep-alive reduces handshakes | App-layer HOL blocking; 6-conn workaround |
| HTTP/2 | TCP | binary | App-layer HOL (multiplexed streams) | TCP-layer HOL blocking on packet loss |
| HTTP/3 | QUIC (UDP) | binary | TCP-layer HOL blocking; TLS built in; 0-RTT; connection migration | Post-quantum crypto (future); middlebox compatibility |

---

## Problem 4: Email Architecture

**(a)** A student at BU sends an email from Gmail to a friend's `@bu.edu` address. List every protocol involved, naming the direction (client→server, server→server), the port used, and what each hop accomplishes.

**(b)** The student accesses Gmail in a browser. They never configure an SMTP or IMAP client. Are SMTP and IMAP involved in delivering this message? Explain the full protocol path, distinguishing what the browser speaks vs what Google's infrastructure speaks.

**(c)** Why has email been slow to evolve compared to HTTP? Give two structural reasons from the lecture.

### Solution

**(a)** Protocol path (Gmail → BU):

| # | From | To | Protocol | Port | Purpose |
|---|------|----|----------|------|---------|
| 1 | Browser | Gmail web app (Google) | HTTPS | 443 | User submits message via web UI |
| 2 | Google mail server | Google SMTP relay | SMTP (internal) | 25/587 | Internal submission |
| 3 | Google SMTP | BU MX server | SMTP (server-to-server) | 25 | Relay across providers |
| 4 | BU MX server | BU mail storage | SMTP (internal) | 25 | Deliver to mailbox |
| 5 | BU mail client / webmail | BU IMAP server | IMAP | 143/993 | Recipient reads mail |

**(b)** Yes, SMTP and IMAP are involved — but the student's **browser never speaks them**. The browser speaks **HTTPS (JSON-over-HTTP) to Google's web application**. Google's backend servers then use SMTP to relay the message to BU's mail servers (step 3 above) and IMAP internally to manage Google's own mail storage. From the user's perspective, it's all HTTPS; SMTP and IMAP are hidden inside Google's infrastructure. This is the "browser complication" — webmail vendors present a modern HTTPS API while the underlying wire protocols between mail servers remain unchanged.

**(c)** Two structural reasons: **(1) Large, heterogeneous public wire surface.** SMTP between mail servers is a public protocol: Google, Microsoft, BU, and thousands of other providers must all interoperate. Any change requires coordinated adoption across all participants simultaneously — a coordination problem far harder than HTTP, where a single browser vendor and CDN can deploy a new version unilaterally. **(2) Strong backward-compatibility pressure.** Billions of deployed mail servers implement RFC 5321 (SMTP) as written. Breaking changes risk dropping mail between providers. HTTP could evolve via HTTP/2 and HTTP/3 because both sides of a connection (browser + CDN) could be updated in lockstep; mail lacks this synchronized upgrade path.

---

## Problem 5: WebSocket and the Limits of Request/Response

**(a)** A multiplayer browser game needs to push real-time position updates (50 per second) from the server to all connected clients. Explain why HTTP/1.1 polling, HTTP/2 server push, and finally WebSocket are progressively better fits for this workload.

**(b)** Write the HTTP upgrade request and 101 response that establish a WebSocket connection to `wss://game.example.com/positions`. Include all required headers.

**(c)** After the WebSocket upgrade, what protocol runs on the connection? Can the server send frames without a prior client request? Does TLS still apply?

### Solution

**(a)** HTTP/1.1 polling: client sends GET every N milliseconds. At 50 updates/second, the client must poll at ≥50 Hz — each poll is a full request/response round trip, adding latency equal to RTT and wasting bandwidth on empty responses when no update occurred. Latency is bounded below by the polling interval, not by network RTT. HTTP/2 server push: the server can proactively send resources, but server push was designed for static assets known at request time (CSS, images), not for unbounded event streams; it was deprecated in browsers precisely because it doesn't fit real-time streaming well. WebSocket: after the one-time upgrade handshake, the connection is **persistent and bidirectional** — the server can push a frame to the client **at any time**, with no polling, no repeated request overhead, and latency limited only by network RTT. Exactly right for 50 updates/second.

**(b)**
```
Client → Server (upgrade request):
GET /positions HTTP/1.1
Host: game.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
Origin: https://game.example.com

Server → Client (101 response):
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```

**(c)** After the upgrade, the connection runs the **WebSocket framing protocol (RFC 6455)** — a lightweight binary/text frame format — not HTTP. The server **can** send frames at any time without a prior client request; this is the defining feature. TLS still applies: `wss://` (WebSocket Secure) means the underlying TCP connection is wrapped in TLS, exactly like HTTPS. The WebSocket frames flow inside the encrypted TLS record layer.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 23 notes.*