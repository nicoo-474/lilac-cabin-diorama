"""Glazed tea-house cabin: thin dark frame, big glass panes, readable interior."""
import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Euler

import lilac as L
from theme import T

FRAME = T.FRAME
DECK = T.DECK
GLASS = T.GLASS
TATAMI = T.TATAMI
WOOD2 = T.WOOD2
CUSHION = T.CUSHION
LAMP = T.LAMP

W, D = 3.05, 2.45          # footprint
H = 2.02                   # wall height
DECK_H = 0.17
POST = 0.105


def _beveled(bm, w, s=2, profile=0.5):
    if w > 0:
        L.bevel_edges(bm, w, s, profile=profile)


def part(name, size, center, mat, collection, bevel=0.004, segs=2, rot=None, profile=0.5):
    bm = bmesh.new()
    L.box(bm, size, (0, 0, 0))
    _beveled(bm, bevel, segs, profile)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.new_obj(name, bm, collection, mat, flat_loose=False)
    ob.location = center
    if rot:
        ob.rotation_euler = rot
    return ob


def glass_pane(name, size, center, mat, collection, rot=None):
    return part(name, size, center, mat, collection, bevel=0.0022, segs=2, rot=rot)


def lathe(name, profile, mat, collection, center=(0, 0, 0), segs=24, scale=1.0):
    """Revolve a (radius, z) profile — teapots and cups are not stacked spheres."""
    bm = bmesh.new()
    rings = []
    for (r, z) in profile:
        ring = []
        for k in range(segs):
            a = math.tau * k / segs
            ring.append(bm.verts.new((math.cos(a) * r * scale, math.sin(a) * r * scale, z * scale)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(segs):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % segs],
                          rings[i + 1][(k + 1) % segs], rings[i + 1][k]))
    # close both ends with fans
    top = bm.verts.new((0, 0, profile[-1][1] * scale))
    bot = bm.verts.new((0, 0, profile[0][1] * scale))
    for k in range(segs):
        bm.faces.new((rings[-1][k], rings[-1][(k + 1) % segs], top))
        bm.faces.new((rings[0][(k + 1) % segs], rings[0][k], bot))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.new_obj(name, bm, collection, mat, flat_loose=False)
    ob.location = center
    return ob



