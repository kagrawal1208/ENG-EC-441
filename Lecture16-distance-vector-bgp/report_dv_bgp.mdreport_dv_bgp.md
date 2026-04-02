# Why the Internet Needs Two Different Routing Protocols

**EC 441 — Lecture 16 Report**  
*Topic: Why distance-vector routing exists, what it gets wrong, and why BGP governs the internet's boundaries*

---

## Introduction

The internet runs two fundamentally different kinds of routing protocols simultaneously. Inside an organization — a university, a data center, a corporate campus — OSPF computes shortest paths using Dijkstra's algorithm and a complete map of the local topology. Between organizations, BGP does something almost entirely different: it doesn't compute shortest paths at all. It enforces contractual business relationships.

Understanding why both exist, and why one cannot replace the other, is the core insight of Lecture 16.

---

## The Bellman-Ford Equation: Routing Without a Map

Dijkstra's algorithm requires the full graph to be present in one place before computation begins. This works in a link-state network because every router floods its local topology everywhere, eventually giving every router the complete picture. But flooding requires bandwidth proportional to the number of links and routers, and every router must store and process the entire LSDB.

The Bellman-Ford approach takes the opposite position: **no router ever needs the full topology**. Each router only needs two things — the cost of its own directly connected links, and what its immediate neighbors claim as their best distances to each destination. The Bellman-Ford equation formalizes this:

```
d_x(y) = min over all neighbors v { c(x,v) + d_v(y) }
```

This is dynamic programming. The correctness rests on optimal substructure: if the shortest path from x to y passes through neighbor v, then the segment of that path from v to y must itself be the shortest path from v to y. If it weren't, you could substitute the cheaper sub-path and contradict the optimality of the original. This property means that each router, armed only with its neighbors' best estimates, can iteratively converge on the globally correct answer.

The result is the distance-vector algorithm: initialize with only directly connected costs, exchange distance vectors with neighbors, update using the Bellman-Ford equation whenever a better path is discovered, and repeat until no changes occur. The network converges in at most |V|-1 rounds because the longest shortest path in a graph with V nodes traverses at most V-1 edges, and each round of exchange extends knowledge by one hop.

---

## Good News Travels Fast, Bad News Travels Slow

The distance-vector algorithm has a fundamental asymmetry in how it handles topology changes. When a link cost *decreases* (good news), improvements propagate quickly: the router that detects the improvement updates its DV, sends it to neighbors, and the benefit ripples outward within a few rounds. Convergence is fast.

When a link *fails* (bad news), something much worse can happen. Consider the simplest case: A–B–C, all links cost 1. A routes to C via B (cost 2). The B–C link fails. B detects the failure and checks its neighbors — it sees A's DV, which says D_A(C) = 2. B computes: "I can reach C via A for cost 1+2=3!" This is wrong — A's route to C goes through B, the very link that just failed. B has used stale information that depends on itself.

The loop then runs: B tells A that D_B(C) = 3. A updates to 1+3 = 4. B updates to 1+4 = 5. Costs increment by 1 every round, counting toward infinity. Packets for C bounce between A and B until their TTL expires. This is the **count-to-infinity problem**, and it is the defining weakness of distance-vector routing.

**Split horizon** partially fixes this by prohibiting a router from advertising a route back to the neighbor it learned that route from. If A routes to C via B, A simply omits C from the DV it sends to B. When B–C fails and B checks A's advertisement, A doesn't mention C, so B can't form the false route. **Poisoned reverse** is more aggressive: A actively advertises D_A(C) = ∞ to B, making the impossibility explicit rather than silent.

Both fixes work only for two-node loops. In a three-or-more-node loop, the stale information can flow through non-adjacent routers and circumvent both countermeasures. This is why RIP caps the maximum hop count at 15 (16 = unreachable): it bounds the counting problem at the cost of limiting usable network diameter to 15 hops.

---

## Why One Routing Algorithm Cannot Run the Entire Internet

At some point in the 1980s and early 1990s, network engineers recognized that neither OSPF nor RIP could scale to the entire internet. The barriers are not technical — they are structural.

**Scale** is the first barrier. OSPF requires every router to store the full topology. The global internet has over 75,000 independently administered networks and hundreds of millions of IP prefixes. An OSPF LSDB of this size would require enormous memory and generate flooding traffic that would consume significant bandwidth on every link, every time any topology change occurred anywhere.

