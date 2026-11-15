"""0.24.173 Creature Cloth - a membrane (user: "드래곤이나 크리쳐 피막 만들 때 쓸 건데 크리쳐 클로스 탭으로 하나 만들어서,
두께는 어플라이 하면 추가 되게 해 주고, 일단 내가 메쉬 위에 따라 그리면 메쉬랑 붙어 있는 부분만 고정되고 나머지는 클로스로
흘러내리게 ... 그리고 사이에 크리쳐 스킨이랑 혈관 같은 거도 만들게 프리셋 만들어 주고"; "피막은 콜리전이 아니라 고정하는
핀 정보로만 내가 만들어 놓은 메쉬에 붙는 걸로 하면 되니까 무겁진 않겠다").

Draw the membrane's outline over your mesh (a dragon's wing: along the arm and the finger bones, across the gaps
between them): an even sheet fills it.  Where the sheet is over the mesh (the outline's parts drawn on it, the bones
inside it) it sits on the mesh and is pinned there; the rest spans between (a smooth surface through the pinned
parts).  Space lets it fall: Blender's own cloth, pins only - no collision (light).  Enter keeps it: a plain mesh,
parented to the mesh it hangs from, with Thickness (a Solidify); Esc drops it.  Its look: a skin with veins growing
from where it is held, six presets (Dragon, Bat, Wyvern, Pale (backlit), Demon, Leather).  It runs in Cloth Drape's
session (the same Space / Enter / Esc and window buttons).
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
import numpy as np
from bpy.props import EnumProperty, FloatProperty, IntProperty, PointerProperty
from mathutils import Matrix, Vector

from . import outline_mesh as om

KEY = 'mch_membrane'              # on a membrane (1)
PIN = 'MCH Pin'
CLOTH_MOD = 'MCH Membrane Cloth'
THICK_MOD = 'MCH Membrane Thickness'
UV_NAME = 'UVMap'

# (id, label, skin colour, vein colour (linear), subsurface, wrinkles, vein count x)
PRESETS = (
    ('DRAGON', 'Dragon', (0.22, 0.045, 0.03), (0.42, 0.03, 0.025), 0.35, 0.5, 1.0),
    ('BAT', 'Bat', (0.045, 0.035, 0.03), (0.018, 0.012, 0.01), 0.15, 1.0, 1.3),
    ('WYVERN', 'Wyvern', (0.07, 0.11, 0.035), (0.25, 0.06, 0.03), 0.3, 0.6, 0.9),
    ('PALE', 'Pale (Backlit)', (0.62, 0.36, 0.3), (0.5, 0.03, 0.035), 0.7, 0.35, 1.2),
    ('DEMON', 'Demon', (0.012, 0.008, 0.008), (0.45, 0.025, 0.01), 0.2, 0.7, 1.0),
    ('LEATHER', 'Leather', (0.2, 0.11, 0.05), (0.09, 0.045, 0.02), 0.1, 0.9, 0.8),
)
PRESET_ITEMS = [(p[0], p[1], '') for p in PRESETS]
LOOK = {p[0]: p for p in PRESETS}


def is_membrane(ob):
    return ob is not None and bool(ob.get(KEY))


def _sim():
    from . import cloth_drape as cd
    return cd.SIM


# ---- the sheet ----------------------------------------------------------------------------------------------------

def _cast(context, dg, o, d, skip):
    """The nearest mesh along the ray (not ``skip`` objects): (t, location, object) or None."""
    from . import target_rules
    oo, dd = Vector(o), Vector(d).normalized()
    walked = 0.0
    for _ in range(16):
        hit, loc, _n, _i, ob, _m = target_rules.scene_ray(context, dg, oo, dd)
        if not hit or ob is None:
            return None
        real = bpy.data.objects.get(ob.name) or ob
        t = walked + (Vector(loc) - oo).length
        if real.type == 'MESH' and real.name not in skip:
            return t, Vector(loc), real
        walked = t + 1e-4
        oo = Vector(loc) + dd * 1e-4
    return None


def _laplace(n, edges, val, fixed, iters=400):
    """``val`` smoothed over the mesh's edges, the ``fixed`` points held (Jacobi)."""
    v = val.copy()
    a, b = edges[:, 0], edges[:, 1]
    deg = np.bincount(a, minlength=n) + np.bincount(b, minlength=n)
    deg = np.maximum(deg, 1)
    free = ~fixed
    for _ in range(iters):
        s = np.bincount(a, weights=v[b], minlength=n) + np.bincount(b, weights=v[a], minlength=n)
        v[free] = s[free] / deg[free]
    return v


