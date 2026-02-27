"""
Lab: ALOHA Throughput Analysis
EC 441 – Intro to Computer Networking | Week 2
Topic: Multiple Access – ALOHA Protocols

This lab computes and plots the throughput curves for Pure ALOHA and Slotted ALOHA,
annotates the efficiency peaks, and prints a summary table.

Usage:
    python aloha_lab.py

Output:
    - aloha_throughput.png  (plot saved to disk)
    - Console summary table

Background:
    Pure ALOHA:    S = G * e^(-2G),  max at G = 0.5,  S_max = 1/(2e) ≈ 18.4%
    Slotted ALOHA: S = G * e^(-G),   max at G = 1.0,  S_max = 1/e    ≈ 36.8%

    where G = offered load (avg transmission attempts per frame-time)
          S = throughput (successful transmissions per frame-time)
"""

import math
import sys

# ── Try to import matplotlib; give a clear message if missing ──────────────────
try:
    import matplotlib
    matplotlib.use("Agg")          # non-interactive backend (works without a display)
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("matplotlib not found. Install with:  pip install matplotlib")
    print("Continuing with text output only.\n")


# ── Core throughput formulas ───────────────────────────────────────────────────

def pure_aloha_throughput(G: float) -> float:
    """
    Pure ALOHA throughput.

    A frame sent at time t can collide with any frame whose transmission
    begins during the 2T collision window [t-T, t+T].
    P(success) = e^(-2G)  =>  S = G * e^(-2G)

    Args:
        G: Offered load (attempts per frame-time T)
    Returns:
        S: Throughput (successful frames per frame-time)
    """
    return G * math.exp(-2 * G)


def slotted_aloha_throughput(G: float) -> float:
    """
    Slotted ALOHA throughput.

    Slot synchronization halves the collision window to T.
    P(success) = e^(-G)  =>  S = G * e^(-G)

    Args:
        G: Offered load (attempts per slot)
    Returns:
        S: Throughput (successful frames per slot)
    """
    return G * math.exp(-G)


# ── Analytical peak values ─────────────────────────────────────────────────────

PURE_G_PEAK     = 0.5                           # dS/dG = 0  =>  G = 1/2
PURE_S_PEAK     = 1 / (2 * math.e)             # S_max = 1/(2e)

SLOTTED_G_PEAK  = 1.0                           # dS/dG = 0  =>  G = 1
SLOTTED_S_PEAK  = 1 / math.e                    # S_max = 1/e


# ── Build data arrays ──────────────────────────────────────────────────────────

N_POINTS = 1000
G_MAX    = 5.0
G_VALUES = [i * G_MAX / N_POINTS for i in range(N_POINTS + 1)]

pure_S    = [pure_aloha_throughput(g)    for g in G_VALUES]
slotted_S = [slotted_aloha_throughput(g) for g in G_VALUES]


# ── Text summary table ─────────────────────────────────────────────────────────

