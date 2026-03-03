"""
Lab: Ethernet Switch Self-Learning Simulator
EC 441 - Intro to Computer Networking | Lecture 8
Topic: Link Layer - Ethernet Switching

This lab simulates the self-learning forwarding algorithm used by Ethernet
switches. It models a network of switches and hosts, replays a frame trace,
and shows exactly how each switch's forwarding table evolves over time.

Usage:
    python switch_lab.py

Output:
    - Console trace of every frame and switch decision
    - switch_tables.png  (forwarding table state over time)

Key concepts illustrated:
    - Learning: source MAC -> ingress port recorded on every frame
    - Forwarding: known dst MAC -> send to that port only
    - Flooding: unknown dst MAC -> send to all ports except ingress
    - Table expiry: entries time out after TTL seconds (simulated)
    - Multi-switch: frames traverse trunk links between switches
"""

import math
import time

try:
    import matplotlib
    import matplotlib.ticker
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("matplotlib not found. Install with: pip install matplotlib")
    print("Continuing with text output only.\n")


# -- Data structures -----------------------------------------------------------

class ForwardingTable:
    """
    MAC address forwarding table with TTL-based expiry.

    Maps MAC address -> (port, timestamp). An entry is considered stale
    if more than TTL seconds have passed since it was last learned.
    """

    def __init__(self, switch_name, ttl=300):
        self.switch_name = switch_name
        self.ttl = ttl
        self._table = {}   # mac -> (port, learned_at)
        self.history = []  # list of (event_num, snapshot) for plotting

    def learn(self, mac, port, event_num):
        """Record mac -> port mapping."""
        old = self._table.get(mac)
        self._table[mac] = (port, event_num)
        learned = old is None or old[0] != port
        return learned

    def lookup(self, mac, now=None):
        """
        Return port for mac, or None if unknown / expired.

        Args:
            mac: destination MAC address string
            now: current event number (used for TTL check)
        Returns:
            port string, or None
        """
        entry = self._table.get(mac)
        if entry is None:
            return None
        port, learned_at = entry
        if now is not None and (now - learned_at) > self.ttl:
            del self._table[mac]
            return None
        return port

    def snapshot(self):
        """Return a copy of the current table contents."""
        return {mac: port for mac, (port, _) in self._table.items()}

    def save_history(self, event_num):
        self.history.append((event_num, self.snapshot()))

    def __str__(self):
        if not self._table:
            return f"  {self.switch_name}: (empty)"
        rows = [
            f"  {self.switch_name}:  {mac} -> {port}"
            for mac, (port, _) in sorted(self._table.items())
        ]
        return "\n".join(rows)


class Switch:
    """
    Single Ethernet switch with self-learning forwarding.

    Ports are named strings (e.g. "p1", "p2", "trunk-S2").
    The switch knows which ports connect to other switches (trunk ports)
    vs. which connect to end hosts.
    """

    def __init__(self, name, ports):
        """
        Args:
            name: switch identifier string (e.g. "S1")
            ports: list of port name strings
        """
        self.name = name
        self.ports = ports
        self.table = ForwardingTable(name)

    def receive(self, frame, ingress_port, event_num):
        """
        Process one incoming frame. Returns list of egress ports.

        Args:
            frame: dict with 'src' and 'dst' MAC address strings
            ingress_port: name of port frame arrived on
            event_num: monotonic counter for TTL tracking
        Returns:
            list of port names to forward out
        """
        src = frame["src"]
        dst = frame["dst"]

        # Learning step
        new_entry = self.table.learn(src, ingress_port, event_num)

        # Lookup step
        egress = self.table.lookup(dst, now=event_num)

        if egress is None:
            # Flood: all ports except ingress
            out_ports = [p for p in self.ports if p != ingress_port]
            action = "FLOOD"
        elif egress == ingress_port:
            # Destination is on the same port as source - filter
            out_ports = []
            action = "FILTER (same port)"
        else:
            out_ports = [egress]
            action = "FORWARD"

        self.table.save_history(event_num)
        return out_ports, action, new_entry


# -- Network topology ----------------------------------------------------------

def build_single_switch_network():
    """
    Simple topology: one switch, four hosts.

        A -- p1
        B -- p2  [S1]
        C -- p3
        D -- p4
    """
    s1 = Switch("S1", ["p1", "p2", "p3", "p4"])
    hosts = {
        "A": ("S1", "p1"),
        "B": ("S1", "p2"),
        "C": ("S1", "p3"),
        "D": ("S1", "p4"),
    }
    macs = {
        "A": "AA:AA:AA:AA:AA:AA",
        "B": "BB:BB:BB:BB:BB:BB",
        "C": "CC:CC:CC:CC:CC:CC",
        "D": "DD:DD:DD:DD:DD:DD",
    }
    return {"S1": s1}, hosts, macs


