import json, math, sys
from PIL import Image, ImageDraw
D = '/tmp/claude-0/-home-user-CustomHeadsetOpenVR/7e2bc25f-fcd2-5c43-817f-f359a797ad9a/scratchpad/sweep/'
M = json.load(open(D + 'meshes.json'))
VIEWS = {'PANEL': (35, 25), 'MULTI_BEND': (55, 20), 'WRAP': (60, 15), 'TEARDROP': (40, 22), 'AUTOMOTIVE': (50, 35), 'DUCT': (40, 25)}
def rot(v, yaw, pitch):
    y, p = math.radians(yaw), math.radians(pitch)
    x, yy, z = v
    x, yy = x * math.cos(y) - yy * math.sin(y), x * math.sin(y) + yy * math.cos(y)
    yy, z = yy * math.cos(p) - z * math.sin(p), yy * math.sin(p) + z * math.cos(p)
    return (x, yy, z)
L = (-0.4, -0.5, 0.75); ln = math.sqrt(sum(c * c for c in L)); L = tuple(c / ln for c in L)
for name, m in M.items():
    yaw, pitch = VIEWS[name]
    vs = [rot(v, yaw, pitch) for v in m['v']]
    xs = [v[0] for v in vs]; zs = [v[2] for v in vs]
    W, H, S = 520, 380, 4
    sc = min((W - 60) / (max(xs) - min(xs) + 1e-9), (H - 60) / (max(zs) - min(zs) + 1e-9))
    cx, cz = (max(xs) + min(xs)) / 2, (max(zs) + min(zs)) / 2
    P = lambda v: ((W / 2 + (v[0] - cx) * sc) * S, (H / 2 - (v[2] - cz) * sc) * S)
    img = Image.new('RGB', (W * S, H * S), (36, 40, 47)); d = ImageDraw.Draw(img)
    polys = []
    for f in m['f']:
        pts = [vs[i] for i in f]
        a, b, c = pts[0], pts[1], pts[2]
        u = [b[k] - a[k] for k in range(3)]; w = [c[k] - a[k] for k in range(3)]
        n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        nl = math.sqrt(sum(k * k for k in n)) or 1
        n = tuple(k / nl for k in n)
        if n[1] > 0:  # facing away (camera looks along +y)
            continue
        depth = sum(p[1] for p in pts) / len(pts)
        sh = max(0.0, -(n[0] * L[0] + n[1] * L[1] + n[2] * L[2]))
        polys.append((depth, [P(p) for p in pts], sh))
    for depth, pp, sh in sorted(polys, key=lambda t: -t[0]):
        g = int(70 + 165 * sh)
        d.polygon(pp, fill=(g, int(g * 1.02), int(g * 1.08)), outline=(int(g * .55), int(g * .57), int(g * .62)))
    img = img.resize((W, H), Image.LANCZOS)
    img.save(D + name.lower() + '.png')
    print('ok', name)
