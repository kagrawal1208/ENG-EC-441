#!/usr/bin/env python3
"""
EC 441 — Lecture 15 Lab: Link-State Routing and Dijkstra's Algorithm
=====================================================================
Lab objectives:
  1. Implement Dijkstra's algorithm from scratch matching the lecture pseudocode
  2. Build the 6-node lecture example graph and reproduce the step-by-step trace table
  3. Derive a forwarding table from the resulting shortest-path tree
  4. Simulate link failure and reconvergence — show how forwarding tables change
  5. Demonstrate the oscillation problem with traffic-sensitive costs
  6. Use networkx to cross-validate results and visualize shortest-path trees

Usage:
    pip install networkx matplotlib   (only for Section 6 visualization)
    python3 routing_dijkstra_lab.py
"""

import math
import heapq
from collections import defaultdict


# ─────────────────────────────────────────────────────────────
# SECTION 1: From-Scratch Dijkstra (matches lecture pseudocode)
# ─────────────────────────────────────────────────────────────

def dijkstra(graph: dict, source: str) -> tuple[dict, dict]:
    """
    Dijkstra's algorithm matching the lecture pseudocode.

    graph: adjacency dict  { node: {neighbor: cost, ...}, ... }
    source: starting node

    Returns:
        dist: {node: shortest distance from source}
        prev: {node: predecessor on shortest path}
    """
    # Initialize
    dist = {v: math.inf for v in graph}
    prev = {v: None for v in graph}
    dist[source] = 0

    # Priority queue: (distance, node)
    # Python's heapq is a min-heap, so smallest distance is always at top
    pq = [(0, source)]
    finalized = set()   # equivalent to N' in the lecture

    while pq:
        d, u = heapq.heappop(pq)

        if u in finalized:
            continue        # already finalized with a shorter path
        finalized.add(u)

        # Relax all neighbors of u
        for v, weight in graph[u].items():
            if v in finalized:
                continue
            new_dist = dist[u] + weight
            if new_dist < dist[v]:              # relaxation step
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(pq, (new_dist, v))

    return dist, prev


def reconstruct_path(prev: dict, source: str, target: str) -> list:
    """Walk predecessor pointers back from target to source."""
    path = []
    node = target
    while node is not None:
        path.append(node)
        node = prev[node]
    path.reverse()
    if path[0] != source:
        return []   # no path exists
    return path


def build_forwarding_table(graph: dict, source: str, dist: dict, prev: dict) -> dict:
    """
    Derive forwarding table: for each destination, what is the first hop from source?
    Returns { destination: (next_hop, cost, full_path) }
    """
    table = {}
    for dest in graph:
        if dest == source:
            continue
        path = reconstruct_path(prev, source, dest)
        if len(path) < 2:
            table[dest] = (None, math.inf, [])
        else:
            next_hop = path[1]
            table[dest] = (next_hop, dist[dest], path)
    return table


# ─────────────────────────────────────────────────────────────
# SECTION 2: Reproduce the Lecture 15 Worked Example
# ─────────────────────────────────────────────────────────────

def section2_lecture_example():
    print("=" * 65)
    print("SECTION 2: Lecture 15 Worked Example — 6-node graph, source = u")
    print("=" * 65)

    # Build graph from lecture
    # Nodes: u, v, w, x, y, z
    # Edges: u-v:2, u-w:1, u-x:5, v-y:3, w-y:3, w-z:2, x-z:1, y-z:4
    edges = [
        ("u", "v", 2), ("u", "w", 1), ("u", "x", 5),
        ("v", "y", 3), ("w", "y", 3), ("w", "z", 2),
        ("x", "z", 1), ("y", "z", 4),
    ]
    graph = defaultdict(dict)
    for a, b, cost in edges:
        graph[a][b] = cost
        graph[b][a] = cost   # undirected

    dist, prev = dijkstra(graph, "u")
    table = build_forwarding_table(graph, "u", dist, prev)

    print("\nShortest distances from u:")
    print(f"  {'Destination':<12} {'Cost':<8} {'Predecessor':<12} {'Full Path'}")
    print("  " + "-" * 55)
    for node in sorted(dist):
        if node == "u":
            continue
        path = reconstruct_path(prev, "u", node)
        print(f"  {node:<12} {dist[node]:<8} {str(prev[node]):<12} {' → '.join(path)}")

    print("\nForwarding table at router u:")
    print(f"  {'Destination':<12} {'Next Hop':<10} {'Cost':<6} {'Path'}")
    print("  " + "-" * 55)
    for dest in sorted(table):
        next_hop, cost, path = table[dest]
        print(f"  {dest:<12} {str(next_hop):<10} {cost:<6} {' → '.join(path)}")

    print("\nVerification against lecture trace table:")
    expected = {"v": 2, "w": 1, "x": 4, "y": 4, "z": 3}
    all_ok = True
    for node, exp_cost in expected.items():
        actual = dist[node]
        status = "✓" if actual == exp_cost else f"✗ (expected {exp_cost})"
        print(f"  D({node}) = {actual} {status}")
        if actual != exp_cost:
            all_ok = False
    print(f"\n  {'All costs match lecture!' if all_ok else 'MISMATCH detected!'}")


