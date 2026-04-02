#!/usr/bin/env python3
"""
EC 441 — Lecture 16 Lab: Distance-Vector Routing, Bellman-Ford, and BGP
========================================================================
Lab objectives:
  1. Implement the distance-vector algorithm from scratch, reproducing the
     lecture's 5-node convergence trace exactly
  2. Simulate the count-to-infinity problem after a link failure
  3. Implement split horizon and poisoned reverse, showing they fix 2-node loops
  4. Simulate BGP AS-PATH loop detection
  5. Model the valley-free routing rule

Usage:
    python3 dv_bgp_lab.py
"""

import math
import copy
from collections import defaultdict


INF = math.inf


# ─────────────────────────────────────────────────────────────
# SECTION 1: Distance-Vector Algorithm (Synchronous simulation)
# ─────────────────────────────────────────────────────────────

class DVRouter:
    def __init__(self, name: str, neighbors: dict):
        """
        name: router label (e.g. 'A')
        neighbors: {neighbor_name: link_cost}
        """
        self.name = name
        self.neighbors = neighbors
        self.all_nodes = None   # set after network is assembled

        # Distance vector: best known cost to each destination
        self.dv = {}
        # Next hop for each destination
        self.next_hop = {}

    def initialize(self, all_nodes: list):
        self.all_nodes = all_nodes
        for node in all_nodes:
            if node == self.name:
                self.dv[node] = 0
                self.next_hop[node] = self.name
            elif node in self.neighbors:
                self.dv[node] = self.neighbors[node]
                self.next_hop[node] = node
            else:
                self.dv[node] = INF
                self.next_hop[node] = None

    def update(self, neighbor_dvs: dict) -> bool:
        """
        Process received DVs from all neighbors.
        Returns True if any entry in this router's DV changed.
        neighbor_dvs: {neighbor_name: {dest: cost}}
        """
        changed = False
        for dest in self.all_nodes:
            if dest == self.name:
                continue
            best = self.dv[dest]
            best_hop = self.next_hop[dest]
            for nbr, nbr_dv in neighbor_dvs.items():
                candidate = self.neighbors[nbr] + nbr_dv.get(dest, INF)
                if candidate < best:
                    best = candidate
                    best_hop = nbr
            if best < self.dv[dest]:
                self.dv[dest] = best
                self.next_hop[dest] = best_hop
                changed = True
        return changed


def run_dv(graph: dict, max_rounds: int = 20, label: str = "") -> dict:
    """
    graph: {node: {neighbor: cost}}
    Returns final distance tables.
    """
    all_nodes = sorted(graph.keys())
    routers = {}
    for node in all_nodes:
        r = DVRouter(node, graph[node])
        r.initialize(all_nodes)
        routers[node] = r

    def fmt(val):
        return "∞" if val == INF else str(val)

    def print_table(round_label):
        header = f"  {'':4}" + "".join(f"{n:^6}" for n in all_nodes)
        print(f"\n  {round_label}")
        print(header)
        print("  " + "-" * len(header.rstrip()))
        for src in all_nodes:
            row = f"  {src:<4}" + "".join(f"{fmt(routers[src].dv[d]):^6}" for d in all_nodes)
            print(row)

    if label:
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")

    print_table("Round 0 (initialization)")

    for rnd in range(1, max_rounds + 1):
        # Collect all current DVs (snapshot — synchronous update)
        snapshots = {n: dict(routers[n].dv) for n in all_nodes}

        # Each router processes its neighbors' DVs
        any_changed = False
        for node in all_nodes:
            nbr_dvs = {nbr: snapshots[nbr] for nbr in routers[node].neighbors}
            changed = routers[node].update(nbr_dvs)
            if changed:
                any_changed = True

        print_table(f"Round {rnd}")
        if not any_changed:
            print(f"\n  Converged after {rnd} round(s)! No changes in this round.")
            break

    return {n: dict(routers[n].dv) for n in all_nodes}


