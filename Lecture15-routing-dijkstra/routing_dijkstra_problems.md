# EC 441 — Lecture 15 Problem Set: Link-State Routing and Dijkstra's Algorithm

**Topic:** Routing — Link State and Dijkstra's Algorithm  
**Lecture:** 15  
**Covers:** Graph representation, Dijkstra's algorithm, shortest-path trees, forwarding tables, OSPF, oscillation problem

---

## Problem 1: Graph Representation and OSPF Costs

A network has five routers with the following links and bandwidths:

| Link    | Bandwidth  |
|---------|------------|
| A – B   | 100 Mb/s   |
| A – C   | 10 Mb/s    |
| B – D   | 1 Gb/s     |
| C – D   | 100 Mb/s   |
| B – E   | 10 Mb/s    |
| D – E   | 100 Mb/s   |

**(a)** Compute the OSPF cost for each link using the formula `cost = 10⁸ / B` (B in b/s).

**(b)** Draw the weighted graph (nodes = routers, edges = links, weights = OSPF costs).

**(c)** Which link has the lowest cost? What does that mean for routing?

**(d)** If the reference bandwidth is raised to 10⁹ b/s instead of 10⁸, recompute the cost of each link. Why would an operator make this change?

### Solution

**(a)** OSPF costs (reference = 10⁸):

| Link  | Bandwidth | Cost = 10⁸ / B        |
|-------|-----------|-----------------------|
| A–B   | 10⁸ b/s   | 10⁸ / 10⁸ = **1**    |
| A–C   | 10⁷ b/s   | 10⁸ / 10⁷ = **10**   |
| B–D   | 10⁹ b/s   | 10⁸ / 10⁹ = **0.1 → 1** (OSPF floors at 1) |
| C–D   | 10⁸ b/s   | 10⁸ / 10⁸ = **1**    |
| B–E   | 10⁷ b/s   | 10⁸ / 10⁷ = **10**   |
| D–E   | 10⁸ b/s   | 10⁸ / 10⁸ = **1**    |

**(b)** Weighted graph:
```
    A ---1--- B ---1--- D
    |         |         |
   10        10         1
    |         |         |
    C ---1--- +    E ---+
              \---10---/
```
More precisely:
- A–B: 1, A–C: 10, B–D: 1, C–D: 1, B–E: 10, D–E: 1

**(c)** Links A–B, B–D, C–D, and D–E all share the lowest cost of 1. A router will prefer paths that use these high-bandwidth links, since lower cost = higher bandwidth = lower transmission delay.

**(d)** Costs with reference = 10⁹:

| Link  | Cost = 10⁹ / B              |
|-------|-----------------------------|
| A–B   | 10⁹ / 10⁸ = **10**         |
| A–C   | 10⁹ / 10⁷ = **100**        |
| B–D   | 10⁹ / 10⁹ = **1**          |
| C–D   | 10⁹ / 10⁸ = **10**         |
| B–E   | 10⁹ / 10⁷ = **100**        |
| D–E   | 10⁹ / 10⁸ = **10**         |

Raising the reference bandwidth creates **finer granularity** between link speeds. With reference 10⁸, a 100 Mb/s and 1 Gb/s link both round to cost 1 — indistinguishable to the algorithm. With reference 10⁹, the Gigabit link gets cost 1 while Fast Ethernet gets cost 10. An operator makes this change when the network has Gigabit or 10-Gigabit links that need to be differentiated.

---

## Problem 2: Dijkstra's Algorithm by Hand

Run Dijkstra's algorithm on the following 7-node network with source node **A**:

Edge costs:
- A–B: 4, A–C: 2
- B–D: 5, B–E: 1
- C–D: 8, C–F: 10
- D–G: 2
- E–D: 2, E–G: 6
- F–G: 3

**(a)** Fill in the step-by-step trace table (columns: N′, D(B), D(C), D(D), D(E), D(F), D(G), node selected).

**(b)** Draw the shortest-path tree rooted at A.

**(c)** Derive A's forwarding table (destination, next hop, cost, full path).

### Solution

**Initialization:**
- N′ = {A}
- D(B) = 4 (p=A), D(C) = 2 (p=A), D(D) = ∞, D(E) = ∞, D(F) = ∞, D(G) = ∞

**Step-by-step trace:**

| Step | N′            | D(B)  | D(C)  | D(D)   | D(E)  | D(F)   | D(G)   | Select |
|------|---------------|-------|-------|--------|-------|--------|--------|--------|
| Init | {A}           | 4,A   | 2,A   | ∞      | ∞     | ∞      | ∞      | —      |
| 1    | {A,C}         | 4,A   | —     | 10,C   | ∞     | 12,C   | ∞      | C      |
| 2    | {A,C,B}       | —     | —     | 9,B    | 5,B   | 12,C   | ∞      | B      |
| 3    | {A,C,B,E}     | —     | —     | 7,E    | —     | 12,C   | 11,E   | E      |
| 4    | {A,C,B,E,D}   | —     | —     | —      | —     | 12,C   | 9,D    | D      |
| 5    | {A,C,B,E,D,G} | —     | —     | —      | —     | 12,C   | —      | G      |
| 6    | {all}         | —     | —     | —      | —     | —      | —      | F      |