def sheet(context, loops, projector, detail):
    """The membrane over the outline: (points N x 3 world, triangles, pinned bool N, uv N x 2, the mesh it hangs from,
    nb).  Raises CutError when nothing of it is over a mesh."""
    from . import core_geometry as cg
    groups = cg.prepare_loops(loops)
    if not groups:
        raise cg.CutError('Draw a bigger membrane')
    outer = np.array(groups[0][0], float)
    size_px = float(np.ptp(outer, axis=0).max())
    pts, tris, nb = om.even_mesh(outer, max(size_px / max(detail, 8), 1.5), max_points=12000)
    if not len(tris):
        raise cg.CutError('Draw a bigger membrane')
    dg = context.evaluated_depsgraph_get()
    skip = {o.name for o in context.scene.objects if is_membrane(o) or o.get('mch_wing')}
    n = len(pts)
    O = np.zeros((n, 3))
    D = np.zeros((n, 3))
    t_hit = np.full(n, np.nan)
    owner = [None] * n
    for i, q in enumerate(pts):
        o, d = projector.ray((float(q[0]), float(q[1])))
        d = Vector(d).normalized()
        O[i], D[i] = tuple(o), tuple(d)
        h = _cast(context, dg, o, d, skip)
        if h is not None:
            t_hit[i] = h[0]
            owner[i] = h[2]
    hit = ~np.isnan(t_hit)
    if not np.any(hit):
        raise cg.CutError('Draw the membrane over your mesh: the parts over it hold it')
    # the outline: on the mesh where it was drawn on it, in between along the outline elsewhere
    tb = t_hit[:nb].copy()
    hb = hit[:nb]
    if np.any(hb):
        k = np.arange(nb)
        kk = np.r_[k[hb] - nb, k[hb], k[hb] + nb]
        tt = np.r_[tb[hb], tb[hb], tb[hb]]
        tb = np.interp(k, kk, tt)
    else:
        tb[:] = float(np.nanmedian(t_hit))
    E = np.r_[tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]
    E = np.unique(np.sort(E, axis=1), axis=0)
    t = np.full(n, float(np.mean(tb)))
    t[:nb] = tb
    fixed = np.zeros(n, bool)
    fixed[:nb] = True
    t = _laplace(n, E, t, fixed)
    # inside: where the mesh is right there (the bones under the membrane), it sits on it and is held
    P0 = O + D * t[:, None]
    size = float(np.linalg.norm(np.ptp(P0, axis=0)))
    on = hit & (np.abs(np.nan_to_num(t_hit, nan=1e9) - t) < size * 0.06)
    on[:nb] = hb
    t[on] = t_hit[on]
    fixed = on.copy()
    fixed[:nb] = True
    t = _laplace(n, E, t, fixed)
    P = O + D * t[:, None]
    rng = np.random.default_rng(7)                  # (a hair off flat where it is free: it can fold either way)
    P[~fixed] += D[~fixed] * rng.uniform(-1.0, 1.0, (int((~fixed).sum()), 1)) * size * 0.0006
    held = [owner[i] for i in np.nonzero(on)[0] if owner[i] is not None]
    body = max(set(held), key=held.count) if held else None
    lo = outer.min(0)
    uv = (pts - lo) / max(size_px, 1e-9)
    return P, tris, on, uv, body, nb


# ---- the veins (an image in the membrane's own place: growing from where it is held) ----------------------------