def build_two_switch_network():
    """
    Two-switch topology with trunk link.

        A -- p1              p2 -- C
             [S1] --p3-p1-- [S2]
        B -- p2              p3 -- D
    """
    s1 = Switch("S1", ["p1", "p2", "p3"])
    s2 = Switch("S2", ["p1", "p2", "p3"])
    # trunk: S1.p3 <-> S2.p1

    hosts = {
        "A": ("S1", "p1"),
        "B": ("S1", "p2"),
        "C": ("S2", "p2"),
        "D": ("S2", "p3"),
    }
    macs = {
        "A": "AA:AA:AA:AA:AA:AA",
        "B": "BB:BB:BB:BB:BB:BB",
        "C": "CC:CC:CC:CC:CC:CC",
        "D": "DD:DD:DD:DD:DD:DD",
    }
    # trunk link: S1 port p3 connects to S2 port p1
    trunk = {"S1": ("p3", "S2", "p1"), "S2": ("p1", "S1", "p3")}
    return {"S1": s1, "S2": s2}, hosts, macs, trunk


# -- Simulation helpers --------------------------------------------------------

DIVIDER = "-" * 60


def simulate_single_switch(trace):
    """
    Run a frame trace through a single-switch network.

    Args:
        trace: list of (src_host, dst_host) tuples
    """
    switches, hosts, macs = build_single_switch_network()
    s1 = switches["S1"]

    print("\n" + "=" * 60)
    print("SIMULATION 1: Single Switch (S1) with 4 hosts")
    print("Hosts: A=p1, B=p2, C=p3, D=p4")
    print("=" * 60)

    all_snapshots = []

    for i, (src_host, dst_host) in enumerate(trace, start=1):
        src_mac = macs[src_host]
        dst_mac = macs[dst_host]
        _, ingress = hosts[src_host]

        frame = {"src": src_mac, "dst": dst_mac}
        out_ports, action, new_entry = s1.receive(frame, ingress, i)

        print(f"\nFrame {i}: {src_host} -> {dst_host}")
        print(f"  src MAC: {src_mac}  |  dst MAC: {dst_mac}")
        print(f"  arrived on: {ingress}")
        learn_str = f" (NEW: {src_host}->{ingress})" if new_entry else ""
        print(f"  learned:{learn_str if new_entry else ' (already known)'}")
        print(f"  action:  {action} -> out ports: {out_ports or ['none']}")
        print(f"  table now:\n{s1.table}")

        all_snapshots.append((i, s1.table.snapshot().copy()))

    return all_snapshots


def simulate_two_switches(trace):
    """
    Run a frame trace through a two-switch network.

    Handles trunk link propagation: when S1 floods or forwards via p3,
    the frame continues into S2 on p1, and vice versa.

    Args:
        trace: list of (src_host, dst_host) tuples
    """
    switches, hosts, macs, trunk = build_two_switch_network()
    s1 = switches["S1"]
    s2 = switches["S2"]

    print("\n" + "=" * 60)
    print("SIMULATION 2: Two Switches (S1, S2) with trunk link")
    print("  S1: A=p1, B=p2, trunk=p3")
    print("  S2: trunk=p1, C=p2, D=p3")
    print("=" * 60)

    for i, (src_host, dst_host) in enumerate(trace, start=1):
        src_mac = macs[src_host]
        dst_mac = macs[dst_host]
        src_switch, ingress = hosts[src_host]

        frame = {"src": src_mac, "dst": dst_mac}

        print(f"\nFrame {i}: {src_host} -> {dst_host}")
        print(f"  src MAC: {src_mac}  dst MAC: {dst_mac}")

        # Process at first switch
        first_sw = switches[src_switch]
        out_ports, action, _ = first_sw.receive(frame, ingress, i)
        print(f"  [{first_sw.name}] arrived on {ingress}: "
              f"{action} -> {out_ports}")
        print(f"  [{first_sw.name}] table: {first_sw.table.snapshot()}")

        # Check if frame crosses the trunk link
        trunk_out, other_name, trunk_in = trunk[src_switch]
        if trunk_out in out_ports:
            other_sw = switches[other_name]
            out2, action2, _ = other_sw.receive(frame, trunk_in, i)
            print(f"  [{other_sw.name}] arrived on {trunk_in} (via trunk): "
                  f"{action2} -> {out2}")
            print(f"  [{other_sw.name}] table: "
                  f"{other_sw.table.snapshot()}")


# -- Plotting ------------------------------------------------------------------

