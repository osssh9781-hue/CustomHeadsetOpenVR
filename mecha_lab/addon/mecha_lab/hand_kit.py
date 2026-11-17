"""0.24.187 Hand / Foot Builder (user: "손이랑 발을 각각 손바닥 발바닥, 그리고 사용할 손가락 프리셋 엄지, (검지 중지), 약지 이렇게
보냈는데 크리쳐 용이라 발에도 써도 될 것 같고 각각 개수랑 길이 두께 조절하면 좋을 것 같고 꺾어도 이상하지 않게 닿는 부분을 둥글게
처리했어"): a hand or a foot put together from the user's own pieces - a palm or a sole, fingers along its far edge,
thumbs on its side - each group's kind (any of the three fingers), number, length, thickness, spread, curl.

One object (the pieces loose inside it: a finger's rounded root sits in the palm, so it can turn there); every slider
rebuilds it.  On a one-piece body (Body Kit window - Hands / Feet: Built) one hangs on each hand / foot bone, the two
sides kept the same.  The pieces: body_kits/hand_parts.npz (tools_dev/hand_kit_build.py).
"""
from __future__ import annotations

import json
import math
import os

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty

FILE = os.path.join(os.path.dirname(__file__), 'body_kits', 'hand_parts.npz')
KEY = 'mch_handkit'                      # on a built hand / foot: json {'side': 'L' | 'R', 'slot': '' | 'Hand' | 'Foot'}
FINGERS = (('Finger', 'Finger', 'The short straight finger (index / middle)'),
           ('Long', 'Long Finger', 'The long thin finger'),
           ('Thumb', 'Thumb', 'The thick finger (thumb)'))
BASES = (('Palm', 'Palm', 'A hand: the palm'), ('Sole', 'Sole', 'A foot: the sole (heel raised)'))
_CACHE = {}
_BUSY = [False]


def load():
    """{name: {'V', 'N', 'L'}} and the meta - the body 1 tall (see the builder for the frames)."""
    if 'd' not in _CACHE:
        with np.load(FILE, allow_pickle=False) as z:
            meta = json.loads(str(z['meta']))
            parts = {n: {'V': z[n + '_V'].astype(np.float64), 'N': np.array(z[n + '_N']).astype(np.int64),
                         'L': np.array(z[n + '_L']).astype(np.int64)} for n in ('Palm', 'Sole', 'Finger', 'Long', 'Thumb')}
        _CACHE['d'] = (parts, meta)
    return _CACHE['d']


def _rot_x(P, a):
    c, s = math.cos(a), math.sin(a)
    return np.stack([P[:, 0], P[:, 1] * c - P[:, 2] * s, P[:, 1] * s + P[:, 2] * c], 1)


def _rot_z(P, a):
    """Round Z: Y toward +X by ``a``."""
    c, s = math.cos(a), math.sin(a)
    return np.stack([P[:, 0] * c + P[:, 1] * s, -P[:, 0] * s + P[:, 1] * c, P[:, 2]], 1)


def _rot_y(P, a):
    c, s = math.cos(a), math.sin(a)
    return np.stack([P[:, 0] * c + P[:, 2] * s, P[:, 1], -P[:, 0] * s + P[:, 2] * c], 1)


def finger(kind, length=1.0, thick=1.0, bend=0.0, face=1.0):
    """One finger's points, its root on 0, along +Y: scaled; ``bend``: curled along its length (toward the palm's
    inside)."""
    parts, meta = load()
    P = parts[kind]['V'] * (thick, length, thick)
    ln = meta[kind]['length'] * length
    if abs(bend) > 1e-5:
        k = bend * face / ln
        y = np.clip(P[:, 1], 0.0, None)               # (the rounded root behind 0 stays as it is)
        th = k * y
        cy, cz = np.sin(th) / k, (1.0 - np.cos(th)) / k
        P = np.stack([P[:, 0], cy + np.minimum(P[:, 1], 0.0) - P[:, 2] * np.sin(th), cz + P[:, 2] * np.cos(th)], 1)
    return P


