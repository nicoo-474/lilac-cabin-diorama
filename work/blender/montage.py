"""Stitch the four wind-phase frames into one 2x2 contact sheet."""
import bpy
import numpy as np

OUT = r"C:\Users\Nico\Desktop\WOrkbudddy工作空间\10.27\renders"
names = ["wind_001.png", "wind_009.png", "wind_017.png", "wind_025.png"]
ims = [bpy.data.images.load(OUT + "\\" + n, check_existing=False) for n in names]
w, h = ims[0].size
sheet = np.zeros((h * 2, w * 2, 4), dtype=np.float32)
for i, im in enumerate(ims):
    buf = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(buf)
    row = 1 - (i // 2)          # image rows start at the bottom, keep f1 top-left
    col = i % 2
    sheet[row * h:(row + 1) * h, col * w:(col + 1) * w] = buf.reshape(h, w, 4)

out = bpy.data.images.new("wind_phases", w * 2, h * 2, alpha=True)
out.colorspace_settings.name = "sRGB"
out.pixels.foreach_set(sheet.reshape(-1))
out.file_format = "PNG"
out.filepath_raw = OUT + "\\wind_phases.png"
out.save()
print("SHEET OK", w * 2, h * 2)