**Administrative autonomy** is the second barrier. Different organizations have legitimately different routing goals. A university optimizes for latency to research networks. A mobile carrier optimizes for cost. A CDN optimizes for proximity to users. No single metric satisfies all of these simultaneously, and no organization wants an external party to define how traffic flows through its own network.

**Business relationships** are the third and most important barrier. Routing between organizations is fundamentally economic. An ISP is paid by its customers to carry their traffic globally. Two competing ISPs may have a "peering" relationship where they carry each other's traffic for free — but only for their *direct* customers, not as transit for third parties. A Tier-1 ISP will not carry a competitor's customer traffic for free across its backbone.

OSPF has no mechanism to express any of this. It knows link costs and computes shortest paths. The shortest path might traverse a competitor's network, or might exit through a less-preferred provider, or might violate a contractual obligation. BGP exists because routing at internet scale is a *policy* problem, not a *shortest-path* problem.

---

## BGP: Policy Over Optimality

BGP's central innovation is the **path vector**. Where distance-vector protocols advertise a distance (a number), BGP advertises the complete AS-PATH — the sequence of autonomous systems a packet would traverse to reach a destination. This serves two purposes simultaneously: it provides loop detection (any router that sees its own ASN in an incoming path simply discards the route) and it gives each AS enough information to make policy decisions based on who is in the path, not just how long it is.

The two fundamental BGP business relationships are **customer-provider** (the customer pays the provider for global reachability) and **peer-peer** (two networks exchange traffic for free, but only for their own customers, not as transit). These relationships produce the **valley-free rule**: a valid BGP path goes up from a customer to a provider, across at most one peer-to-peer link, then back down from a provider to a customer. Traffic never goes down then back up — that would mean using a provider's network to carry traffic for another provider without compensation.

The consequence is that BGP routing is not optimal in any geometric sense. The best BGP path is the one that satisfies business contracts, not the one with the lowest latency or highest bandwidth. A packet from Boston to London might traverse a path that adds 20ms of latency because the "shorter" path would cross a competitor's network without a transit agreement. This is not a bug — it is a deliberate design decision that makes the internet's economic model function.

---

## BGP's Brittleness: When Policy Fails

BGP is trust-based. Every AS trusts its neighbors' route announcements. If a neighbor announces a false route — whether through misconfiguration or malice — that announcement can propagate globally before anyone detects it, because BGP has no cryptographic mechanism to verify that an AS is actually the legitimate originator of a prefix.

The 2008 Pakistan Telecom incident illustrates this. Pakistan Telecom announced a more-specific prefix (/25) for YouTube's IP block (/24). BGP's longest-prefix-match rule caused routers globally to prefer the more-specific announcement — sending all YouTube traffic to Pakistan Telecom, where it was dropped. YouTube was unreachable for roughly two hours. The "fix" required manually withdrawing the false announcement, which required human coordination across multiple networks.

The 2021 Facebook outage is more instructive. Facebook's own engineers withdrew BGP routes for all Facebook-owned prefixes during a configuration change. Because Facebook's DNS servers, management systems, and internal infrastructure were all accessed via those BGP routes, withdrawing them made everything simultaneously unreachable and unmanageable — engineers couldn't log in remotely to fix the problem. The outage lasted six hours. The lesson: BGP affects not just external connectivity but the operational infrastructure needed to manage the network itself.

RPKI (Resource Public Key Infrastructure) provides a cryptographic fix for origin validation — an AS can publish a signed certificate proving it is the authorized originator of its prefixes. But RPKI adoption, like IPv6 adoption, has been uneven and slow despite clear technical benefits.

---

## The Routing Landscape in Full

The routing architecture of the internet is now complete across Lectures 13–16:

Within an AS, OSPF provides fast, loop-free shortest-path routing using Dijkstra's algorithm on a complete topology. RIP provides simpler but slower distance-vector routing for small networks. Between ASes, BGP provides policy-based path-vector routing that reflects business relationships rather than geometric optimality.

This three-protocol architecture is not elegant — it's a layered accumulation of solutions to problems that became apparent only as the internet grew. OSPF replaced RIP inside networks because count-to-infinity was operationally intolerable. BGP emerged because OSPF couldn't express policy. Each layer solves the problems the layer below couldn't handle, at the cost of additional complexity.

The Bellman-Ford equation, with its beautiful recursive structure based on optimal substructure, powers one of these layers. Its limitations — the need for multiple rounds of exchange, the susceptibility to count-to-infinity — drove the development of the alternatives. Understanding why the limitations exist is as important as understanding the algorithm itself.

---

*Generated with assistance from Claude (Anthropic). Based on EC 441 Lecture 16 notes.*