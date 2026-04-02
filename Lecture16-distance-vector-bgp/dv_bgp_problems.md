# EC 441 — Lecture 16 Problem Set: Distance Vector, Bellman-Ford, and BGP

**Topic:** Routing — Distance Vector, Bellman-Ford, and BGP  
**Lecture:** 16  
**Covers:** Bellman-Ford equation, DV algorithm convergence, count-to-infinity, split horizon/poisoned reverse, RIP, autonomous systems, BGP path vectors and business relationships

---

## Problem 1: The Bellman-Ford Equation

Consider the following 5-node network:

```
    A ---2--- B ---3--- E
    |         |
    4         1
    |         |
    C ---5--- D
```

Edge costs: A–B: 2, A–C: 4, B–D: 1, B–E: 3, C–D: 5

**(a)** Write the Bellman-Ford equation for d_A(E).

**(b)** Compute d_B(E) and d_C(E) first, then solve d_A(E). Show each step.

**(c)** What is the shortest path from A to E and its cost? Trace the predecessor pointers.

**(d)** Why does the Bellman-Ford equation rely on "optimal substructure"? Give a one-sentence explanation in your own words.

### Solution

**(a)** A's neighbors are B and C:

```
d_A(E) = min{ c(A,B) + d_B(E),  c(A,C) + d_C(E) }
       = min{ 2 + d_B(E),       4 + d_C(E) }
```

**(b)** Work bottom-up:

**d_B(E):** B's neighbors are A, D, E:
- Via E directly: c(B,E) = 3 → d_B(E) via E = 3
- Via D: c(B,D) + d_D(E). d_D(E) via B→E would be circular; D has no direct link to E. So no improvement from D.
- d_B(E) = **3** (direct link B–E)

