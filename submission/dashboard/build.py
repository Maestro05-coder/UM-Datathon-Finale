"""Build the dashboard pack: ten 16:9 pages, one per feature group plus a cover
and a method page, exported as a vector PDF and as PNG previews.

    python dashboard/build.py              # all pages
    python dashboard/build.py 3 5          # only pages 3 and 5

The deck shows the result of each rule; these pages show the test behind it, so
no chart form is repeated between the two documents. Every page carries the
finding as its title, a one-line "how to read" above the chart, a baseline
drawn in ochre, the sample size, and a rule block (condition / effect / scope).

All numbers come from the CSVs in `data/`, rebuilt by
`analysis/refresh_panels.py`. Nothing here reads the parquet.
"""
import json
import sys
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import LinearSegmentedColormap, PowerNorm
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import style as S  # noqa: E402

DATA = HERE / "data"
OUT = HERE / "png"
DOCS = ROOT / "docs"
DPI = 200
PAGE = (13.333, 7.5)      # 960 x 540 pt, the size the pack has always shipped at
TOTAL = 10

# the chart column and the right rail, one rhythm for all eight rule pages
LEFT = 0.085
WIDTH = 0.520
HEAD = 0.735               # figure y of every chart title
TOP = 0.672                # figure y where a chart's plot area starts
RAIL_X = 0.650

PLUM_RAMP = LinearSegmentedColormap.from_list(
    "plum", ["#ffffff", "#ecdde3", "#b98ba0", S.PLUM])

GROUPS = [
    "When payments happen",
    "Which currency",
    "How much",
    "Banks and client class",
    "How long the chain",
    "How long it takes",
    "Who is paying whom",
    "What goes wrong",
]


def read(name, **kw):
    # country code NA (Namibia) is a code here, never a missing value
    kw.setdefault("keep_default_na", False)
    kw.setdefault("na_values", [""])
    return pd.read_csv(DATA / f"{name}.csv", **kw)


