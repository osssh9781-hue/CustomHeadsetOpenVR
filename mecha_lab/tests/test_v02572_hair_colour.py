"""0.24.169 (user: "머리카락 색 바뀌게 해 줘" and "생머리, 파마머리, 수염, 동물털 이런 거 프리셋 좀 만들어 줘"): Creature Hair's
colour - its own material (not the head's), root -> tip colours along each strand, each strand a little different,
Shine, the rings' colour, colour presets, changed at once without rebuilding the strands, or the body's material - and
four more styles: Straight Hair, Perm (corkscrew curls), Beard, Animal Fur.  A Cycles render checks the colour along
the strands."""
import math
import os
import tempfile
import time

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, creature_hair as ch  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)        # (looking down: 100 px = 1, (500, 500) = origin)
SCALP = [[(500 + 45 * math.cos(t), 500 + 45 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 48, endpoint=False)]]

check('Creature Hair styles: + Straight Hair, Perm, Beard, Animal Fur (eight)',
      [s[0] for s in ch.STYLE_ITEMS] == ['DREADS', 'TENTACLE', 'QUILLS', 'STRANDS', 'STRAIGHT', 'PERM', 'BEARD', 'FUR'])
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=(0, 0, 0))
head = C.active_object
head.name = 'Head'
skin = bpy.data.materials.new('Skin')
skin.diffuse_color = (0.8, 0.1, 0.1, 1.0)
head.data.materials.append(skin)
st = S.mch_hair


def grow(style, **kw):
    st.style = style
    for k, v in kw.items():
        setattr(st, k, v)
    for o in C.selected_objects:
        o.select_set(False)
    head.select_set(True)
    C.view_layer.objects.active = head
    msg = ch.perform(C, SCALP, TOP)
    return C.active_object, msg


def attr(ob, name):
    a = ob.data.attributes.get(name)
    v = np.zeros(len(ob.data.vertices), np.float32)
    if a is not None:
        a.data.foreach_get('value', v)
    return v, a is not None


def co(ob):
    m = np.array(ob.matrix_world)
    return np.array([v.co for v in ob.data.vertices]) @ m[:3, :3].T + m[:3, 3]


hair, msg = grow('STRANDS')
p = hair.mch_hair
mats = [m.name if m else None for m in hair.data.materials]
check(f'a hair has its own material, not the head\'s ({mats})',
      mats[0].startswith('MCH Hair - ') and mats[0] != 'Skin' and mats[1].startswith('MCH Hair Rings - '), mats)
t, has_t = attr(hair, ch.T_ATTR)
r, has_r = attr(hair, ch.R_ATTR)
check(f'every point knows how far along its strand it is (0 at the root .. 1 at the tip: {t.min():.2f} - {t.max():.2f}) and '
      f'its strand\'s random ({len(np.unique(np.round(r, 5)))} different)', has_t and has_r and t.min() < 0.01
      and t.max() > 0.99 and len(np.unique(np.round(r, 5))) > 50)
nf = len(hair.data.polygons)
t0 = time.perf_counter()
bpy.ops.mch.hair_colour(preset='BLONDE')
dt = time.perf_counter() - t0
nt = hair.data.materials[0].node_tree
a_, b_ = [i for i in nt.nodes['Colour'].inputs if i.type == 'RGBA'][:2]
blonde = next(c for c in ch.COLOUR_PRESETS if c[0] == 'BLONDE')
check(f'the Blonde preset: root and tip colours into its material ({dt * 1000:.0f} ms, the strands not rebuilt: '
      f'{nf} faces)', np.allclose(a_.default_value[:3], blonde[2], atol=1e-4)
      and np.allclose(b_.default_value[:3], blonde[3], atol=1e-4) and len(hair.data.polygons) == nf and dt < 0.5)