def section1_lecture_example():
    print("=" * 60)
    print("SECTION 1: Lecture 16 Worked Example — 5-node DV")
    print("=" * 60)

    # Lecture graph: A-B:1, A-C:4, B-C:2, B-D:3, C-E:1, D-E:5
    graph = {
        "A": {"B": 1, "C": 4},
        "B": {"A": 1, "C": 2, "D": 3},
        "C": {"A": 4, "B": 2, "E": 1},
        "D": {"B": 3, "E": 5},
        "E": {"C": 1, "D": 5},
    }

    final = run_dv(graph, label="5-node network, source = A for reference")

    print("\n  Final forwarding table at A:")
    routers_ref = {}
    all_nodes = sorted(graph.keys())
    for node in all_nodes:
        r = DVRouter(node, graph[node])
        r.initialize(all_nodes)
        routers_ref[node] = r
    # Re-run to get next hops
    for _ in range(10):
        snapshots = {n: dict(routers_ref[n].dv) for n in all_nodes}
        for node in all_nodes:
            nbr_dvs = {nbr: snapshots[nbr] for nbr in routers_ref[node].neighbors}
            routers_ref[node].update(nbr_dvs)

    a = routers_ref["A"]
    print(f"  {'Dest':<6} {'Next Hop':<10} {'Cost'}")
    print("  " + "-" * 25)
    for dest in sorted(all_nodes):
        if dest == "A":
            continue
        cost = a.dv[dest]
        nh = a.next_hop[dest]
        print(f"  {dest:<6} {str(nh):<10} {cost if cost != INF else '∞'}")


# ─────────────────────────────────────────────────────────────
# SECTION 2: Count-to-Infinity Simulation
# ─────────────────────────────────────────────────────────────

def section2_count_to_infinity():
    print("\n" + "=" * 60)
    print("SECTION 2: Count-to-Infinity Simulation")
    print("=" * 60)

    print("""
  Network: A ---1--- B ---1--- C
  After convergence, B-C link fails.
  Without split horizon, B reads A's stale route and counts up.
    """)

    # Before failure: A-B:1, B-C:1
    dv_a = {"A": 0, "B": 1, "C": 2}   # A→B→C
    dv_b = {"A": 1, "B": 0, "C": 1}   # B→C direct
    dv_c = {"A": 2, "B": 1, "C": 0}

    next_hop_a = {"B": "B", "C": "B"}
    next_hop_b = {"A": "A", "C": "C"}

    print(f"  {'Round':<8} {'D_B(C)':<12} {'D_A(C)':<12} Event")
    print("  " + "-" * 55)
    print(f"  {'Before':<8} {dv_b['C']:<12} {dv_a['C']:<12} Normal operation")

    # B-C link fails
    dv_b["C"] = INF   # B loses direct path
    next_hop_b["C"] = None

    for rnd in range(1, 12):
        # B checks neighbors: only A (C is gone)
        via_a = 1 + dv_a["C"]   # c(B,A) + D_A(C)
        if via_a < dv_b["C"]:
            dv_b["C"] = via_a
            next_hop_b["C"] = "A"

        # A checks neighbors: only B
        via_b = 1 + dv_b["C"]
        if via_b < dv_a["C"]:
            dv_a["C"] = via_b
            next_hop_a["C"] = "B"

        b_cost = dv_b["C"] if dv_b["C"] != INF else "∞"
        a_cost = dv_a["C"] if dv_a["C"] != INF else "∞"
        event = "B detects failure, checks A" if rnd == 1 else "A←B←A routing loop, counts up"
        print(f"  {rnd:<8} {str(b_cost):<12} {str(a_cost):<12} {event}")

        if dv_b["C"] >= 16:
            print(f"\n  RIP would now declare C unreachable (cost ≥ 16 = ∞)")
            break

    print("""
  Root cause: B used A's route to C, not knowing A routes through B.
  Packets for C bounce A→B→A→B... until TTL expires.
    """)


# ─────────────────────────────────────────────────────────────
# SECTION 3: Split Horizon and Poisoned Reverse
# ─────────────────────────────────────────────────────────────