# ─────────────────────────────────────────────────────────────
# SECTION 3: Step-by-Step Trace (verbose mode)
# ─────────────────────────────────────────────────────────────

def dijkstra_verbose(graph: dict, source: str):
    """
    Same algorithm as above but prints the full step-by-step table,
    matching the format of the lecture trace table.
    """
    nodes = sorted(graph.keys())
    others = [n for n in nodes if n != source]

    dist = {v: math.inf for v in graph}
    prev = {v: None for v in graph}
    dist[source] = 0
    finalized = set()
    pq = [(0, source)]
    step = 0

    def format_cell(node):
        d = dist[node]
        p = prev[node]
        if node in finalized:
            return "—"
        if d == math.inf:
            return "∞"
        return f"{d},{p}"

    # Header
    header = f"{'Step':<6} {'N_prime':<25} " + \
             "".join(f"D({n}),p({n})".ljust(12) for n in others) + "  Select"
    print(header)
    print("-" * len(header))

    def print_row(step_label, selected):
        n_prime_str = "{" + source + ("," if finalized else "") + \
                      ",".join(sorted(finalized)) + "}"
        row = f"{str(step_label):<6} {n_prime_str:<25} " + \
              "".join(format_cell(n).ljust(12) for n in others)
        row += f"  {selected}"
        print(row)

    print_row("Init", "—")

    while pq:
        d, u = heapq.heappop(pq)
        if u in finalized:
            continue
        finalized.add(u)
        step += 1

        for v, weight in graph[u].items():
            if v in finalized:
                continue
            new_dist = dist[u] + weight
            if new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(pq, (new_dist, v))

        print_row(step, f"{u} (cost {d})")

    return dist, prev


def section3_verbose_trace():
    print("\n" + "=" * 65)
    print("SECTION 3: Verbose Step-by-Step Trace")
    print("=" * 65)
    edges = [
        ("u", "v", 2), ("u", "w", 1), ("u", "x", 5),
        ("v", "y", 3), ("w", "y", 3), ("w", "z", 2),
        ("x", "z", 1), ("y", "z", 4),
    ]
    graph = defaultdict(dict)
    for a, b, cost in edges:
        graph[a][b] = cost
        graph[b][a] = cost
    print()
    dijkstra_verbose(graph, "u")


# ─────────────────────────────────────────────────────────────
# SECTION 4: Link Failure and Reconvergence Simulation
# ─────────────────────────────────────────────────────────────

def section4_link_failure():
    print("\n" + "=" * 65)
    print("SECTION 4: Link Failure and Reconvergence")
    print("=" * 65)

    def make_graph(edges):
        g = defaultdict(dict)
        for a, b, cost in edges:
            g[a][b] = cost
            g[b][a] = cost
        return g

    base_edges = [
        ("u", "v", 2), ("u", "w", 1), ("u", "x", 5),
        ("v", "y", 3), ("w", "y", 3), ("w", "z", 2),
        ("x", "z", 1), ("y", "z", 4),
    ]

    # Scenario A: normal topology
    graph_normal = make_graph(base_edges)
    dist_n, prev_n = dijkstra(graph_normal, "u")
    table_n = build_forwarding_table(graph_normal, "u", dist_n, prev_n)

    print("\nNormal topology — forwarding table at u:")
    print(f"  {'Dest':<6} {'Next Hop':<10} {'Cost':<6} {'Path'}")
    print("  " + "-" * 40)
    for dest in sorted(table_n):
        nh, cost, path = table_n[dest]
        print(f"  {dest:<6} {str(nh):<10} {cost:<6} {' → '.join(path)}")

    # Scenario B: link w–z fails
    failed_edge = ("w", "z")
    edges_after_failure = [e for e in base_edges
                           if not (set(e[:2]) == set(failed_edge))]
    graph_failed = make_graph(edges_after_failure)
    dist_f, prev_f = dijkstra(graph_failed, "u")
    table_f = build_forwarding_table(graph_failed, "u", dist_f, prev_f)

    print(f"\nAfter link {failed_edge[0]}–{failed_edge[1]} fails:")
    print(f"  {'Dest':<6} {'Next Hop':<10} {'Cost':<6} {'Path':<30} {'Change'}")
    print("  " + "-" * 65)
    for dest in sorted(table_f):
        nh, cost, path = table_f[dest]
        old_cost = table_n[dest][1]
        old_nh = table_n[dest][0]
        if cost == math.inf:
            change = "UNREACHABLE"
        elif cost != old_cost or nh != old_nh:
            change = f"was cost {old_cost} via {old_nh}"
        else:
            change = "(unchanged)"
        print(f"  {dest:<6} {str(nh):<10} {str(cost):<6} {' → '.join(path):<30} {change}")

    # Scenario C: link u–w also fails (dual failure)
    failed_edge2 = ("u", "w")
    edges_dual = [e for e in edges_after_failure
                  if not (set(e[:2]) == set(failed_edge2))]
    graph_dual = make_graph(edges_dual)
    dist_d, prev_d = dijkstra(graph_dual, "u")
    table_d = build_forwarding_table(graph_dual, "u", dist_d, prev_d)

    print(f"\nDual failure: {failed_edge[0]}–{failed_edge[1]} AND {failed_edge2[0]}–{failed_edge2[1]} both down:")
    print(f"  {'Dest':<6} {'Next Hop':<10} {'Cost':<6} {'Path'}")
    print("  " + "-" * 40)
    for dest in sorted(table_d):
        nh, cost, path = table_d[dest]
        if cost == math.inf:
            print(f"  {dest:<6} {'—':<10} {'∞':<6} (no path)")
        else:
            print(f"  {dest:<6} {str(nh):<10} {cost:<6} {' → '.join(path)}")