def socket_end(B, u, half):
    """Where a finger sits on the palm's far edge at ``u`` across it: (x, y, z) - the far end of the strip there."""
    m = np.abs(B[:, 0] - u) < half
    if m.sum() < 4:
        m = np.abs(B[:, 0] - u) < half * 3
    S = B[m]
    far = S[S[:, 1] >= np.quantile(S[:, 1], 0.9)]
    return np.array([u, far[:, 1].mean(), far[:, 2].mean()])


def socket_side(B, v, half, sign):
    """Where a thumb sits on the palm's side at ``v`` along it."""
    m = np.abs(B[:, 1] - v) < half
    S = B[m]
    q = S[S[:, 0] * sign >= np.quantile(S[:, 0] * sign, 0.9)]
    return np.array([q[:, 0].mean(), v, q[:, 2].mean()])


def build(p):
    """(V, N, L) of the whole hand / foot in its own frame (origin the wrist, Y along, Z the palm's normal, X across) -
    the body 1 tall.  ``p``: the sliders (a dict - see MCH_PG_HandKit)."""
    parts, meta = load()
    face = meta['face']
    tside = meta['thumb_side']
    base = parts[p['base']]
    B = base['V'] * (p['width'], p['length'], p['thick'])
    Vs, Ns, Ls, off = [B], [base['N']], [base['L']], len(B)

    def add(kind, P):
        nonlocal off
        Vs.append(P)
        Ns.append(parts[kind]['N'])
        Ls.append(parts[kind]['L'] + off)
        off += len(P)
    x0, x1 = B[:, 0].min(), B[:, 0].max()
    wid = x1 - x0
    n = int(p['f_count'])
    for i in range(n):
        t = (i + 0.5) / n
        thick = p['f_thick']
        fw = meta[p['f_kind']]['thick'] * thick
        u = x0 + fw * 0.6 + (wid - fw * 1.2) * t
        s = socket_end(B, u, max(fw * 0.5, wid * 0.04))
        ln = p['f_length'] * (1.0 - p['f_arc'] * (2.0 * t - 1.0) ** 2)
        P = finger(p['f_kind'], ln, thick, p['f_bend'], face)
        P = _rot_x(P, p['f_curl'] * face)
        P = _rot_z(P, p['f_spread'] * (t - 0.5) * 2.0)
        s[1] -= fw * p['f_inset']                      # (its rounded root sunk into the palm)
        add(p['f_kind'], P + s)
    m = int(p['t_count'])
    y1 = B[:, 1].max()
    for i in range(m):
        sign = tside if i == 0 else -tside            # (the second thumb: the other side)
        tw = meta[p['t_kind']]['thick'] * p['t_thick']
        s = socket_side(B, y1 * p['t_pos'], max(tw * 0.6, y1 * 0.06), sign)
        P = finger(p['t_kind'], p['t_length'], p['t_thick'], p['t_bend'], face)
        P = _rot_x(P, p['t_curl'] * face)
        P = _rot_z(P, p['t_angle'] * sign)
        s[0] -= sign * tw * p['f_inset']
        add(p['t_kind'], P + s)
    V = np.concatenate(Vs)
    V = _rot_y(V, (meta[p['base']]['turn'] if p.get('on_body') else 0.0) + p['turn'])   # (on a body: turned as it was sculpted on the arm)
    return V, np.concatenate(Ns), np.concatenate(Ls)


PARAMS = ('base', 'width', 'length', 'thick', 'turn', 'f_kind', 'f_count', 'f_length', 'f_thick', 'f_spread', 'f_arc',
          'f_curl', 'f_bend', 'f_inset', 't_kind', 't_count', 't_length', 't_thick', 't_pos', 't_angle', 't_curl',
          't_bend')


def params(ob):
    kp = ob.mch_handkit
    return {k: (getattr(kp, k) if isinstance(getattr(kp, k), str) else float(getattr(kp, k))) for k in PARAMS}


def is_hand(ob):
    return ob is not None and ob.type == 'MESH' and KEY in ob


def info(ob):
    try:
        return json.loads(ob[KEY])
    except (KeyError, TypeError, ValueError):
        return {'side': 'L', 'slot': ''}


def length_of(p):
    """How long the base is (wrist to where the fingers start), the body 1 tall."""
    _parts, meta = load()
    return meta[p['base']]['size'][1] * p['length']


