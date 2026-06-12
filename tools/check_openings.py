"""Overlay detected openings (from house.json) onto the original plan renders."""
import json
import pymupdf
from PIL import Image, ImageDraw
import sys

sys.path.insert(0, "tools")
from build_model import SRC, OFFSETS, SCALE, load_walls, FLOORS

m = json.load(open("viewer/house.json"))
doc = pymupdf.open("plans/house_plans.pdf")
page = doc[4]

walls_pts = {f: load_walls(f) for f in FLOORS}
gb = walls_pts["ground"].bounds
ox, oy = gb[0], gb[3]

for name in FLOORS:
    bbox = SRC[name][1]
    dx, dy = OFFSETS[name]
    zoom = 5.0
    clip = pymupdf.Rect(*bbox)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    def to_px(xm, ym):
        # meters -> ground pts -> this frame pts -> px
        xp = xm / SCALE + ox - dx
        yp = oy - ym / SCALE - dy
        return ((xp - bbox[0]) * zoom, (yp - bbox[1]) * zoom)

    for o in m["floors"][name]["openings"]:
        x0, y0, x1, y1 = o["rect"]
        c = {"window": (0, 200, 0, 150), "glazing": (0, 120, 255, 150),
             "entry": (255, 0, 255, 150), "door": (255, 150, 0, 170)}[o["kind"]]
        p0 = to_px(x0, y1)
        p1 = to_px(x1, y0)
        d.rectangle([p0, p1], fill=c, outline=(0, 0, 0, 255))
    Image.alpha_composite(img, ov).convert("RGB").save(f"plans/crops/openings_{name}.png")
print("ok")
