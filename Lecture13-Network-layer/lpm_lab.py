"""
Lab: Longest-Prefix Match (LPM) Router Simulator
EC 441 - Intro to Computer Networking | Lecture 13
Topic: Network Layer - Forwarding and Longest-Prefix Match

This lab builds on the Python LPM demo from the lecture notes. It:
  1. Implements a forwarding table with LPM lookup
  2. Traces every match step so you can see exactly which prefixes
     are considered and why the longest one wins
  3. Simulates a small router forwarding a stream of packets
  4. Plots per-interface traffic distribution
  5. Demonstrates CIDR aggregation: how specific routes override
     a covering aggregate

Usage:
    python lpm_lab.py

Output:
    - Console trace of LPM decisions
    - lpm_traffic.png  (bar chart of packets forwarded per interface)

Key concepts illustrated:
    - Longest-prefix match rule
    - Default route (0.0.0.0/0) as a catch-all
    - More-specific routes overriding less-specific aggregates
    - What happens when NO route matches (no default)
    - CIDR prefix containment using Python ipaddress module
"""

import ipaddress
import collections

try:
    import matplotlib
    import matplotlib.ticker
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("matplotlib not found. Install with: pip install matplotlib")
    print("Continuing with text output only.\n")


# -- Forwarding table ----------------------------------------------------------

class ForwardingTable:
    """
    IP forwarding table with longest-prefix match lookup.

    Entries are stored as (ip_network, interface, next_hop) tuples.
    Lookup iterates all entries, collects all matches, and returns
    the one with the longest prefix length.
    """

    def __init__(self):
        self._entries = []   # list of (ip_network, iface, next_hop)

    def add(self, prefix_str, interface, next_hop=None):
        """
        Add a forwarding table entry.

        Args:
            prefix_str: CIDR prefix string, e.g. "10.1.2.0/24"
            interface:  outgoing interface name, e.g. "eth3"
            next_hop:   next-hop IP string or None for directly connected
        """
        net = ipaddress.ip_network(prefix_str, strict=False)
        self._entry_check(net, interface)
        self._entries.append((net, interface, next_hop))

    def _entry_check(self, net, interface):
        """Warn about duplicate entries (same prefix, different interface)."""
        for existing_net, existing_iface, _ in self._entries:
            if existing_net == net and existing_iface != interface:
                print(
                    f"  WARNING: duplicate prefix {net} with different "
                    f"interfaces ({existing_iface} vs {interface})"
                )

    def lookup(self, dest_str, verbose=False):
        """
        Perform longest-prefix match for dest_str.

        Args:
            dest_str: destination IP address string
            verbose:  if True, print all matches considered
        Returns:
            (matched_prefix, interface, next_hop) or None if no match
        """
        dest = ipaddress.ip_address(dest_str)
        matches = [
            (net, iface, nh)
            for net, iface, nh in self._entries
            if dest in net
        ]

        if verbose:
            if matches:
                print(f"  Matches for {dest_str}:")
                for net, iface, nh in sorted(
                    matches, key=lambda x: x[0].prefixlen
                ):
                    marker = ""
                    if net.prefixlen == max(
                        m[0].prefixlen for m in matches
                    ):
                        marker = "  <-- LONGEST"
                    nh_str = f" via {nh}" if nh else " (direct)"
                    print(
                        f"    /{net.prefixlen:>2}  {str(net):<22}"
                        f" -> {iface}{nh_str}{marker}"
                    )
            else:
                print(f"  No match for {dest_str} -- packet dropped")

        if not matches:
            return None
        best = max(matches, key=lambda x: x[0].prefixlen)
        return best

    def show(self):
        """Print the forwarding table."""
        print("\n  Forwarding Table:")
        print(f"  {'Prefix':<22} {'Len':>4}  {'Interface':<8}  Next Hop")
        print("  " + "-" * 55)
        for net, iface, nh in sorted(
            self._entries, key=lambda x: x[0].prefixlen
        ):
            nh_str = nh if nh else "(direct)"
            print(
                f"  {str(net):<22} {net.prefixlen:>4}  {iface:<8}  {nh_str}"
            )
        print()


# -- Router simulation ---------------------------------------------------------