def vein_lines(uv, nb, pinned, count=1.0, seed=0):
    """Veins as polylines in uv: from the held parts of the outline, branching toward the free edge."""
    rng = random.Random(seed * 131 + 7)
    ring = uv[:nb]
    held = ring[pinned[:nb]] if np.any(pinned[:nb]) else uv[pinned]
    if not len(held):
        return []
    free_c = ring[~pinned[:nb]].mean(0) if np.any(~pinned[:nb]) else uv.mean(0)
    seeds = held[np.linspace(0, len(held) - 1, max(3, int(9 * count))).astype(int)]
    from mathutils.kdtree import KDTree
    kd = KDTree(len(held))
    for i, q in enumerate(held):
        kd.insert((float(q[0]), float(q[1]), 0.0), i)
    kd.balance()
    out = []
    step = 0.018

    def away(p):
        """Away from where it is held (the nearest held point): veins spread out, they do not meet."""
        _c, i, dist = kd.find((float(p[0]), float(p[1]), 0.0))
        v = p - held[i]
        if dist < 1e-6:
            v = free_c - p
        return math.atan2(v[1], v[0])

    def grow(p, ang, width, gen, steps):
        line, ws = [p.copy()], [width]
        for k in range(steps):
            want = away(p)
            da = (want - ang + math.pi) % (2 * math.pi) - math.pi
            ang += 0.15 * da + rng.uniform(-0.3, 0.3)
            p = p + step * np.array([math.cos(ang), math.sin(ang)])
            if not om.inside(p[None], [ring])[0]:
                break
            line.append(p.copy())
            width *= 0.985
            ws.append(width)
            if gen < 4 and k > 3 and rng.random() < 0.09:
                side = rng.choice((-1, 1))
                grow(p.copy(), ang + side * rng.uniform(0.35, 0.8), width * 0.65, gen + 1, int(steps * 0.6))
        if len(line) > 1:
            out.append((np.array(line), np.array(ws), False))
    for s in seeds:
        to_free = free_c - s
        ang = math.atan2(to_free[1], to_free[0]) + rng.uniform(-0.5, 0.5)
        grow(s.copy() + 0.004 * (to_free / max(np.linalg.norm(to_free), 1e-9)), ang, 0.0045, 0, 60)
    return out


def vein_image(name, lines, res=1024):
    lo, hi = np.zeros(2), np.ones(2)
    px = 1.0 / res
    R = om.raster_lines(lo, hi, px, lines) if lines else np.zeros((res + 1, res + 1), np.float32)
    Hh, Ww = R.shape
    im = bpy.data.images.get(name)
    if im is not None and (im.size[0] != Ww or im.size[1] != Hh):
        bpy.data.images.remove(im)
        im = None
    if im is None:
        im = bpy.data.images.new(name, Ww, Hh, alpha=True, float_buffer=True)
        im.colorspace_settings.name = 'Non-Color'
    rgba = np.zeros((Hh, Ww, 4), np.float32)
    rgba[..., 0] = R
    rgba[..., 3] = 1.0
    im.pixels.foreach_set(rgba.ravel())
    im.update()
    try:
        im.pack()
    except RuntimeError:
        pass
    return im


def membrane_material(ob, image, preset):
    _pid, _label, skin, vein, sss, wrinkle, _vc = LOOK.get(preset, PRESETS[0])
    m = next((s for s in ob.data.materials if s is not None and s.get('mch_membrane_mat')), None)
    if m is None:
        m = bpy.data.materials.new(f'MCH Membrane ({ob.name})')
        m['mch_membrane_mat'] = 1
        ob.data.materials.clear()
        ob.data.materials.append(m)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    pb = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(pb.outputs[0], out.inputs['Surface'])
    uvn = nt.nodes.new('ShaderNodeUVMap')
    uvn.uv_map = UV_NAME
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = image
    tx.extension = 'EXTEND'
    nt.links.new(uvn.outputs['UV'], tx.inputs['Vector'])
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(tx.outputs['Color'], sep.inputs[0])
    vmask = nt.nodes.new('ShaderNodeMath')
    vmask.operation = 'MULTIPLY'
    vmask.use_clamp = True
    nt.links.new(sep.outputs[0], vmask.inputs[0])
    vmask.inputs[1].default_value = 2.5
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    sock = {i.identifier: i for i in mix.inputs}
    nt.links.new(vmask.outputs[0], sock['Factor_Float'])
    sock['A_Color'].default_value = (*skin, 1.0)
    sock['B_Color'].default_value = (*vein, 1.0)
    nt.links.new(next(o for o in mix.outputs if o.identifier == 'Result_Color'), pb.inputs['Base Color'])
    # the skin: fine wrinkles (noise in the membrane's own place) + the veins raised
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 60.0
    noise.inputs['Detail'].default_value = 6.0
    noise.inputs['Roughness'].default_value = 0.6
    nt.links.new(uvn.outputs['UV'], noise.inputs['Vector'])
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.feature = 'DISTANCE_TO_EDGE'
    vor.inputs['Scale'].default_value = 90.0
    nt.links.new(uvn.outputs['UV'], vor.inputs['Vector'])
    h = nt.nodes.new('ShaderNodeMath')
    h.operation = 'MULTIPLY_ADD'
    nt.links.new(noise.outputs['Fac'], h.inputs[0])
    h.inputs[1].default_value = 0.25 * wrinkle
    nt.links.new(sep.outputs[0], h.inputs[2])
    h2 = nt.nodes.new('ShaderNodeMath')
    h2.operation = 'MULTIPLY_ADD'
    nt.links.new(vor.outputs['Distance'], h2.inputs[0])
    h2.inputs[1].default_value = 0.6 * wrinkle
    nt.links.new(h.outputs[0], h2.inputs[2])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.5
    bump.inputs['Distance'].default_value = 0.003
    nt.links.new(h2.outputs[0], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], pb.inputs['Normal'])
    pb.inputs['Roughness'].default_value = 0.55
    for k, v in (('Subsurface Weight', sss), ('Subsurface Scale', 0.05), ('Sheen Weight', 0.1)):
        try:
            pb.inputs[k].default_value = v
        except KeyError:
            pass
    try:
        pb.inputs['Subsurface Radius'].default_value = (1.0, 0.25, 0.15)
    except KeyError:
        pass
    m.diffuse_color = (*[min(1.0, c * 1.6) for c in skin], 1.0)
    return m


