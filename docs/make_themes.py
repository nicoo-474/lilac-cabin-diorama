"""Build docs/themes.png: the same shot under the three palettes, side by side."""
import os
import bpy
import numpy as np

ROOT = r"C:\Users\Nico\Desktop\WOrkbudddy工作空间\10.27"
SRC = [
    ("purple", os.path.join(ROOT, r"backups\v4_purple_20261028_2150\renders\01_hero.png")),
    ("green", os.path.join(ROOT, r"backups\v5_green_20261028_2212\renders\01_hero.png")),
    ("gold", os.path.join(ROOT, r"renders\01_hero.png")),
]


def load(path):
    im = bpy.data.images.load(path, check_existing=False)
    w, h = im.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(buf)
    bpy.data.images.remove(im)
    return buf.reshape(h, w, 4)


def halve(a):
    h, w, _ = a.shape
    return a[:h // 2 * 2, :w // 2 * 2].reshape(h // 2, 2, w // 2, 2, 4).mean(axis=(1, 3))


tiles = [halve(load(p)) for _n, p in SRC]
h, w, _ = tiles[0].shape
strip = np.concatenate(tiles, axis=1)          # horizontal, same height
print("STRIP", strip.shape)

out = bpy.data.images.new("themes", w * 3, h, alpha=True)
out.colorspace_settings.name = "sRGB"
out.pixels.foreach_set(np.ascontiguousarray(strip).reshape(-1))
out.file_format = "PNG"
os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
out.filepath_raw = os.path.join(ROOT, "docs", "themes.png")
out.save()
print("SAVED", out.filepath_raw, w * 3, h)
