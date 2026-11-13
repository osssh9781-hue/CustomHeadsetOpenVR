"""0.24.147 (user: "크리쳐용 hdri ... 기본 텍스쳐가 잘보이고 라이팅이 어느정도 부드럽고 스펙큘러도 과하지 않게 ... 익스포져랑
빛부분 에미션 ... 휴랑 세추리이션 ... 바닥은 쉐도우 케쳐 ... 그라데이션 맵으로 가운데부분만 불투명하고 외곽은 투명하게 원처럼 ...
30종 ... 가볍게"): Creature Light - 30 set-ups made in the world's nodes (no files), the controls, the floor.
Real Cycles renders (small) read back as numbers."""
import math
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bg_color, creature_light as cl  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
TMP = tempfile.mkdtemp(prefix='mch_clight_')

# --- the set-ups ---------------------------------------------------------------------------------------------------
check('30 set-ups, each its own name, 1 to 4 lights', len(cl.PRESETS) == 30 and len(set(cl.ORDER)) == 30
      and all(1 <= len(p[6]) <= cl.SLOTS for p in cl.PRESETS))
check('every set-up has its preview tile (96 x 72, small)',
      all(os.path.isfile(cl.thumb_path(i)) for i in cl.ORDER)
      and sum(os.path.getsize(cl.thumb_path(i)) for i in cl.ORDER) < 600 * 1024,
      sum(os.path.getsize(cl.thumb_path(i)) for i in cl.ORDER if os.path.isfile(cl.thumb_path(i))))
check('soft lights only (every light at least 15 degrees wide - soft shadows, quiet highlights)',
      all(lt[2] >= 15 for p in cl.PRESETS for lt in p[6]))
check('no picture files: nothing loaded into the file', len(bpy.data.images) == 0)


def render(name, res=(64, 48), samples=16, denoise=False, transparent=False):
    S.render.engine = 'CYCLES'
    S.cycles.device = 'CPU'
    S.cycles.samples = samples
    S.cycles.use_denoising = denoise
    S.cycles.use_adaptive_sampling = False
    S.render.film_transparent = transparent
    S.render.resolution_x, S.render.resolution_y = res
    S.render.resolution_percentage = 100
    S.view_settings.view_transform = 'Standard'
    S.view_settings.exposure = 0.0
    S.render.image_settings.file_format = 'OPEN_EXR'
    S.render.filepath = os.path.join(TMP, name + '.exr')
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(S.render.filepath)
    a = np.array(img.pixels[:], dtype=np.float32).reshape(res[1], res[0], 4)
    bpy.data.images.remove(img)
    return a


def white_sphere():
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 1.0), segments=32, ring_count=16)
    sp = C.active_object
    bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new('White')
    pb = m.node_tree.nodes.get('Principled BSDF')
    pb.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1)
    pb.inputs['Roughness'].default_value = 1.0
    for key in ('Specular IOR Level', 'Specular'):
        if key in pb.inputs:
            pb.inputs[key].default_value = 0.0
            break
    sp.data.materials.append(m)
    return sp


def camera(loc, look):
    cam = bpy.data.objects.get('Cam') or bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    if cam.name not in S.collection.objects:
        S.collection.objects.link(cam)
    from mathutils import Vector
    cam.location = loc
    cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    S.camera = cam
    return cam


# --- on / off: the scene's own world kept --------------------------------------------------------------------------
mine = bpy.data.worlds.new('My World')
mine.node_tree.nodes.new('ShaderNodeTexNoise')
n_mine = len(mine.node_tree.nodes)
S.world = mine
st = cl.settings(S)
r = bpy.ops.mch.creature_light(action='SET', ident='soft_studio')
check('Creature Light on: the scene\'s world is MCH Creature Light (made in nodes), your world remembered',
      'FINISHED' in r and cl.on(S) and S.world.name.startswith(cl.WORLD) and S.get(cl.PREV_KEY) == 'My World')
check('... your world untouched (its nodes as they were, kept in the file)',
      len(mine.node_tree.nodes) == n_mine and bpy.data.worlds.get('My World') is mine)
gn = cl._group_node(S.world)
check('... one group node, a Background, the Output (light: about 40 nodes in the group, no images)',
      gn is not None and len(S.world.node_tree.nodes) == 3 and len(gn.node_tree.nodes) < 60)

sp = white_sphere()
camera((0, -6, 1.0), (0, 0, 1.0))
peak = {}
for ident in ('soft_studio', 'overcast', 'golden_hour', 'arctic'):
    cl.apply(S, ident)
    a = render('lvl_' + ident)
    peak[ident] = float(a[..., :3].mean(2)[18:40, 22:42].max())
vals = list(peak.values())
check('every set-up levelled: the brightest side of the white sphere about the same (within 35 %)',
      max(vals) / max(min(vals), 1e-6) < 1.35, {k: round(v, 3) for k, v in peak.items()})

