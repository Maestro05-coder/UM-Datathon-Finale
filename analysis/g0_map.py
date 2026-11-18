"""g0 - the causal map: how the generator builds one payment, in the order it happens.

This chart is a summary of groups 1-8. Every number on it is a full-data number
already published in that group's README; nothing new is measured here.

Reading rules for the picture:
  white box        = drawn independently (nothing points into it)
  light blue box   = computed from the boxes to its left
  dashed red box   = a field that LOOKS caused by the row but is not (decoy)
  dashed grey box  = we could not establish what drives it
  arrow label      = the effect size, measured with everything else held fixed
"""
import os
import sys

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Patch
from matplotlib.path import Path
import matplotlib.patheffects as pe

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _style as S
from _common import savefig

S.apply()

# ---------------------------------------------------------------- palette
FILL_DRAW = "#ffffff"
FILL_COMP = "#e8f0f9"
FILL_DECOY = "#fdeaea"
FILL_UNK = "#f4f4f5"
STROKE = S.C_ACCENT
MUTED = S.C_MUTED


def box(ax, x0, x1, y0, y1, title, body, kind="draw", fontsize=8.4):
    """One rounded box with a bold title and a small body line."""
    style = {
        "draw": dict(fc=FILL_DRAW, ec=STROKE, lw=1.6, ls="-"),
        "comp": dict(fc=FILL_COMP, ec=STROKE, lw=1.4, ls="-"),
        "decoy": dict(fc=FILL_DECOY, ec=S.C_WARN, lw=1.8, ls=(0, (5, 3))),
        "unk": dict(fc=FILL_UNK, ec=S.C_GREY, lw=1.6, ls=(0, (4, 3))),
    }[kind]
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0,
                                boxstyle="round,pad=0,rounding_size=2.5",
                                zorder=2, **style))
    cx = (x0 + x1) / 2
    ax.text(cx, y1 - 3.2, title, ha="center", va="top", zorder=3,
            fontsize=fontsize + 1.6, fontweight="semibold", color=S.C_TEXT,
            linespacing=1.25)
    if body:
        ax.text(cx, y1 - 3.2 - 6.4 - (title.count("\n") * 3.0), body,
                ha="center", va="top", zorder=3, fontsize=fontsize,
                color=MUTED, linespacing=1.45)


def rounded(pts, r=4.0):
    """A polyline with rounded corners, as a Path."""
    pts = [np.asarray(p, dtype=float) for p in pts]
    verts, codes = [pts[0]], [Path.MOVETO]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
        d1, d2 = p0 - p1, p2 - p1
        r1 = min(r, np.linalg.norm(d1) / 2)
        r2 = min(r, np.linalg.norm(d2) / 2)
        verts += [p1 + d1 / np.linalg.norm(d1) * r1, p1,
                  p1 + d2 / np.linalg.norm(d2) * r2]
        codes += [Path.LINETO, Path.CURVE3, Path.CURVE3]
    verts.append(pts[-1])
    codes.append(Path.LINETO)
    return Path(verts, codes)


def arrow(ax, pts, color=STROKE, ls="-", lw=1.5, head=13, z=4):
    """Straight or elbow arrow; a white stroke keeps crossings readable."""
    if len(pts) == 2:
        path = Path(np.asarray(pts, dtype=float), [Path.MOVETO, Path.LINETO])
    else:
        path = rounded(pts)
    a = FancyArrowPatch(path=path, arrowstyle="-|>", mutation_scale=head,
                        shrinkA=0, shrinkB=0, lw=lw, color=color,
                        linestyle=ls, zorder=z, joinstyle="round")
    a.set_path_effects([pe.withStroke(linewidth=lw + 2.4, foreground="white")])
    ax.add_patch(a)


def elabel(ax, x, y, text, ha="left", va="center", color=MUTED, fontsize=8.2):
    ax.text(x, y, text, ha=ha, va=va, fontsize=fontsize, color=color,
            zorder=6, linespacing=1.4,
            path_effects=[pe.withStroke(linewidth=3.0, foreground="white")])