**d_C(E):** C's neighbors are A and D:
- Via A: c(C,A) + d_A(E) — circular (depends on what we're computing)
- Via D: c(C,D) + d_D(E). d_D(E) via B = c(D,B) + d_B(E) = 1 + 3 = 4
- d_C(E) = 5 + 4 = **9**

**d_A(E):**
```
d_A(E) = min{ 2 + 3,   4 + 9 }
       = min{ 5,       13 }
       = 5 via B
```

**(c)** Path: **A → B → E**, cost **5**.  
Predecessor pointers: p(E) = B, p(B) = A. Follow back: E ← B ← A.

**(d)** Optimal substructure means that if the shortest path from A to E passes through B, then the portion of that path from B to E must itself be the shortest path from B to E — if there were a shorter sub-path, you could substitute it and get a shorter full path, contradicting the optimality of the original.

---

## Problem 2: Distance Vector Convergence Trace

Use the lecture's 5-node network (same as slides):

```
    A ---1--- B ---2--- C
         \       /
          3     1
           \   /
            \ /
             D ---5--- E
              \
               3
                \
                 (B-D cost 3, C-D cost 1 from slide topology)
```

Exact edge costs: A–B: 1, A–C: 4, B–C: 2, B–D: 3, C–D: 1 (wait — use the slide's graph exactly):

**Graph:** A–B:1, A–C:4, B–C:2, B–D:3, C–E:1, D–E:5

**(a)** Fill in the Round 0 distance table (each node knows only its direct links).

**(b)** Fill in the Round 1 table after one full exchange of DVs. Show at least two update calculations explicitly.

**(c)** How many rounds until convergence? What is A's final forwarding table?

### Solution

Using exact lecture graph: A–B:1, A–C:4, B–C:2, B–D:3, C–E:1, D–E:5.

**(a) Round 0 — initialization:**

|   | A | B | C | D | E |
|---|---|---|---|---|---|
| **A** | 0 | 1 | 4 | ∞ | ∞ |
| **B** | 1 | 0 | 2 | 3 | ∞ |
| **C** | 4 | 2 | 0 | ∞ | 1 |
| **D** | ∞ | 3 | ∞ | 0 | 5 |
| **E** | ∞ | ∞ | 1 | 5 | 0 |

**(b) Round 1 — after first exchange:**

Each node receives its neighbors' DVs and applies the Bellman-Ford equation.

**Node A updates** (neighbors: B, C):
- D_A(C) = min{4, c(A,B)+D_B(C)} = min{4, 1+2} = **3** via B (improved!)
- D_A(D) = min{∞, c(A,B)+D_B(D)} = min{∞, 1+3} = **4** via B (new!)
- D_A(E) = min{∞, c(A,C)+D_C(E)} = min{∞, 4+1} = **5** via C (new!)

**Node D updates** (neighbors: B, E):
- D_D(A) = min{∞, c(D,B)+D_B(A)} = min{∞, 3+1} = **4** via B (new!)
- D_D(C) = min{∞, c(D,B)+D_B(C)} = min{∞, 3+2} = **5** via B (new!)

| Round 1 | A | B | C | D | E | Changes |
|---------|---|---|---|---|---|---------|
| **A** | 0 | 1 | 3 | 4 | 5 | C:4→3 via B; D:∞→4 via B; E:∞→5 via C |
| **B** | 1 | 0 | 2 | 3 | 3 | E:∞→3 via C |
| **C** | 3 | 2 | 0 | 3 | 1 | A:4→3 via B; D:∞→3 via E (5+?) — wait: D_C(D) via E = 1+5=6; via B = 2+3=5 → **5** |
| **D** | 4 | 3 | 5 | 0 | 5 | A:∞→4 via B; C:∞→5 via B |
| **E** | 5 | 3 | 1 | 5 | 0 | A:∞→5 via C; B:∞→3 via C |

**(c)** Round 2 sees D_A(E) improve from 5 to 4 (via B→E: 1+3=4). After Round 2, all costs are stable → **converged in 2–3 rounds**.

**A's final forwarding table:**

| Destination | Next Hop | Cost | Path |
|-------------|----------|------|------|
| B | B | 1 | A→B |
| C | B | 3 | A→B→C |
| D | B | 4 | A→B→D |
| E | B | 4 | A→B→E |

All destinations route through B — A's only low-cost neighbor.

---

## Problem 3: Count-to-Infinity and Its Fixes

Consider a linear network: **A — B — C**, with A–B cost 1 and B–C cost 1. The B–C link fails.

**(a)** Trace the count-to-infinity problem step-by-step for 6 rounds after the failure. Show D_B(C) and D_A(C) at each step.

**(b)** Show how **split horizon** prevents the loop. What does A advertise to B after the failure?

**(c)** Show how **poisoned reverse** prevents the loop. What does A advertise to B?

**(d)** A network has four routers in a loop: A–B–C–D–A. A link fails inside the loop. Why do split horizon and poisoned reverse *not* fully solve count-to-infinity in this case?

### Solution

**(a) Count-to-infinity trace:**

Before failure: D_A(C) = 2 via B, D_B(C) = 1 direct.

| Round | D_B(C) | D_A(C) | What happened |
|-------|--------|--------|---------------|
| 0 (before) | 1 | 2 via B | Normal |
| 1 | 3 via A | 2 | B detects failure, sees D_A(C)=2, sets D_B(C)=1+2=3. Wrong — A's route goes through B! |
| 2 | 3 | 4 via B | A gets D_B(C)=3, updates D_A(C)=1+3=4 |
| 3 | 5 via A | 4 | B gets D_A(C)=4, updates D_B(C)=1+4=5 |
| 4 | 5 | 6 via B | A updates: 1+5=6 |
| 5 | 7 | 6 | B updates: 1+6=7 |
| 6 | 7 | 8 | ... counting to infinity |

Packets for C bounce between A and B — a routing loop.

**(b) Split horizon fix:**

Rule: "Don't advertise a route back to the neighbor you learned it from."

A routes to C **via B**, so A does **not** include C in the DV it sends to B. When B's link to C fails, B checks its neighbors' DVs. A's advertisement to B does not include C at all. B therefore cannot learn a (false) route to C from A, and correctly sets D_B(C) = **∞**.

Convergence happens in 1 round instead of counting to infinity.

**(c) Poisoned reverse fix:**

Rule: "If you route to C via B, tell B your distance to C is ∞."

A routes to C via B → A tells B: D_A(C) = **∞** (poison). When B's link to C fails, it checks A's advertisement and sees D_A(C) = ∞. B cannot route through A to reach C, so it correctly sets D_B(C) = ∞ immediately. Poisoned reverse is more aggressive than split horizon — it actively lies rather than staying silent.

**(d) Why loops with 3+ nodes are not fixed:**

Split horizon and poisoned reverse only prevent a node from advertising a route back to the *direct* neighbor it learned it from. In a 4-node loop A–B–C–D–A, if the A–B link fails:
- C learned about A via B, so C poisons B's route to A.
- But D does *not* route to A via B (D routes via A directly or via C), so D still advertises a valid-looking route to A when queried by B.
- B can now use D's advertisement to construct a false route to A: B→D→C→B (a loop).

The root cause is that split horizon only breaks 2-node loops. Larger loops require the stale routing information to "time out" via hold-down timers or maximum hop count — hence RIP's max of 15.

---

## Problem 4: RIP Parameters and Autonomous Systems

**(a)** RIP uses hop count as its metric with a maximum of 15. A path requires 12 hops. The B–D link goes down and the only alternative path is 17 hops. What does RIP do? What happens to traffic?

**(b)** An AS has the following properties: it has two upstream ISPs (for redundancy), does not carry traffic for other organizations, and is a university. What AS type is it? Explain.

**(c)** Distinguish between iBGP and the use case for BGP at an AS boundary. Why can OSPF not replace BGP for inter-AS routing?

**(d)** A BGP router receives an UPDATE message with the AS-PATH: [701, 1239, 3356, 111]. Its own ASN is 1239. What does it do and why?

### Solution

**(a)** RIP treats hop count 16 as infinity — unreachable. Since the alternative path is 17 hops, RIP considers the destination **unreachable (∞)** and withdraws the route. Traffic to that destination is **dropped** until an alternative path within 15 hops is found or the topology changes. This is the fundamental limitation of RIP's 15-hop maximum — networks larger than 15 hops diameter are simply unsupportable.

**(b)** A university with two upstream ISPs is a **multi-homed stub AS**. It is:
- **Multi-homed**: connected to multiple ISPs for redundancy
- **Stub**: does not carry transit traffic for third parties; all traffic either originates from or is destined for the university itself

**(c)** OSPF cannot replace BGP for inter-AS routing for three reasons: (1) **Scale** — OSPF requires every router to store the full topology; with 75,000+ ASes and millions of prefixes, the LSDB would be impossibly large. (2) **Administrative autonomy** — different organizations run different policies; OSPF has no mechanism to express "carry traffic for my customers but not for my competitors." (3) **Business relationships** — BGP routes based on contractual agreements (customer-provider, peer-peer), not just link costs. BGP is a *policy* protocol; OSPF is a *shortest-path* protocol.

**(d)** The router's own ASN is 1239, which appears in the received AS-PATH. BGP's loop prevention rule says: **if your own ASN appears in the AS-PATH, reject the route**. The router discards this UPDATE entirely. This is how BGP prevents routing loops without count-to-infinity — the path carries its full history, so any loop is immediately detectable.

---

## Problem 5: BGP Business Relationships and the Valley-Free Rule

An ISP topology:
- **AS 1 (Tier-1)** peers with **AS 2 (Tier-1)** (peer relationship, free)
- **AS 3 (Regional ISP)** is a customer of AS 1 (pays AS 1)
- **AS 4 (University)** is a customer of AS 3
- **AS 5 (Startup)** is a customer of AS 2

**(a)** AS 4 wants to send traffic to AS 5. Trace the AS-PATH the packet takes. What type of relationship is crossed at each hop?

**(b)** Would AS 1 carry traffic from AS 3 destined for AS 5? What about AS 2 — would it carry traffic from AS 1 destined for AS 4? Explain using the valley-free rule.

**(c)** AS 3 advertises a route to 10.20.0.0/16 to AS 1. Should AS 1 re-advertise this route to AS 2? What about to AS 3's other customers (if it has any)?

**(d)** Briefly explain how the 2021 Facebook outage relates to BGP. What should Facebook have done to prevent it?

### Solution

**(a)** Traffic from AS 4 to AS 5:

AS-PATH: **4 → 3 → 1 → 2 → 5**

| Hop | Relationship |
|-----|-------------|
| AS 4 → AS 3 | Customer → Provider (AS 4 pays AS 3) |
| AS 3 → AS 1 | Customer → Provider (AS 3 pays AS 1) |
| AS 1 → AS 2 | Peer → Peer (free exchange) |
| AS 2 → AS 5 | Provider → Customer (AS 5 pays AS 2) |

This is a valid **valley-free path**: traffic goes up (customer→provider), across one peering link, then down (provider→customer). No valley (down then up).

**(b)**
- AS 1 **will** carry traffic from AS 3 to AS 5: AS 3 is a customer of AS 1, so AS 1 is paid to carry its traffic. AS 5 is reachable via AS 2 (a peer). This is economically rational.
- AS 2 **will** carry traffic from AS 1 destined for AS 4: AS 1 is a peer of AS 2 — peering traffic is exchanged. AS 4 is a customer of AS 3, which is a customer of AS 1, not of AS 2. However, AS 2 would still forward this traffic down to AS 5 if needed. AS 2 would **not** carry peer→peer→customer→customer traffic that doesn't benefit it economically. The valley-free rule prevents AS 2 from forwarding traffic received from a peer (AS 1) out to another peer or up to a provider — only down to customers.

**(c)**
- **To AS 2 (peer):** Yes — AS 1 should re-advertise AS 3's routes to its peer AS 2, because AS 3 is AS 1's customer, and AS 1 is paid to provide global reachability for AS 3's prefixes.
- **To AS 3's other customers (if any):** Yes — customer routes are advertised globally, including to other customers of the same provider.
- **Back to AS 3:** No — AS 1 should not re-advertise AS 3's own prefix back to AS 3 (split horizon).

**(d)** In October 2021, a Facebook engineer pushed a configuration change that withdrew BGP route advertisements for all Facebook-owned prefixes from the global internet. Facebook's own DNS servers, internal services, and management systems were all behind those BGP routes. Without the routes, DNS could not resolve facebook.com (or any Facebook property), and engineers could not remotely access systems to fix the problem. The outage lasted ~6 hours.

Prevention: Facebook should have had **out-of-band management access** (a separate, independent network path not dependent on their own BGP routes), **staged rollout with automatic rollback**, and **change validation** that checks whether withdrawing routes would break management connectivity before executing.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 16 notes.*