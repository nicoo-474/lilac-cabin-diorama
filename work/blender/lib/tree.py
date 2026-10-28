"""Procedural purple trees: lofted branching wood + textured leaf cards.

Leaf clusters deliberately stretch along their branch so a cluster never reads
as a ball; the cluster shading uses spherical normals around its own centre.
"""
import bpy
import bmesh
import math
import os
import random
from mathutils import Vector, Matrix, Euler

import lilac as L
from theme import T

LEAF_HEX = T.LEAF         # one colour for every leaf
BARK_HEX = T.BARK
TEX_DIR = r"C:\Users\Nico\Desktop\WOrkbudddy工作空间\10.27\work\blender\assets"


# --------------------------------------------------------------- leaf atlas
def make_leaf_texture(name="LeafAtlas", size=1024, seed=7, nleaf=26, hexcol=LEAF_HEX):
    """Single-colour leaf cluster with alpha, written as PNG and loaded back."""
    import numpy as np

    rng = random.Random(seed)
    ss = 2
    W = size * ss
    yy, xx = np.mgrid[0:W, 0:W].astype(np.float32)
    acc = np.zeros((W, W), dtype=np.float32)

    def stamp(cx, cy, a, b, ang, sharp=0.62):
        ca, sa = math.cos(ang), math.sin(ang)
        X = (xx - cx) * ca + (yy - cy) * sa
        Y = -(xx - cx) * sa + (yy - cy) * ca
        u = np.abs(X) / max(a, 1e-3)
        v = np.abs(Y) / max(b, 1e-3)
        # pointed-oval leaf: superellipse with sharp tips along u
        d = (u ** 2.2 + v ** 1.15) ** (1.0 / 1.15)
        edge = 1.4
        cover = np.clip((1.0 - d) * edge * 3.0, 0.0, 1.0)
        return cover

    for i in range(nleaf):
        ang = rng.uniform(0, math.tau)
        rad = rng.uniform(0.12, 0.40) * W
        cx = W * 0.5 + math.cos(ang) * rad
        cy = W * 0.5 + math.sin(ang) * rad
        a = rng.uniform(0.055, 0.105) * W
        b = a * rng.uniform(0.26, 0.42)
        acc = np.maximum(acc, stamp(cx, cy, a, b, ang + rng.uniform(-0.5, 0.5)))
    # a few leaves crossing the middle so the card is not a ring
    for i in range(6):
        cx = W * 0.5 + rng.uniform(-0.10, 0.10) * W
        cy = W * 0.5 + rng.uniform(-0.10, 0.10) * W
        a = rng.uniform(0.06, 0.09) * W
        acc = np.maximum(acc, stamp(cx, cy, a, a * 0.34, rng.uniform(0, math.pi)))

    acc = acc.reshape(size, ss, size, ss).mean(axis=(1, 3))
    alpha = np.clip(acc, 0.0, 1.0)

    _lin = L.hex2lin(hexcol)
    r, g, b = _lin[0], _lin[1], _lin[2]
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, width=size, height=size, alpha=True)
    px = np.zeros((size, size, 4), dtype=np.float32)
    px[..., 0] = r
    px[..., 1] = g
    px[..., 2] = b
    px[..., 3] = alpha
    # image rows are bottom-up; flip so it does not matter visually
    img.pixels.foreach_set(px.reshape(-1))
    path = os.path.join(TEX_DIR, name + ".png")
    os.makedirs(TEX_DIR, exist_ok=True)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return img, path