def plot_table_evolution(snapshots, all_macs, title, output_path):
    """
    Visualise how the forwarding table fills in over time.

    Creates a grid: rows = MAC addresses, columns = event numbers.
    Each cell shows the port the switch associated with that MAC at
    that point in the simulation.

    Args:
        snapshots: list of (event_num, table_dict) from simulate_*
        all_macs: dict of host_name -> mac_address
        title: plot title string
        output_path: filename to save PNG
    """
    if not HAS_MPL:
        print("Skipping plot (matplotlib unavailable).")
        return

    hosts = list(all_macs.keys())
    macs = list(all_macs.values())
    n_events = len(snapshots)
    n_hosts = len(hosts)

    # Build a 2D grid: grid[host_idx][event_idx] = port or ""
    port_colors = {"p1": "#AED6F1", "p2": "#A9DFBF",
                   "p3": "#F9E79F", "p4": "#F5CBA7"}
    default_color = "#EAECEE"

    grid_text = [["" for _ in range(n_events)] for _ in range(n_hosts)]
    grid_color = [
        [default_color for _ in range(n_events)] for _ in range(n_hosts)
    ]

    for col, (_, snapshot) in enumerate(snapshots):
        for row, mac in enumerate(macs):
            port = snapshot.get(mac, "")
            grid_text[row][col] = port
            if port:
                grid_color[row][col] = port_colors.get(port, "#D7BDE2")

    fig, ax = plt.subplots(
        figsize=(max(8, n_events * 0.9), max(3, n_hosts * 0.7 + 1.5))
    )
    ax.set_xlim(0, n_events)
    ax.set_ylim(0, n_hosts)
    ax.axis("off")

    cell_w = 1.0
    cell_h = 1.0

    for row in range(n_hosts):
        for col in range(n_events):
            x = col * cell_w
            y = (n_hosts - 1 - row) * cell_h
            color = grid_color[row][col]
            rect = patches.FancyBboxPatch(
                (x + 0.04, y + 0.06), cell_w - 0.08, cell_h - 0.12,
                boxstyle="round,pad=0.02",
                facecolor=color, edgecolor="#AAAAAA", linewidth=0.8,
            )
            ax.add_patch(rect)
            text = grid_text[row][col] or "-"
            ax.text(
                x + cell_w / 2, y + cell_h / 2, text,
                ha="center", va="center", fontsize=9,
                color="#222222" if text != "-" else "#BBBBBB",
            )

    # Row labels (host names)
    for row, host in enumerate(hosts):
        y = (n_hosts - 1 - row) * cell_h + cell_h / 2
        ax.text(
            -0.35, y,
            f"{host}\n{macs[row][:8]}...",
            ha="right", va="center", fontsize=8, color="#333333",
        )

    # Column labels (event numbers)
    for col, (ev, _) in enumerate(snapshots):
        x = col * cell_w + cell_w / 2
        ax.text(
            x, n_hosts + 0.1, f"t={ev}",
            ha="center", va="bottom", fontsize=8, color="#555555",
        )

    ax.set_title(title, fontsize=12, fontweight="bold", pad=18)

    # Legend
    legend_handles = []
    for port, color in sorted(port_colors.items()):
        legend_handles.append(
            patches.Rectangle((0, 0), 1, 1, facecolor=color, label=port)
        )
    legend_handles.append(
        patches.Rectangle(
            (0, 0), 1, 1, facecolor=default_color, label="unknown"
        )
    )
    ax.legend(
        handles=legend_handles,
        loc="lower right", fontsize=8, title="Port",
        bbox_to_anchor=(1.0, -0.08),
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Plot saved to: {output_path}")


# -- Entry point ---------------------------------------------------------------

if __name__ == "__main__":

    # ── Simulation 1: single switch ──────────────────────────────────────────
    trace1 = [
        ("A", "C"),  # A->C: learn A, flood (C unknown)
        ("C", "A"),  # C->A: learn C, forward (A known)
        ("B", "D"),  # B->D: learn B, flood (D unknown)
        ("D", "B"),  # D->B: learn D, forward (B known)
        ("A", "B"),  # A->B: both known, forward
        ("C", "D"),  # C->D: both known, forward
    ]

    _, hosts1, macs1 = build_single_switch_network()
    all_macs1 = {h: macs1[h] for h in ["A", "B", "C", "D"]}
    snapshots = simulate_single_switch(trace1)

    # ── Simulation 2: two switches ───────────────────────────────────────────
    trace2 = [
        ("A", "D"),  # A->D: unknown at both switches, floods everywhere
        ("D", "A"),  # D->A: A now known at S1 and S2
        ("B", "C"),  # B->C: C unknown at S1, known at S2
        ("C", "B"),  # C->B: B now known
    ]
    simulate_two_switches(trace2)

    # ── Plot table evolution for simulation 1 ────────────────────────────────
    plot_table_evolution(
        snapshots,
        all_macs1,
        title=(
            "S1 Forwarding Table Evolution\n"
            "EC 441 - Switch Self-Learning (Single Switch)"
        ),
        output_path="switch_tables.png",
    )

    print("\nDone.")