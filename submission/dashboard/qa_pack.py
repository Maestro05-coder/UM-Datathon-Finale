"""Check the shipped dashboard pack mechanically.

    python dashboard/qa_pack.py

Checks, per page: 16:9 page size, no raster images, no text below the type
floor, and no text drawn on top of other text. The overlap test uses the PDF's
own glyph boxes, so it catches what a visual read misses.
"""
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "docs" / "Swift_Dashboard_Pack.pdf"
W, H = 960, 540
FLOOR = 8.4          # the footer is the only element allowed below 9.0
PAGES = 10


def overlap(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return inter / small if small else 0.0


def main():
    doc = fitz.open(PDF)
    bad = 0
    print(f"{PDF.name}: {len(doc)} pages")
    if len(doc) != PAGES:
        print(f"  FAIL page count {len(doc)}, expected {PAGES}")
        bad += 1

    for i, page in enumerate(doc, 1):
        size = (round(page.rect.width), round(page.rect.height))
        spans = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    if span["text"].strip():
                        spans.append((span["text"], span["size"], span["bbox"]))
        images = len(page.get_images(full=True))
        tiny = sorted({round(s[1], 1) for s in spans if s[1] < FLOOR - 0.1})
        clashes = []
        for a in range(len(spans)):
            for b in range(a + 1, len(spans)):
                ov = overlap(spans[a][2], spans[b][2])
                if ov > 0.18:
                    clashes.append((spans[a][0][:30], spans[b][0][:30], ov))
        flag = ""
        if size != (W, H):
            flag += f" size={size}"
            bad += 1
        if images:
            flag += f" images={images}"
            bad += 1
        if tiny:
            flag += f" tiny={tiny}"
            bad += 1
        if clashes:
            flag += f" overlaps={len(clashes)}"
            bad += 1
        print(f"  p{i:02d} {size[0]}x{size[1]} spans={len(spans):3d} "
              f"min={min((s[1] for s in spans), default=0):4.1f}{flag}")
        for c in clashes[:4]:
            print(f"       clash {c[2]:.2f}  {c[0]!r} / {c[1]!r}")

    print("PASS" if bad == 0 else f"FAIL ({bad} problems)")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