def make_single_leaf_texture(name="LeafSingle", size=256, seed=3, hexcol=LEAF_HEX):
    import numpy as np
    rng = random.Random(seed)
    ss = 3
    W = size * ss
    yy, xx = np.mgrid[0:W, 0:W].astype(np.float32)
    cx = cy = W * 0.5
    a = W * 0.30
    ang = math.radians(-18)
    ca, sa = math.cos(ang), math.sin(ang)
    X = (xx - cx) * ca + (yy - cy) * sa
    Y = -(xx - cx) * sa + (yy - cy) * ca
    u = np.abs(X) / a
    v = np.abs(Y) / (a * 0.46)
    d = (u ** 2.3 + v ** 1.12) ** (1.0 / 1.12)
    alpha = np.clip((1.0 - d) * 6.0, 0.0, 1.0)
    alpha = alpha.reshape(size, ss, size, ss).mean(axis=(1, 3))
    lin = L.hex2lin(hexcol)
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, width=size, height=size, alpha=True)
    px = np.zeros((size, size, 4), dtype=np.float32)
    px[..., 0], px[..., 1], px[..., 2] = lin[0], lin[1], lin[2]
    px[..., 3] = alpha
    img.pixels.foreach_set(px.reshape(-1))
    path = os.path.join(TEX_DIR, name + ".png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return img, path


def simple_leaf_material(img, name="M_LeafSimple", hexcol=None):
    hexcol = hexcol or T.LEAF_SIMPLE
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = L.principled(nt)
    bsdf.inputs["Base Color"].default_value = L.hex2lin(hexcol)
    bsdf.inputs["Roughness"].default_value = 0.6
    bsdf.inputs["Specular IOR Level"].default_value = 0.10
    bsdf.inputs["Emission Color"].default_value = L.hex2lin(hexcol)
    bsdf.inputs["Emission Strength"].default_value = 0.65
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "CLIP"
    nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    m.use_backface_culling = False
    return m


def leaf_material(img, name="M_Leaf", emission=0.22):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = L.principled(nt)
    bsdf.inputs["Base Color"].default_value = L.hex2lin(LEAF_HEX)
    bsdf.inputs["Roughness"].default_value = 0.55
    bsdf.inputs["Specular IOR Level"].default_value = 0.12
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    tex.extension = "CLIP"
    # leaf = diffuse + translucent, then cut by the atlas alpha
    trans = nt.nodes.new("ShaderNodeBsdfTranslucent")
    trans.inputs["Color"].default_value = L.hex2lin(LEAF_HEX)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.15
    bsdf.inputs["Emission Color"].default_value = L.hex2lin(LEAF_HEX)
    bsdf.inputs["Emission Strength"].default_value = 0.55
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    cut = nt.nodes.new("ShaderNodeMixShader")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    nt.links.new(bsdf.outputs[0], mix.inputs[1])
    nt.links.new(trans.outputs[0], mix.inputs[2])
    nt.links.new(tex.outputs["Alpha"], cut.inputs["Fac"])
    nt.links.new(tr.outputs[0], cut.inputs[1])
    nt.links.new(mix.outputs[0], cut.inputs[2])
    nt.links.new(cut.outputs[0], out.inputs["Surface"])
    m.use_backface_culling = False
    try:
        m.blend_method = "CLIP"
        m.alpha_threshold = 0.45
    except Exception:
        pass
    return m


def bark_material(name="M_Bark"):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = L.principled(nt)
    bsdf.inputs["Roughness"].default_value = 0.86
    bsdf.inputs["Specular IOR Level"].default_value = 0.08
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (7.0, 7.0, 0.65)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.2
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.62
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.36
    ramp.color_ramp.elements[0].color = L.hex2lin(T.BARK_DARK)
    ramp.color_ramp.elements[1].position = 0.66
    ramp.color_ramp.elements[1].color = L.hex2lin(T.BARK_LIGHT)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.45
    bump.inputs["Distance"].default_value = 0.03
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


# ------------------------------------------------------------------- wood
def _frame(axis):
    a = axis.normalized()
    up = Vector((0, 0, 1))
    if abs(a.dot(up)) > 0.95:
        up = Vector((1, 0, 0))
    x = a.cross(up).normalized()
    y = a.cross(x).normalized()
    return x, y


def add_tube(bm, pts, radii, sides=7, cap_end=False):
    """Loft with a parallel-transported frame so the tube never twists or pinches."""
    axes = [(pts[i + 1] - pts[i]).normalized() for i in range(len(pts) - 1)]
    x, y = _frame(axes[0])
    rings = []
    for i, p in enumerate(pts):
        if i > 0:
            a_prev = axes[i - 1]
            a_now = axes[min(i, len(axes) - 1)]
            q = a_prev.rotation_difference(a_now)
            x = (q @ x)
            x = (x - a_now * x.dot(a_now)).normalized()
            y = a_now.cross(x).normalized()
        r = radii[i]
        ring = []
        for k in range(sides):
            a = math.tau * k / sides
            ring.append(bm.verts.new(p + x * (math.cos(a) * r) + y * (math.sin(a) * r)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(sides):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % sides],
                          rings[i + 1][(k + 1) % sides], rings[i + 1][k]))
    if cap_end:
        bm.faces.new(rings[-1][::-1])
    bm.faces.new(rings[0])