def jload(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def short(x):
    if x >= 1e6:
        return f"{x/1e6:.1f}m"
    if x >= 1e3:
        return f"{x/1e3:.1f}k"
    return f"{x:.0f}"


def money_short(x):
    if x >= 1e6:
        v = f"{x/1e6:.1f}m"
    elif x >= 1e4:
        v = f"{x/1e3:.0f}k"
    elif x >= 1e3:
        v = f"{x/1e3:.1f}k"
    else:
        return f"${x:.0f}"
    return "$" + v.replace(".0m", "m").replace(".0k", "k")


# ----------------------------------------------------------------- page furniture
def new_page(number, kicker, title, claim=None):
    fig = plt.figure(figsize=PAGE)
    fig.patch.set_facecolor(S.BG)
    fig.text(0.05, 0.960, kicker.upper(), fontsize=S.FS["kicker"], color=S.TEAL,
             fontweight="bold", va="top")
    fig.text(0.05, 0.925, title, fontsize=S.FS["title"], color=S.PLUM,
             fontweight="bold", va="top")
    if claim:
        fig.text(0.05, 0.868, textwrap.fill(claim, 118), fontsize=S.FS["standfirst"],
                 color=S.BODY, va="top", linespacing=1.38)
    foot(fig, number)
    return fig


def foot(fig, number):
    fig.text(0.05, 0.028, "UM Datathon 2026  \u00b7  Swift case study",
             fontsize=S.FS["footer"], color=S.MUTED)
    fig.text(0.500, 0.028, "synthetic data, 10,000,000 payments",
             fontsize=S.FS["footer"], color=S.MUTED, ha="center")
    fig.text(0.950, 0.028, f"{number:02d} / {TOTAL}", fontsize=S.FS["footer"],
             color=S.MUTED, ha="right")


def takeaway(fig, text):
    fig.patches.append(Rectangle((0.05, 0.062), 0.900, 0.058,
                                 transform=fig.transFigure, facecolor=S.TINT,
                                 edgecolor="none", zorder=-5))
    fig.patches.append(Rectangle((0.05, 0.062), 0.004, 0.058,
                                 transform=fig.transFigure, facecolor=S.OCHRE,
                                 edgecolor="none", zorder=-4))
    fig.text(0.066, 0.091, textwrap.fill(text, 126), fontsize=S.FS["takeaway"],
             color=S.BODY, va="center", linespacing=1.30)


def stat(fig, x, y, value, label, color=S.PLUM):
    fig.text(x, y, value, fontsize=S.FS["stat_value"], color=color,
             fontweight="bold", va="top")
    fig.text(x, y - 0.045, textwrap.fill(label, 40), fontsize=S.FS["stat_label"],
             color=S.MUTED, va="top", linespacing=1.30)


def rule_block(fig, x, y, rows):
    fig.text(x, y, "THE RULE", fontsize=S.FS["rule_key"], color=S.MUTED,
             fontweight="bold")
    yy = y - 0.028
    for label, text in rows:
        fig.text(x, yy, label, fontsize=S.FS["rule_key"], color=S.MUTED,
                 fontweight="bold")
        body = "\n".join(textwrap.wrap(text, 46))
        n = body.count("\n") + 1
        fig.text(x, yy - 0.022, body, fontsize=S.FS["rule_text"], color=S.BODY,
                 va="top", linespacing=1.28)
        yy -= 0.022 + 0.0265 * n + 0.014
    return yy


def baseline_note(fig, x, y, text):
    fig.text(x, y, "COMPARED AGAINST", fontsize=S.FS["rule_key"], color=S.MUTED,
             fontweight="bold")
    fig.text(x, y - 0.022, "\n".join(textwrap.wrap(text, 46)),
             fontsize=S.FS["baseline"], color=S.BODY, va="top", linespacing=1.28)


def rail(fig, stats, rows, baseline, top=0.812, x=RAIL_X):
    """Right rail: three numbers, the rule, and the baseline, in one fixed rhythm."""
    y = top
    for value, label in stats:
        stat(fig, x, y, value, label)
        y -= 0.106
    y = rule_block(fig, x, y - 0.006, rows)
    baseline_note(fig, x, y - 0.004, baseline)


def axes_at(fig, rect):
    return fig.add_axes(rect)


def panel(rect, height=None):
    """A chart-column plot area: fixed top, fixed left, one width."""
    left, bottom, width, *rest = rect
    return [left, bottom, width, height or (TOP - bottom)]


def chart(ax, title, howto, chars=62, y=HEAD):
    """One contract for every chart: the finding, then how to read it.

    The header sits in figure coordinates above the axes, so a two-line
    'how to read' can never grow into the title or the plot.
    """
    pos = ax.get_position()
    fig = ax.figure
    fig.text(pos.x0, y, title, fontsize=S.FS["chart_title"], color=S.INK,
             fontweight="bold", va="bottom")
    fig.text(pos.x0, y - 0.020, "\n".join(textwrap.wrap(howto, chars)),
             fontsize=S.FS["howto"], color=S.MUTED, va="top", linespacing=1.30)


def caption(ax, text):
    """Small label above a secondary panel, inside the space it is given."""
    pos = ax.get_position()
    ax.figure.text(pos.x0, pos.y1 + 0.010, text, fontsize=S.FS["howto"],
                   color=S.MUTED, va="bottom")


def log_ticks(ax, axis="y"):
    def fmt(v, _):
        if v >= 1e6:
            return f"{v/1e6:g}m"
        if v >= 1e3:
            return f"{v/1e3:g}k"
        return f"{v:g}"
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(mtick.FuncFormatter(fmt))


def clock(offset):
    """Whole-hour offset as a readable UTC label, signed the way clocks are."""
    o = int(offset)
    o = o - 24 if o > 12 else o
    if o == 0:
        return "UTC"
    return f"UTC{o:+d}"


def heat(ax, m, x0, x1, vmin=0, vmax=None):
    """Vector heatmap: pcolormesh, never imshow, so the PDF stays image-free."""
    m = np.asarray(m, dtype=float)
    rows, cols = m.shape
    xs = np.linspace(x0, x1, cols + 1)
    ys = np.arange(rows + 1) - 0.5
    ceiling = np.quantile(m, 0.99) if vmax is None else vmax
    ax.pcolormesh(xs, ys, m, cmap=PLUM_RAMP,
                  norm=PowerNorm(0.62, vmin=vmin, vmax=ceiling),
                  shading="flat", linewidth=0, antialiased=False)
    ax.set_xlim(x0, x1)
    ax.set_ylim(rows - 0.5, -0.5)
    ax.grid(False)


# ------------------------------------------------------------------------- cover
def page_cover(pdf=None):
    fig = plt.figure(figsize=PAGE)
    fig.patch.set_facecolor(S.BG)

    fig.patches.append(Rectangle((0.615, 0.055), 0.335, 0.875,
                                 transform=fig.transFigure, facecolor=S.PLUM,
                                 edgecolor="none", zorder=-5))

    fig.text(0.065, 0.840, "UM DATATHON 2026  \u00b7  SWIFT CASE STUDY",
             fontsize=S.FS["kicker"], color=S.MUTED, fontweight="bold")
    fig.text(0.065, 0.770, "One file,\nten million payments,\nno outside data",
             fontsize=30, color=S.PLUM, fontweight="bold", va="top",
             linespacing=1.28)
    fig.text(0.065, 0.470,
             "Eight rules recovered from a synthetic SWIFT payment file, each\n"
             "shown as a test with a baseline it could have failed. One page\n"
             "per rule; the deck reads the result, this pack reads the evidence.",
             fontsize=12.5, color=S.BODY, va="top", linespacing=1.50)

    for i, (label, value) in enumerate([("payments", "10,000,000"),
                                        ("fields", "21"),
                                        ("days", "90")]):
        fig.text(0.065 + i * 0.175, 0.268, value, fontsize=19, color=S.PLUM,
                 fontweight="bold")
        fig.text(0.065 + i * 0.175, 0.236, label, fontsize=S.FS["stat_label"],
                 color=S.MUTED)

    fig.text(0.660, 0.865, "THE EIGHT RULES", fontsize=S.FS["kicker"],
             color="#d9c3cd", fontweight="bold")
    y = 0.805
    for i, name in enumerate(GROUPS):
        fig.text(0.660, y, f"{i + 1:02d}", fontsize=11, color="#d9c3cd",
                 fontweight="bold")
        fig.text(0.700, y, name, fontsize=10.5, color="#ffffff")
        fig.text(0.918, y, f"p.{i + 3}", fontsize=9.5, color="#d9c3cd", ha="right")
        y -= 0.073
    fig.text(0.660, 0.240, "10 pages  \u00b7  one rule each  \u00b7  one baseline each",
             fontsize=9.5, color="#d9c3cd")
    fig.text(0.660, 0.135, "Every figure from all ten million rows",
             fontsize=9.5, color="#d9c3cd")

    foot(fig, 1)
    return save(fig, "00_cover", pdf)


# ------------------------------------------------------------------------ method
def page_method(pdf=None):
    fig = new_page(
        2, "How to read these pages",
        "Every rule is tested against a baseline it could have failed",
        "Four tests per rule. A rule is only written when the control holds and the "
        "second half reproduces it.")

    steps = [
        ("1", "Full data, never a sample",
         "Every count, median and ratio comes from all 10,000,000 rows. Samples are "
         "used only to draw a chart shape."),
        ("2", "Hold everything else fixed",
         "Compare inside one corridor, one chain length or one client class, so the "
         "effect cannot be the composition."),
        ("3", "A baseline that predicts nothing",
         "Equal volume per account, a uniform draw, one geometric law, "
         "drawn on the chart in ochre."),
        ("4", "A half the rule never saw",
         "The same test on a deterministic 50/50 split. A rule that fails on the "
         "second half is a coincidence."),
    ]
    y = 0.788
    for number, head, body in steps:
        fig.text(0.060, y, number, fontsize=17, color=S.OCHRE, fontweight="bold")
        fig.text(0.105, y + 0.002, head, fontsize=11.5, color=S.INK, fontweight="bold")
        fig.text(0.105, y - 0.040, "\n".join(textwrap.wrap(body, 58)),
                 fontsize=10, color=S.BODY, va="top", linespacing=1.34)
        y -= 0.162

    fig.text(0.560, 0.812, "THREE CLAIMS WE WITHDREW", fontsize=S.FS["rule_key"],
             color=S.MUTED, fontweight="bold")
    rows = [
        ("A fixed decimal shift", "Fat-finger amounts shift by 10^k with k varying per row; "
         "one fixed position would spike at one value, not spread over 2.2 dex"),
        ("An FX-rate table", "Currency is decided on the sender side; the foreign residual "
         "has no rate relationship to amount or date"),
        ("Real payee geography", "Payee addresses match the bank's country on 0.98% of rows, "
         "against 100% for the payer"),
    ]
    y = 0.770
    for head, body in rows:
        fig.text(0.560, y, head, fontsize=10.5, color=S.INK, fontweight="bold")
        fig.text(0.560, y - 0.028, "\n".join(textwrap.wrap(body, 44)),
                 fontsize=9.5, color=S.BODY, va="top", linespacing=1.30)
        y -= 0.140

    fig.patches.append(Rectangle((0.545, 0.235), 0.002, 0.580,
                                 transform=fig.transFigure, facecolor=S.RULE,
                                 edgecolor="none", zorder=-5))

    takeaway(fig, "The difference between the deck and this pack is the difference between "
                  "a result and its evidence. Every chart here can fail, and each one says "
                  "what failure would have looked like.")
    return save(fig, "01_method", pdf)


# -------------------------------------------------------------------- group 1, time
def page_time(pdf=None):
    curves = read("hour_curves", index_col="oc")
    tz = read("tz_shift")
    keep = tz.country.tolist()
    n_by_country = tz.set_index("country").n

    m = curves.loc[keep].values.astype(float)
    m = m / m.sum(axis=1, keepdims=True)
    offsets = tz.set_index("country").offset.reindex(keep).values.astype(int)
    signed = np.where(offsets > 12, offsets - 24, offsets)

    # local hour = UTC hour + offset: rolling by the offset puts every country's
    # own clock at the same place on the x axis
    m = np.vstack([np.roll(row, off) for row, off in zip(m, offsets)])
    order = np.lexsort((-n_by_country.reindex(keep).values, signed))
    m, signed, offsets = m[order], signed[order], offsets[order]

    fig = new_page(
        3, "Group 1 of 8  \u00b7  When payments happen",
        "Countries keep their own working day",
        "One template, stamped on 113 local clocks. Read each country at its own hour "
        "and the same day appears 17 times; read them all at UTC and it smears into nothing.")

    ax = axes_at(fig, panel([0.135, 0.180, 0.445]))
    heat(ax, m, 0, 24)

    ticks, labels = [], []
    for o in sorted(set(signed)):
        idx = np.where(signed == o)[0]
        if idx[0] > 0:
            ax.axhline(idx[0] - 0.5, color="white", lw=1.4, zorder=3)
        if len(idx) >= 6:
            ticks.append(float(idx.mean()))
            labels.append(f"{clock(int(o))}  \u00b7  {len(idx)}")
    ax.set_yticks(ticks)
    ax.set_yticklabels(labels)
    ax.set_xticks([0, 6, 12, 18, 24])
    ax.set_xlabel("hour of the day, on the country's own clock")
    ax.tick_params(length=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    chart(ax, "Every country runs the same local day",
          "one row per country, grouped by clock and labelled clock \u00b7 markets; "
          "brightness is the share of that country's payments, row by row", chars=60)

    meta = jload("hour_meta.json")
    rail(fig, [
        (f"{meta['offsets']}", "distinct clocks in the file"),
        (f"{meta['pairwise_after']:.2f}", "agreement between any two countries"),
        (f"{meta['pairwise_before']:.2f}", "the same countries on one clock"),
    ], [
        ("CONDITION", "country of the first bank on the route"),
        ("EFFECT", "one curve, slid by whole hours"),
        ("SCOPE", f"{meta['countries']} markets, {meta['offsets']} offsets"),
    ], "the same curves left on UTC, which agree 0.19")

    takeaway(fig, "Time features must be built on each country's own clock. The day opens "
                  "at 05:00 everywhere, dips at lunch and closes after 22:00; on a single "
                  "global clock those 17 days land in 17 different places.")
    return save(fig, "02_when", pdf)


# ---------------------------------------------------------------- group 2, currency
def page_currency(pdf=None):
    d = read("currency_two_sides")
    rng = np.random.default_rng(7)
    jitter = rng.uniform(-0.13, 0.13, len(d))

    fig = new_page(
        4, "Group 2 of 8  \u00b7  Which currency",
        "The payer's currency, and almost nothing else",
        "Each dot is one of 113 sender markets. The same payments bill in their own "
        "currency far more often than in the payee's, and no market reverses it.")

    ax = axes_at(fig, panel([0.095, 0.230, 0.515]))
    ax.scatter(d.payer_local * 100, 1 + jitter, s=26, color=S.PLUM, alpha=0.65,
               edgecolor="none", zorder=3)
    ax.scatter(d.payee_local * 100, jitter, s=26, color=S.OCHRE, alpha=0.75,
               edgecolor="none", zorder=3)
    for side, y in ((d.payer_local, 1), (d.payee_local, 0)):
        med = side.median() * 100
        ax.plot([med, med], [y - 0.26, y + 0.26], color=S.INK, lw=1.6, zorder=4)
        ax.annotate(f"{med:.0f}%", (med, y + 0.30), ha="center", va="bottom",
                    fontsize=S.FS["data"], color=S.INK, fontweight="bold")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["payee's\nhome currency", "payer's\nown currency"])
    ax.set_ylim(-0.5, 1.5)
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of a market's payments billed in that side's home currency (%)")
    S.clean(ax, "x")
    chart(ax, "Every market bills at home, none bills abroad",
          "one dot per market; the dark bar is the median market; 113 markets with "
          "5,000+ payments")

    wins = int((d.payer_local > d.payee_local).sum())

    rail(fig, [
        (f"{d.payer_local.median()*100:.0f}%", "median market billed in the payer's currency"),
        (f"{d.payee_local.median()*100:.0f}%", "median market billed in the payee's"),
        (f"{wins} of {len(d)}", "markets where the payer's side wins"),
    ], [
        ("CONDITION", "which side the currency is read from"),
        ("EFFECT", "currency follows the sender's market"),
        ("SCOPE", f"{len(d)} markets, 5,000+ payments each"),
    ], "the payee's own currency, which a shared-currency model would predict")

    takeaway(fig, "Currency is a property of the payer, so an FX exposure model built on "
                  "destination is measuring the wrong side. A payment billed in the payee's "
                  "currency is one that happens to travel inside a single currency area.")
    return save(fig, "03_currency", pdf)


# ------------------------------------------------------------------ group 3, amount
def page_amount(pdf=None):
    c = read("amount_centred")
    shape = read("country_shape")

    total = c.groupby("bin").n.sum()
    bins = total.index.values
    counts = total.values
    mean = float((bins * counts).sum() / counts.sum())
    sd = float(np.sqrt(((bins - mean) ** 2 * counts).sum() / counts.sum()))

    fig = new_page(
        5, "Group 3 of 8  \u00b7  How much",
        "One shape, slid to each market's own centre",
        "Subtract each market's median log amount and pool 158 markets. The residual is "
        "one normal curve, so only the centre carries information about the market.")

    ax = axes_at(fig, panel([0.090, 0.470, 0.500]))
    ax.bar(bins, counts / 1000, width=0.095, color=S.PLUM, alpha=0.88, zorder=2)
    xs = np.linspace(-2, 2, 300)
    dens = np.exp(-0.5 * ((xs - mean) / sd) ** 2) / (sd * np.sqrt(2 * np.pi))
    ax.plot(xs, dens * counts.sum() * 0.1 / 1000, color=S.OCHRE, lw=2.2, zorder=3)

    for cc in ["US", "IN", "BR", "NG", "DE"]:
        sub = c[c.cc == cc]
        if not len(sub):
            continue
        v = sub.set_index("bin").n.reindex(bins).fillna(0).values
        ax.plot(bins, v / v.sum() * counts.sum() / 1000, color=S.PLUM,
                lw=0.8, alpha=0.35, zorder=2)

    ax.set_xlim(-2, 2)
    ax.set_xticks([-2, -1, 0, 1, 2])
    ax.set_xticklabels(["\u00f7100", "\u00f710", "market\nmedian", "\u00d710", "\u00d7100"])
    ax.set_xlabel("payment amount, relative to its market's median")
    ax.set_yticks([])
    S.clean(ax, None)
    ax.text(0.985, 0.90, "ochre: one normal law\nplum hairlines: five markets alone",
            transform=ax.transAxes, ha="right", va="top", fontsize=S.FS["howto"],
            color=S.MUTED)
    chart(ax, "Every market is the same curve, moved",
          "all 158 markets pooled after subtracting their own centre; bars are payments "
          "in thousands, the ochre line is a normal fit")

    ax2 = axes_at(fig, [0.090, 0.235, 0.215, 0.130])
    ax2.scatter(shape.centre, shape.width, s=12, color=S.PLUM, alpha=0.6,
                edgecolor="none")
    ax2.axhline(shape.width.median(), color=S.OCHRE, lw=1.2, ls="--")
    ax2.set_ylim(0.90, 1.30)
    ax2.set_yticks([1.0, 1.1, 1.2])
    ax2.set_xticks([2.5, 3.5, 4.5])
    ax2.set_xlabel("centre (log10 USD)")
    ax2.set_ylabel("width (dex)")
    S.clean(ax2, "both")
    caption(ax2, "width is flat as the centre moves")

    ax3 = axes_at(fig, [0.380, 0.235, 0.210, 0.130])
    ax3.scatter(shape.centre_a, shape.centre_b, s=12, color=S.PLUM, alpha=0.6,
                edgecolor="none")
    lo, hi = 2.4, 4.6
    ax3.plot([lo, hi], [lo, hi], color=S.OCHRE, lw=1.2, ls="--")
    r = float(np.corrcoef(shape.centre_a, shape.centre_b)[0, 1])
    ax3.set_xlim(lo, hi)
    ax3.set_ylim(lo, hi)
    ax3.set_xticks([2.5, 3.5, 4.5])
    ax3.set_yticks([2.5, 3.5, 4.5])
    ax3.set_xlabel("centre, first half")
    ax3.set_ylabel("centre, second half")
    S.clean(ax3, "both")
    caption(ax3, f"r = {r:.3f} between the two halves")

    rail(fig, [
        (f"{len(shape)}", "markets, each with its own centre"),
        (f"{shape.width.median():.2f} dex", "the same width in every market"),
        ("650\u00d7", "poorest market's centre to richest"),
    ], [
        ("CONDITION", "the sender's market, shape held fixed"),
        ("EFFECT", "one lognormal, centre moves with market"),
        ("SCOPE", "158 markets; width 1.02 to 1.08 dex"),
    ], "the pooled normal fit, which every market sits on once its centre is removed")

    takeaway(fig, "Amount carries one free parameter per market: where the centre sits. "
                  "Width, skew and tail do not vary, so a model needs a country median and "
                  "nothing else about the payment.")
    return save(fig, "04_amount", pdf)


# ------------------------------------------------------------------- group 4, banks
def page_banks(pdf=None):
    bc = read("country_bc_medians").sort_values("ratio").reset_index(drop=True)
    q1, q3 = bc.ratio.quantile([0.25, 0.75])
    med = bc.ratio.median()

    fig = new_page(
        6, "Group 4 of 8  \u00b7  Banks and client class",
        "Client class is a constant dial on top of geography",
        "Each dot is one market's business-to-retail ticket ratio. The band is the middle "
        "half; the line is the file-wide constant. Geography sets the centre, not the step.")

    ax = axes_at(fig, panel([0.090, 0.210, 0.515]))
    x = np.arange(1, len(bc) + 1)
    ax.axhspan(q1, q3, color=S.OCHRE_SOFT, zorder=1)
    ax.axhline(med, color=S.OCHRE, lw=1.5, zorder=2)
    ax.scatter(x, bc.ratio, s=13, color=S.PLUM, edgecolor="none", zorder=3)
    ax.set_yscale("log")
    ax.set_ylim(1, 30)
    ax.set_yticks([1, 2, 3, 5, 7, 10, 20])
    log_ticks(ax, "y")
    ax.set_xlim(0, len(bc) + 1)
    ax.set_xticks([1, 40, 80, 120, len(bc)])
    ax.set_xlabel(f"{len(bc)} markets, ranked by the ratio")
    ax.set_ylabel("business ticket \u00f7 retail ticket")
    S.clean(ax, "y")
    ax.annotate(f"file-wide constant {med:.1f}\u00d7", (len(bc) * 0.06, med),
                xytext=(0, 9), textcoords="offset points", fontsize=S.FS["data"],
                color=S.OCHRE, fontweight="bold", ha="left")
    ax.text(0.015, 0.96, f"middle half: {q1:.1f}\u00d7 to {q3:.1f}\u00d7",
            transform=ax.transAxes, fontsize=S.FS["howto"], color=S.MUTED, va="top")
    chart(ax, "The 7.3\u00d7 step holds, to within a tenth of a dex",
          "one dot per market with 300+ payments in each class, ranked; 101 of 167 sit "
          "inside 0.80 to 0.95 dex, and none falls to 1\u00d7")

    rail(fig, [
        ("0", "banks outside the eight-slot code, in 25.8m appearances"),
        (f"{med:.1f}\u00d7", "business over retail median"),
        ("49\u00d7", "business-to-business over consumer-to-consumer"),
    ], [
        ("CONDITION", "client class at each end, market fixed"),
        ("EFFECT", "business multiplies the ticket by about 7.3"),
        ("SCOPE", "167 markets, 6.4\u00d7 to 8.3\u00d7 in the middle half"),
    ], "a ratio of 1, the grey floor, which would mean client class does nothing")

    takeaway(fig, "Client class is a second, independent dial on ticket size. Average ticket "
                  "says more about who is paying than about where the payment goes, which is "
                  "why country medians alone mislead.")
    return save(fig, "05_banks", pdf)


# ------------------------------------------------------------------ group 5, chain
def page_chain(pdf=None):
    d = read("participants_by_type")
    total = d.groupby("pc").n.sum()
    total = total[total.index >= 2]
    k = total.index.values.astype(float)
    obs = total.values.astype(float)
    N = obs.sum()
    share2 = obs[0] / N
    r = obs[1] / obs[0]

    pred_all = N * share2 * r ** (k - 2)
    # a z score needs an expected count: below half a payment per bucket it is noise
    keep = pred_all >= 0.5
    k_all, obs_all, pred_all = k[keep], obs[keep], pred_all[keep]
    z_all = (obs_all - pred_all) / np.sqrt(pred_all)
    k_max = int(k_all[-1])

    fig = new_page(
        7, "Group 5 of 8  \u00b7  How long the chain",
        "Chains grow by one fixed rule, and the tail obeys it",
        "Observed chain lengths against a geometric law fitted on two to ten banks. The band "
        "is two standard errors; fifteen of the sixteen lengths fall inside it, one at 2.1\u03c3.")

    ax = axes_at(fig, panel([0.090, 0.210, 0.515]))
    ax.axhspan(-2, 2, color=S.TINT, zorder=1)
    ax.axhline(0, color=S.FAINT, lw=1.0, zorder=2)
    for s in (-2, 2):
        ax.axhline(s, color=S.FAINT, lw=1.0, ls="--", zorder=2)
    ax.vlines(k_all, 0, z_all, color=S.PLUM_SOFT, lw=1.2, zorder=2)
    fitted = k_all <= 10
    ax.scatter(k_all[fitted], z_all[fitted], s=46, color=S.PLUM, zorder=4)
    ax.scatter(k_all[~fitted], z_all[~fitted], s=34, facecolor="white",
               edgecolor=S.PLUM, lw=1.1, zorder=4)
    ax.set_xticks([2, 4, 6, 8, 10, 12, 14, 16, 18])
    ax.set_xlim(1.4, 18.6)
    ax.set_ylim(-2.7, 2.7)
    ax.set_yticks([-2, -1, 0, 1, 2])
    ax.set_xlabel("banks in the visible chain")
    ax.set_ylabel("observed minus expected, in \u03c3")
    S.clean(ax, "y")
    ax.text(0.985, 0.06, "hollow: lengths past the ten-bank fit window",
            transform=ax.transAxes, ha="right", fontsize=S.FS["howto"], color=S.MUTED)
    chart(ax, f"The geometric law survives all the way to {k_max} banks",
          "each dot is one chain length with at least half a payment expected; the shaded "
          "band is what chance alone allows")

    meta_pairs = 2338
    rail(fig, [
        (f"{share2*100:.0f}%", "of payments use exactly two banks"),
        (f"{r:.3f}", "the chance of one more bank, at every step"),
        ("0 of 2,338", "country pairs that ever convert"),
    ], [
        ("CONDITION", "the visible chain and the banks at each hop"),
        ("EFFECT", "each extra bank is 0.368 as likely as the last"),
        ("SCOPE", f"chains of 2 to {k_max} banks, 2,338 country pairs"),
    ], "one geometric law fitted on two to ten banks and extended across the tail")

    takeaway(fig, "Chain length is a single parameter, not a policy choice, so long chains are "
                  "rare by construction. Conversion is a corridor property and never a "
                  "per-payment decision.")
    return save(fig, "06_chain", pdf)


# --------------------------------------------------------------- group 6, duration
def page_duration(pdf=None):
    g = read("settlement_grid")
    d = read("duration_by_pc")
    grid = g.pivot(index="pc", columns="dec", values="med").loc[sorted(g.pc.unique())]
    vals = np.log10(grid.values)

    fig = new_page(
        8, "Group 6 of 8  \u00b7  How long it takes",
        "The chain sets the wait; the ticket barely moves it",
        "Median settlement time for every chain length and amount decile. Moving down a "
        "column changes the wait 44-fold; moving across a row changes it at most 2.8-fold.")

    ax = axes_at(fig, panel([0.110, 0.180, 0.455]))
    xs = np.arange(vals.shape[1] + 1)
    ys = np.arange(vals.shape[0] + 1)
    ax.pcolormesh(xs, ys, vals, cmap=PLUM_RAMP, norm=PowerNorm(0.9, vmin=1.4, vmax=3.3),
                  shading="flat", linewidth=0, antialiased=False)
    ax.set_xlim(0, vals.shape[1])
    ax.set_ylim(vals.shape[0], 0)
    ax.grid(False)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            v = grid.values[i, j]
            txt = f"{v:.0f}" if v < 1000 else f"{v/1000:.1f}k"
            ax.text(j + 0.5, i + 0.5, txt, ha="center", va="center", fontsize=9.0,
                    color="white" if np.log10(v) > 2.55 else S.INK)
    ax.set_xticks(np.arange(10) + 0.5)
    ax.set_xticklabels([f"{c}" for c in grid.columns])
    ax.set_yticks(np.arange(len(grid.index)) + 0.5)
    ax.set_yticklabels([f"{p}" for p in grid.index])
    ax.set_xlabel("amount decile, cheapest to dearest within the file")
    ax.set_ylabel("banks in the chain")
    ax.tick_params(length=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    chart(ax, "Rows differ 44-fold, columns barely at all",
          "cell = median seconds; colour follows the same value on a log scale")

    rail(fig, [
        (f"{d.loc[d.pc == 2, 'med'].iloc[0]:.0f} s", "median wait at two banks"),
        (f"{d.loc[d.pc == 10, 'med'].iloc[0]:,.0f} s", "at ten banks, more legs, same money"),
        ("2.8\u00d7", "largest amount effect in a chain"),
    ], [
        ("CONDITION", "the number of banks in the chain"),
        ("EFFECT", "duration is the sum of the legs"),
        ("SCOPE", "2 to 10 banks, 10.0m clean payments"),
    ], "payments carrying one conversion, which sit on the same curve as those with none")

    takeaway(fig, "Latency is operational, not financial. A slow payment is a long chain of "
                  "ordinary processors, so queue time is a routing feature and not a size or "
                  "risk signal.")
    return save(fig, "07_duration", pdf)


# ---------------------------------------------------------------- group 7, parties
def page_parties(pdf=None):
    d = read("address_mix")
    meta = jload("address_meta.json")
    mix = jload("address_mix_meta.json")

    order = d.groupby("own").tot.max().sort_values(ascending=False).index.tolist()
    seg = [S.PLUM, "#8c5f74", "#ab7f92", "#c6a4b1", "#ddc9d1"]

    fig = new_page(
        9, "Group 7 of 8  \u00b7  Who is paying whom",
        "The payee's country belongs to the bank, not the payment",
        "Each row is a destination and a full bar of the countries its payee addresses name. A "
        "real address would fill the bar with one colour, the destination's own.")

    ax = axes_at(fig, [0.100, 0.205, 0.400, 0.467])
    for i, own in enumerate(order):
        g = d[d.own == own].sort_values("rk")
        left = 0.0
        for k, row in enumerate(g.itertuples()):
            if row.share <= 0:
                continue
            ax.barh(i, row.share, left=left, height=0.62, color=seg[min(k, 4)],
                    edgecolor="none", zorder=3)
            if row.share >= 0.07:
                ax.text(left + row.share / 2, i, f"{row.cc} {row.share*100:.0f}%",
                        ha="center", va="center", fontsize=9.0,
                        color="white" if k < 2 else S.INK, fontweight="bold", zorder=4)
            left += row.share
        if left < 0.999:
            ax.barh(i, 1 - left, left=left, height=0.62, color="#f2ebe6",
                    edgecolor="none", zorder=3)
        own_share = float(g.loc[g.cc == own, "share"].sum())
        ax.annotate(f"{own_share*100:.1f}%", (1.015, i), ha="left", va="center",
                    fontsize=S.FS["data"], color=S.OCHRE, fontweight="bold",
                    annotation_clip=False, zorder=4)

    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order)
    ax.tick_params(axis="y", length=0, pad=8, labelsize=S.FS["data"])
    for lab in ax.get_yticklabels():
        lab.set_fontweight("bold")
        lab.set_color(S.INK)
    ax.set_ylim(len(order) - 0.5, -0.5)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    S.percent_axis(ax, "x", decimals=0)
    ax.set_xlabel("share of the destination's payee addresses (%)")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="#ece7e1", lw=0.8)
    ax.set_axisbelow(True)
    chart(ax, "Each destination points at somebody else",
          "one row per destination; segments are the countries its addresses name, "
          "largest first; the ochre figure is the share naming the bank's own country",
          chars=74)

    rail(fig, [
        (f"{meta['payee_match']*100:.2f}%", f"of {short(meta['payee_rows'])} payee addresses "
         "name the bank's country"),
        (f"{meta['payer_match']*100:.0f}%", "of payer addresses do, so one side is real"),
        (f"{mix['own_top']*100:.1f}%", "name their own country first"),
    ], [
        ("CONDITION", "the payee address block, destination fixed"),
        ("EFFECT", "each destination names another country, not its own"),
        ("SCOPE", f"6.11m addresses, {mix['banks']:,} banks, {len(order)} destinations"),
    ], "the bank's own country, which would fill every bar one colour")

    takeaway(fig, "The payee's country is a property of the bank, not of the payment: a US "
                  "payment carries Brazilian addresses and a Singapore payment Chinese ones. "
                  "Only the payer's address block locates anything.")
    return save(fig, "08_parties", pdf)