def rebuild(ob):
    """The sliders -> the object's mesh (its points and faces replaced; materials kept)."""
    from .body_kit import _flip
    d = info(ob)
    p = params(ob)
    p['on_body'] = bool(d.get('slot'))
    V, N, L = build(p)
    V = V * ob.mch_handkit.size * d.get('unit', 1.0)
    if d.get('side') == 'R':
        V = V * (-1.0, 1.0, 1.0)
        L = _flip(N, L)
    me = ob.data
    me.clear_geometry()
    me.vertices.add(len(V))
    me.vertices.foreach_set('co', V.astype(np.float32).ravel())
    me.loops.add(len(L))
    me.loops.foreach_set('vertex_index', L.astype(np.int32))
    me.polygons.add(len(N))
    me.polygons.foreach_set('loop_start', np.concatenate([[0], np.cumsum(N)[:-1]]).astype(np.int32))
    me.polygons.foreach_set('use_smooth', [True] * len(N))
    me.update(calc_edges=True)


def make(context, base='Palm', side='L', location=None, name=None, slot='', unit=1.0, link=True):
    """A new hand ('Palm') or foot ('Sole') object; ``unit``: what 1 (a body's height) is in its space."""
    me = bpy.data.meshes.new(name or ('Hand' if base == 'Palm' else 'Foot'))
    ob = bpy.data.objects.new(me.name, me)
    if link:
        (context.collection or context.scene.collection).objects.link(ob)
    ob[KEY] = json.dumps({'side': side, 'slot': slot, 'unit': unit})
    _BUSY[0] = True
    try:
        kp = ob.mch_handkit
        kp.base = base
        if base == 'Sole':                            # (a foot: three toes forward, one small one at the side)
            kp.f_count, kp.f_kind, kp.f_length, kp.f_spread, kp.t_count = 3, 'Thumb', 0.8, math.radians(12), 0
    finally:
        _BUSY[0] = False
    if location is not None:
        ob.location = location
    rebuild(ob)
    return ob


def twins(ob):
    """The same hand / foot on the body's other side (hung on the same bones object)."""
    d = info(ob)
    if not d.get('slot') or ob.parent is None:
        return []
    return [o for o in ob.parent.children if o is not ob and is_hand(o) and info(o).get('slot') == d['slot']]