class Router:
    """Simple software router that forwards packets using LPM."""

    def __init__(self, name, table):
        self.name = name
        self.table = table
        self.counters = collections.defaultdict(int)
        self.dropped = 0

    def forward(self, dest_str, verbose=False):
        """
        Forward one packet to dest_str.

        Args:
            dest_str: destination IP address string
            verbose:  print LPM trace
        Returns:
            interface string, or None if dropped
        """
        result = self.table.lookup(dest_str, verbose=verbose)
        if result is None:
            self.dropped += 1
            return None
        net, iface, nh = result
        self.counters[iface] += 1
        return iface

    def stats(self):
        """Print per-interface packet counts."""
        total = sum(self.counters.values()) + self.dropped
        print(f"\n  {self.name} forwarding stats ({total} packets total):")
        for iface, count in sorted(self.counters.items()):
            bar = "#" * (count * 30 // max(self.counters.values()))
            print(f"    {iface:<8} {count:>5} pkts  {bar}")
        if self.dropped:
            print(f"    dropped  {self.dropped:>5} pkts  (no route)")


# -- Build the demo forwarding table -------------------------------------------

def build_table():
    """
    Forwarding table matching the Lecture 13 example, with one extra
    /25 entry to demonstrate more-specific override.

    Prefix             Len  Interface  Next Hop
    0.0.0.0/0            0  eth0       203.0.113.1   (default)
    10.0.0.0/8           8  eth1       10.255.0.1
    10.1.0.0/16         16  eth2       10.1.255.1
    10.1.2.0/24         24  eth3       10.1.2.254
    10.1.2.128/25       25  eth4       10.1.2.129    (more specific)
    192.168.0.0/16      16  eth5       192.168.0.1
    """
    t = ForwardingTable()
    t.add("0.0.0.0/0",       "eth0", "203.0.113.1")
    t.add("10.0.0.0/8",      "eth1", "10.255.0.1")
    t.add("10.1.0.0/16",     "eth2", "10.1.255.1")
    t.add("10.1.2.0/24",     "eth3", "10.1.2.254")
    t.add("10.1.2.128/25",   "eth4", "10.1.2.129")
    t.add("192.168.0.0/16",  "eth5", "192.168.0.1")
    return t


# -- Demo scenarios ------------------------------------------------------------

def demo_lpm_trace(table):
    """
    Trace LPM decisions for a set of representative destinations,
    matching the worked examples in the lecture and problem set.
    """
    test_cases = [
        ("10.1.2.200",   "Matches /0, /8, /16, /24, /25 -> eth4"),
        ("10.1.2.50",    "Matches /0, /8, /16, /24 -> eth3"),
        ("10.1.5.1",     "Matches /0, /8, /16 -> eth2"),
        ("10.5.6.7",     "Matches /0, /8 -> eth1"),
        ("192.168.100.1","Matches /0, /16 -> eth5"),
        ("172.16.0.1",   "Matches /0 only -> eth0 (default)"),
        ("10.1.2.128",   "Network addr of /25 -- still matches /25 -> eth4"),
        ("10.1.2.255",   "Broadcast of /24 -- matches /24, /25? (255>=128) -> eth4"),
    ]

    print("\n" + "=" * 60)
    print("LPM TRACE: step-by-step match for each destination")
    print("=" * 60)

    for dest, note in test_cases:
        print(f"\n>>> {dest}  ({note})")
        table.lookup(dest, verbose=True)


def demo_no_default_route():
    """
    Show what happens when there is no default route and a packet
    arrives for an unknown destination.
    """
    print("\n" + "=" * 60)
    print("DEMO: Router with NO default route")
    print("=" * 60)
    t = ForwardingTable()
    t.add("10.0.0.0/8",  "eth1", "10.255.0.1")
    t.add("192.168.0.0/16", "eth2", "192.168.0.1")
    t.show()

    for dest in ["10.5.6.7", "172.16.0.1", "8.8.8.8"]:
        print(f">>> {dest}")
        result = t.lookup(dest, verbose=True)
        if result is None:
            print(
                f"  -> DROPPED: no route to {dest}. "
                "Router would send ICMP Destination Unreachable."
            )


def demo_traffic_simulation(table):
    """
    Simulate a stream of 200 packets to random destinations and
    show per-interface distribution. Returns router for plotting.
    """
    import random
    random.seed(42)

    print("\n" + "=" * 60)
    print("SIMULATION: 200 packets forwarded through the router")
    print("=" * 60)

    router = Router("R1", table)

    # Weighted destination pools to produce interesting distribution
    dest_pools = [
        # (weight, prefix) -- random host in each prefix
        (40, "10.1.2.128/25"),   # eth4: many hosts in this subnet
        (30, "10.1.2.0/24"),     # eth3: note /25 steals the upper half
        (20, "10.1.0.0/16"),     # eth2
        (15, "10.0.0.0/8"),      # eth1
        (10, "192.168.0.0/16"),  # eth5
        (10, "172.16.0.0/12"),   # eth0 (default - no specific route)
    ]

    def random_host(prefix_str):
        net = ipaddress.ip_network(prefix_str, strict=False)
        num_hosts = net.num_addresses
        if num_hosts <= 2:
            return str(net.network_address)
        offset = random.randint(1, num_hosts - 2)
        return str(net.network_address + offset)

    for _ in range(200):
        weights = [w for w, _ in dest_pools]
        total_w = sum(weights)
        r = random.randint(0, total_w - 1)
        cumulative = 0
        chosen_prefix = dest_pools[-1][1]
        for w, prefix in dest_pools:
            cumulative += w
            if r < cumulative:
                chosen_prefix = prefix
                break
        dest = random_host(chosen_prefix)
        router.forward(dest, verbose=False)

    router.stats()
    return router


# -- Plotting ------------------------------------------------------------------

def plot_traffic(router, output_path="lpm_traffic.png"):
    """
    Bar chart of packets forwarded per interface.
    """
    if not HAS_MPL:
        print("Skipping plot (matplotlib unavailable).")
        return

    ifaces = sorted(router.counters.keys())
    counts = [router.counters[i] for i in ifaces]
    colors = [
        "#2C6BE0", "#E05C2C", "#27AE60",
        "#8E44AD", "#F39C12", "#1ABC9C", "#E74C3C",
    ]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(
        ifaces, counts,
        color=colors[:len(ifaces)],
        edgecolor="white", linewidth=1.2,
        zorder=3,
    )

    # Annotate bar tops
    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1,
            str(count),
            ha="center", va="bottom", fontsize=10, fontweight="bold",
        )

    # Interface -> prefix label
    prefix_labels = {
        "eth0": "eth0\n(default /0)",
        "eth1": "eth1\n(10.0.0.0/8)",
        "eth2": "eth2\n(10.1.0.0/16)",
        "eth3": "eth3\n(10.1.2.0/24)",
        "eth4": "eth4\n(10.1.2.128/25)",
        "eth5": "eth5\n(192.168.0.0/16)",
    }
    ax.set_xticks(range(len(ifaces)))
    ax.set_xticklabels(
        [prefix_labels.get(i, i) for i in ifaces],
        fontsize=9,
    )

    ax.set_ylabel("Packets forwarded", fontsize=11)
    ax.set_title(
        "Packet Distribution by Output Interface\n"
        "EC 441 - Longest-Prefix Match Simulation (200 packets)",
        fontsize=12, fontweight="bold",
    )
    ax.set_ylim(0, max(counts) * 1.18)
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Note about /25 stealing from /24
    ax.text(
        0.98, 0.92,
        "Note: 10.1.2.128-255 matched by /25 (eth4),\n"
        "not /24 (eth3) — longest-prefix wins",
        transform=ax.transAxes,
        ha="right", va="top", fontsize=8, color="#555555",
        bbox=dict(
            boxstyle="round,pad=0.3",
            facecolor="#F9F9F9",
            edgecolor="#CCCCCC",
        ),
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\nPlot saved to: {output_path}")


# -- Entry point ---------------------------------------------------------------

if __name__ == "__main__":
    table = build_table()
    table.show()

    demo_lpm_trace(table)
    demo_no_default_route()

    router = demo_traffic_simulation(table)
    plot_traffic(router, "lpm_traffic.png")

    print("\nDone.")