check('...remembered: the next hair starts blonde', np.allclose(st.root_colour, blonde[2], atol=1e-4))
p.shine = 1.0
check('Shine 1: glossy (roughness 0.25)', abs(nt.nodes['BSDF'].inputs['Roughness'].default_value - 0.25) < 1e-6)
p.ring_colour = (0.1, 0.9, 0.2)
check('the rings\' colour into the rings\' material',
      np.allclose(hair.data.materials[1].diffuse_color[:3], (0.1, 0.9, 0.2), atol=1e-4))

# the render: red roots, blue tips (no variation) - the strands redder at the top, bluer down where they hang
p.root_colour, p.tip_colour, p.tip_start, p.colour_random = (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.0, 0.0
head.hide_render = True
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.location = (0.0, -6.0, 0.3)
cam.rotation_euler = (Vector((0, 0, 0.3)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
S.render.engine = 'CYCLES'
S.cycles.samples = 16
S.cycles.device = 'CPU'
S.render.film_transparent = True
S.render.resolution_x = S.render.resolution_y = 160
S.world = bpy.data.worlds.new('W')
S.world.color = (1.0, 1.0, 1.0)
out = os.path.join(tempfile.mkdtemp(), 'hair.png')
S.render.filepath = out
S.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
img = bpy.data.images.load(out)
px = np.array(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], 4)
ys, xs = np.nonzero(px[:, :, 3] > 0.5)
red = px[ys, xs, 0] / np.maximum(px[ys, xs, 0] + px[ys, xs, 2], 1e-6)
top_ = ys > np.percentile(ys, 70)                      # (image rows go up: high y = the top)
low_ = ys < np.percentile(ys, 30)
check(f'a Cycles render: red roots / blue tips - the strands\' top {red[top_].mean():.2f} red, their lower part '
      f'{red[low_].mean():.2f} red', len(ys) > 200 and red[top_].mean() > red[low_].mean() + 0.2,
      (len(ys), red[top_].mean(), red[low_].mean()))
head.hide_render = False

p.colour_mode = 'BODY'
check('Colour: Body\'s Material - the head\'s material on the hair', hair.data.materials[0] == skin)
p.colour_mode = 'OWN'
check('...and back: its own', hair.data.materials[0].name.startswith('MCH Hair - '))

# the styles: Straight Hair hangs straight, Perm curls, Beard shorter, Animal Fur lies close
st.colour_mode = 'OWN'


def strand_runs(ob):
    """Each strand's points (by its random), root to tip."""
    c_ = co(ob)
    t_, _h = attr(ob, ch.T_ATTR)
    r_, _h = attr(ob, ch.R_ATTR)
    out_ = {}
    for key in np.unique(np.round(r_, 6)):
        m = np.round(r_, 6) == key
        order = np.argsort(t_[m])
        out_[key] = (c_[m][order], t_[m][order])
    return out_


straight, _m = grow('STRAIGHT')
perm, _m = grow('PERM')
beard, _m = grow('BEARD')
fur, _m = grow('FUR')
st.curl = 0.0
nocurl, _m = grow('PERM', curl=0.0)
st.curl = 0.55


def plumb(ob):
    """How vertical the lower half of the strands runs (1 = straight down)."""
    vals = []
    for pts, tt in strand_runs(ob).values():
        low = pts[tt > 0.6]
        if len(low) > 4:
            d = low[-1] - low[0]
            vals.append(-d[2] / max(np.linalg.norm(d), 1e-9))
    return float(np.median(vals)) if vals else 0.0


def centres(pts, tt):
    """A strand's middle line: the mean of each ring (the points with the same t)."""
    keys = np.round(tt, 5)
    u = np.unique(keys)
    return np.array([pts[keys == k].mean(0) for k in u])


def wiggle(ob):
    """How far a strand's middle line strays from itself smoothed over a dozen rings (a corkscrew: by its width; a
    smooth arc: hardly at all) - x the strand's length."""
    vals = []
    for pts, tt in strand_runs(ob).values():
        c_ = centres(pts, tt)
        if len(c_) < 20:
            continue
        k = 12
        sm = np.array([c_[max(0, i - k // 2):i + k // 2 + 1].mean(0) for i in range(len(c_))])
        L = np.sum(np.linalg.norm(np.diff(c_, axis=0), axis=1))
        vals.append(np.linalg.norm((c_ - sm)[k:-k], axis=1).mean() / max(L, 1e-9))
    return float(np.median(vals)) if vals else 0.0


def strand_len(ob):
    return float(np.median([np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)) for pts, _t in strand_runs(ob).values()]))


def tip_off(ob):
    """How far the tips are off the head's surface (x the strand length)."""
    vals = []
    for pts, _tt in strand_runs(ob).values():
        L = np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1))
        vals.append((np.linalg.norm(pts[-1]) - 1.0) / max(L, 1e-9))
    return float(np.median(vals))


pl_s, pl_d = plumb(straight), plumb(ch_d := grow('DREADS')[0])
check(f'Straight Hair: thin, many ({len(strand_runs(straight))} strands), hanging plumb (lower half {pl_s:.2f} straight '
      f'down)', len(strand_runs(straight)) > 150 and pl_s > 0.95, pl_s)
w_p, w_n = wiggle(perm), wiggle(nocurl)
check(f'Perm: each strand a corkscrew - its middle line {w_p * 100:.2f} % of its length off its own smoothed line '
      f'(Curl 0: {w_n * 100:.2f} %)', w_p > 3 * w_n and w_p > 0.01, (w_p, w_n))
check(f'Beard: shorter strands ({strand_len(beard) / strand_len(straight):.2f} x Straight Hair\'s)',
      strand_len(beard) < 0.5 * strand_len(straight))
check(f'Animal Fur: short ({strand_len(fur) / strand_len(straight):.2f} x Straight Hair\'s), dense '
      f'({len(strand_runs(fur))} strands), lying close (the tips {tip_off(fur):.2f} of a strand off the head)',
      len(strand_runs(fur)) > 300 and tip_off(fur) < 0.4 and strand_len(fur) < 0.2 * strand_len(straight))
check('every new style takes the colour (its own material, blonde from the remembered settings)',
      all(o.data.materials[0].name.startswith('MCH Hair - ') for o in (straight, perm, beard, fur)))
for o in C.selected_objects:
    o.select_set(False)
fur.select_set(True)
C.view_layer.objects.active = fur
bpy.ops.mch.hair_apply()
check('Apply: a plain mesh, its material kept', not fur.mch_hair.live and fur.data.materials[0].name.startswith('MCH Hair - '))

# 0.24.169 (user: "머리카락은 왜 미러가 안 돼?"): a head with a live Mirror - the hair grown on one side mirrored too
from mecha_lab import mirror_tools, symmetry  # noqa: E402
for o in [o for o in bpy.data.objects if o is not head and o.type == 'MESH']:   # (the hairs above: off the head)
    bpy.data.objects.remove(o)
for o in C.selected_objects:
    o.select_set(False)
head.select_set(True)
C.view_layer.objects.active = head
symmetry.set_mode(C, head, 'MIRROR')
side = [[(500 + 40 + 25 * math.cos(t), 500 + 25 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 32, endpoint=False)]]
st.style = 'STRANDS'
for o in C.selected_objects:
    o.select_set(False)
head.select_set(True)
C.view_layer.objects.active = head
msg = ch.perform(C, side, TOP)
hm = C.active_object
mod = hm.modifiers.get(mirror_tools.MOD_NAME)
ev = hm.evaluated_get(C.evaluated_depsgraph_get()).data
xs = np.array([hm.matrix_world @ v.co for v in ev.vertices])[:, 0]
check(f'a head with a live Mirror: the hair drawn on its +X side gets the same Mirror - strands on both sides '
      f'(x {xs.min():.2f} .. {xs.max():.2f}) ({msg})', mod is not None and xs.min() < -0.2 and xs.max() > 0.2,
      (mod is not None, xs.min(), xs.max()))

mecha_lab.unregister()
summary()