**Relaxation notes:**
- Step 1 (select C, cost 2): C→D: 2+8=10; C→F: 2+10=12
- Step 2 (select B, cost 4): B→D: 4+5=9 < 10 ✓ update; B→E: 4+1=5
- Step 3 (select E, cost 5): E→D: 5+2=7 < 9 ✓ update; E→G: 5+6=11
- Step 4 (select D, cost 7): D→G: 7+2=9 < 11 ✓ update
- Step 5 (select G, cost 9): G has no unfinalized neighbors with improvement
- Step 6 (select F, cost 12): F is finalized

**(b)** Shortest-path tree rooted at A:
```
A --2--> C --10--> F
|
4
|
v
B --1--> E --2--> D --2--> G
```
Paths:
- A→B: direct (cost 4)
- A→C: direct (cost 2)
- A→B→E→D: (cost 7)
- A→B→E: (cost 5)
- A→C→F: (cost 12)
- A→B→E→D→G: (cost 9)

**(c)** Forwarding table at router A:

| Destination | Next Hop | Cost | Full Path        |
|-------------|----------|------|------------------|
| B           | B        | 4    | A → B            |
| C           | C        | 2    | A → C            |
| D           | B        | 7    | A → B → E → D   |
| E           | B        | 5    | A → B → E        |
| F           | C        | 12   | A → C → F        |
| G           | B        | 9    | A → B → E → D → G |

Note: A only stores the **next hop**, not the full path. All traffic to D, E, G goes out the B interface; all traffic to C, F goes out the C interface.

---

## Problem 3: Link Failure and Reconvergence

Using the same network from Problem 2, suppose the link **B–E fails**.

**(a)** Which destinations in A's forwarding table are affected?

**(b)** Re-run Dijkstra from A with B–E removed. What are the new shortest paths to D, E, and G?

**(c)** What is the cost increase to reach each affected destination? Which destination suffers the largest detour?

**(d)** Describe the sequence of events in OSPF after B–E fails: what messages are sent, in what order, before A's forwarding table is updated?

### Solution

**(a)** With B–E removed, destinations D, E, and G are affected (their shortest paths all used B→E as a segment).

**(b)** Re-run Dijkstra from A, graph without B–E:

Re-initialization: D(B)=4, D(C)=2, others ∞.

| Step | Select | Key updates |
|------|--------|-------------|
| 1    | C (2)  | D(D)=10 via C, D(F)=12 via C |
| 2    | B (4)  | D(D)=9 via B–D (4+5=9 < 10) |
| 3    | D (9)  | D(G)=11 via D–G (9+2=11) |
| 4    | F (12) | no improvement |
| 5    | G (11) | finalized |
| 6    | E: only reachable via D: D(E) via D→E? No direct D→E in original — B–E was the only path to E |

Wait — checking the original edges: B–E and E–D and E–G. Without B–E, can E be reached?
- From A: A→B→D (cost 9), then D←E (cost 2, undirected), so A→B→D→E = 9+2 = **11**
- Or A→C→D (cost 10) then D→E = 10+2 = **12**
- Best path to E: A→B→D→E = **11**

New shortest paths:

| Destination | New Path             | New Cost | Old Cost |
|-------------|----------------------|----------|----------|
| D           | A → B → D            | 9        | 7        |
| E           | A → B → D → E        | 11       | 5        |
| G           | A → B → D → G        | 11       | 9        |

**(c)** Cost increases:

| Destination | Old Cost | New Cost | Increase |
|-------------|----------|----------|----------|
| D           | 7        | 9        | +2       |
| E           | 5        | 11       | **+6**   |
| G           | 9        | 11       | +2       |

**E suffers the largest detour** (+6), because it was only reachable through B–E, which is now gone. It must now take a long path through D.

**(d)** OSPF reconvergence sequence after B–E fails:

1. **Failure detection:** Router B stops receiving Hello packets from E on that interface. After the dead interval (default 40 s), B declares E's adjacency down.
2. **LSA generation:** B generates a new LSA with an incremented sequence number, removing the B–E link from its advertisement.
3. **LSA flooding:** B sends the new LSA out all its other interfaces. Each router that receives it — first A and D — stores it and re-floods it out all interfaces except the one it arrived on (minus duplicates by sequence number).
4. **LSDB update:** Every router in the area updates its link-state database with B's new LSA.
5. **SPF recomputation:** Each router independently re-runs Dijkstra on the updated topology.
6. **Forwarding table update:** Each router installs the new routes. A's forwarding table now reflects the paths from part (b).

Typical total time: **1–10 seconds** (dominated by dead interval if not using BFD; much faster with Bidirectional Forwarding Detection).

