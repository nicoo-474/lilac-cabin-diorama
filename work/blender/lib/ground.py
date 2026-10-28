"""Ground plate, impasto paint daubs, grass clumps and pale blue flowers."""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix

import lilac as L

# ------------------------------------------------------------------ palette
from theme import T

BASE = T.BASE           # plate / open ground
MID = T.MID             # impasto daubs (transition tone between base and deep)
GRASS = T.GRASS         # one colour for every blade
FLOWER = T.FLOWER       # pale ice blue petals
FLOWER_CORE = T.FLOWER_CORE
STEMC = T.STEMC
DEEP = T.DEEP
PATHC = T.PATHC

PLATE_W, PLATE_D, PLATE_H = 16.0, 11.0, 0.34
CABIN_C = Vector((0.30, 0.55, 0.0))

# ---- winding path from the deck steps to the front edge of the slab ----
PATH_A = Vector((CABIN_C.x + 0.05, CABIN_C.y - 2.02))
PATH_C = Vector((1.55, -3.25))
PATH_B = Vector((-1.95, -PLATE_D / 2 + 0.08))
PATH_HALF = 0.56          # stones stay inside this band


def path_point(t):
    a = PATH_A.lerp(PATH_C, t)
    b = PATH_C.lerp(PATH_B, t)
    return a.lerp(b, t)


_PATH_SAMPLES = [path_point(i / 96.0) for i in range(97)]


def dist_to_path(p):
    px, py = p.x, p.y
    return min((s.x - px) ** 2 + (s.y - py) ** 2 for s in _PATH_SAMPLES) ** 0.5


def path_tangent(t):
    d = 0.02
    p0 = path_point(max(0.0, t - d))
    p1 = path_point(min(1.0, t + d))
    v = Vector((p1.x - p0.x, p1.y - p0.y, 0.0))
    return v.normalized() if v.length > 1e-6 else Vector((0, -1, 0))


def margin_of(p, w=PLATE_W, d=PLATE_D):
    return min(w / 2 - abs(p.x), d / 2 - abs(p.y))


# -------------------------------------------------------------------- plate
def paint_material(name, img):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = L.principled(nt)
    bsdf.inputs["Roughness"].default_value = 0.82
    bsdf.inputs["Specular IOR Level"].default_value = 0.06
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "EXTEND"
    tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def build_plate(collection, mats, paint_img):
    bm = bmesh.new()
    L.box(bm, (PLATE_W, PLATE_D, PLATE_H), (0, 0, -PLATE_H / 2))
    # a slightly larger top bevel than bottom: the slab reads as cut turf
    L.bevel_edges(bm, 0.06, 3)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.new_obj("Ground_Plate", bm, collection, mats["paint"])
    me = ob.data
    # planar UVs over the slab footprint so the paint map lands 1:1
    uvl = me.uv_layers.new(name="UVMap")
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co
        uvl.data[loop.index].uv = ((co.x + PLATE_W / 2) / PLATE_W,
                                   (co.y + PLATE_D / 2) / PLATE_D)
    # the cut side of the slab keeps a flat deep tone so the diorama has a base line
    me.materials.append(mats["deep"])
    for poly in me.polygons:
        if poly.normal.z < 0.55:
            poly.material_index = 1
    return ob


