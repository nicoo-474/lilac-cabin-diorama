"""Camera, world, two-light rig and render helpers."""
import bpy
import bmesh
import math
from mathutils import Vector

import lilac as L
from theme import T


def setup_render(scene, gpu=True, samples=96, res=(1024, 640)):
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.02
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = "OPTIX"
    except Exception:
        pass
    scene.cycles.max_bounces = 8
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 3
    scene.cycles.transmission_bounces = 8
    scene.cycles.transparent_max_bounces = 8
    scene.cycles.volume_bounces = 2
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.cycles.blur_glossy = 1.0
    if gpu:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.refresh_devices()
        for d in prefs.devices:
            d.use = d.type == "OPTIX"
        scene.cycles.device = "GPU"
    else:
        scene.cycles.device = "CPU"
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0


def setup_world(scene, ambient=None, strength=1.15, bg=None):
    """Uniform ambient light for every shading ray, dark backdrop for the camera."""
    ambient = ambient or T.AMBIENT
    bg = bg or T.WORLD_BG
    w = scene.world or bpy.data.worlds.new("World")
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    mix = nt.nodes.new("ShaderNodeMixShader")
    lp = nt.nodes.new("ShaderNodeLightPath")
    amb = nt.nodes.new("ShaderNodeBackground")
    amb.inputs["Color"].default_value = L.hex2lin(ambient)
    amb.inputs["Strength"].default_value = strength
    bgd = nt.nodes.new("ShaderNodeBackground")
    bgd.inputs["Color"].default_value = L.hex2lin(bg)
    bgd.inputs["Strength"].default_value = 1.0
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(amb.outputs["Background"], mix.inputs[1])
    nt.links.new(bgd.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return w


def add_fog(collection, density=0.012, color=None, size=26):
    color = color or T.FOG
    mat = bpy.data.materials.get("FogVol")
    if not mat:
        mat = bpy.data.materials.new("FogVol")
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        pv = nt.nodes.new("ShaderNodeVolumePrincipled")
        pv.inputs["Color"].default_value = L.hex2lin(color)
        pv.inputs["Density"].default_value = density
        pv.inputs["Anisotropy"].default_value = 0.35
        nt.links.new(pv.outputs["Volume"], out.inputs["Volume"])
    bm = None
    import bmesh as _bm
    bm = _bm.new()
    _bm.ops.create_cube(bm, size=1.0)
    me = bpy.data.meshes.new("FogVolume")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("FogVolume", me)
    collection.objects.link(ob)
    ob.location = (0, 0, size * 0.25)
    ob.scale = (size, size, size * 0.6)
    ob.data.materials.append(mat)
    ob.visible_shadow = False
    return ob


def add_beam(collection, target=(0.3, -0.3, 1.4), azim=-118.0, elev=52.0,
             dist=13.0, angle=9.0, energy=2600, color=None, shaft=True,
             shaft_alpha=0.10):
    """The single hard light of the scene, plus its visible shaft."""
    color = color or T.BEAM
    light = bpy.data.lights.new("BeamSpot", "SPOT")
    light.energy = energy
    light.spot_size = math.radians(angle)
    light.spot_blend = 0.08
    light.color = L.hex2srgb(color)[:3]
    light.shadow_soft_size = 0.05
    ob = bpy.data.objects.new("BeamSpot", light)
    collection.objects.link(ob)
    a = math.radians(azim)
    e = math.radians(elev)
    pos = Vector(target) + Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))) * dist
    ob.location = pos
    d = Vector(target) - pos
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

    if shaft:
        bm = bmesh.new()
        r_lo = math.tan(math.radians(angle)) * dist * 0.92
        r_hi = r_lo * 0.10
        bmesh.ops.create_cone(bm, cap_ends=False, segments=48, radius1=r_lo,
                              radius2=r_hi, depth=dist)
        me = bpy.data.meshes.new("BeamShaft")
        bm.to_mesh(me)
        bm.free()
        me.shade_smooth()
        mesh_ob = bpy.data.objects.new("BeamShaft", me)
        collection.objects.link(mesh_ob)
        mesh_ob.data.materials.append(_shaft_material(color, shaft_alpha, dist, r_lo))
        # cone points +Z; put its narrow end at the lamp and aim it at the target
        mesh_ob.location = pos + d.normalized() * (dist * 0.5)
        mesh_ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        # camera-only overlay: it must never light the scene or cast shadows
        mesh_ob.visible_shadow = False
        mesh_ob.visible_diffuse = False
        mesh_ob.visible_glossy = False
        mesh_ob.visible_transmission = False
        mesh_ob.visible_volume_scatter = False
    return ob


def _shaft_material(color, alpha, length, r_lo):
    mat = bpy.data.materials.get("M_BeamShaft")
    if mat:
        return mat
    mat = bpy.data.materials.new("M_BeamShaft")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = L.hex2lin(color)
    bsdf.inputs["Emission Color"].default_value = L.hex2lin(color)
    bsdf.inputs["Emission Strength"].default_value = 1.15
    bsdf.inputs["Roughness"].default_value = 0.9
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -length * 0.5
    mr.inputs["From Max"].default_value = length * 0.5
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = alpha
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    # radial fade so the cone never shows a hard silhouette
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    div = nt.nodes.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = max(r_lo, 1e-4)
    eramp = nt.nodes.new("ShaderNodeValToRGB")
    eramp.color_ramp.elements[0].position = 0.55
    eramp.color_ramp.elements[0].color = (1, 1, 1, 1)
    eramp.color_ramp.elements[1].position = 1.0
    eramp.color_ramp.elements[1].color = (0, 0, 0, 1)
    emul = nt.nodes.new("ShaderNodeMath")
    emul.operation = "MULTIPLY"

    nt.links.new(sep.outputs["X"], comb.inputs["X"])
    nt.links.new(sep.outputs["Y"], comb.inputs["Y"])
    nt.links.new(comb.outputs["Vector"], ln.inputs[0])
    nt.links.new(ln.outputs["Value"], div.inputs[0])
    nt.links.new(div.outputs["Value"], eramp.inputs["Fac"])

    nt.links.new(ramp.outputs["Color"], mul.inputs[0])
    nt.links.new(eramp.outputs["Color"], emul.inputs[0])
    nt.links.new(mul.outputs["Value"], emul.inputs[1])
    nt.links.new(emul.outputs["Value"], bsdf.inputs["Alpha"])
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    mat.use_backface_culling = False
    try:
        mat.blend_method = "BLEND"
    except Exception:
        pass
    return mat


def add_camera(collection, target=(0.0, 0.1, 0.85), azim=-72.0, elev=30.0,
               dist=17.5, lens=60.0):
    cam = bpy.data.cameras.new("ShotCam")
    cam.lens = lens
    cam.sensor_width = 36
    ob = bpy.data.objects.new("ShotCam", cam)
    collection.objects.link(ob)
    a = math.radians(azim)
    e = math.radians(elev)
    pos = Vector(target) + Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))) * dist
    ob.location = pos
    d = Vector(target) - pos
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob
    return ob


def render_to(path, samples=None):
    sc = bpy.context.scene
    if samples:
        sc.cycles.samples = samples
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path
