"""One chart style for every group. Deliberately plain, so a chart explains itself.

House rules:
- one idea per chart
- the title states the finding; a grey subtitle says how to read the axes
- every axis is labelled with its unit; percentages are ticks like "12%"
- the legend always sits OUTSIDE the plotting area (below it), never over the data
- the numbers are printed on the bars, so a reader can quote them directly

Usage:
    import _style as S
    S.apply()
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    ...
    S.clean(ax)
    S.title(ax, "Headline finding", "How to read this chart.")
    S.pct_axis(ax, "y")
    S.legend_below(ax, ncol=2)
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter

# A small, consistent palette: blue = the thing being measured,
# grey = a comparison / baseline, red = a contrast or warning.
C_ACCENT = "#2b6cb0"
C_ACCENT_SOFT = "#b9d1ea"
C_GREY = "#94a3b8"
C_GREY_SOFT = "#d7dde5"
C_WARN = "#c53030"
C_MUTED = "#4a5568"
C_TEXT = "#1a202c"


def apply():
    """Call once at the top of a chart script."""
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "font.size": 11,
        "axes.titlesize": 14,
        "axes.titleweight": "semibold",
        "axes.labelsize": 11,
        "axes.labelcolor": C_MUTED,
        "axes.edgecolor": "#cbd5e0",
        "axes.linewidth": 1.0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": C_MUTED,
        "ytick.color": C_MUTED,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.frameon": False,
        "legend.fontsize": 10,
    })


def clean(ax, grid="y"):
    """Drop the box, keep one light grid direction (y for bars, x for horizontal bars)."""
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.grid(axis=grid, color="#e2e8f0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    return ax


def title(ax, headline, subtitle=None):
    """Headline finding above the axes, plus an optional grey line under it."""
    ax.set_title(headline, loc="left", pad=32 if subtitle else 12, color=C_TEXT)
    if subtitle:
        ax.annotate(subtitle, xy=(0, 1), xycoords="axes fraction",
                    xytext=(0, 9), textcoords="offset points",
                    ha="left", va="bottom", fontsize=10.5, color=C_MUTED)


def pct_axis(ax, axis="y", decimals=0, step=None, xmax=1.0):
    """Ticks as percentages. Data is a fraction (0.12 -> 12%) unless xmax says otherwise.

    xmax: the data value that means 100% (use 100 when the data is already 0-100).
    step: optional tick step in data units (0.05 -> a tick every 5%).
    """
    target = ax.yaxis if axis == "y" else ax.xaxis
    target.set_major_formatter(PercentFormatter(xmax=xmax, decimals=decimals))
    if step:
        from matplotlib.ticker import MultipleLocator
        target.set_major_locator(MultipleLocator(step))


def count_axis(ax, axis="y"):
    """Ticks with thousands separators (1,234,567)."""
    fmt = FuncFormatter(lambda v, _: f"{v:,.0f}")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def vlabels(ax, bars, texts, fontsize=10, color=C_TEXT, dy=3):
    """Print a value above each vertical bar."""
    for bar, text in zip(bars, texts):
        ax.annotate(text,
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, dy), textcoords="offset points",
                    ha="center", va="bottom", fontsize=fontsize, color=color)


def hlabels(ax, bars, texts, fontsize=10, color=C_TEXT, dx=4):
    """Print a value at the end of each horizontal bar."""
    for bar, text in zip(bars, texts):
        ax.annotate(text,
                    xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
                    xytext=(dx, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=fontsize, color=color)


def legend_below(ax, ncol=2, handles=None, labels=None, y=-0.20):
    """Legend under the chart, out of the way of the data. Always use this."""
    kw = dict(loc="upper center", bbox_to_anchor=(0.5, y), ncol=ncol,
              frameon=False, handlelength=1.4, columnspacing=2.0,
              borderaxespad=0, fontsize=10)
    if handles is not None:
        ax.legend(handles=handles, labels=labels, **kw)
    else:
        ax.legend(**kw)


def baseline(ax, value, label=None, axis="y", color=C_MUTED):
    """A dashed reference line with a short label, e.g. 'no difference' at 1.0."""
    if axis == "y":
        ax.axhline(value, color=color, lw=1.1, ls="--", zorder=1)
        if label:
            ax.annotate(label, xy=(1, value), xycoords=("axes fraction", "data"),
                        xytext=(4, 3), textcoords="offset points",
                        ha="right", va="bottom", fontsize=9, color=color)
    else:
        ax.axvline(value, color=color, lw=1.1, ls="--", zorder=1)
        if label:
            ax.annotate(label, xy=(value, 1), xycoords=("data", "axes fraction"),
                        xytext=(4, -4), textcoords="offset points",
                        ha="left", va="top", fontsize=9, color=color)


def money(v):
    """Short money label: 464 -> $464, 22883 -> $22.9k, 1.2e6 -> $1.2M."""
    v = float(v)
    if abs(v) >= 1e9:
        return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e4:
        return f"${v/1e3:.0f}k"
    if abs(v) >= 1e3:
        return f"${v/1e3:.1f}k"
    return f"${v:,.0f}"