# ─────────────────────────────────────────────────────────────
# SECTION 5: OSPF Cost Calculation
# ─────────────────────────────────────────────────────────────

def ospf_cost(bandwidth_bps: int, reference: int = 10**8) -> int:
    """Compute OSPF cost; floor at 1."""
    return max(1, int(reference / bandwidth_bps))


def section5_ospf_costs():
    print("\n" + "=" * 65)
    print("SECTION 5: OSPF Cost Calculator")
    print("=" * 65)

    links = [
        ("10 Mb/s Ethernet",  10 * 10**6),
        ("100 Mb/s Fast Ethernet", 100 * 10**6),
        ("1 Gb/s Ethernet",   10**9),
        ("10 Gb/s Ethernet",  10 * 10**9),
        ("T1 (1.544 Mb/s)",   1_544_000),
        ("OC-3 (155 Mb/s)",   155_520_000),
        ("OC-192 (10 Gb/s)",  9_953_280_000),
    ]

    refs = [10**8, 10**9, 10**10]

    header = f"  {'Link Type':<28}" + "".join(f"{'ref='+str(r//10**6)+'M':<12}" for r in refs)
    print(header)
    print("  " + "-" * (28 + 12 * len(refs)))
    for name, bw in links:
        costs = [ospf_cost(bw, r) for r in refs]
        row = f"  {name:<28}" + "".join(f"{c:<12}" for c in costs)
        print(row)

    print("\n  Note: with reference=10⁸, both 100Mb/s and 1Gb/s have cost 1 —")
    print("  indistinguishable! Raising to 10⁹ gives 1Gb/s cost=1, 100Mb/s cost=10.")

    # Build a network using OSPF costs and find shortest path
    print("\n  Example: route from A to E using OSPF costs (ref=10⁸)")
    link_data = [
        ("A", "B", 100 * 10**6),   # Fast Ethernet
        ("A", "C", 10 * 10**6),    # Ethernet
        ("B", "D", 10**9),         # Gigabit
        ("C", "D", 100 * 10**6),   # Fast Ethernet
        ("B", "E", 10 * 10**6),    # Ethernet
        ("D", "E", 100 * 10**6),   # Fast Ethernet
    ]
    g = defaultdict(dict)
    for a, b, bw in link_data:
        cost = ospf_cost(bw)
        g[a][b] = cost
        g[b][a] = cost

    dist, prev = dijkstra(g, "A")
    table = build_forwarding_table(g, "A", dist, prev)
    print(f"\n  {'Dest':<6} {'Next Hop':<10} {'Cost':<6} {'Path'}")
    print("  " + "-" * 45)
    for dest in sorted(table):
        nh, cost, path = table[dest]
        print(f"  {dest:<6} {str(nh):<10} {cost:<6} {' → '.join(path)}")


# ─────────────────────────────────────────────────────────────
# SECTION 6: Oscillation Problem Demonstration
# ─────────────────────────────────────────────────────────────

