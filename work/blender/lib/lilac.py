"""Core utilities for the lilac forest cabin scene.

Design rules baked in here:
  * every colour is a single flat sRGB value, converted to linear for nodes
  * bevel widths are per-element, never one global rounding
  * irregular forms are built from custom outlines / lofts, not scaled primitives
"""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix

TAU = math.pi * 2.0


# ---------------------------------------------------------------- colour ----
def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex2lin(h, alpha=1.0):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), alpha)


def hex2srgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)) + (1.0,)


# ------------------------------------------------------------- materials ----
def principled(nt):
    """Node names are localised in the UI, so look the BSDF up by type."""
    for n in nt.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return bsdf


def mat_flat(name, hexcol, rough=0.62, spec=0.18, emit_hex=None, emit_str=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = principled(nt)
    bsdf.inputs["Base Color"].default_value = hex2lin(hexcol)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = spec
    if emit_hex:
        bsdf.inputs["Emission Color"].default_value = hex2lin(emit_hex)
        bsdf.inputs["Emission Strength"].default_value = emit_str
    return m


def mat_glass(name, hexcol, rough=0.035, ior=1.33, tint_alpha=0.22):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = principled(nt)
    bsdf.inputs["Base Color"].default_value = hex2lin(hexcol)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["IOR"].default_value = ior
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.14
    m.use_backface_culling = False
    return m


# ------------------------------------------------------------- structure ----
def purge_scene():
    """Data-API only. bpy.ops deadlocks when called from the bridge's timer."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for block in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                  bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for b in list(block):
            if b.users == 0:
                block.remove(b)


def coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def new_obj(name, bm, collection, material=None, smooth=False, flat_loose=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if flat_loose:
        me.shade_flat()
    else:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    if material:
        me.materials.append(material)
    return ob


# ---------------------------------------------------------------- bmesh -----
def bevel_edges(bm, width, segments=2, edges=None, profile=0.5):
    if width <= 0:
        return
    geom = edges if edges is not None else list(bm.edges)
    kw = dict(geom=geom, offset=width, offset_type="OFFSET",
              segments=segments, profile=profile, affect="EDGES",
              clamp_overlap=True, loop_slide=True)
    for miter in ("ARC", "MITER_ARC"):
        try:
            bmesh.ops.bevel(bm, miter_outer=miter, **kw)
            return
        except TypeError:
            continue
        except ValueError:
            continue
    bmesh.ops.bevel(bm, **kw)


def box(bm, size, center=(0, 0, 0), mat=None):
    """Axis aligned box appended into an existing bmesh."""
    sx, sy, sz = size
    cx, cy, cz = center
    verts = []
    for dz in (-1, 1):
        for dy in (-1, 1):
            for dx in (-1, 1):
                verts.append(bm.verts.new((cx + dx * sx / 2, cy + dy * sy / 2, cz + dz * sz / 2)))
    idx = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    faces = []
    for f in idx:
        faces.append(bm.faces.new([verts[i] for i in f]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return verts, faces


def rounded_box(name, size, bevel=0.02, segs=2, collection=None, material=None,
                center=(0, 0, 0), profile=0.5):
    bm = bmesh.new()
    box(bm, size, center)
    bevel_edges(bm, bevel, segs, profile=profile)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_obj(name, bm, collection, material)


def blob_points(rng, rx, ry, n=None, rough=None):
    """Closed outline from summed low harmonics so it never turns into a star."""
    n = n or rng.choice([20, 24, 28])
    h1 = rough if rough else rng.uniform(0.07, 0.15)
    h2 = h1 * rng.uniform(0.35, 0.6)
    phase = rng.uniform(0, TAU)
    k1 = rng.choice([3, 3, 4, 5])
    k2 = rng.choice([5, 6, 7])
    squash = rng.uniform(0.34, 0.82)
    pts = []
    for i in range(n):
        a = TAU * i / n
        r = 1.0 + h1 * math.sin(k1 * a + phase) + h2 * math.sin(k2 * a + phase * 1.9)
        r += rng.uniform(-0.012, 0.012)
        pts.append(Vector((math.cos(a) * rx * r, math.sin(a) * ry * r * squash, 0.0)))
    return pts


def impasto_daub(name, rng, rx, ry, thick=0.035, collection=None, material=None,
                 location=(0, 0, 0), rot=0.0, bevel=0.018, dome=True):
    """A paint daub: irregular outline -> wall -> poked dome -> soft rim."""
    bm = bmesh.new()
    pts = blob_points(rng, rx, ry)
    verts = [bm.verts.new((p.x, p.y, 0.0)) for p in pts]
    face = bm.faces.new(verts)
    bmesh.ops.recalc_face_normals(bm, faces=[face])
    res = bmesh.ops.extrude_face_region(bm, geom=[face])
    top = [e for e in res["geom"] if isinstance(e, bmesh.types.BMFace)]
    tv = [v for v in res["geom"] if isinstance(v, bmesh.types.BMVert)]
    for v in tv:
        v.co.z += thick
    if dome:
        poked = bmesh.ops.poke(bm, faces=top, offset=thick * rng.uniform(0.10, 0.30))
        seeds = poked["verts"]
    else:
        seeds = [v for f in top for v in f.verts]
    top_faces = set()
    for v in seeds:
        for f in v.link_faces:
            top_faces.add(f)
    rim = set()
    for f in set(top_faces):
        for e in f.edges:
            if len(e.link_faces) == 2:
                nz = [abs(f2.normal.z) for f2 in e.link_faces]
                if min(nz) < 0.35:
                    rim.add(e)
    bmesh.ops.bevel(bm, geom=list(rim), offset=bevel, offset_type="OFFSET",
                    segments=2, profile=0.6, affect="EDGES", clamp_overlap=True)
    # extrude / poke / bevel can leave faces wound inward; make them consistent
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_flat()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    if material:
        me.materials.append(material)
    ob.location = location
    ob.rotation_euler = (0, 0, rot)
    return ob


def join_objects(objs, name, collection=None):
    """Merge meshes with bmesh instead of bpy.ops.object.join (no ops allowed)."""
    objs = [o for o in objs if o and o.type == "MESH"]
    if not objs:
        return None
    bm = bmesh.new()
    for o in objs:
        me = o.data
        tmp = bm.copy()
        # apply the object's matrix into a temp bmesh, then append
        src = bmesh.new()
        src.from_mesh(me)
        bmesh.ops.transform(src, matrix=o.matrix_world, verts=src.verts)
        src.to_mesh(me) if False else None
        me2 = bpy.data.meshes.new("tmp")
        src.to_mesh(me2)
        src.free()
        bm.from_mesh(me2)
        bpy.data.meshes.remove(me2)
        tmp.free()
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    ob = bpy.data.objects.new(name, out)
    (collection or bpy.context.scene.collection).objects.link(ob)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    return ob