def build_impasto(collection, mats, rng, count=300):
    """Irregular paint daubs in the single mid tone, with overhang at the border."""
    objs = []
    for i in range(count):
        near_edge = rng.random() < 0.25
        if near_edge:
            side = rng.choice([0, 1, 2, 3])
            if side == 0:
                x, y = rng.uniform(-PLATE_W / 2, PLATE_W / 2), rng.uniform(PLATE_D / 2 - 0.5, PLATE_D / 2)
            elif side == 1:
                x, y = rng.uniform(-PLATE_W / 2, PLATE_W / 2), rng.uniform(-PLATE_D / 2, -PLATE_D / 2 + 0.5)
            elif side == 2:
                x, y = rng.uniform(-PLATE_W / 2, -PLATE_W / 2 + 0.5), rng.uniform(-PLATE_D / 2, PLATE_D / 2)
            else:
                x, y = rng.uniform(PLATE_W / 2 - 0.5, PLATE_W / 2), rng.uniform(-PLATE_D / 2, PLATE_D / 2)
        else:
            x = rng.uniform(-PLATE_W / 2 + 0.35, PLATE_W / 2 - 0.35)
            y = rng.uniform(-PLATE_D / 2 + 0.35, PLATE_D / 2 - 0.35)
        if dist_to_path(Vector((x, y, 0))) < PATH_HALF + 0.12:
            continue
        big = rng.random() < 0.3
        rx = rng.uniform(0.48, 1.05) if big else rng.uniform(0.13, 0.30)
        ry = rx * rng.uniform(0.45, 1.0)
        thick = rng.uniform(0.016, 0.032)
        deep = rng.random() < 0.3
        ob = L.impasto_daub(
            f"Impasto_{i:03d}", rng, rx * (0.6 if deep else 1.0), ry * (0.6 if deep else 1.0),
            thick=thick * (0.75 if deep else 1.0),
            collection=collection, material=mats["deep"] if deep else mats["mid"],
            location=(x, y, i * 0.0006), rot=rng.uniform(0, L.TAU),
            bevel=min(0.014, thick * 0.5),
        )
        objs.append(ob)
    return objs


# -------------------------------------------------------------------- grass
def add_blade(bm, base, height, width, ang, lean, twist, rng, segs=4, ridge=0.32):
    d = Vector((math.cos(ang), math.sin(ang), 0.0))
    side = Vector((-math.sin(ang), math.cos(ang), 0.0))
    up = Vector((0, 0, 1))
    wob = rng.uniform(-0.22, 0.22)
    rows = []
    for i in range(segs):
        t = i / segs
        bend = lean * (t ** 1.55) * height
        spine = base + d * bend + side * (wob * math.sin(t * 1.9) * height * 0.16) + up * (height * t)
        wt = width * ((1.0 - t) ** 0.62)
        tw = twist * t
        s2 = side * math.cos(tw) + up * math.sin(tw) * 0.15
        nrm = side.cross(up).normalized()
        rows.append([
            bm.verts.new(spine - s2 * wt * 0.5),
            bm.verts.new(spine + nrm * (ridge * wt) + up * (wt * 0.10)),
            bm.verts.new(spine + s2 * wt * 0.5),
        ])
    tip = bm.verts.new(base + d * (lean * height) + up * height * 1.02)
    for i in range(segs - 1):
        a, b = rows[i], rows[i + 1]
        bm.faces.new((a[0], a[1], b[1], b[0]))
        bm.faces.new((a[1], a[2], b[2], b[1]))
    a = rows[-1]
    bm.faces.new((a[0], a[1], tip))
    bm.faces.new((a[1], a[2], tip))


def grass_positions(rng, count_ring=2000, count_inner=520):
    pos = []
    tries = 0
    while len(pos) < count_ring and tries < count_ring * 12:
        tries += 1
        x = rng.uniform(-PLATE_W / 2, PLATE_W / 2)
        y = rng.uniform(-PLATE_D / 2, PLATE_D / 2)
        p = Vector((x, y, 0))
        m = margin_of(p)
        # ring density falls off inward, and a corridor in the front stays open
        if m > 1.30:
            continue
        if rng.random() > (1.0 - (m / 1.30) ** 1.7) ** 1.5:
            continue
        if dist_to_path(p) < PATH_HALF + 0.18:
            continue
        pos.append(p)
    tries = 0
    while len(pos) < count_ring + count_inner and tries < count_inner * 25:
        tries += 1
        p = Vector((rng.uniform(-PLATE_W / 2 + 0.3, PLATE_W / 2 - 0.3),
                    rng.uniform(-PLATE_D / 2 + 0.3, PLATE_D / 2 - 0.3), 0))
        if margin_of(p) < 1.15:
            continue
        if abs(p.x - CABIN_C.x) < 2.55 and abs(p.y - CABIN_C.y) < 2.25:
            continue
        if dist_to_path(p) < PATH_HALF + 0.10:
            continue
        if rng.random() > 0.5:
            continue
        # inner clumps gather into loose islands, not an even sprinkle
        if math.sin(p.x * 1.7 + 1.1) * math.cos(p.y * 1.4 - 0.6) < -0.15:
            continue
        pos.append(p)
    return pos