# ---- the session (in Cloth Drape's: Space / Enter / Esc) ----------------------------------------------------------

def cloth_settings(ob, mp, size):
    cm = ob.modifiers.get(CLOTH_MOD)
    if cm is None:
        return
    cs = cm.settings
    cs.quality = 6
    cs.mass = 0.15
    cs.air_damping = 1.5
    cs.tension_stiffness = 2.0 + mp.stiffness * 0.8
    cs.compression_stiffness = 2.0 + mp.stiffness * 0.8
    cs.shear_stiffness = 2.0 + mp.stiffness * 0.3
    cs.bending_stiffness = 0.5 * (0.02 ** (mp.folds / 100.0))
    cs.shrink_min = -mp.slack / 100.0               # (looser: more to sag)
    cs.effector_weights.gravity = mp.gravity / 100.0
    cs.vertex_group_mass = PIN
    cs.pin_stiffness = 1.0
    cc = cm.collision_settings
    cc.use_collision = False                        # (pins only - no collision: light)
    cc.use_self_collision = False


def perform(context, loops, projector):
    """The membrane drawn: the sheet, its pins, its look; Space lets it fall."""
    from . import cloth_drape as cd
    from . import core_geometry as cg
    if cd.sim_active():
        raise cg.CutError('Cloth Drape: keep (Enter) or drop (Esc) the cloth you have first')
    mp = context.scene.mch_membrane
    P, tris, pinned, uv, body, nb = sheet(context, loops, projector, mp.detail)
    if not np.any(pinned):
        raise cg.CutError('Draw the membrane over your mesh: the parts over it hold it')
    if pinned.all():
        raise cg.CutError('The whole membrane is on the mesh: draw part of it off the mesh (it falls there)')
    me = bpy.data.meshes.new('Creature Cloth')
    ob = bpy.data.objects.new('Creature Cloth', me)
    coll = body.users_collection[0] if body is not None and body.users_collection else context.scene.collection
    coll.objects.link(ob)
    c = P.mean(0)
    ob.matrix_basis = Matrix.Translation(Vector(tuple(c)))
    bm = bmesh.new()
    vs = [bm.verts.new(tuple(p - c)) for p in P]
    for f in tris:
        try:
            bm.faces.new([vs[int(i)] for i in f])
        except ValueError:
            pass
    bmesh.ops.join_triangles(bm, faces=bm.faces[:], angle_face_threshold=math.radians(25),
                             angle_shape_threshold=math.radians(40))
    uvl = bm.loops.layers.uv.new(UV_NAME)
    for f in bm.faces:
        for lp in f.loops:
            lp[uvl].uv = tuple(uv[lp.vert.index])
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    vg = ob.vertex_groups.new(name=PIN)
    vg.add([int(i) for i in np.nonzero(pinned)[0]], 1.0, 'REPLACE')
    ob[KEY] = 1
    size = float(np.linalg.norm(np.ptp(P, axis=0)))
    lines = vein_lines(uv, nb, pinned, LOOK.get(mp.preset, PRESETS[0])[6] * mp.vein_count, mp.seed)
    if abs(mp.vein_width - 1.0) > 1e-6:
        lines = [(q, w * mp.vein_width, cl) for q, w, cl in lines]
    im = vein_image(f'MCH Membrane Veins ({ob.name})', lines)
    membrane_material(ob, im, mp.preset)
    if body is not None:                            # (it hangs from the mesh: moves with it)
        ob.parent = body
        ob.matrix_parent_inverse = body.matrix_world.inverted_safe()
    frame0 = context.scene.frame_current
    cm = ob.modifiers.new(CLOTH_MOD, 'CLOTH')
    cm.point_cache.frame_start = frame0
    cm.point_cache.frame_end = frame0 + mp.frames
    cloth_settings(ob, mp, size)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    SIM = _sim()
    SIM.clear()
    SIM.update(mode='MEMBRANE', ob=ob.name, target=body.name if body is not None else '', frame0=frame0, size=size,
               running=False, done=False, want=None,
               sess=dict(frame=0, frames=mp.frames, points=len(me.vertices)))
    return (f'{ob.name}: {len(me.vertices):,} points, {int(pinned.sum()):,} pinned on '
            f'{body.name if body is not None else "the mesh"} - Space: let it fall · Enter keep · Esc drop')