# ---------------------------------------------------------------- canvas
fig, ax = plt.subplots(figsize=(16.0, 12.6))
ax.set_xlim(0, 164)
ax.set_ylim(0, 158)
ax.axis("off")

# column / row edges
C1, C2, C3 = (4, 42), (60, 98), (118, 132)
R1, R2, R3, R4 = (96, 122), (58, 84), (20, 46), (2, 18)

# ---------------------------------------------------------------- boxes
box(ax, *C1, *R1, "Countries of the two ends",
    "only 7.3% of payments\nstay inside one country")
box(ax, *C2, *R1, "Banks on the path",
    "2 banks 63.2% · 3 banks 23.2%\n4 banks 8.6% · 5+ banks 5.0%")
box(ax, *C3, *R1, "Party type\nat each end",
    "B or C\n78.8% of senders\nare B; 28.8% of\nbeneficiaries are B")

box(ax, *C1, *R2, "Local clock",
    "one 24-hour template,\nshifted by the country's\nwhole-hour offset")
box(ax, *C2, *R2, "Each bank's currency",
    "fixed per bank, not per row\n(predicts conversions\n99.91% on a held-out half)")
box(ax, 118, 156, *R2, "Amount (USD_AMOUNT)",
    "country centre + type lift\n+ USD round mode\n(see the three arrows)")

box(ax, *C1, *R3, "Sender's address text",
    "= its bank's country\n100.00% of 8,453,693 rows")
box(ax, *C2, *R3, "Conversion count",
    "= neighbouring banks\nwhose currencies differ\n2 banks: 0.00% same-country\nvs 90.93% cross-country")
box(ax, 118, 156, *R3, "Duration",
    "= sum of the banks' own\nstep delays\nactual ≈ −13 s + 0.99 × Σ\n(predicted from 2-bank rows)")

# the decoy and the unknown
box(ax, 4, 98, *R4, "Beneficiary's address text — DECOY",
    "drawn from a random world population pool: it matches the beneficiary bank's country only 0.98% of the time,\n"
    "while the sender's address matches its bank 100.00%. The bank column carries the real geography; this text does not.",
    kind="decoy")
box(ax, *C2, 128, 148, "What makes a route Covered rather than Indirect",
    "NOT ESTABLISHED — only lead:\nsame-country corridors go Covered\n20.7% vs 10.6% cross-country",
    kind="unk")

# ---------------------------------------------------------------- arrows
# country -> clock
arrow(ax, [(23, 96), (23, 84)])
elabel(ax, 25.5, 90, "one shared 24-h template, shifted\n"
                     "by the country's whole-hour clock:\ncurve match −0.024 → +0.990")

# banks -> currencies
arrow(ax, [(79, 96), (79, 84)])
elabel(ax, 81.5, 90, "learn each bank's currency,\nthen predict: 99.91% correct\non a held-out half (≈4m rows)")

# currencies -> conversions
arrow(ax, [(79, 58), (79, 46)])
elabel(ax, 81.5, 52, "banks that differ:\n2-bank routes 0.00% same-\ncountry vs 90.93% cross-country")

# country -> amount, along the top margin, entering above the party-type box
arrow(ax, [(14, 122), (14, 151), (142, 151), (142, 84)])
elabel(ax, 20, 153, "amount level: every country has its own lognormal centre — 0.572 dex between countries, "
                    "split-half r = 0.998 (g3)", va="bottom")
elabel(ax, 145, 120, "…so the two\ncountries set\nhow big\npayments are", ha="left")

# party type -> amount
arrow(ax, [(122, 96), (122, 84)])
elabel(ax, 124, 90, "+0.865 dex per business end\n(B→B = +1.69 dex = ×49)")

# currency -> amount (the only backward edge: amount is drawn before this label exists)
arrow(ax, [(98, 72), (118, 72)], ls=(0, (5, 3)), color=S.C_WARN)
elabel(ax, 109.5, 78.5, "USD round mode\napplied last:\n0.94% → 37.5%\nwhole dollars", ha="center", va="center")