cl.apply(S, 'soft_studio')
a0 = render('exp0')
st.exposure = 1.0
a1 = render('exp1')
st.exposure = 0.0
c0, c1 = float(a0[24, 32, :3].mean()), float(a1[24, 32, :3].mean())
check('Exposure +1 = twice the light (a stop)', abs(c1 / c0 - 2.0) < 0.15, (round(c0, 4), round(c1, 4)))

st.emission = 0.0
a2 = render('em0')
st.emission = 1.0
st.fill = 0.0
a3 = render('fill0')
st.fill = 1.0
c2, c3 = float(a2[24, 32, :3].mean()), float(a3[24, 32, :3].mean())
check('Light Emission 0: only the sky lights the part (darker); Sky Fill 0: only the lights',
      c2 < c0 * 0.75 and c3 < c0 * 0.9 and c2 > 0.01 and c3 > 0.01, (round(c0, 3), round(c2, 3), round(c3, 3)))

# hue / saturation on the background the camera sees (a coloured set-up)
sp.hide_render = True
cl.apply(S, 'deep_sea')
b1 = render('sat1')[24, 32, :3]
st.saturation = 0.0
b0 = render('sat0')[24, 32, :3]
st.saturation = 1.0
st.hue = 0.33
bh = render('hue')[24, 32, :3]
st.hue = 0.0
check('Saturation 0: grey light (the teal sky grey)', float(np.ptp(b0)) < 0.01 < float(np.ptp(b1)),
      (b1.round(3).tolist(), b0.round(3).tolist()))
check('Hue turned: other colours (teal -> another hue, the brightness kept roughly)',
      int(np.argmax(bh)) != int(np.argmax(b1)) and 0.5 < bh.max() / b1.max() < 2.0, (b1.round(3).tolist(), bh.round(3).tolist()))

# the lights hidden from the camera (it sees the sky gradient), shown on request; Rotation turns them
cl.apply(S, 'arctic')                                # (one light: nothing else turned into its place)
key = cl.BY_ID['arctic'][6][0]
d = cl._dir(key[0], key[1])
camera((0, 0, 1.0), (d[0] * 5, d[1] * 5, 1.0 + d[2] * 5))
h_off = float(render('cam_hidden')[24, 32, :3].mean())
st.show_lights = True
h_on = float(render('cam_shown')[24, 32, :3].mean())
st.rotation = math.pi
h_rot = float(render('cam_rot')[24, 32, :3].mean())
st.rotation = 0.0
st.show_lights = False
check('Lights Seen by Camera off: the camera sees only the sky there; on: the light patch (much brighter)',
      h_on > h_off * 3, (round(h_off, 3), round(h_on, 3)))
check('Rotation 180 degrees: the light gone from there (turned round the model)', h_rot < h_on * 0.4,
      (round(h_on, 3), round(h_rot, 3)))

# softness keeps the light put out, softens the highlight
sp.hide_render = False
camera((0, -6, 1.0), (0, 0, 1.0))
st.softness = 0.6
s1 = render('soft06')[..., :3].mean(2)
st.softness = 2.0
s2 = render('soft20')[..., :3].mean(2)
st.softness = 1.0
m1, m2 = float(s1[12:36, 20:44].mean()), float(s2[12:36, 20:44].mean())
check('Softness: bigger, softer lights put out about the same light (the sphere within 20 %)',
      abs(m2 / m1 - 1.0) < 0.2, (round(m1, 3), round(m2, 3)))

# --- the floor -----------------------------------------------------------------------------------------------------
sp.location = (0.7, -0.4, 1.3)
C.view_layer.update()
r = bpy.ops.mch.creature_floor(kind='FADE')
fl = cl.floor_object(S)
check('Fade Floor: a disc under the lowest part, centred under the parts, not pickable, no shadow cast',
      'FINISHED' in r and fl is not None and abs(fl.location.z - 0.3) < 1e-3
      and abs(fl.location.x - 0.7) < 1e-3 and abs(fl.location.y + 0.4) < 1e-3 and fl.hide_select
      and not fl.visible_shadow and st.floor == 'FADE', tuple(fl.location) if fl else None)
sp.location = (0.0, 0.0, 1.0)
C.view_layer.update()
bpy.ops.mch.creature_floor(kind='FIT')
check('Fit Floor to Model: under the part again after a move', abs(fl.location.z) < 1e-3 and abs(fl.location.x) < 1e-3)

sp.hide_render = True
cam = camera((0, 0, 9.0), (0, 0, 0))
cam.data.type = 'ORTHO'
cam.data.ortho_scale = fl.scale.x * 2.0
al = render('fade_alpha', res=(96, 96), samples=32, transparent=True)[..., 3]
mid = al[48, 48:]                                    # centre -> edge along a radius
check('Fade Floor: solid in the centre, transparent at the edge (a circle)',
      mid[0] > 0.95 and mid[-3] < 0.05 and al[2, 2] < 0.01 and al[48, 2] < 0.05, mid[::6].round(2).tolist())
