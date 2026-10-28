"""Wind and falling leaves.

Grass is bent by a Geometry Nodes rig: a *purely horizontal* offset scaled by
(z/h)^2, so the roots stay planted and the tips arc over. A Wave modifier was
tried first and had to go -- its displacement axis is local Z, so on a meadow it
pushes every blade up and down and reads as vertical stretching.
Leaf clusters get a small rotational sway on top; falling leaves are hand-keyed
cards so the shot is deterministic and renders the same on every frame.
"""
import bpy
import bmesh
import math
import random
from mathutils import Vector

import lilac as L

# global wind heading (grass bends this way, gusts travel along it)
WIND_DIR = (0.94, 0.34, 0.0)
WIND_CROSS = (-0.42, 0.91, 0.0)


# ------------------------------------------------------------- node helpers
def _is_sock(v):
    return hasattr(v, "is_output")


def _math(nt, op, loc, a=None, b=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.location = loc
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if _is_sock(v):
            nt.links.new(v, n.inputs[i])
        else:
            n.inputs[i].default_value = float(v)
    return n.outputs[0]


def _vmath(nt, op, loc, a=None, b=None, scale=None):
    n = nt.nodes.new("ShaderNodeVectorMath")
    n.operation = op
    n.location = loc
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if _is_sock(v):
            nt.links.new(v, n.inputs[i])
        else:
            n.inputs[i].default_value = v
    if scale is not None:
        if _is_sock(scale):
            nt.links.new(scale, n.inputs[3])
        else:
            n.inputs[3].default_value = float(scale)
    return n.outputs[0]


def add_grass_wind(ob, height=0.72, amplitude=0.155, speed=0.16, cross=0.34):
    """Bend the meadow: horizontal offset only, weighted by a cantilever curve.

    The weight profile is (z/h)^1.7, which tracks a real cantilever's deflection
    u^2(3-u)/2 closely (0.30 vs 0.31 at mid-blade) -- the whole blade curves
    instead of only the tip flipping over. Z of both directions is 0, so no
    vertex can ever move vertically.

    Two crossing sine waves (one along WIND_DIR, one along WIND_CROSS) give the
    blades a small elliptical trace instead of a flat back-and-forth; the phase
    comes from a spatial noise field, so gusts roll across the field as bands
    instead of the whole meadow pulsing in sync.
    """
    for old in list(ob.modifiers):
        if old.name.startswith("Wind"):
            ob.modifiers.remove(old)
    vg = ob.vertex_groups.get("wind")
    if vg:
        ob.vertex_groups.remove(vg)

    ng = bpy.data.node_groups.new("GrassWind", "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    s_amp = ng.interface.new_socket(name="Amplitude", in_out="INPUT", socket_type="NodeSocketFloat")
    s_spd = ng.interface.new_socket(name="Speed", in_out="INPUT", socket_type="NodeSocketFloat")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    gi = ng.nodes.new("NodeGroupInput")
    gi.location = (-1560, 0)
    go = ng.nodes.new("NodeGroupOutput")
    go.location = (1180, 0)
    geo_in = gi.outputs[0]
    amp_in = gi.outputs[1]
    spd_in = gi.outputs[2]

    pos = ng.nodes.new("GeometryNodeInputPosition")
    pos.location = (-1560, -340)
    clock = ng.nodes.new("GeometryNodeInputSceneTime")
    clock.location = (-1560, 300)

    # --- root/tip weight: 0 at the soil, 1 at the blade tip
    sep = ng.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-1340, -300)
    ng.links.new(pos.outputs[0], sep.inputs[0])
    mr = ng.nodes.new("ShaderNodeMapRange")
    mr.location = (-1150, -300)
    mr.clamp = True
    mr.inputs[1].default_value = 0.0          # from min
    mr.inputs[2].default_value = height       # from max
    mr.inputs[3].default_value = 0.0          # to min
    mr.inputs[4].default_value = 1.0          # to max
    ng.links.new(sep.outputs[2], mr.inputs[0])
    arc = _math(ng, "POWER", (-960, -300), mr.outputs[0], 1.7)

    # --- per-area phase from a noise field (features ~3 m wide -> rolling gusts)
    nvec = _vmath(ng, "MULTIPLY", (-1340, 120), pos.outputs[0], (0.30, 0.30, 0.0))
    noise = ng.nodes.new("ShaderNodeTexNoise")
    noise.location = (-1150, 120)
    ng.links.new(nvec, noise.inputs[0])
    noise.inputs[2].default_value = 1.0       # scale (coords are pre-scaled)
    noise.inputs[3].default_value = 2.0       # detail
    noise.inputs[4].default_value = 0.55      # roughness
    nfac = noise.outputs[0]

    # --- travelling gust along WIND_DIR
    phase_a = _math(ng, "MULTIPLY", (-940, 220), nfac, 6.2832)
    travel = _vmath(ng, "DOT_PRODUCT", (-960, 60), pos.outputs[0], (0.62, 0.24, 0.0))
    time_a = _math(ng, "MULTIPLY", (-960, 420), clock.outputs[1], spd_in)
    ph1 = _math(ng, "ADD", (-720, 260), phase_a, travel)
    ph1 = _math(ng, "ADD", (-560, 260), ph1, time_a)
    s1 = _math(ng, "SINE", (-400, 260), ph1)
    a1 = _math(ng, "MULTIPLY", (-240, 200), s1, arc)
    a1 = _math(ng, "MULTIPLY", (-80, 200), a1, amp_in)
    off1 = _vmath(ng, "SCALE", (120, 240), WIND_DIR, scale=a1)

    # --- smaller cross wave, so the motion is a little elliptical
    phase_b = _math(ng, "MULTIPLY", (-940, -60), nfac, 11.7)
    travel_b = _vmath(ng, "DOT_PRODUCT", (-960, -200), pos.outputs[0], (-0.28, 0.96, 0.0))
    spd_b = _math(ng, "MULTIPLY", (-960, 560), spd_in, 1.31)
    time_b = _math(ng, "MULTIPLY", (-780, 560), clock.outputs[1], spd_b)
    ph2 = _math(ng, "ADD", (-720, -60), phase_b, travel_b)
    ph2 = _math(ng, "ADD", (-560, -60), ph2, time_b)
    ph2 = _math(ng, "ADD", (-400, -60), ph2, 1.7)
    s2 = _math(ng, "SINE", (-240, -60), ph2)
    a2 = _math(ng, "MULTIPLY", (-80, -60), s2, arc)
    a2 = _math(ng, "MULTIPLY", (60, -60), a2, amp_in)
    a2 = _math(ng, "MULTIPLY", (200, -60), a2, cross)
    off2 = _vmath(ng, "SCALE", (360, -60), WIND_CROSS, scale=a2)

    off = _vmath(ng, "ADD", (560, 100), off1, off2)
    setp = ng.nodes.new("GeometryNodeSetPosition")
    setp.location = (800, 0)
    ng.links.new(geo_in, setp.inputs[0])
    ng.links.new(off, setp.inputs[3])          # Offset; Z of both dirs is 0
    ng.links.new(setp.outputs[0], go.inputs[0])

    # 5.2 dropped ID-property access on the modifier (`mod["Socket_1"]`), so the
    # values live on the group interface -- fine, this group has one user.
    s_amp.default_value = amplitude
    s_spd.default_value = speed

    mod = ob.modifiers.new("Wind", "NODES")
    mod.node_group = ng
    return mod


def add_cluster_sway(objs, rng, frames=96, amp=0.045):
    """Sinusoidal rotation keys, phase-shifted per cluster so nothing beats in sync."""
    _prefs = bpy.context.preferences.edit
    _keep = _prefs.keyframe_new_interpolation_type
    _prefs.keyframe_new_interpolation_type = "BEZIER"
    for i, ob in enumerate(objs):
        ob.rotation_mode = "XYZ"
        phase = rng.uniform(0, math.tau)
        freq = rng.uniform(0.55, 1.05)
        a = amp * rng.uniform(0.6, 1.5)
        for f in range(1, frames + 1, 12):
            t = (f - 1) / max(1, frames - 1) * math.tau * freq + phase
            ob.rotation_euler = (math.sin(t) * a, math.cos(t * 1.3) * a * 0.8, math.sin(t * 0.7) * a * 0.4)
            ob.keyframe_insert("rotation_euler", frame=f)
        _prefs.keyframe_new_interpolation_type = _keep



def make_card(name, size, mat, collection, uv=True):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    vs = [bm.verts.new((-size / 2, 0, -size / 2)), bm.verts.new((size / 2, 0, -size / 2)),
          bm.verts.new((size / 2, 0, size / 2)), bm.verts.new((-size / 2, 0, size / 2))]
    f = bm.faces.new(vs)
    for loop, uvco in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop[uvl].uv = uvco
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    ob.visible_shadow = False
    return ob


def build_falling_leaves(collection, mat, rng, count=90, frames=96,
                         spawn_centers=None, area=(15.0, 10.0), z_top=(2.6, 6.2)):
    """Staggered falls: each leaf starts high and drifts down through the shot."""
    objs = []
    prefs = bpy.context.preferences.edit
    keep = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for i in range(count):
        if spawn_centers:
            cx, cy, r = spawn_centers[i % len(spawn_centers)]
            x = cx + rng.uniform(-r, r)
            y = cy + rng.uniform(-r, r)
        else:
            x = rng.uniform(-area[0] / 2, area[0] / 2)
            y = rng.uniform(-area[1] / 2, area[1] / 2)
        z0 = rng.uniform(*z_top)
        size = rng.uniform(0.26, 0.42)
        ob = make_card(f"FallLeaf_{i:03d}", size, mat, collection)
        start = rng.uniform(-frames * 0.75, frames)
        dur = rng.uniform(70, 110)
        drift = Vector((rng.uniform(-1.6, 1.6), rng.uniform(-1.6, 1.6), 0))
        spin = rng.uniform(0.8, 2.4) * rng.choice([-1, 1])
        for k, (fr, t) in enumerate(((start, 0.0), (start + dur * 0.5, 0.5), (start + dur, 1.0))):
            sway = Vector((math.sin(t * 6.0 + i) * 0.35, math.cos(t * 5.0 + i * 1.7) * 0.35, 0))
            ob.location = Vector((x, y, z0)) + drift * t + sway + Vector((0, 0, -(z0 + 0.25) * t))
            ob.rotation_euler = (spin * t * 3.0 + i, spin * t * 1.7, spin * t * 0.9)
            ob.keyframe_insert("location", frame=fr)
            ob.keyframe_insert("rotation_euler", frame=fr)

        objs.append(ob)
    prefs.keyframe_new_interpolation_type = keep
    return objs
