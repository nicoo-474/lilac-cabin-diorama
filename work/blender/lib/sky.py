"""Sky gradient and stylised cloud banks for the floating diorama."""
import bpy
import bmesh
import math
import random
from mathutils import Vector

import lilac as L
from theme import T

SKY_TOP = T.SKY_TOP
SKY_MID = T.SKY_MID
SKY_HOR = T.SKY_HOR
CLOUD = T.CLOUD


def setup_sky(scene, top=SKY_TOP, mid=SKY_MID, horizon=SKY_HOR, strength=1.0,
              ambient=None, ambient_strength=1.15):
    ambient = ambient or T.AMBIENT
    w = scene.world or bpy.data.worlds.new("World")
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    tc = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    # this shot looks downward, so the useful sky band sits below the horizon
    mr.inputs["From Min"].default_value = -0.95
    mr.inputs["From Max"].default_value = 0.05
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    e0 = ramp.color_ramp.elements[0]
    e1 = ramp.color_ramp.elements[1]
    e0.position = 0.0
    e0.color = L.hex2lin(mid)
    e1.position = 1.0
    e1.color = L.hex2lin(horizon)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    nt.links.new(tc.outputs["Incoming"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])

    # camera sees the painted sky, every shading ray sees one even ambient tone
    amb = nt.nodes.new("ShaderNodeBackground")
    amb.inputs["Color"].default_value = L.hex2lin(ambient)
    amb.inputs["Strength"].default_value = ambient_strength
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(amb.outputs["Background"], mix.inputs[1])
    nt.links.new(bg.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return w


def sky_dome_material():
    """Emissive gradient painted on an inside-out dome: no direction guessing."""
    m = bpy.data.materials.get("M_SkyDome")
    if m:
        return m
    m = bpy.data.materials.new("M_SkyDome")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -210.0
    mr.inputs["From Max"].default_value = -35.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = L.hex2lin(SKY_MID)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = L.hex2lin(SKY_HOR)
    mid = ramp.color_ramp.elements.new(0.55)
    mid.color = L.hex2lin(SKY_TOP)
    emi = nt.nodes.new("ShaderNodeEmission")
    emi.inputs["Strength"].default_value = 1.0
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emi.inputs["Color"])
    nt.links.new(emi.outputs[0], out.inputs["Surface"])
    return m


def build_sky_dome(collection, radius=260.0):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=radius)
    for f in bm.faces:
        f.normal_flip()
    me = bpy.data.meshes.new("SkyDome")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("SkyDome", me)
    collection.objects.link(ob)
    me.materials.append(sky_dome_material())
    ob.visible_shadow = False
    ob.visible_diffuse = False
    ob.visible_glossy = False
    ob.visible_transmission = False
    return ob


def cloud_material():
    m = bpy.data.materials.get("M_Cloud")
    if m:
        return m
    m = bpy.data.materials.new("M_Cloud")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = L.principled(nt)
    bsdf.inputs["Base Color"].default_value = L.hex2lin(CLOUD)
    bsdf.inputs["Roughness"].default_value = 0.95
    bsdf.inputs["Specular IOR Level"].default_value = 0.03
    bsdf.inputs["Emission Color"].default_value = L.hex2lin(CLOUD)
    bsdf.inputs["Emission Strength"].default_value = 0.20
    m.use_backface_culling = False
    return m


def build_cloud(name, center, scale, rng, collection, mat, puffs=7):
    """A cloud is a cluster of squashed spheres, flat shaded like painted paper."""
    bm = bmesh.new()
    for i in range(puffs):
        r = scale * rng.uniform(0.45, 1.0)
        off = Vector((rng.uniform(-1.15, 1.15) * scale,
                      rng.uniform(-0.45, 0.45) * scale,
                      rng.uniform(-0.18, 0.30) * scale))
        tmp = bmesh.new()
        bmesh.ops.create_icosphere(tmp, subdivisions=2, radius=r)
        for v in tmp.verts:
            v.co.z *= 0.62
            v.co.x *= 1.25
        bmesh.ops.translate(tmp, verts=tmp.verts, vec=off)
        me = bpy.data.meshes.new("tmp")
        tmp.to_mesh(me)
        tmp.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.new_obj(name, bm, collection, mat, flat_loose=True)
    ob.location = center
    ob.visible_shadow = False
    return ob


def build_clouds(collection, rng, count=8, mat=None, radius=46.0):
    """A low cloud sea plus a few higher banks so the diorama sits in the sky."""
    mat = mat or cloud_material()
    objs = []
    for i in range(count):
        ang = rng.uniform(0, math.tau)
        dist = rng.uniform(52.0, 105.0)
        # follow the camera's sight line so the banks actually sit behind the slab
        z = 1.0 - 0.674 * (dist - 33.0) + rng.uniform(-4.0, 4.0)
        sc = rng.uniform(2.6, 5.2)
        ob = build_cloud(f"Cloud_{i}", (math.cos(ang) * dist, math.sin(ang) * dist, z),
                         sc, rng, collection, mat)
        objs.append(ob)
    return objs