def section6_oscillation():
    print("\n" + "=" * 65)
    print("SECTION 6: Oscillation Problem with Load-Sensitive Costs")
    print("=" * 65)

    # Two paths from A to D:
    # Path 1 (direct): A → D  (base cost 1, congested cost 10)
    # Path 2 (via B,C): A → B → C → D  (each link base cost 1, congested cost 10)

    print("""
  Network:  A ---1--- D   (direct link)
            |         |
            B ---1--- C   (indirect path A→B→C→D, total cost 3 when idle)
  
  Traffic-sensitive: if all traffic uses a path, that path's cost rises to 10.
  """)

    def compute_path(graph):
        dist, prev = dijkstra(graph, "A")
        path = reconstruct_path(prev, "A", "D")
        return path, dist["D"]

    idle_graph = defaultdict(dict, {
        "A": {"D": 1, "B": 1},
        "D": {"A": 1, "C": 1},
        "B": {"A": 1, "C": 1},
        "C": {"B": 1, "D": 1},
    })

    print("  Simulating 8 rounds of traffic routing:\n")
    print(f"  {'Round':<8} {'Path Chosen':<30} {'Cost':<6} {'Notes'}")
    print("  " + "-" * 65)

    state = "idle"
    for rnd in range(1, 9):
        path, cost = compute_path(idle_graph)
        path_str = " → ".join(path)

        if path == ["A", "D"]:
            # All traffic goes direct; direct link congests
            note = "Direct link congests → cost rises to 10"
            current_graph = defaultdict(dict, {
                "A": {"D": 10, "B": 1},   # direct now congested
                "D": {"A": 10, "C": 1},
                "B": {"A": 1, "C": 1},
                "C": {"B": 1, "D": 1},
            })
        else:
            # All traffic goes indirect; indirect path congests
            note = "Indirect path congests → cost rises"
            current_graph = idle_graph   # resets next round

        print(f"  {rnd:<8} {path_str:<30} {cost:<6} {note}")

        # Alternate graphs each round to simulate oscillation
        if rnd % 2 == 0:
            idle_graph = defaultdict(dict, {
                "A": {"D": 1, "B": 1},
                "D": {"A": 1, "C": 1},
                "B": {"A": 1, "C": 1},
                "C": {"B": 1, "D": 1},
            })
        else:
            idle_graph = defaultdict(dict, {
                "A": {"D": 10, "B": 1},
                "D": {"A": 10, "C": 1},
                "B": {"A": 1, "C": 1},
                "C": {"B": 1, "D": 1},
            })

    print("""
  Observation: traffic alternates between direct and indirect path every round.
  Fix: use static bandwidth-based costs (standard OSPF), not load-sensitive ones.
  """)


# ─────────────────────────────────────────────────────────────
# SECTION 7: networkx Cross-Validation
# ─────────────────────────────────────────────────────────────

def section7_networkx():
    print("=" * 65)
    print("SECTION 7: networkx Cross-Validation")
    print("=" * 65)

    try:
        import networkx as nx
    except ImportError:
        print("\n  networkx not installed. Run: pip install networkx")
        print("  Skipping this section.")
        return

    edges = [
        ("u", "v", 2), ("u", "w", 1), ("u", "x", 5),
        ("v", "y", 3), ("w", "y", 3), ("w", "z", 2),
        ("x", "z", 1), ("y", "z", 4),
    ]
    G = nx.Graph()
    for a, b, cost in edges:
        G.add_edge(a, b, weight=cost)

    nx_lengths, nx_paths = nx.single_source_dijkstra(G, "u", weight="weight")

    print("\n  networkx results (cross-check):")
    print(f"  {'Dest':<6} {'nx cost':<10} {'Our cost':<10} {'Match?'}")
    print("  " + "-" * 35)

    our_dist, our_prev = dijkstra(
        defaultdict(dict, {a: {b: c, **{}} for a, b, c in edges} |
                    {b: {a: c} for a, b, c in edges}), "u")

    # Rebuild graph properly for cross-check
    g = defaultdict(dict)
    for a, b, cost in edges:
        g[a][b] = cost
        g[b][a] = cost
    our_dist, _ = dijkstra(g, "u")

    all_match = True
    for node in sorted(nx_lengths):
        if node == "u":
            continue
        nx_c = nx_lengths[node]
        our_c = our_dist[node]
        match = "✓" if nx_c == our_c else "✗"
        if nx_c != our_c:
            all_match = False
        print(f"  {node:<6} {nx_c:<10} {our_c:<10} {match}")

    print(f"\n  {'All results match networkx!' if all_match else 'MISMATCH!'}")

    # Print SPT edges
    print("\n  Shortest-path tree edges (from predecessor pointers):")
    _, our_prev = dijkstra(g, "u")
    for node, parent in sorted(our_prev.items()):
        if parent is not None:
            nx_path = nx_paths[node]
            our_edge = f"{parent} → {node}"
            print(f"    {our_edge:<15}  (full nx path: {' → '.join(nx_path)})")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    section2_lecture_example()
    section3_verbose_trace()
    section4_link_failure()
    section5_ospf_costs()
    section6_oscillation()
    section7_networkx()

    print("\n" + "=" * 65)
    print("Lab complete.")
    print("=" * 65)