def build_grass(collection, mats, rng):
    positions = grass_positions(rng)
    bm = bmesh.new()
    for p in positions:
        m = margin_of(p)
        tight = max(0.0, min(1.0, (1.35 - m) / 1.35))
        clump_h = 0.22 + 0.62 * (tight ** 0.8) + rng.uniform(-0.06, 0.12)
        clump_r = rng.uniform(0.05, 0.11)
        blades = int(rng.uniform(7, 13))
        for _ in range(blades):
            a = rng.uniform(0, L.TAU)
            r = clump_r * math.sqrt(rng.random())
            base = p + Vector((math.cos(a) * r, math.sin(a) * r, -0.01))
            h = clump_h * rng.uniform(0.62, 1.18)
            w = rng.uniform(0.042, 0.078) * (0.8 + tight * 0.45)
            add_blade(bm, base, h, w, a, rng.uniform(0.10, 0.42),
                        rng.uniform(-0.7, 0.7), rng, segs=4)
    # tufts along the trail edges so the path reads as worn, not mown
    for i in range(240):
        t = rng.uniform(0.16, 0.97)
        c = path_point(t)
        tan = path_tangent(t)
        side = Vector((-tan.y, tan.x, 0.0))
        off = rng.choice([-1, 1]) * rng.uniform(PATH_HALF + 0.10, PATH_HALF + 0.55)
        p = Vector((c.x + side.x * off, c.y + side.y * off, 0))
        if margin_of(p) < 0.12:
            continue
        clump_h = rng.uniform(0.22, 0.42)
        for _ in range(int(rng.uniform(6, 11))):
            a = rng.uniform(0, L.TAU)
            r = rng.uniform(0.02, 0.09)
            base = p + Vector((math.cos(a) * r, math.sin(a) * r, -0.01))
            add_blade(bm, base, clump_h * rng.uniform(0.7, 1.25), rng.uniform(0.035, 0.06),
                      a, rng.uniform(0.12, 0.38), rng.uniform(-0.6, 0.6), rng, segs=4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.new_obj("Grass", bm, collection, mats["grass"])
    return ob


# ------------------------------------------------------------------ flowers
def build_flower_mesh(rng, name, petal_len=0.082, petal_n=5):
    bm = bmesh.new()
    # stem: three-sided tapered tube with a gentle S bend
    segs = 5
    ring_prev = None
    bend = Vector((rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), 0))
    for i in range(segs + 1):
        t = i / segs
        c = Vector((bend.x * t * t, bend.y * t * t, 0.0)) + Vector((0, 0, 0.17 * t))
        r = 0.0045 * (1 - 0.45 * t)
        ring = []
        for k in range(3):
            a = L.TAU * k / 3
            ring.append(bm.verts.new(c + Vector((math.cos(a) * r, math.sin(a) * r, 0))))
        if ring_prev:
            for k in range(3):
                bm.faces.new((ring_prev[k], ring_prev[(k + 1) % 3], ring[(k + 1) % 3], ring[k]))
        ring_prev = ring
    head = Vector((bend.x, bend.y, 0.17))
    # petals: parametric cup, 5 around, alternating tilt
    for i in range(petal_n):
        ang = L.TAU * i / petal_n + rng.uniform(-0.06, 0.06)
        d = Vector((math.cos(ang), math.sin(ang), 0))
        sd = Vector((-math.sin(ang), math.cos(ang), 0))
        tilt = 0.55 + rng.uniform(-0.12, 0.12)
        rows = []
        nu, nv = 4, 3
        lenj = petal_len * rng.uniform(0.9, 1.1)
        for u in range(nu):
            tu = u / (nu - 1)
            wmax = 0.55 * lenj * (math.sin(math.pi * (0.15 + 0.85 * tu)) ** 0.7)
            row = []
            for v in range(nv):
                tv = (v / (nv - 1)) * 2 - 1
                pos = head + d * (lenj * tu * math.cos(tilt)) + sd * (wmax * tv)
                pos.z += lenj * tu * math.sin(tilt) + 0.006 * (1 - tv * tv) * math.sin(math.pi * tu)
                row.append(bm.verts.new(pos))
            rows.append(row)
        for u in range(nu - 1):
            for v in range(nv - 1):
                bm.faces.new((rows[u][v], rows[u][v + 1], rows[u + 1][v + 1], rows[u + 1][v]))
    # core
    core = []
    for k in range(6):
        a = L.TAU * k / 6
        core.append(bm.verts.new(head + Vector((math.cos(a) * 0.009, math.sin(a) * 0.009, 0.006))))
    cen = bm.verts.new(head + Vector((0, 0, 0.012)))
    for k in range(6):
        bm.faces.new((core[k], core[(k + 1) % 6], cen))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_flat()
    return me


