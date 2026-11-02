"""Static charts for the README and stakeholder report (matplotlib)."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import config as C  # noqa: E402
from . import kpis as K  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e6e5e1"
BLUE = "#2a78d6"
ORANGE = "#eb6834"


def _style(ax, title: str, subtitle: str | None = None):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=12, color=INK, fontweight="bold", pad=18 if subtitle else 8)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=INK_2)


def on_time_trend(f, path):
    t = K.monthly_trend(f)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(t.month, t.on_time_pct * 100, color=BLUE, linewidth=2, marker="o", markersize=4)
    ax.axhline(C.TARGETS["on_time_pct"] * 100, color=INK_2, linewidth=1, linestyle="--")
    ax.text(len(t) - 1, C.TARGETS["on_time_pct"] * 100 + 1, "Target 85%", ha="right", fontsize=9, color=INK_2)
    ax.set_ylim(0, 100)
    ax.set_ylabel("On-time %", color=INK_2)
    ax.set_xticks(range(0, len(t), 3))
    ax.set_xticklabels(t.month[::3])
    _style(ax, "On-time delivery vs contracted TAT, by ship month", "Share of closed repair orders shipped within contract")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def stage_bottleneck(ev, f, path):
    b = K.stage_bottleneck(ev, f).iloc[::-1]
    top = b.avg_days.max()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    colors = [ORANGE if v == top else BLUE for v in b.avg_days]
    ax.barh(b.stage, b.avg_days, color=colors, height=0.6)
    for y, (v, s) in enumerate(zip(b.avg_days, b.share_of_tat)):
        ax.text(v + 0.1, y, f"{v:.1f} d  ({s:.0%})", va="center", fontsize=9, color=INK)
    ax.set_xlabel("Average days per order", color=INK_2)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    _style(ax, "Where repair time goes: average days in each stage", "Orange marks the largest bottleneck")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def delay_pareto(f, path):
    p = K.delay_pareto(f)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(p.primary_delay_reason, p.late_orders, color=BLUE, width=0.6)
    for x, (v, cp) in enumerate(zip(p.late_orders, p.cum_pct)):
        ax.text(x, v + p.late_orders.max() * 0.02, f"{v}  (cum {cp:.0%})", ha="center", fontsize=9, color=INK)
    ax.set_ylim(0, p.late_orders.max() * 1.15)
    ax.set_ylabel("Late orders", color=INK_2)
    plt.setp(ax.get_xticklabels(), rotation=12, ha="right")
    _style(ax, "Pareto: primary reason for late orders", "Labels show count and cumulative share of late orders")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def on_time_by_site(f, path):
    s = K.by_dimension(f, "site")
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.barh(s.site, s.on_time_pct * 100, color=BLUE, height=0.55)
    for y, v in enumerate(s.on_time_pct):
        ax.text(v * 100 + 1, y, f"{v:.0%}", va="center", fontsize=9, color=INK)
    ax.axvline(C.TARGETS["on_time_pct"] * 100, color=INK_2, linewidth=1, linestyle="--")
    ax.set_xlim(0, 100)
    ax.set_xlabel("On-time %", color=INK_2)
    _style(ax, "On-time delivery by repair site", "Dashed line = 85% target")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run(f, ev):
    C.CHART_DIR.mkdir(parents=True, exist_ok=True)
    on_time_trend(f, C.CHART_DIR / "on_time_trend.png")
    stage_bottleneck(ev, f, C.CHART_DIR / "stage_bottleneck.png")
    delay_pareto(f, C.CHART_DIR / "delay_pareto.png")
    on_time_by_site(f, C.CHART_DIR / "on_time_by_site.png")
    print(f"Charts saved -> {C.CHART_DIR}")
