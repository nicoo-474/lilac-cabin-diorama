"""Irregular impasto: smooth multi-lobe outline, domed top, soft rim."""
import math
import bmesh
from mathutils import Vector

import lilac as L


def blob_points(rng, rx, ry, n=None, rough=None):
    """Closed outline from summed low harmonics so it never turns into a star."""
    n = n or rng.choice([20, 24, 28])
    h1 = rough if rough else rng.uniform(0.07, 0.15)
    h2 = h1 * rng.uniform(0.35, 0.6)
    phase = rng.uniform(0, math.pi * 2)
    k1 = rng.choice([2, 3, 3, 4])
    k2 = rng.choice([5, 6, 7])
    squash = rng.uniform(0.55, 0.95)
    pts = []
    for i in range(n):
        a = math.pi * 2 * i / n
        r = 1.0 + h1 * math.sin(k1 * a + phase) + h2 * math.sin(k2 * a + phase * 1.9)
        r += rng.uniform(-0.012, 0.012)
        pts.append(Vector((math.cos(a) * rx * r * 1.0, math.sin(a) * ry * r * squash, 0.0)))
    return pts
