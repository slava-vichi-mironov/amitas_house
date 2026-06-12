"""Render a region with a pt-coordinate grid overlay for manual measurement."""
import sys
import pymupdf
from PIL import Image, ImageDraw

x0, y0, x1, y1, zoom, out = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), sys.argv[6]
doc = pymupdf.open("plans/house_plans.pdf")
page = doc[4]
clip = pymupdf.Rect(x0, y0, x1, y1)
pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip)
img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
d = ImageDraw.Draw(img)
step = 10  # pt
xx = int(x0 // step) * step
while xx < x1:
    px = (xx - x0) * zoom
    d.line([(px, 0), (px, img.height)], fill=(0, 160, 255), width=1)
    d.text((px + 2, 4), str(int(xx)), fill=(0, 100, 255))
    xx += step
yy = int(y0 // step) * step
while yy < y1:
    py = (yy - y0) * zoom
    d.line([(0, py), (img.width, py)], fill=(0, 160, 255), width=1)
    d.text((2, py + 2), str(int(yy)), fill=(0, 100, 255))
    yy += step
img.save(out)
print(out, img.size)