def quad_slab(name, corners, thick, mat, collection, bevel=0.0, segs=1):
    """Thickness along the quad normal; corners are world points, so nothing drifts."""
    bm = bmesh.new()
    vs = [bm.verts.new(c) for c in corners]
    f = bm.faces.new(vs)
    bmesh.ops.recalc_face_normals(bm, faces=[f])
    n = f.normal.copy()
    res = bmesh.ops.extrude_face_region(bm, geom=[f])
    tv = [v for v in res["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=tv, vec=n * thick)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, offset_type="OFFSET",
                        segments=segs, profile=0.5, affect="EDGES", clamp_overlap=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return L.new_obj(name, bm, collection, mat, flat_loose=False)


def beam_between(name, p0, p1, w, h, mat, collection, bevel=0.004, segs=2):
    p0, p1 = Vector(p0), Vector(p1)
    d = (p1 - p0)
    L_ = d.length
    if L_ < 1e-5:
        return None
    z = d.normalized()
    up = Vector((0, 0, 1))
    if abs(z.dot(up)) > 0.98:
        up = Vector((0, 1, 0))
    x = z.cross(up).normalized()
    y = z.cross(x).normalized()
    bm = bmesh.new()
    verts = []
    for t in (0.0, 1.0):
        c = p0 + d * t
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            verts.append(bm.verts.new(c + x * (sx * w / 2) + y * (sy * h / 2)))
    idx = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    for q in idx:
        bm.faces.new([verts[i] for i in q])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        L.bevel_edges(bm, bevel, segs)
    return L.new_obj(name, bm, collection, mat, flat_loose=False)


def build_cabin(collection, mats, rng):
    objs = []
    hw, hd = W / 2, D / 2

    # ---- deck: two thin slabs so the edge reads as boards, not one block
    objs.append(part("Deck", (W + 0.62, D + 0.62, DECK_H), (0, 0, DECK_H / 2), mats["deck"],
                     collection, bevel=0.028, segs=3))
    objs.append(part("DeckLip", (W + 0.70, D + 0.70, 0.035), (0, 0, 0.017), mats["deck"],
                     collection, bevel=0.010, segs=2))
    ztop = DECK_H

    # ---- posts
    for sx in (-1, 0, 1):
        for sy in (-1, 1):
            objs.append(part(f"Post_{sx}_{sy}", (POST, POST, H), (sx * hw, sy * hd, ztop + H / 2),
                             mats["frame"], collection, bevel=0.006, segs=2))
    # two posts on the open front edge, leaving the door bay clear
    for sx in (-1, 1):
        objs.append(part(f"PostF_{sx}", (POST, POST, H), (sx * hw, -hd, ztop + H / 2),
                         mats["frame"], collection, bevel=0.006, segs=2))

    # ---- sill + head beams
    objs.append(part("Sill_S", (W + 0.1, 0.07, 0.10), (0, hd, ztop + 0.05), mats["frame"],
                     collection, bevel=0.005, segs=2))
    objs.append(part("Sill_N", (W + 0.1, 0.07, 0.10), (0, -hd, ztop + 0.05), mats["frame"],
                     collection, bevel=0.005, segs=2))
    for sx in (-1, 1):
        objs.append(part(f"Sill_{sx}", (0.07, D, 0.10), (sx * hw, 0, ztop + 0.05), mats["frame"],
                         collection, bevel=0.005, segs=2))
    for sy in (-1, 1):
        objs.append(part(f"Head_{sy}", (W + 0.16, 0.085, 0.12), (0, sy * hd, ztop + H - 0.06),
                         mats["frame"], collection, bevel=0.005, segs=2))
    for sx in (-1, 1):
        objs.append(part(f"HeadSide_{sx}", (0.085, D + 0.16, 0.12), (sx * hw, 0, ztop + H - 0.06),
                         mats["frame"], collection, bevel=0.005, segs=2))

    # ---- glass: three closed sides + a half-open sliding door in front
    gy0, gy1 = ztop + 0.10, ztop + H - 0.12
    gh = gy1 - gy0
    gz = (gy0 + gy1) / 2
    objs.append(glass_pane("Glass_Back", (W - 0.02, 0.022, gh), (0, hd - 0.03, gz),
                           mats["glass"], collection))
    for sx in (-1, 1):
        objs.append(glass_pane(f"Glass_Side_{sx}", (0.022, D - 0.02, gh), (sx * (hw - 0.03), 0, gz),
                               mats["glass"], collection))
    # front: left half fixed glazing, right half a slid-open door panel
    objs.append(glass_pane("Glass_FrontL", (W * 0.46, 0.022, gh), (-W * 0.24, -hd + 0.03, gz),
                           mats["glass"], collection))
    objs.append(glass_pane("DoorPanel", (W * 0.44, 0.026, gh * 0.98),
                           (W * 0.20, -hd + 0.14, gz), mats["glass"], collection))
    objs.append(part("DoorFrameT", (W * 0.46, 0.045, 0.05), (W * 0.20, -hd + 0.14, gy1 - 0.02),
                     mats["frame"], collection, bevel=0.004, segs=2))
    objs.append(part("DoorFrameB", (W * 0.46, 0.045, 0.05), (W * 0.20, -hd + 0.14, gy0 + 0.02),
                     mats["frame"], collection, bevel=0.004, segs=2))

    # ---- mullions: vertical + horizontal bars that give the glazed lattice look
    for sy in (-1, 1):
        for i in range(1, 4):
            x = -hw + i * W / 4
            objs.append(part(f"Mullion_{sy}_{i}", (0.032, 0.036, gh), (x, sy * (hd - 0.02), gz),
                             mats["frame"], collection, bevel=0.003, segs=2))
        objs.append(part(f"MullionH_{sy}", (W, 0.034, 0.03), (0, sy * (hd - 0.02), gz + 0.02),
                         mats["frame"], collection, bevel=0.003, segs=2))
    for sx in (-1, 1):
        for i in range(1, 3):
            y = -hd + i * D / 3
            objs.append(part(f"MullionS_{sx}_{i}", (0.036, 0.032, gh), (sx * (hw - 0.02), y, gz),
                             mats["frame"], collection, bevel=0.003, segs=2))
        objs.append(part(f"MullionSH_{sx}", (0.034, D, 0.03), (sx * (hw - 0.02), 0, gz + 0.02),
                         mats["frame"], collection, bevel=0.003, segs=2))

    # ---- gable roof, built from explicit world-space corners
    ridge_z = ztop + H + 0.72
    eave_z = ztop + H - 0.04
    over = 0.42
    edge_x = hw + 0.18
    objs.append(beam_between("Ridge", (-edge_x - 0.05, 0, ridge_z), (edge_x + 0.05, 0, ridge_z),
                             0.11, 0.11, mats["frame"], collection, bevel=0.006, segs=2))
    for sy in (-1, 1):
        objs.append(quad_slab(f"RoofGlass_{sy}",
                              [(-edge_x, 0, ridge_z), (edge_x, 0, ridge_z),
                               (edge_x, sy * (hd + over), eave_z),
                               (-edge_x, sy * (hd + over), eave_z)],
                              0.030, mats["glass"], collection, bevel=0.003, segs=2))
        for i in range(4):
            x = -hw + 0.12 + i * (W - 0.24) / 3
            objs.append(beam_between(f"Rafter_{sy}_{i}", (x, 0, ridge_z - 0.03),
                                     (x, sy * (hd + over), eave_z - 0.03),
                                     0.042, 0.055, mats["frame"], collection, bevel=0.004, segs=2))
        objs.append(beam_between(f"Eave_{sy}", (-edge_x, sy * (hd + over), eave_z - 0.02),
                                 (edge_x, sy * (hd + over), eave_z - 0.02),
                                 0.06, 0.075, mats["frame"], collection, bevel=0.004, segs=2))
    # gable ends closed with tinted glass triangles
    for sx in (-1, 1):
        objs.append(quad_slab(f"GableGlass_{sx}",
                              [(sx * (hw + 0.02), -hd + 0.02, ztop + H - 0.10),
                               (sx * (hw + 0.02), hd - 0.02, ztop + H - 0.10),
                               (sx * (hw + 0.02), 0, ridge_z - 0.14)],
                              0.02, mats["glass"], collection))

    # ---- interior: tatami, table, cushions, tea set, lantern
    objs.append(part("Tatami_A", (W / 2 - 0.12, D - 0.24, 0.10), (-W / 4 + 0.02, 0, ztop + 0.05),
                     mats["tatami"], collection, bevel=0.01, segs=2))
    objs.append(part("Tatami_B", (W / 2 - 0.12, D - 0.24, 0.10), (W / 4 - 0.02, 0, ztop + 0.05),
                     mats["tatami"], collection, bevel=0.01, segs=2))
    tz = ztop + 0.10
    objs.append(part("TableTop", (0.94, 0.62, 0.055), (0.05, 0.02, tz + 0.30), mats["wood2"],
                     collection, bevel=0.012, segs=3))
    for sx in (-1, 1):
        for sy in (-1, 1):
            objs.append(part(f"TableLeg_{sx}{sy}", (0.05, 0.05, 0.30),
                             (0.05 + sx * 0.38, 0.02 + sy * 0.23, tz + 0.15), mats["wood2"],
                             collection, bevel=0.008, segs=2))
    for i, (cx, cy) in enumerate(((-0.62, -0.55), (0.72, 0.42))):
        objs.append(part(f"Cushion_{i}", (0.44, 0.44, 0.10), (cx, cy, tz + 0.05), mats["cushion"],
                         collection, bevel=0.045, segs=4))
    # teapot: lathe profile with a spout and handle
    pot = lathe("Teapot",
                [(0.0, 0.0), (0.060, 0.005), (0.086, 0.032), (0.101, 0.071),
                 (0.092, 0.113), (0.064, 0.140), (0.046, 0.152), (0.048, 0.161)],
                mats["tatami"], collection, (0.06, 0.04, tz + 0.325), segs=22)
    objs.append(pot)
    spout = lathe("Spout", [(0.0, 0.0), (0.019, 0.0), (0.034, 0.036)], mats["tatami"], collection,
                  (0.130, 0.04, tz + 0.37), segs=10)
    spout.rotation_euler = (0, math.radians(58), 0)
    objs.append(spout)
    for i, (cx, cy) in enumerate(((0.15, -0.16), (0.02, -0.20), (-0.12, -0.13))):
        objs.append(lathe(f"Cup_{i}",
                          [(0.0, 0.0), (0.024, 0.0), (0.031, 0.007), (0.029, 0.040), (0.024, 0.043)],
                          mats["tatami"], collection, (cx, cy, tz + 0.328), segs=14))
    # lantern
    objs.append(part("LampCord", (0.012, 0.012, 0.34), (0, 0.34, ztop + H - 0.28), mats["frame"],
                     collection, bevel=0.0))
    objs.append(lathe("Lantern",
                      [(0.0, 0.0), (0.055, 0.0), (0.072, 0.025), (0.075, 0.085),
                       (0.062, 0.135), (0.040, 0.155), (0.0, 0.16)],
                      mats["lamp"], collection, (0, 0.34, ztop + H - 0.48), segs=18))
    return objs
