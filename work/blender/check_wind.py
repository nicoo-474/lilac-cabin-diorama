import os, sys, math, random
HERE = r"C:\Users\Nico\Desktop\WOrkbudddy工作空间\10.27\work\blender"
LIB = os.path.join(HERE, "lib")
sys.path.insert(0, LIB)
import bpy
import ground, lilac as L, anim

L.purge_scene()
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 96
c = L.coll("Veg")
mats = {"grass": L.mat_flat("M_Grass", ground.GRASS, rough=0.64, spec=0.16)}
ob = ground.build_grass(c, mats, random.Random(20261027))
n = len(ob.data.vertices)
rest = [v.co.copy() for v in ob.data.vertices]
print("VERTS", n)
mod = anim.add_grass_wind(ob)
print("MOD group", mod.node_group.name,
      [(i.identifier, getattr(i, "default_value", None)) for i in mod.node_group.interface.items_tree
       if getattr(i, "in_out", "") == "INPUT"])

roots = [i for i in range(n) if rest[i].z < 0.02]
print("root verts", len(roots))

for f in (1, 9, 17, 25):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = [v.co.copy() for v in me.vertices]
    dz = max(abs(co[i].z - rest[i].z) for i in range(n))
    dr = max(math.hypot(co[i].x - rest[i].x, co[i].y - rest[i].y) for i in roots)
    tall = sorted(range(n), key=lambda i: -rest[i].z)[:400]
    dxy = max(math.hypot(co[i].x - rest[i].x, co[i].y - rest[i].y) for i in tall)
    avg = sum(math.hypot(co[i].x - rest[i].x, co[i].y - rest[i].y) for i in tall) / len(tall)
    half = [i for i in range(n) if 0.28 < rest[i].z < 0.42]
    hv = sum(math.hypot(co[i].x - rest[i].x, co[i].y - rest[i].y) for i in half) / max(1, len(half))
    print("FRAME %3d  dz=%.6f  root=%.5f  tip_avg=%.4f  mid_avg=%.4f" % (f, dz, dr, avg, hv))
    ev.to_mesh_clear()
print("OK")