def sim_step(context):
    SIM = _sim()
    sess = SIM.get('sess')
    if sess is None:
        return False
    if sess['frame'] >= sess['frames']:
        SIM['running'] = False
        SIM['done'] = True
        return False
    sess['frame'] += 1
    context.scene.frame_set(SIM['frame0'] + sess['frame'])
    return True


def sim_keep(context):
    """The membrane kept as it hangs now: a plain mesh (still on the mesh it hangs from) + Thickness."""
    SIM = _sim()
    ob = bpy.data.objects.get(SIM.get('ob', ''))
    if ob is None:
        SIM.clear()
        return 'nothing to keep'
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    old = ob.data
    cm = ob.modifiers.get(CLOTH_MOD)
    if cm is not None:
        ob.modifiers.remove(cm)
    me.name = old.name
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    frame = SIM['sess']['frame']
    size = SIM.get('size', 1.0)
    if 'frame0' in SIM:
        context.scene.frame_set(SIM['frame0'])
    mp = context.scene.mch_membrane
    thick = False
    if mp.thickness > 0:
        md = ob.modifiers.new(THICK_MOD, 'SOLIDIFY')
        md.thickness = size * mp.thickness / 100.0
        md.offset = 0.0
        md.use_even_offset = False
        md.use_quality_normals = True
        md.use_rim = True
        thick = True
    if KEY in ob.keys():
        del ob[KEY]
    SIM.clear()
    return (f'{ob.name}: kept at frame {frame} ({len(me.vertices):,} points)' +
            (f' + Thickness {mp.thickness:.2f} % (its Solidify)' if thick else ''))


def sim_drop(context):
    SIM = _sim()
    ob = bpy.data.objects.get(SIM.get('ob', ''))
    if 'frame0' in SIM:
        context.scene.frame_set(SIM['frame0'])
    if ob is not None:
        me = ob.data
        bpy.data.objects.remove(ob)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    SIM.clear()
    return 'Creature Cloth: dropped'


def sim_restart(context):
    SIM = _sim()
    ob = bpy.data.objects.get(SIM.get('ob', ''))
    if ob is None:
        return False
    mp = context.scene.mch_membrane
    context.scene.frame_set(SIM['frame0'])
    cm = ob.modifiers.get(CLOTH_MOD)
    if cm is not None:
        cm.point_cache.frame_end = SIM['frame0'] + mp.frames
    cloth_settings(ob, mp, SIM.get('size', 1.0))
    SIM['sess'].update(frame=0, frames=mp.frames)
    SIM.update(done=False, running=True)
    return True


def sim_status():
    SIM = _sim()
    sess = SIM.get('sess') or {}
    f, n = sess.get('frame', 0), sess.get('frames', 0)
    if SIM.get('done'):
        return f'Creature Cloth done: frame {f} / {n}  (Enter keep · Esc drop · Space again)'
    return (f'Creature Cloth {"falling" if SIM.get("running") else "ready"}: frame {f} / {n}  '
            f'(Space {"pause" if SIM.get("running") else "let it fall"} · Enter keep · Esc drop)')


# ---- settings / window ----------------------------------------------------------------------------------------------

def _restart(self, context):
    SIM = _sim()
    if SIM.get('mode') == 'MEMBRANE':
        sim_restart(context)
        SIM['running'] = False