def section3_fixes():
    print("=" * 60)
    print("SECTION 3: Split Horizon and Poisoned Reverse")
    print("=" * 60)

    print("""
  Same failure: A---1---B---1---C, B-C fails.
    """)

    # ── Fix 1: Split Horizon ──
    print("  Fix 1: Split Horizon")
    print("  Rule: Don't advertise a route back to the neighbor you learned it from.")
    print()

    dv_a = {"A": 0, "B": 1, "C": 2}
    dv_b = {"A": 1, "B": 0, "C": 1}
    next_hop_a_c = "B"   # A routes to C via B

    # B-C fails
    dv_b["C"] = INF

    # B checks neighbors (only A available now).
    # With split horizon: A does NOT advertise C to B (since A routes C via B).
    # So B sees no route to C from A.
    # A's DV sent to B omits C (split horizon).
    dv_a_to_b = {"A": 0, "B": 1}   # C omitted — split horizon!

    via_a = 1 + dv_a_to_b.get("C", INF)   # = 1 + INF = INF
    print(f"  After B-C fails, B queries A.")
    print(f"  A's DV advertised to B (split horizon): {dv_a_to_b}")
    print(f"  B's candidate route to C via A: 1 + {dv_a_to_b.get('C', '∞')} = {'∞'}")
    print(f"  B correctly sets D_B(C) = ∞ in 1 round. ✓")

    print()

    # ── Fix 2: Poisoned Reverse ──
    print("  Fix 2: Poisoned Reverse")
    print("  Rule: If A routes to C via B, advertise D_A(C) = ∞ to B (actively lie).")
    print()

    dv_b2 = {"A": 1, "B": 0, "C": 1}
    dv_b2["C"] = INF   # failure

    # A sends its DV to B with C poisoned
    dv_a_to_b_poisoned = {"A": 0, "B": 1, "C": INF}   # poisoned reverse!

    via_a_poisoned = 1 + dv_a_to_b_poisoned["C"]
    print(f"  A's DV advertised to B (poisoned reverse): {{'A':0, 'B':1, 'C':∞}}")
    print(f"  B's candidate route to C via A: 1 + ∞ = ∞")
    print(f"  B correctly sets D_B(C) = ∞ immediately. ✓")

    print()
    print("  Limitation: both fixes only break 2-node loops.")
    print("  In a 3+ node loop, stale routes from non-adjacent routers still cause counting.")


# ─────────────────────────────────────────────────────────────
# SECTION 4: BGP AS-PATH Loop Detection
# ─────────────────────────────────────────────────────────────

def bgp_accept_route(my_asn: int, as_path: list, prefix: str) -> tuple[bool, str]:
    """
    Simulate BGP loop detection.
    Returns (accept, reason).
    """
    if my_asn in as_path:
        return False, f"Rejected: own ASN {my_asn} found in AS-PATH {as_path}"
    return True, f"Accepted: prefix {prefix} via AS-PATH {as_path}"