def build_flowers(collection, mats, rng, count=230):
    variants = [build_flower_mesh(rng, f"FlowerMesh_{i}") for i in range(6)]
    objs = []
    placed = 0
    tries = 0
    while placed < count and tries < count * 30:
        tries += 1
        p = Vector((rng.uniform(-PLATE_W / 2 + 0.35, PLATE_W / 2 - 0.35),
                    rng.uniform(-PLATE_D / 2 + 0.35, PLATE_D / 2 - 0.35), 0))
        if abs(p.x - CABIN_C.x) < 1.95 and abs(p.y - CABIN_C.y) < 1.75:
            continue
        if dist_to_path(p) < PATH_HALF + 0.05:
            continue
        m = margin_of(p)
        if m > 1.55 and rng.random() < 0.55:
            continue
        me = variants[rng.randrange(len(variants))]
        ob = bpy.data.objects.new(f"Flower_{placed:03d}", me)
        collection.objects.link(ob)
        ob.location = p
        ob.rotation_euler = (0, 0, rng.uniform(0, L.TAU))
        s = rng.uniform(1.0, 1.45)
        ob.scale = (s, s, s * rng.uniform(0.9, 1.25))
        if not me.materials:
            me.materials.append(mats["flower"])
        objs.append(ob)
        placed += 1
    return objs

def build_path(collection, mats, rng):
    """Stepping stones that follow the winding centreline, each one an irregular slab."""
    objs = []
    t = 0.02
    i = 0
    while t < 0.985:
        p = path_point(t)
        tan = path_tangent(t)
        ang = math.atan2(tan.y, tan.x) + rng.uniform(-0.16, 0.16)
        side = Vector((-tan.y, tan.x, 0.0))
        off = side * rng.uniform(-0.13, 0.13)
        rx = rng.uniform(0.30, 0.42)
        ry = rx * rng.uniform(0.70, 0.96)
        ob = L.impasto_daub(f"Stone_{i:03d}", rng, rx, ry, thick=rng.uniform(0.030, 0.045),
                            collection=collection, material=mats["path"],
                            location=(p.x + off.x, p.y + off.y, 0.002 + i * 0.0006),
                            rot=ang, bevel=0.010, dome=False)
        objs.append(ob)
        i += 1
        t += rng.uniform(0.098, 0.122)
    return objs