---

## Problem 4: Negative Weights Break Dijkstra

**(a)** Construct a 4-node example (nodes A, B, C, D) with one negative edge weight that causes Dijkstra to produce an incorrect shortest path.

**(b)** Trace through Dijkstra's steps on your example, showing exactly where it goes wrong.

**(c)** Explain *why* the greedy invariant breaks with negative weights.

### Solution

**(a)** Graph with negative edge:
- A–B: 3
- A–C: 2
- C–B: -2   ← negative edge
- B–D: 1

True shortest paths from A:
- A→B: min(3, 2 + (−2)) = min(3, 0) = **0** via A→C→B
- A→C: 2
- A→D: 0 + 1 = **1** via A→C→B→D

**(b)** Dijkstra trace:

| Step | N′      | D(B) | D(C) | D(D) | Select |
|------|---------|------|------|------|--------|
| Init | {A}     | 3,A  | 2,A  | ∞    | —      |
| 1    | {A,C}   | 3,A  | —    | ∞    | C (cost 2) |
| 2    | After relaxing C's neighbors: C→B: 2+(−2)=0 < 3 → D(B)=0,C | — | | |
| 2    | {A,C,B} | 0,C  | —    | ∞    | B (cost 0) ← **but B was already "finalized" as cost 3 in step 1 if we had selected it** |

The issue: Dijkstra selects the minimum-cost unfinalized node each step. With all non-negative weights, once a node is finalized its distance can't decrease. But with C→B = −2:
- At step 1, we correctly finalize C with cost 2.
- We then relax C→B, correctly updating D(B) to 0.
- We finalize B with cost 0 — this actually works here.

The real danger: if B had been finalized *before* C was processed (because 3 < 2 is false here, but construct it as: A–B: 1, A–C: 3, C–B: −5, B–D: 1):
- Dijkstra finalizes B first (cost 1), then C (cost 3), then relaxes C→B: 3+(−5)=−2 < 1 — but B is already finalized! The update is silently discarded, giving D(D) = 1+1 = 2. True shortest: A→C→B→D = 3−5+1 = −1. **Wrong answer.**

**(c)** The greedy invariant states: when we finalize node w (minimum D(w)), no future path can improve on D(w) — because all remaining unfinalized nodes have D ≥ D(w), and adding positive edges only increases cost. A negative edge breaks this: a future path through an unfinalized node could use a negative edge to swing back to w with a lower cost, but w is already locked in. Dijkstra can't "go back" and revise finalized distances.

---

## Problem 5: OSPF Areas and the Oscillation Problem

**(a)** A large ISP has 500 routers in one OSPF area. Estimate how many LSAs each router stores and the total LSA messages generated by a single link failure. Why is this a problem?

**(b)** An operator notices that during peak hours, traffic oscillates between two paths every few minutes. What is likely causing this? Describe two ways to fix it without eliminating dynamic routing.

**(c)** Router A has two equal-cost paths to prefix 10.10.0.0/24 (cost 5 each). How should A handle traffic to this prefix? What is this called?

### Solution

**(a)** In a single OSPF area, every router stores one LSA per router (each router advertises its own links). With 500 routers:
- **LSAs stored per router:** 500 (one per router in the area)
- **Total LSA messages per flooding event:** When one router generates a new LSA, each router that receives it re-floods it out all interfaces except the one it arrived on. In the worst case, a flooding event generates O(|V| × |E|) messages — for 500 routers with ~1000 links, that's potentially **thousands of LSA messages** propagating network-wide.

This is a problem because: (1) every router must run Dijkstra (O(V²) or O((V+E) log V)) on every topology change — 500 routers means large computation, (2) flooding 500-router LSDBs consumes bandwidth, and (3) any transient instability (flapping link) can cause a flood of recomputations. OSPF areas exist to contain this — flooding and SPF computation stay local to each area.

**(b)** This is the **oscillation problem** caused by load-sensitive link costs. When path 1 becomes congested its cost rises, all routers shift traffic to path 2, path 2 becomes congested, routers shift back — the cycle repeats.

Two fixes:
1. **Use static bandwidth-based costs (standard OSPF practice).** Costs based on link capacity never change due to traffic load. Load balancing is achieved by provisioning, not dynamic re-routing.
2. **Dampen cost updates with long time constants.** Use an exponentially weighted moving average of link load, updated infrequently (e.g., every 5–10 minutes). By the time costs change, traffic has already redistributed, reducing the swing amplitude. This doesn't eliminate oscillation but reduces its frequency and magnitude.

**(c)** When two equal-cost paths exist, the router should **split traffic across both paths** — sending some flows via one and some via another. This is called **ECMP (Equal-Cost Multi-Path) routing**. OSPF supports ECMP natively; the router installs both next hops in its forwarding table for the same prefix. Traffic is typically split per-flow (using a hash of source/destination IP and port) to preserve packet ordering within a flow.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 15 notes.*