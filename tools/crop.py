"""Render a region of a PDF page at high zoom.

Usage: uv run python tools/crop.py PAGE X0 Y0 X1 Y1 ZOOM OUT
Coordinates are fractions (0..1) of the *rendered* (rotation-applied) page.
"""
import sys
import pymupdf

page_idx = int(sys.argv[1])
x0, y0, x1, y1 = map(float, sys.argv[2:6])
zoom = float(sys.argv[6])
out = sys.argv[7]

doc = pymupdf.open("plans/house_plans.pdf")
page = doc[page_idx]
r = page.rect  # already rotation-applied
clip = pymupdf.Rect(x0 * r.width, y0 * r.height, x1 * r.width, y1 * r.height)
pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip)
pix.save(out)
print(out, pix.width, pix.height)
