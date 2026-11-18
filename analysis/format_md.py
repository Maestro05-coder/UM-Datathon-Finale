"""Pad all markdown tables to equal column widths so they read as tables in plain text.
Run after editing any group README:  python analysis/format_md.py
Honors the separator row's alignment (---: = right). Adds blank lines around tables."""
import io, os, glob, unicodedata

def dlen(s):
    """Display width: wide chars (emoji etc.) count as 2."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)

def is_sep(cells):
    return all(c and set(c) <= set("-: ") for c in cells) and any("-" in c for c in cells)

def align_of(sep_cell):
    s = sep_cell.strip()
    if s.startswith(":") and s.endswith(":"):
        return "center"
    return "right" if s.endswith(":") else "left"

def pad(s, w, align):
    if align == "right":
        return s.rjust(w)
    if align == "center":
        left = (w - dlen(s)) // 2
        return " " * left + s + " " * (w - dlen(s) - left)
    return s.ljust(w)

def fmt_block(block):
    """block = list of raw table lines -> list of formatted lines (or None if not a table)."""
    rows = []
    for ln in block:
        t = ln.strip()
        if not (t.startswith("|") and t.endswith("|")):
            return None
        cells = [c.strip() for c in t[1:-1].split("|")]
        rows.append(cells)
    if len(rows) < 2 or not is_sep(rows[1]):
        return None
    ncol = len(rows[0])
    if any(len(r) != ncol for r in rows):
        return None                      # ragged structure - leave untouched
    aligns = [align_of(c) for c in rows[1]]
    body = [rows[0]] + rows[2:]
    widths = [max(dlen(r[i]) for r in body) for i in range(ncol)]
    out = ["| " + " | ".join(pad(r[i], widths[i], aligns[i]) for i in range(ncol)) + " |"
           for r in body]
    def sep_cell(i):
        w = widths[i]
        if aligns[i] == "right":
            return "-" * max(w - 1, 1) + ":"
        if aligns[i] == "center" and w >= 3:
            return ":" + "-" * (w - 2) + ":"
        return ":" + "-" * max(w - 1, 1)        # left (explicit colon per the md rules)
    sep = "| " + " | ".join(sep_cell(i) for i in range(ncol)) + " |"
    return [out[0], sep] + out[1:]

def format_file(path):
    lines = io.open(path, encoding="utf-8").read().splitlines()
    out, i, changed = [], 0, False
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            block = lines[i:j]
            fixed = fmt_block(block)
            if fixed:
                if out and out[-1].strip():
                    out.append("")
                out.extend(fixed)
                if j < len(lines) and lines[j].strip():
                    out.append("")
                changed = True
            else:
                out.extend(block)
            i = j
        else:
            out.append(lines[i])
            i += 1
    if changed:
        io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
        print("formatted:", path)
    else:
        print("no tables  :", path)

for p in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "**", "*.md"), recursive=True):
    if "_archive" not in p:
        format_file(os.path.normpath(p))
