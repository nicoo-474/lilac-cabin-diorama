import sys, os, time, random, importlib

HERE = r"C:\Users\Nico\Desktop\WOrkbudddy工作空间\10.27\work\blender"
LIB = os.path.join(HERE, "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)

import bpy
import theme, lilac, ground, tree, cabin, shot, paintmap, sky, anim
for m in (theme, lilac, ground, tree, cabin, shot, paintmap, sky, anim):
    importlib.reload(m)

L, G, T, C, S, PM, KY, A = lilac, ground, tree, cabin, shot, paintmap, sky, anim
TH = theme
LOG = os.path.join(HERE, "build.log")
OUT = r"C:\Users\Nico\Desktop\WOrkbudddy工作空间\10.27\renders"


def log(msg):
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))


t0 = time.time()
log("=== build scene · theme=%s ===" % TH.THEME)
L.purge_scene()
sc = bpy.context.scene
rng = random.Random(20261027)

c_sky = L.coll("Sky")
c_ground = L.coll("Ground")
c_veg = L.coll("Vegetation")
c_cabin = L.coll("Cabin")
c_light = L.coll("Lighting")

mats = {
    "base": L.mat_flat("M_GroundBase", G.BASE, rough=0.78, spec=0.09),
    "mid": L.mat_flat("M_Impasto", G.MID, rough=0.74, spec=0.10),
    "deep": L.mat_flat("M_ImpastoDeep", G.DEEP, rough=0.74, spec=0.10),
    "path": L.mat_flat("M_PathStone", G.PATHC, rough=0.66, spec=0.14),
    "grass": L.mat_flat("M_Grass", G.GRASS, rough=0.64, spec=0.16),
    "flower": L.mat_flat("M_Flower", G.FLOWER, rough=0.5, spec=0.25),
    "bark": T.bark_material(),
    "frame": L.mat_flat("M_Frame", C.FRAME, rough=0.52, spec=0.28),
    "deck": L.mat_flat("M_Deck", C.DECK, rough=0.6, spec=0.16),
    "glass": L.mat_glass("M_Glass", C.GLASS),
    "tatami": L.mat_flat("M_Tatami", C.TATAMI, rough=0.72),
    "wood2": L.mat_flat("M_Wood2", C.WOOD2, rough=0.58),
    "cushion": L.mat_flat("M_Cushion", C.CUSHION, rough=0.78),
    "lamp": L.mat_flat("M_Lamp", C.LAMP, rough=0.4, emit_hex=C.LAMP, emit_str=2.2),
}
log("materials %.1fs" % (time.time() - t0))

paint_img, paint_path = PM.build_paint_texture("PaintMap", G.PLATE_W, G.PLATE_D,
                                              px_per_meter=150, seed=77)
mats["paint"] = G.paint_material("M_Paint", paint_img)
log("paint texture")
G.build_plate(c_ground, mats, paint_img)
G.build_path(c_ground, mats, rng)
log("plate + path")
grass_ob = G.build_grass(c_veg, mats, rng)
log("grass")
G.build_flowers(c_veg, mats, rng, count=230)
log("flowers")

img, tex_path = T.make_leaf_texture()
leaf_mat = T.leaf_material(img)
log("leaf texture")

tree_plan = [
    (-6.75, 3.55, 1.45), (-4.05, 4.25, 1.80), (-1.30, 4.60, 1.55),
    (1.75, 4.50, 1.70), (4.55, 4.05, 1.50), (6.85, 3.15, 1.30),
    (-6.95, 0.15, 1.15), (6.60, -0.10, 1.20), (-5.55, -3.70, 1.05),
    (5.75, -3.95, 1.10),
]#
clusters = []
for i, (x, y, s) in enumerate(tree_plan):
    _wood, _cl = T.build_tree("Tree%d" % i, (x, y, 0.0), s, rng, c_veg, mats["bark"], leaf_mat)
    clusters.extend(_cl)
log("trees %.1fs" % (time.time() - t0))

# wind: a travelling gust through the meadow + a slow sway on every leaf cluster
A.add_grass_wind(grass_ob)
A.add_cluster_sway(clusters, rng, frames=96, amp=0.040)
log("wind rigged")

C.build_cabin(c_cabin, mats, random.Random(11))
cab = bpy.data.objects.get("Deck")
for ob in c_cabin.objects:
    ob.location.x += G.CABIN_C.x
    ob.location.y += G.CABIN_C.y