def _upd(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if not is_hand(ob):
        return
    rebuild(ob)
    _BUSY[0] = True
    try:
        for o in twins(ob):                           # (the other side: the same sliders)
            for k in PARAMS + ('size',):
                setattr(o.mch_handkit, k, getattr(self, k))
            rebuild(o)
    finally:
        _BUSY[0] = False


def _f(name, default, lo, hi, desc, soft=None):
    kw = {'name': name, 'default': default, 'min': lo, 'max': hi, 'description': desc, 'update': _upd}
    if soft:
        kw['soft_min'], kw['soft_max'] = soft
    return FloatProperty(**kw)


def _a(name, default, lo, hi, desc):
    return FloatProperty(name=name, default=math.radians(default), min=math.radians(lo), max=math.radians(hi),
                         subtype='ANGLE', description=desc, update=_upd)


class MCH_PG_HandKit(bpy.types.PropertyGroup):
    base: EnumProperty(name='Base', items=BASES, default='Palm', update=_upd)
    size: _f('Size', 1.0, 0.05, 20.0, 'The whole hand / foot bigger or smaller', soft=(0.3, 3.0))
    width: _f('Width', 1.0, 0.3, 3.0, 'The palm / sole wider', soft=(0.5, 2.0))
    length: _f('Length', 1.0, 0.3, 3.0, 'The palm / sole longer', soft=(0.5, 2.0))
    thick: _f('Thickness', 1.0, 0.3, 3.0, 'The palm / sole thicker', soft=(0.5, 2.0))
    turn: _a('Turn', 0, -180, 180, 'The whole hand / foot turned round its own length')
    f_kind: EnumProperty(name='Fingers', items=FINGERS, default='Finger', update=_upd)
    f_count: IntProperty(name='Number', default=4, min=0, max=8, description='How many fingers / toes', update=_upd)
    f_length: _f('Length', 1.0, 0.2, 5.0, 'Finger length', soft=(0.4, 3.0))
    f_thick: _f('Thickness', 1.0, 0.3, 4.0, 'Finger thickness', soft=(0.5, 2.5))
    f_spread: _a('Spread', 16, -40, 80, 'The fingers fanned out')
    f_arc: _f('Middle Longer', 0.15, -0.5, 0.8, 'The outer fingers shorter than the middle ones')
    f_curl: _a('Curl', 0, -120, 120, 'Each finger turned at its root (toward the palm\'s inside)')
    f_bend: _a('Bend', 0, -200, 200, 'Each finger curled along its length')
    f_inset: _f('Root Depth', 0.5, 0.0, 1.5, 'How deep the rounded roots sit in the palm')
    t_kind: EnumProperty(name='Thumbs', items=FINGERS, default='Thumb', update=_upd)
    t_count: IntProperty(name='Number', default=1, min=0, max=2, description='Thumbs: none, one, or one on each side',
                         update=_upd)
    t_length: _f('Length', 1.0, 0.2, 5.0, 'Thumb length', soft=(0.4, 3.0))
    t_thick: _f('Thickness', 1.0, 0.3, 4.0, 'Thumb thickness', soft=(0.5, 2.5))
    t_pos: _f('Position', 0.45, 0.05, 0.95, 'Where on the palm\'s side the thumb sits (wrist - fingers)')
    t_angle: _a('Angle', 50, 0, 120, 'The thumb turned out to the side')
    t_curl: _a('Curl', 0, -120, 120, 'The thumb turned at its root (toward the palm\'s inside)')
    t_bend: _a('Bend', 0, -200, 200, 'The thumb curled along its length')


class MCH_OT_handkit_add(bpy.types.Operator):
    bl_idname = 'mch.handkit_add'
    bl_label = 'Build a Hand / Foot'
    bl_description = ('A hand or a foot put together from your pieces (palm / sole + fingers + thumbs) at the 3D '
                      'cursor: the number, length, thickness, spread and curl of the fingers by sliders')
    bl_options = {'REGISTER', 'UNDO'}
    base: EnumProperty(name='Base', items=BASES, default='Palm')
    mirror: BoolProperty(name='Right Side', default=False)

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        h = getattr(context.scene, 'mch_bodykit_new', None)
        ob = make(context, self.base, 'R' if self.mirror else 'L', context.scene.cursor.location,
                  unit=float(h.height) if h is not None else 1.8)
        try:
            from .body_kit import _material
            ob.data.materials.append(_material('creature'))
        except (ImportError, KeyError):
            pass
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        self.report({'INFO'}, f'{ob.name}: {len(ob.data.polygons):,} faces - its sliders in the window')
        return {'FINISHED'}


def draw_add(layout):
    col = layout.column(align=True)
    col.label(text='Hand / Foot Builder (palm + fingers)', icon='VIEW_PAN')
    row = col.row(align=True)
    row.operator('mch.handkit_add', text='Hand').base = 'Palm'
    row.operator('mch.handkit_add', text='Foot').base = 'Sole'


def draw(layout, context):
    ob = getattr(context, 'active_object', None)
    if not is_hand(ob):
        return False
    kp = ob.mch_handkit
    col = layout.column(align=True)
    col.label(text=f'{ob.name} - base')
    col.prop(kp, 'base', text='')
    for k in ('size', 'width', 'length', 'thick', 'turn'):
        col.prop(kp, k, slider=True)
    col = layout.column(align=True)
    col.label(text='Fingers / Toes')
    col.prop(kp, 'f_kind', text='')
    col.prop(kp, 'f_count')
    for k in ('f_length', 'f_thick', 'f_spread', 'f_arc', 'f_curl', 'f_bend', 'f_inset'):
        col.prop(kp, k, slider=True)
    col = layout.column(align=True)
    col.label(text='Thumbs (on the side)')
    col.prop(kp, 't_kind', text='')
    col.prop(kp, 't_count')
    for k in ('t_length', 't_thick', 't_pos', 't_angle', 't_curl', 't_bend'):
        col.prop(kp, k, slider=True)
    return True


CLASSES = (MCH_PG_HandKit, MCH_OT_handkit_add)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_handkit = PointerProperty(type=MCH_PG_HandKit)


def unregister():
    if hasattr(bpy.types.Object, 'mch_handkit'):
        del bpy.types.Object.mch_handkit
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