def grow_branch(bm, base, direction, length, r0, r1, level, rng,
                terminals, max_level=3, curve=0.22):
    d = direction.normalized()
    perp = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.4, 1))).normalized()
    perp = (perp - d * perp.dot(d)).normalized() if abs(perp.dot(d)) < 0.98 else _frame(d)[0]
    pts, radii = [], []
    n = 4
    for i in range(n + 1):
        t = i / n
        p = base + d * (length * t) + perp * (curve * length * (t ** 2)) + Vector((0, 0, -0.06 * length * t * t))
        pts.append(p)
        radii.append(r0 + (r1 - r0) * t)
    add_tube(bm, pts, radii, sides=7 if level < 2 else 5, cap_end=level >= max_level)

    tip = pts[-1]
    if level >= max_level:
        terminals.append((pts[int(n * 0.35)], pts[-1] - pts[-2], length))
        return
    kids = rng.choice([2, 3, 3]) if level else rng.choice([3, 4])
    for k in range(kids):
        spread = 0.55 + 0.35 * rng.random()
        ang = math.tau * k / kids + rng.uniform(-0.5, 0.5)
        x, y = _frame(d)
        nd = (d + (x * math.cos(ang) + y * math.sin(ang)) * spread).normalized()
        nd.z += rng.uniform(-0.12, 0.34)
        nd.normalize()
        nl = length * rng.uniform(0.58, 0.78)
        # start the child slightly inside the parent so the fork never shows a step
        fork = tip - nd * (length * 0.055)
        grow_branch(bm, fork, nd, nl, r1 * rng.uniform(0.80, 0.92), r1 * 0.46,
                    level + 1, rng, terminals, max_level, curve * rng.uniform(0.7, 1.3))


def build_tree(name, base, scale, rng, collection, bark_mat, leaf_mat, max_level=3):
    bm = bmesh.new()
    terminals = []
    trunk_dir = Vector((rng.uniform(-0.16, 0.16), rng.uniform(-0.16, 0.16), 1)).normalized()
    grow_branch(bm, Vector(base), trunk_dir, 1.75 * scale, 0.15 * scale, 0.09 * scale,
                0, rng, terminals, max_level)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    wood = L.new_obj(name + "_Wood", bm, collection, bark_mat, flat_loose=False)
    wood.data.shade_smooth()

    clusters = []
    for (c, axis, blen) in terminals:
        cl = leaf_cluster(name + "_Leaves", c, axis, blen * 1.15, blen * 0.42, rng, leaf_mat, collection)
        clusters.append(cl)
    return wood, clusters


# ------------------------------------------------------------------- leaves
def leaf_cluster(name, center, axis, length, width, rng, mat, collection, cards=34):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    a = axis.normalized()
    x, y = _frame(a)
    for i in range(cards):
        t = rng.uniform(-0.5, 0.5)
        off = x * rng.uniform(-width, width) + y * rng.uniform(-width, width)
        pos = center + a * (length * t) + off
        # card orientation: mostly facing outward from the branch axis
        n = (off.normalized() if off.length > 1e-4 else x) + a * rng.uniform(-0.35, 0.35)
        n = (n + Vector((0, 0, rng.uniform(0.1, 0.7)))).normalized()
        tx = a.cross(n).normalized()
        ty = n.cross(tx).normalized()
        s = rng.uniform(0.55, 1.0) * (0.55 + 0.45 * (1 - abs(t)))
        hw, hh = 0.46 * s, 0.46 * s
        rows = []
        nu = nv = 3
        for iu in range(nu):
            u = iu / (nu - 1)
            row = []
            for iv in range(nv):
                v = iv / (nv - 1)
                local = tx * ((u - 0.5) * 2 * hw) + ty * ((v - 0.5) * 2 * hh)
                bulge = n * (0.10 * hw * (1 - (2 * u - 1) ** 2) * 1.4)
                vert = bm.verts.new(pos + local + bulge)
                row.append((vert, (u, v)))
            rows.append(row)
        for iu in range(nu - 1):
            for iv in range(nv - 1):
                q = [rows[iu][iv], rows[iu][iv + 1], rows[iu + 1][iv + 1], rows[iu + 1][iv]]
                f = bm.faces.new([q[0][0], q[1][0], q[2][0], q[3][0]])
                for loop, (vv, uv) in zip(f.loops, (q[0], q[1], q[2], q[3])):
                    loop[uvl].uv = uv

    # move the mesh so the object origin sits at the cluster centre (wind pivots here)
    bmesh.ops.translate(bm, verts=bm.verts, vec=-Vector(center))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    ob.location = center
    collection.objects.link(ob)
    me.materials.append(mat)
    ob.visible_shadow = False
    ob["cluster_center"] = tuple(center)
    return ob


def spherical_normals(ob, center):
    """Every vertex takes the normal of the sphere around the cluster centre."""
    me = ob.data
    c = Vector(center)
    normals = []
    for v in me.vertices:
        d = v.co - c
        if d.length < 1e-6:
            d = Vector((0, 0, 1))
        normals.append(d.normalized())
    try:
        me.normals_split_custom_set_from_vertices(normals)
        me.shade_smooth()
        return True
    except Exception as e:
        print("custom normal failed", e)
        return False