log("cabin")

# interior light: one warm point above the table, one low fill near the tatami
for name, energy, loc, size in (("InnerTop", 300, (0.10, 0.05, 1.62), 0.24),
                                ("InnerLow", 90, (-0.45, -0.5, 0.55), 0.16)):
    li = bpy.data.lights.new(name, "POINT")
    li.energy = energy
    li.color = (1.0, 0.70, 0.42)
    li.shadow_soft_size = size
    lo = bpy.data.objects.new(name, li)
    c_light.objects.link(lo)
    lo.location = (loc[0] + G.CABIN_C.x, loc[1] + G.CABIN_C.y, loc[2])
log("interior lights")

S.setup_render(sc, gpu=True, samples=64, res=(1200, 720))
KY.build_sky_dome(c_sky)
KY.build_clouds(c_sky, rng, count=16)
S.setup_world(sc, strength=1.24)
log("sky + clouds")
S.add_fog(c_light, density=0.0005, size=34)
S.add_beam(c_light, target=(1.55, -2.55, 0.10),
           energy=8000, angle=3.8, dist=16.5, azim=-112, elev=54, shaft_alpha=0.16)
S.add_camera(c_light, target=(0.0, -0.45, 0.80), azim=-70, elev=34, dist=33.0, lens=50)
log("lighting + camera")

single_img, _p = T.make_single_leaf_texture()
fall_mat = T.simple_leaf_material(single_img)
spawn = [(x, y, 2.2) for (x, y, s) in tree_plan]
A.build_falling_leaves(c_veg, fall_mat, rng, count=130, frames=96, spawn_centers=spawn, z_top=(3.2, 7.0))
sc.frame_start = 1
sc.frame_end = 96
sc.render.fps = 24
log("falling leaves")

# save last: the .blend must carry the falling leaves and the real frame range
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "assets", "lilac_cabin.blend"))
log("blend saved")

QUICK = os.environ.get('QUICK') == '1'
ANIM = os.environ.get('ANIM') == '1'
ALL = os.environ.get('STILLS_ALL') == '1'
if ANIM:
    sc.frame_start, sc.frame_end = 1, 96
    sc.cycles.samples = 26
    S.setup_render(sc, gpu=True, samples=26, res=(960, 540))
    frames_dir = os.path.join(OUT, "_frames")
    os.makedirs(frames_dir, exist_ok=True)
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = os.path.join(frames_dir, "f_")
    log("animation start")
    bpy.ops.render.render(animation=True)
    log("=== animation done %.1fs ===" % (time.time() - t0))
    raise SystemExit

# ---- stills only (the default): one hero + four wind phases of the meadow
S.setup_render(sc, gpu=True, samples=48 if QUICK else 96, res=(1080, 648) if QUICK else (1280, 768))
S.render_to(os.path.join(OUT, "01_hero.png"), samples=48 if QUICK else 96)
log("hero rendered %.1fs" % (time.time() - t0))

S.add_camera(c_light, target=(-2.10, -4.55, 0.42), azim=-99, elev=17, dist=3.30, lens=52)
S.setup_render(sc, gpu=True, samples=20 if QUICK else 28, res=(760, 500))
for f in (1, 9, 17, 25):
    sc.frame_set(f)
    S.render_to(os.path.join(OUT, "wind_%03d.png" % f), samples=20 if QUICK else 28)
log("wind phases %.1fs" % (time.time() - t0))

if not ALL:
    log("=== done %.1fs ===" % (time.time() - t0))
    raise SystemExit

# cabin close-up
S.add_camera(c_light, target=(G.CABIN_C.x - 0.05, G.CABIN_C.y - 0.35, 1.05), azim=-82,
             elev=15, dist=9.8, lens=55)
S.setup_render(sc, gpu=True, samples=220, res=(1200, 900))
S.render_to(os.path.join(OUT, "02_cabin.png"), samples=220)
log("cabin rendered %.1fs" % (time.time() - t0))

# plan view of the paint field
S.setup_render(sc, gpu=True, samples=180, res=(1400, 950))
S.add_camera(c_light, target=(0.0, 0.0, 0.0), azim=-90, elev=82, dist=16.0, lens=48)
S.render_to(os.path.join(OUT, "03_plan.png"), samples=180)
log("=== done %.1fs ===" % (time.time() - t0))
