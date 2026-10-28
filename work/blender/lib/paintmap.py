"""Paint map: a flat impasto layer painted straight onto the ground texture.

No geometry, no thickness — the light and deep strokes are rasterised into one
image that the slab's top face samples through its UVs.
"""
import math
import os
import random

import numpy as np
import bpy

import lilac as L
from theme import T

BASE = T.PAINT_BASE
MID = T.PAINT_MID
DEEP = T.PAINT_DEEP


def _blob_mask(xx, yy, cx, cy, rx, ry, ang, rng_params, ss):
    """Return a boolean mask of one irregular stroke inside a pixel window."""
    ca, sa = math.cos(ang), math.sin(ang)
    dx = (xx - cx) * ca + (yy - cy) * sa
    dy = -(xx - cx) * sa + (yy - cy) * ca
    r = np.sqrt(dx * dx + dy * dy)
    a = np.arctan2(dy, dx)
    k1, k2, p1, p2, h1, h2 = rng_params
    R = 1.0 + h1 * np.sin(k1 * a + p1) + h2 * np.sin(k2 * a + p2)
    R = R * (rx * np.abs(np.cos(a)) ** 0.25 + ry * np.abs(np.sin(a)) ** 0.25)
    return r < R


def build_paint_texture(name, meters_x, meters_y, px_per_meter=140, seed=31,
                        n_big=13, n_small=105, hex_base=BASE, hex_mid=MID,
                        hex_deep=DEEP, path_clear=None):
    """Rasterise base + uniformly scattered light/deep strokes into a PNG."""
    rng = random.Random(seed)
    SS = 2
    W = int(meters_x * px_per_meter)
    H = int(meters_y * px_per_meter)
    WS, HS = W * SS, H * SS

    rgb = np.zeros((HS, WS, 3), dtype=np.float32)
    base = np.array(L.hex2lin(hex_base)[:3], dtype=np.float32)
    rgb[:] = base

    tones = [np.array(L.hex2lin(hex_mid)[:3], dtype=np.float32),
             np.array(L.hex2lin(hex_deep)[:3], dtype=np.float32)]

    yy, xx = np.mgrid[0:HS, 0:WS].astype(np.float32)

    def draw(cx_m, cy_m, r_m, tone, stretch, ang):
        cx = (cx_m + meters_x / 2) * px_per_meter * SS
        cy = (cy_m + meters_y / 2) * px_per_meter * SS
        rx = r_m * px_per_meter * SS
        ry = rx * stretch
        pad = rx * 1.6 + 8
        x0, x1 = max(0, int(cx - pad)), min(WS, int(cx + pad))
        y0, y1 = max(0, int(cy - pad)), min(HS, int(cy + pad))
        if x0 >= x1 or y0 >= y1:
            return
        sub_x = xx[y0:y1, x0:x1]
        sub_y = yy[y0:y1, x0:x1]
        params = (rng.choice([3, 3, 4, 5]), rng.choice([5, 6, 7]),
                  rng.uniform(0, math.tau), rng.uniform(0, math.tau),
                  rng.uniform(0.08, 0.18), rng.uniform(0.03, 0.09))
        m = _blob_mask(sub_x, sub_y, cx, cy, rx, ry, ang, params, SS)
        rgb[y0:y1, x0:x1][m] = tone

    # jittered grid: one wash per cell keeps both tones spread evenly, never clumped
    cell = 1.55
    cols = max(1, int(round(meters_x / cell)))
    rows = max(1, int(round(meters_y / cell)))
    cw, ch = meters_x / cols, meters_y / rows
    tones_seq = [tones[i % 2] for i in range(cols * rows)]
    rng.shuffle(tones_seq)
    k = 0
    for iy in range(rows):
        for ix in range(cols):
            cx = -meters_x / 2 + (ix + 0.5) * cw + rng.uniform(-0.35, 0.35) * cw
            cy = -meters_y / 2 + (iy + 0.5) * ch + rng.uniform(-0.35, 0.35) * ch
            tone = tones_seq[k % len(tones_seq)]
            k += 1
            if rng.random() < 0.25:
                continue
            r = rng.uniform(0.15, 0.28)
            draw(cx, cy, max(r, 0.16), tone, rng.uniform(0.42, 0.85), rng.uniform(0, math.pi))
            # a couple of small dabs per cell fill the gaps organically
            for _ in range(rng.randint(0, 1)):
                r2 = rng.uniform(0.04, 0.09)
                draw(cx + rng.uniform(-cw * 0.45, cw * 0.45),
                     cy + rng.uniform(-ch * 0.45, ch * 0.45),
                     r2, tones[0] if rng.random() < 0.5 else tones[1],
                     rng.uniform(0.5, 0.9), rng.uniform(0, math.pi))

    # downsample so stroke edges stay crisp but not aliased
    rgb = rgb.reshape(H, SS, W, SS, 3).mean(axis=(1, 3))

    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, width=W, height=H, alpha=False)
    px = np.ones((H, W, 4), dtype=np.float32)
    px[..., :3] = rgb
    img.pixels.foreach_set(px.reshape(-1))
    path = os.path.join(r"C:\Users\Nico\Desktop\WOrkbudddy工作空间\10.27\work\blender\assets",
                        name + ".png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return img, path