smooth = np.convolve(mid, np.ones(5) / 5, 'valid')
check('... a smooth fade outward (no step: never falls more than 0.15 between two pixels after a 5-px average)',
      float(np.max(-np.diff(smooth))) < 0.15, np.diff(smooth).round(3).tolist())
ring = []
yy, xx = np.mgrid[0:96, 0:96]
rad = np.hypot(xx - 47.5, yy - 47.5) / 48.0
for r0 in (0.45, 0.6, 0.75):
    m = (rad > r0 - 0.02) & (rad < r0 + 0.02)
    ring.append(float(al[m].std()))
check('... even round each circle (16 samples, no denoise: the alpha varies little - a soft circle, not speckle)',
      max(ring) < 0.12, [round(x, 3) for x in ring])
st.floor_edge = 0.2
al2 = render('fade_edge', res=(96, 96), samples=32, transparent=True)[..., 3]
check('Edge Fade smaller: solid further out', al2[48, 48 + 26] > al[48, 48 + 26] + 0.15,
      (round(float(al[48, 74]), 2), round(float(al2[48, 74]), 2)))
st.floor_edge = 0.7
st.floor_opacity = 0.5
al3 = render('fade_op', res=(96, 96), samples=32, transparent=True)[..., 3]
st.floor_opacity = 1.0
check('Floor Opacity 0.5: the centre half see-through', abs(float(al3[44:52, 44:52].mean()) - 0.5) < 0.12,
      round(float(al3[44:52, 44:52].mean()), 3))
cam.data.type = 'PERSP'

r = bpy.ops.mch.creature_floor(kind='CATCHER')
check('Shadow Catcher: the same disc made a shadow catcher (no material)',
      'FINISHED' in r and cl.floor_object(S) is fl and fl.is_shadow_catcher and not fl.data.materials)
sp.hide_render = False
camera((0, -7, 3.0), (0, 0, 0.6))
sc_img = render('catcher', res=(96, 72), samples=32, denoise=False)
bpy.ops.mch.creature_floor(kind='OFF')
no_floor = render('nofloor', res=(96, 72), samples=32, denoise=False)
ratio = sc_img[:30, :, :3].mean(2) / np.maximum(no_floor[:30, :, :3].mean(2), 1e-4)   # (the floor rows)
k = np.ones((3, 3)) / 9.0
sm = np.array([[float((ratio[y:y + 3, x:x + 3] * k).sum()) for x in range(94)] for y in range(28)])
check('... the floor shows the background (the far corners as without it), darker only in the shadow by the part',
      sm.min() < 0.8 and abs(float(sm[:4, :6].mean()) - 1.0) < 0.08 and abs(float(sm[:4, -6:].mean()) - 1.0) < 0.08,
      (round(float(sm.min()), 3), round(float(sm[:4, :6].mean()), 3), round(float(sm[:4, -6:].mean()), 3)))
check('No Floor: the disc and its mesh removed', cl.floor_object(S) is None and not bpy.data.meshes.get(cl.FLOOR)
      and st.floor == 'OFF')

# --- the Background colour of the Render tab goes on with it, and back -----------------------------------------
cl.off(S)
check('Off: your world back, ours removed from the file', S.world is mine and not any(w.get(cl.TAG) for w in bpy.data.worlds))
bg_color.apply(S)
check('(Background Colour on your world)', bg_color.on(S))
cl.apply(S, 'museum')
check('Creature Light on while the Background Colour was on: the colour on the new world too', bg_color.on(S)
      and cl.on(S))
cl.off(S)
check('... and Off: your world back with the colour as before', S.world is mine and bg_color.on(S))

# --- the Render tab -------------------------------------------------------------------------------------------------
from mecha_lab import mech_shader_ui as msu  # noqa: E402
items, hgt = msu.hdri_content(C, 0, 320, 1.0)
heads = [it.label for it in items if it.kind == 'shead']
tiles = [it for it in items if it.kind == 'btile']
check('the Render tab: a Creature Light section with 9 preview tiles a page (the pictures found)',
      any(h.startswith('CREATURE LIGHT') for h in heads) and sum(1 for t in tiles if 'creature_light' in t.icon) == 9,
      heads)
bpy.ops.mch.creature_light(action='PAGE', step=1)
items, _h = msu.hdri_content(C, 0, 320, 1.0)
names = [t.label for t in items if t.kind == 'btile' and 'creature_light' in t.icon]
check('... the page arrow: the next 9', names and names[0] == cl.PRESETS[9][1], names[:2])
summary()
