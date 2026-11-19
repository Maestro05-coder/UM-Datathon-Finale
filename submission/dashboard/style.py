"""Shared visual identity for the dashboard pack.

One palette for both submitted files: the deck's plum and ochre on paper white.
Plum carries the finding, ochre carries the baseline, and the neutrals carry
text. Two rules keep 960 x 540 pt pages legible: ochre never carries text below
14 pt bold, and the faint rule grey never carries text at all, only lines.
"""
import matplotlib as mpl
import matplotlib.ticker as mtick

# --- palette, identical to deck/build_deck.py -------------------------------
PLUM = "#5b2a3d"          # the finding: data marks, headings
PLUM_SOFT = "#eadfe4"     # fills, bands, the light end of a heatmap
OCHRE = "#a9762f"         # baseline, threshold, comparator
OCHRE_SOFT = "#f6ebdc"    # comparator wash
INK = "#1d1d1b"
BODY = "#3a3a37"
MUTED = "#6c6c67"
FAINT = "#9b9b94"         # rules and reference lines only
RULE = "#e2ded7"
TINT = "#f6f3ef"
BG = "#ffffff"

# aliases: the page code still says NAVY and GOLD, and should keep saying it
NAVY = PLUM
GOLD = OCHRE
TEAL = MUTED              # small caps kickers
GREY = FAINT              # reference lines, never text
CORAL = PLUM              # the one flagged case, drawn as a hollow ring
GREEN = PLUM
LGREY = RULE

PAIRS = {"B\u2192B": PLUM, "B\u2192C": MUTED, "C\u2192B": OCHRE, "C\u2192C": FAINT}
CYCLE = [PLUM, OCHRE, MUTED, PLUM_SOFT, FAINT, OCHRE_SOFT]

# --- type scale -------------------------------------------------------------
# 9.0 pt is the floor for anything a reader has to read; the footer is the
# single exception at 8.5, because it is furniture rather than content.
FS = {
    "kicker": 9.0,
    "title": 20.0,
    "standfirst": 11.5,
    "chart_title": 11.0,
    "howto": 9.5,
    "stat_value": 20.0,
    "stat_label": 9.5,
    "rule_key": 9.0,
    "rule_text": 10.0,
    "baseline": 9.5,
    "takeaway": 10.5,
    "axis": 10.0,
    "tick": 9.0,
    "data": 9.5,
    "footer": 8.5,
}


def setup():
    mpl.rcParams.update({
        "figure.facecolor": BG,
        "axes.facecolor": BG,
        "savefig.facecolor": BG,
        "font.family": "Segoe UI",
        "font.size": 10,
        "text.parse_math": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "axes.edgecolor": RULE,
        "axes.linewidth": 0.8,
        "axes.labelcolor": MUTED,
        "axes.labelsize": FS["axis"],
        "axes.titlesize": FS["chart_title"],
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "axes.grid": True,
        "grid.color": "#ece7e1",
        "grid.linewidth": 0.8,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelsize": FS["tick"],
        "ytick.labelsize": FS["tick"],
        "legend.frameon": False,
        "legend.fontsize": FS["tick"],
        "figure.dpi": 200,
    })


def clean(ax, grid_axis="y"):
    """Hairline spines, no top or right, grid behind the marks."""
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(RULE)
    if grid_axis:
        ax.grid(axis=grid_axis, color="#ece7e1", lw=0.8)
        ax.grid(axis="x" if grid_axis == "y" else "y", visible=False)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=FS["tick"])


def _axis(ax, axis):
    return ax.yaxis if axis == "y" else ax.xaxis


def percent_axis(ax, axis="y", decimals=0):
    """Label a 0-1 axis as percentages: 0.42 -> 42%."""
    fmt = (mtick.FuncFormatter(lambda v, _: f"{v*100:g}%") if decimals is None
           else mtick.PercentFormatter(1.0, decimals=decimals))
    targets = [ax.yaxis, ax.xaxis] if axis == "both" else [_axis(ax, axis)]
    for t in targets:
        t.set_major_formatter(fmt)


def money_axis(ax, axis="x"):
    """Label an axis in short USD: 22_888 -> $23k."""
    _axis(ax, axis).set_major_formatter(mtick.FuncFormatter(money))


def thousands_axis(ax, axis="y", suffix="k"):
    _axis(ax, axis).set_major_formatter(
        mtick.FuncFormatter(lambda v, _: f"{v:,.0f}{suffix}"))


def pct(x, _=None):
    return f"{x*100:.0f}%"


def money(x, _=None):
    if x >= 1e9:
        return f"${x/1e9:.0f}bn"
    if x >= 1e6:
        return f"${x/1e6:.0f}m"
    if x >= 1e3:
        return f"${x/1e3:,.0f}k"
    return f"${x:,.0f}"
