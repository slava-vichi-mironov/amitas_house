"""Overlay translated first-floor walls on the ground-floor plan render."""
import json
import pymupdf
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, box

OFFSETS = {"first": (746.00, 3.16), "stairroom": (1434.81, 9.67)}
BBOXES = {"first": (3170, 880, 3640, 1420), "stairroom": (2480, 880, 2950, 1420)}

doc = pymupdf.open("plans/house_plans.pdf")
page = doc[4]
zoom = 4.0
clip = pymupdf.Rect(3900, 880, 4330, 1420)
pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip)
img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
d = ImageDraw.Draw(ov)
colors = {"first": (0, 120, 255, 140), "stairroom": (0, 200, 0, 170)}

for name, (dx, dy) in OFFSETS.items():
    data = json.load(open(f"plans/extracted_{name}.json"))
    bx = box(*BBOXES[name])
    for cls in ("red", "blue"):
        for loop in data[cls]:
            if len(loop) < 3:
                continue
            p = Polygon(loop)
            if not p.is_valid:
                p = p.buffer(0)
            if p.is_empty or p.area < 0.5:
                continue
            r = p.bounds
            if r[2] - r[0] > 350 or r[3] - r[1] > 350 or not bx.contains(p.centroid):
                continue
            pts = [((x + dx - clip.x0) * zoom, (y + dy - clip.y0) * zoom)
                   for x, y in p.exterior.coords]
            d.polygon(pts, fill=colors[name])

Image.alpha_composite(img, ov).convert("RGB").save("plans/crops/align_check.png")
print("ok")