def _look(self, context):
    """A preset / the veins: the live membrane's look again."""
    SIM = _sim()
    ob = bpy.data.objects.get(SIM.get('ob', '')) if SIM.get('mode') == 'MEMBRANE' else None
    if ob is None:
        ob = context.view_layer.objects.active
        if ob is None or not any(s is not None and s.get('mch_membrane_mat') for s in getattr(ob.data, 'materials', ())):
            return
    im = next((n.image for s in ob.data.materials if s is not None and s.get('mch_membrane_mat')
               for n in s.node_tree.nodes if n.bl_idname == 'ShaderNodeTexImage'), None)
    if im is not None:
        membrane_material(ob, im, self.preset)


class MCH_PG_Membrane(bpy.types.PropertyGroup):
    preset: EnumProperty(name='Skin', items=PRESET_ITEMS, default='DRAGON', update=_look)
    slack: FloatProperty(name='Slack', default=15.0, min=0.0, max=60.0, update=_restart,
                         description='How loose the membrane is (% larger than it was drawn): more to sag and fold')
    gravity: FloatProperty(name='Gravity', default=100.0, min=0.0, max=300.0, update=_restart)
    stiffness: FloatProperty(name='Stiffness', default=25.0, min=0.0, max=100.0, update=_restart,
                             description='How hard it is to stretch')
    folds: FloatProperty(name='Folds', default=35.0, min=0.0, max=100.0, update=_restart,
                         description='0: soft wide folds .. 100: fine sharp folds')
    frames: IntProperty(name='Frames', default=50, min=10, max=400, update=_restart)
    thickness: FloatProperty(name='Thickness %', default=0.6, min=0.0, max=10.0, soft_max=3.0,
                             description='Added when it is kept (Enter): a Solidify, % of the membrane\'s size')
    detail: IntProperty(name='Detail', default=50, min=10, max=150,
                        description='Points across the membrane (the next one drawn)')
    vein_count: FloatProperty(name='Veins', default=1.0, min=0.0, max=3.0,
                              description='How many veins grow from where it is held (the next one drawn)')
    vein_width: FloatProperty(name='Vein Width', default=1.0, min=0.2, max=4.0)
    seed: IntProperty(name='Seed', default=0, min=0)


def draw(layout, context):
    from . import cloth_drape as cd
    mp = context.scene.mch_membrane
    SIM = _sim()
    live = cd.sim_active() and SIM.get('mode') == 'MEMBRANE'
    box = layout.box()
    box.label(text=sim_status() if live else 'Draw the membrane over your mesh: the parts over it hold it',
              icon='PLAY' if live else 'INFO')
    if live:
        r = box.row(align=True)
        r.operator('mch.cdrape_control', text='Fall / Pause (Space)').action = 'toggle'
        r.operator('mch.cdrape_control', text='Keep (Enter)').action = 'confirm'
        r.operator('mch.cdrape_control', text='Drop (Esc)').action = 'cancel'
    layout.label(text='Skin and veins')
    g = layout.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
    for pid, label, *_r in PRESETS:
        g.prop_enum(mp, 'preset', pid, text=label)
    col = layout.column(align=True)
    for k in ('slack', 'gravity', 'stiffness', 'folds', 'frames', 'thickness'):
        col.prop(mp, k)
    col = layout.column(align=True)
    col.label(text='The next membrane')
    for k in ('detail', 'vein_count', 'vein_width', 'seed'):
        col.prop(mp, k)
    col = layout.column(align=True)
    for line in ('Draw over your mesh: pinned where it is on the mesh',
                 'Space: the rest falls (cloth, pins only)',
                 'Enter: keep (+ Thickness),  Esc: drop'):
        col.label(text=line)


class MCH_OT_membrane_keep(bpy.types.Operator):
    """Keep the Creature Cloth as it hangs now (+ Thickness) - Enter"""
    bl_idname = 'mch.membrane_keep'
    bl_label = 'Keep Creature Cloth'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        from . import cloth_drape as cd
        return cd.sim_active() and _sim().get('mode') == 'MEMBRANE'

    def execute(self, context):
        from . import cloth_drape as cd
        if _sim().get('modal'):                     # (the running session keeps it itself)
            _sim()['want'] = 'confirm'
            return {'FINISHED'}
        self.report({'INFO'}, cd.confirm(context))
        return {'FINISHED'}


CLASSES = (MCH_PG_Membrane, MCH_OT_membrane_keep)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_membrane = PointerProperty(type=MCH_PG_Membrane)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_membrane'):
        del bpy.types.Scene.mch_membrane
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