def print_summary_table():
    header = f"{'G':>6}  {'Pure ALOHA S':>14}  {'Slotted ALOHA S':>16}"
    sep    = "-" * len(header)
    print("\n── ALOHA Throughput Summary ──────────────────────────────")
    print(header)
    print(sep)
    sample_G = [0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
    for g in sample_G:
        ps = pure_aloha_throughput(g)
        ss = slotted_aloha_throughput(g)
        marker_p = " ← PEAK" if abs(g - PURE_G_PEAK)    < 0.01 else ""
        marker_s = " ← PEAK" if abs(g - SLOTTED_G_PEAK) < 0.01 else ""
        print(f"{g:>6.2f}  {ps:>13.4f}   {ss:>15.4f}{marker_p or marker_s}")
    print(sep)
    print(f"\nPure ALOHA    peak: S = {PURE_S_PEAK:.4f} ({PURE_S_PEAK*100:.1f}%)  at G = {PURE_G_PEAK}")
    print(f"Slotted ALOHA peak: S = {SLOTTED_S_PEAK:.4f} ({SLOTTED_S_PEAK*100:.1f}%)  at G = {SLOTTED_G_PEAK}")
    print(f"\nSlotted is exactly {SLOTTED_S_PEAK / PURE_S_PEAK:.1f}x more efficient than Pure ALOHA at peak.\n")


# ── Plotting ───────────────────────────────────────────────────────────────────

def make_plot(output_path: str = "aloha_throughput.png"):
    if not HAS_MPL:
        print("Skipping plot (matplotlib unavailable).")
        return

    fig, ax = plt.subplots(figsize=(9, 5.5))

    # ── Throughput curves ──────────────────────────────────────────────────────
    ax.plot(G_VALUES, pure_S,    color="#E05C2C", linewidth=2.2,
            label=f"Pure ALOHA   (peak ≈ {PURE_S_PEAK*100:.1f}% at G={PURE_G_PEAK})")
    ax.plot(G_VALUES, slotted_S, color="#2C6BE0", linewidth=2.2,
            label=f"Slotted ALOHA (peak ≈ {SLOTTED_S_PEAK*100:.1f}% at G={SLOTTED_G_PEAK})")

    # ── Peak markers ───────────────────────────────────────────────────────────
    ax.plot(PURE_G_PEAK,    PURE_S_PEAK,    "o", color="#E05C2C", markersize=9, zorder=5)
    ax.plot(SLOTTED_G_PEAK, SLOTTED_S_PEAK, "o", color="#2C6BE0", markersize=9, zorder=5)

    # Dashed drop lines to axes
    for gp, sp, col in [(PURE_G_PEAK,    PURE_S_PEAK,    "#E05C2C"),
                         (SLOTTED_G_PEAK, SLOTTED_S_PEAK, "#2C6BE0")]:
        ax.plot([gp, gp],   [0, sp],  "--", color=col, linewidth=1, alpha=0.55)
        ax.plot([0, gp],    [sp, sp], "--", color=col, linewidth=1, alpha=0.55)

    # Annotations
    ax.annotate(f" S_max = 1/(2e)\n ≈ {PURE_S_PEAK*100:.1f}%",
                xy=(PURE_G_PEAK, PURE_S_PEAK),
                xytext=(PURE_G_PEAK + 0.35, PURE_S_PEAK + 0.03),
                fontsize=9, color="#C04010",
                arrowprops=dict(arrowstyle="->", color="#C04010", lw=1.2))

    ax.annotate(f" S_max = 1/e\n ≈ {SLOTTED_S_PEAK*100:.1f}%",
                xy=(SLOTTED_G_PEAK, SLOTTED_S_PEAK),
                xytext=(SLOTTED_G_PEAK + 0.35, SLOTTED_S_PEAK + 0.03),
                fontsize=9, color="#1040B0",
                arrowprops=dict(arrowstyle="->", color="#1040B0", lw=1.2))

    # ── Shaded region showing wasted capacity ──────────────────────────────────
    ax.fill_between(G_VALUES, pure_S, slotted_S,
                    alpha=0.12, color="#2C6BE0",
                    label="Slotted advantage over Pure")

    # ── Labels and formatting ──────────────────────────────────────────────────
    ax.set_xlabel("Offered Load  G  (attempts per frame-time)", fontsize=11)
    ax.set_ylabel("Throughput  S  (successful frames per frame-time)", fontsize=11)
    ax.set_title("ALOHA Protocol Throughput Comparison\n"
                 "EC 441 – Multiple Access Protocols", fontsize=13, fontweight="bold")
    ax.set_xlim(0, G_MAX)
    ax.set_ylim(0, 0.45)
    ax.set_xticks([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0])
    ax.set_yticks([i * 0.05 for i in range(10)])
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1.0))
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(loc="upper right", fontsize=9.5)

    # Note about the overloaded regime
    ax.text(3.2, 0.38,
            "As G → ∞, both protocols\ncollapse toward S → 0\n(channel saturated with collisions)",
            fontsize=8.5, color="#555555",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#F5F5F5", edgecolor="#BBBBBB"))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Plot saved to: {output_path}")


# ── Bonus: slotted ALOHA slot outcome breakdown at peak load ───────────────────

def slot_outcome_breakdown():
    """
    At G=1 (slotted ALOHA peak), what fraction of slots are:
      - successful (exactly 1 transmission)
      - empty (0 transmissions)
      - collision (2+ transmissions)
    Assuming Poisson arrivals.
    """
    G = 1.0
    p_success   = G * math.exp(-G)              # P(exactly 1) = G*e^{-G}
    p_empty     = math.exp(-G)                  # P(0 attempts) = e^{-G}
    p_collision = 1 - p_success - p_empty       # everything else

    print("── Slotted ALOHA slot outcomes at peak load (G=1) ────────")
    print(f"  Successful  (1 tx):   {p_success*100:5.1f}%  (= 1/e)")
    print(f"  Empty       (0 tx):   {p_empty*100:5.1f}%  (= 1/e)")
    print(f"  Collision   (2+ tx):  {p_collision*100:5.1f}%")
    print(f"  Total:                {(p_success+p_empty+p_collision)*100:.1f}%\n")
    print("  Key insight: even at the efficiency-maximizing load,")
    print("  only ~37% of slots carry useful data.\n")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print_summary_table()
    slot_outcome_breakdown()
    output = "aloha_throughput.png"
    make_plot(output)
    print("Done.")