# banks -> duration, down the middle gutter
arrow(ax, [(98, 108), (100.5, 108), (100.5, 33), (118, 33)])
elabel(ax, 101, 26, "duration = sum of\nthe banks' own\nstep delays (g6)", ha="left")

# country -> sender address, bypassing the clock in the left gutter
arrow(ax, [(42, 100), (48, 100), (48, 30), (42, 30)])
elabel(ax, 44, 23.5, "address country =\nbank country, 100.00%\n(sender only)", ha="left")

# unknown -> banks
arrow(ax, [(79, 128), (79, 122)], color=S.C_GREY, ls=(0, (4, 3)))
elabel(ax, 84, 125, "the label is the bank count (100%);\nIndirect vs Covered has no rule", ha="left", va="center")

# decoy: no arrow reaches it
elabel(ax, 99, 10, "✗", color=S.C_WARN, fontsize=15, ha="left", va="center")
elabel(ax, 104, 10, "nothing in the row causes this text — it is decoration", color=S.C_WARN)

# ---------------------------------------------------------------- title & key
ax.set_title("How the generator builds one payment: the whole causal map", loc="left",
             pad=72, fontsize=16, color=S.C_TEXT)
ax.annotate("Left to right is the order the generator works in. White = drawn freely. "
            "Blue = computed from the boxes it points at. Arrow labels are full-data effect sizes,\n"
            "each measured with everything else held fixed. 10,000,000 rows; clean rows only "
            "(ANOMALY_TYPE IS NULL), n = 9,992,994.",
            xy=(0, 1), xycoords="axes fraction", xytext=(0, 14),
            textcoords="offset points", ha="left", va="bottom",
            fontsize=10.5, color=MUTED, linespacing=1.5)

# ---------------------------------------------------------------- what is independent
notes = (
    "WHAT DOES NOT MOVE ANYTHING  —  every line below is a full-data control\n"
    "• route length → amount: median log10 amount 3.563 / 3.564 / 3.565 / 3.566 / 3.566 dex for 2–6 banks\n"
    "• route length → party type: business senders 78.76% / 78.76% / 78.86% / 78.66% / 78.77% for 2–6 banks\n"
    "• currency → amount size: median |Δ| 0.017 dex; only the USD number format changes, not the level\n"
    "• conversions → duration: 44 s with none vs 38 s with one  ·  hidden bank → duration: 44 s vs 44 s\n"
    "• the Covered label → duration: 3.27× raw, 1.99× same corridor, 1.14× same corridor + same middle bank (g6)"
)
ax.annotate(notes, xy=(0, -0.035), xycoords="axes fraction", xytext=(0, 0),
            textcoords="offset points", ha="left", va="top", fontsize=10,
            color=S.C_MUTED, linespacing=1.55, zorder=7,
            bbox=dict(boxstyle="round,pad=0.7", fc="#f7f8fa", ec="#d7dde5", lw=1.0))

key = [
    Patch(fc=FILL_DRAW, ec=STROKE, lw=1.6, label="drawn first — independent of everything else"),
    Patch(fc=FILL_COMP, ec=STROKE, lw=1.4, label="computed from the boxes it points at"),
    Patch(fc=FILL_DECOY, ec=S.C_WARN, lw=1.8, ls=(0, (5, 3)), label="decoy — no cause in the row"),
    Patch(fc=FILL_UNK, ec=S.C_GREY, lw=1.6, ls=(0, (4, 3)), label="not established"),
    Patch(fc="none", ec=S.C_WARN, lw=1.5, ls=(0, (5, 3)), label="backward edge — applied after the amount is drawn"),
]
ax.legend(handles=key, loc="upper left", bbox_to_anchor=(-0.005, -0.245), ncol=2,
          frameon=False, fontsize=10, handlelength=1.8, columnspacing=2.4,
          borderaxespad=0, labelspacing=0.7)

savefig(fig, "causal_map.png", group="g0_causal_map")
