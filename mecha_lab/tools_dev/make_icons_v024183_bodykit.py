"""0.24.183 the Body Kit tool's icon: a figure in parts (joints marked) on the tools' dark tile."""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(HERE, '..', 'addon', 'mecha_lab', 'icons')
S = 4                                                    # drawn 4x, scaled down (smooth edges)
bg = Image.open(os.path.join(ICONS, 'cbase.png')).convert('RGBA').resize((128 * S, 128 * S))
tile = Image.new('RGBA', bg.size, (0, 0, 0, 0))
# keep only the tile (its rounded dark square): the corner colour off
px = bg.load()
corner = px[2, 2]
base = Image.new('RGBA', bg.size, (0, 0, 0, 0))
mask = Image.new('L', bg.size, 0)
ImageDraw.Draw(mask).rounded_rectangle((4 * S, 4 * S, 124 * S, 124 * S), radius=22 * S, fill=255)
base.paste((38, 40, 46, 255), (0, 0), mask)
d = ImageDraw.Draw(base)
col = (226, 214, 204, 255)
acc = (255, 150, 60, 255)


def seg(a, b, w):
    d.line([(a[0] * S, a[1] * S), (b[0] * S, b[1] * S)], fill=col, width=int(w * S))
    for p in (a, b):
        r = w / 2
        d.ellipse(((p[0] - r) * S, (p[1] - r) * S, (p[0] + r) * S, (p[1] + r) * S), fill=col)


def joint(p, r=4.2):
    d.ellipse(((p[0] - r) * S, (p[1] - r) * S, (p[0] + r) * S, (p[1] + r) * S), fill=acc)


d.ellipse((55 * S, 12 * S, 73 * S, 32 * S), fill=col)                    # head
d.rounded_rectangle((47 * S, 36 * S, 81 * S, 70 * S), radius=9 * S, fill=col)   # torso
d.rounded_rectangle((50 * S, 72 * S, 78 * S, 82 * S), radius=5 * S, fill=col)   # pelvis
seg((43, 41), (35, 62), 9)
seg((35, 62), (31, 82), 8)                                                 # left arm
seg((85, 41), (93, 62), 9)
seg((93, 62), (97, 82), 8)                                                 # right arm
seg((57, 86), (54, 101), 11)
seg((54, 101), (52, 116), 9)                                               # legs
seg((71, 86), (74, 101), 11)
seg((74, 101), (76, 116), 9)
for p in ((43, 41), (85, 41), (35, 62), (93, 62), (57, 86), (71, 86), (54, 101), (74, 101)):
    joint(p)
out = base.resize((128, 128), Image.LANCZOS)
out.save(os.path.join(ICONS, 'bodykit.png'))
print('saved bodykit.png')