# --------------------------------------------------------------- group 8, anomaly
def page_anomaly(pdf=None):
    a = read("anomaly_amounts")
    gaps = read("repeat_gaps")

    pretty = {
        "FAT_FINGER_MISTAKE": "Fat finger",
        "CEO_SCAM": "CEO scam",
        "ACCOUNT_REPLACEMENT_SCAM": "Account replacement",
        "CLEAN": "Clean payment",
        "CUSTOMER_RECALL": "Customer recall",
        "DUPLICATE_PAYMENT": "Duplicate",
        "ROMANCE_SCAM": "Romance scam",
    }
    a["name"] = a.label.map(pretty).fillna(a.label)
    a = a.sort_values("med", ascending=False).reset_index(drop=True)

    fig = new_page(
        10, "Group 8 of 8  \u00b7  What goes wrong",
        "Six labels, six mechanisms, and one null",
        "Top: the typical and 90th-percentile ticket per label, with clean payments in the "
        "middle. Bottom: how soon an identical payment repeats. Neither test alone separates "
        "all six.")

    ax = axes_at(fig, panel([0.195, 0.455, 0.375]))
    for i, row in a.iterrows():
        base = S.OCHRE if row.label == "CLEAN" else S.PLUM
        ax.plot([row.med, row.p90], [i, i], color=S.RULE, lw=4.0,
                solid_capstyle="round", zorder=2)
        ax.plot([row.med], [i], "o", ms=7, color=base, zorder=3)
        ax.plot([row.p90], [i], "o", ms=7, mfc="white", mec=base, mew=1.6, zorder=3)
        if row.med < 400:
            ax.annotate(money_short(row.med), (row.med, i), xytext=(0, 7),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=9.0, color=S.INK, fontweight="bold")
        else:
            ax.annotate(money_short(row.med), (row.med, i), xytext=(-7, 0),
                        textcoords="offset points", ha="right", va="center",
                        fontsize=9.0, color=S.INK, fontweight="bold")
        ax.annotate(money_short(row.p90), (row.p90, i), xytext=(7, 0),
                    textcoords="offset points", ha="left", va="center",
                    fontsize=9.0, color=S.INK, fontweight="bold")
    ax.set_yticks(np.arange(len(a)))
    ax.set_yticklabels(a.name)
    ax.set_xscale("log")
    ax.set_xlim(60, 2.2e8)
    ax.set_ylim(len(a) - 0.5, -0.5)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    S.clean(ax, "x")
    chart(ax, "Amount separates three of the six labels",
          "filled dot = median payment, hollow = 90th percentile, USD on a log scale; "
          "clean payments in ochre")

    order = ["under 2 min", "2-10 min", "10-30 min", "30-60 min",
             "1-6 hours", "6-24 hours", "1-3 days", "3-90 days"]
    g = gaps.pivot(index="bucket", columns="grp", values="n").reindex(order).fillna(0)
    share = g.div(g.sum(axis=0), axis=1)
    x = np.arange(len(order))
    ax2 = axes_at(fig, [0.090, 0.200, 0.495, 0.105])
    ax2.bar(x - 0.19, share.duplicate, width=0.34, color=S.PLUM, zorder=3)
    ax2.bar(x + 0.19, share.normal, width=0.34, color=S.OCHRE_SOFT, zorder=3,
            edgecolor=S.OCHRE, lw=0.9)
    ax2.set_xticks(x)
    ax2.set_xticklabels(["<2m", "2-10m", "10-30m", "30-60m", "1-6h", "6-24h", "1-3d", "3-90d"])
    ax2.set_xlabel("time between two identical payments")
    ax2.set_ylim(0, 0.86)
    S.percent_axis(ax2, "y", decimals=0)
    S.clean(ax2, "y")
    ax2.annotate(f"{share.duplicate.iloc[2]*100:.0f}%",
                 (x[2] - 0.19, share.duplicate.iloc[2]), xytext=(0, 4),
                 textcoords="offset points", ha="center", fontsize=9.0,
                 color=S.PLUM, fontweight="bold")
    ax2.annotate(f"{share.normal.iloc[7]*100:.0f}%",
                 (x[7] + 0.19, share.normal.iloc[7]), xytext=(0, 4),
                 textcoords="offset points", ha="center", fontsize=9.0,
                 color=S.OCHRE, fontweight="bold")
    fig.text(0.090, 0.348, "Duplicates repeat within the hour; real repeats wait days",
             fontsize=S.FS["chart_title"], color=S.INK, fontweight="bold", va="bottom")
    fig.text(0.090, 0.328, "plum: 494 duplicate pairs;  ochre: 3,125 identical clean pairs",
             fontsize=S.FS["howto"], color=S.MUTED, va="top")

    rail(fig, [
        ("7,006", "flagged rows, 0.07% of the file"),
        ("33 to 7,914", "flags per 100,000, by destination"),
        ("56%", "of fat-finger rows fix on \u00f7100"),
    ], [
        ("CONDITION", "the label, the route, the repeat timing"),
        ("EFFECT", "three labels move amount, one moves timing"),
        ("SCOPE", "7,006 rows, six labels, 233 destinations"),
    ], "clean payments: the ochre row above, the pale bars below")

    takeaway(fig, "The labels are mechanisms, not severities. A single anomaly score would "
                  "average a decimal shift, a timing pattern and two labels that look exactly "
                  "like normal payments.")
    return save(fig, "09_anomaly", pdf)


# ------------------------------------------------------------------------- driver
PAGES = {
    1: page_cover,
    2: page_method,
    3: page_time,
    4: page_currency,
    5: page_amount,
    6: page_banks,
    7: page_chain,
    8: page_duration,
    9: page_parties,
    10: page_anomaly,
}


def save(fig, name, pdf=None):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=DPI)
    if pdf is not None:
        pdf.savefig(fig, dpi=300)
    plt.close(fig)
    print(f"saved {name}")


def main(argv):
    S.setup()
    wanted = [int(a) for a in argv] if argv else sorted(PAGES)
    DOCS.mkdir(parents=True, exist_ok=True)
    target = DOCS / "Swift_Dashboard_Pack.pdf"
    with PdfPages(target) as pdf:
        pdf.infodict().update({
            "Title": "UM Datathon 2026 \u00b7 Swift case study \u00b7 dashboard",
            "Subject": "Eight reconstructed business rules, one page per feature group",
            "Author": "UM Datathon 2026",
        })
        for number in wanted:
            PAGES[number](pdf)
    print(f"wrote {target} ({target.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main(sys.argv[1:])