def section4_bgp():
    print("\n" + "=" * 60)
    print("SECTION 4: BGP AS-PATH Loop Detection and Valley-Free Routing")
    print("=" * 60)

    # ── AS-PATH Loop Detection ──
    print("\n  4a. AS-PATH Loop Detection")
    print("  " + "-" * 45)

    scenarios = [
        (7922,  [1239, 3356, 111],          "128.197.0.0/16"),
        (1239,  [701, 1239, 3356, 111],     "10.0.0.0/8"),      # loop: 1239 in path
        (15169, [7922, 3356, 15169, 701],   "172.16.0.0/12"),   # loop: 15169 in path
        (111,   [7922, 3356],               "203.0.113.0/24"),  # clean
    ]

    for my_asn, path, prefix in scenarios:
        accept, reason = bgp_accept_route(my_asn, path, prefix)
        status = "✓ ACCEPT" if accept else "✗ REJECT"
        print(f"  AS{my_asn} receives route to {prefix}")
        print(f"    AS-PATH: {path}")
        print(f"    {status} — {reason}")
        print()

    # ── Valley-Free Routing ──
    print("  4b. Valley-Free Routing Simulation")
    print("  " + "-" * 45)
    print("""
  Topology:
    AS4 (University) → customer of → AS3 (Regional ISP)
    AS3               → customer of → AS1 (Tier-1)
    AS1               ←→ peer ←→      AS2 (Tier-1)
    AS5 (Startup)     → customer of → AS2

  Traffic: AS4 → AS5
  Valley-free path: AS4 → AS3 → AS1 → AS2 → AS5
    """)

    path = ["AS4", "AS3", "AS1", "AS2", "AS5"]
    relationships = {
        ("AS4", "AS3"): "customer→provider",
        ("AS3", "AS1"): "customer→provider",
        ("AS1", "AS2"): "peer→peer",
        ("AS2", "AS5"): "provider→customer",
    }

    print(f"  {'Hop':<20} {'Relationship'}")
    print("  " + "-" * 45)
    for i in range(len(path) - 1):
        hop = f"{path[i]} → {path[i+1]}"
        rel = relationships.get((path[i], path[i+1]), "unknown")
        print(f"  {hop:<20} {rel}")

    print("""
  Direction: up → up → peer → down → down
  This is valley-free: goes UP then across ONE peer then DOWN. ✓
  A valley would be: down then up (provider→customer then back to provider) — invalid.
    """)

    # ── BGP Incident: Route Hijack ──
    print("  4c. BGP Incident Simulation (Pakistan/YouTube 2008 pattern)")
    print("  " + "-" * 45)

    legitimate = {"208.65.153.0/24": {"as_path": [15169], "origin": "Google/YouTube"}}
    hijack     = {"208.65.153.0/24": {"as_path": [17557], "origin": "Pakistan Telecom"}}
    # More-specific prefix announced
    hijack_specific = {"208.65.153.128/25": {"as_path": [17557], "origin": "Pakistan Telecom (hijack)"}}

    print(f"\n  Legitimate route: 208.65.153.0/24 via AS-PATH {legitimate['208.65.153.0/24']['as_path']}")
    print(f"  Hijack route:     208.65.153.0/24 via AS-PATH {hijack['208.65.153.0/24']['as_path']}")
    print(f"  More-specific:    208.65.153.128/25 via AS-PATH {hijack_specific['208.65.153.128/25']['as_path']}")
    print()
    print("  BGP longest-prefix match: /25 is MORE specific than /24.")
    print("  Routers prefer 208.65.153.128/25 → traffic black-holed to Pakistan Telecom.")
    print("  Fix: RPKI (Resource Public Key Infrastructure) — cryptographically validates")
    print("  that only the legitimate AS can originate a prefix. Prevents unauthorized hijacks.")


# ─────────────────────────────────────────────────────────────
# SECTION 5: LS vs DV Comparison
# ─────────────────────────────────────────────────────────────

def section5_comparison():
    print("\n" + "=" * 60)
    print("SECTION 5: Link-State vs. Distance-Vector Summary")
    print("=" * 60)

    rows = [
        ("Information needed",  "Full graph at one place",       "Only neighbor DVs"),
        ("Computation",         "Centralized per-router (Dijkstra)", "Distributed (BF equation)"),
        ("Communication",       "Flood topology to all",          "Exchange DVs with neighbors"),
        ("Negative weights",    "Not supported",                  "Supported"),
        ("Good news speed",     "Fast (1 flood + recompute)",     "Fast (a few rounds)"),
        ("Bad news speed",      "Fast (same as good news)",       "Slow (count-to-infinity)"),
        ("Loop-free?",          "Yes (full topology known)",      "Not guaranteed during conv."),
        ("Memory",              "Higher (stores full LSDB)",      "Lower (stores only DV)"),
        ("Deployed as",         "OSPF, IS-IS",                    "RIP"),
        ("Scope",               "Intra-AS",                       "Intra-AS"),
    ]

    print(f"\n  {'Property':<28} {'Link-State (OSPF)':<35} {'Distance-Vector (RIP)'}")
    print("  " + "-" * 90)
    for prop, ls, dv in rows:
        print(f"  {prop:<28} {ls:<35} {dv}")

    print("""
  Key takeaway: LS wins on convergence correctness (loop-free, fast bad news).
  DV wins on simplicity and memory. OSPF has largely replaced RIP in production.
  BGP (inter-AS) is a third family: path-vector — neither LS nor DV.
    """)


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    section1_lecture_example()
    section2_count_to_infinity()
    section3_fixes()
    section4_bgp()
    section5_comparison()

    print("=" * 60)
    print("Lab complete.")
    print("=" * 60)