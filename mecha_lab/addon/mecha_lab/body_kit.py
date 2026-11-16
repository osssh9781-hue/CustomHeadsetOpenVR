"""0.24.183 Body Kit (user: "그냥 어렵지 않게 팔다리 허벅지 이런 거 분리해서 내가 각각 조절하는 게 나을 수도 있어" /
"이걸 이용해서 슬라이더로 체형이랑 다리 길이 이런 것도 변경하고 싶어" - the user's two part-split bodies, a human and a
creature): a body made of its parts (head / torso, arms, hands, pelvis, thighs, knees, shins, feet - left and right),
each a mesh of its own hung on the one before it at the joint where they meet.

* Body Shape (the whole body): Height, Legs, Arms, Torso, Shoulders, Hips, Build, Muscle, Definition, Head, Hands, Feet -
  the feet kept on the ground.
* The part picked: Length, Width, Depth, Taper, Size, Muscle, Definition, Bend (+ where) - the other side the same
  (Symmetry).
* Pose: each part turns round its joint (R) - the parts after it go with it; Mirror Pose, Reset Pose.
* Swap a part for the other body's (a creature's shin on the human) or for your own: Use Selected Mesh (your sculpt over
  the part) / Save as My Part (kept in Blender's config folder, there in every file).
* Join to One Mesh: the parts as one mesh (Remesh: fused, to sculpt).

Every slider is live (a Geometry Nodes deform on each part - the part's own mesh untouched); the parts below a part move
to where its end goes."""
from __future__ import annotations

import json
import math
import os

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty
from mathutils import Matrix, Quaternion, Vector

KIT_DIR = os.path.join(os.path.dirname(__file__), 'body_kits')
KITS = (('human', 'Human', 'Your human body: head and torso, upper arms, forearms, hands, pelvis, thighs, knees, '
         'shins, feet'),
        ('creature', 'Creature', 'Your creature body: head, torso, long arms, clawed hands, pelvis, thighs, knees, '
         'digitigrade shins, feet'))
KIT_LABEL = {k[0]: k[1] for k in KITS}
PART_KEY = 'mch_bodypart'               # on a part: json - kit, name, slot, side, its frame, where its children hang
GROUP = 'MCH Body Part'
GROUP_VERSION = 3
MOD = 'MCH Body Part'
COLLECTION = 'Body Kit'
LEGS = {'Thigh', 'Shin'}
ARMS = {'Arm', 'UpperArm', 'Forearm'}
GIRTH = {'Torso', 'Pelvis', 'Thigh', 'Knee', 'Shin', 'Arm', 'UpperArm', 'Forearm'}
SIZE_OF = {'Head': 'head', 'Hand': 'hands', 'Foot': 'feet'}
SLOT_LABEL = {'Pelvis': 'Pelvis', 'Torso': 'Torso', 'Head': 'Head', 'Arm': 'Arm', 'UpperArm': 'Upper Arm',
              'Forearm': 'Forearm', 'Hand': 'Hand', 'Thigh': 'Thigh', 'Knee': 'Knee', 'Shin': 'Shin', 'Foot': 'Foot'}
MY_DIR = [None]                          # (a test points it elsewhere: never the user's own folder)
BEND_W = 0.12                            # the bend's soft zone (share of the part's length either side)
MUSCLE_K = 0.05                          # Muscle 1: the belly out by 5 % of the part's length
TIP_ZONE = (1.05, 1.4)                   # past its end a part eases back to its own size (the head on a torso)
_CACHE = {}
_BUSY = [False]


# -----------------------------------------------------------------------------
# the kits
# -----------------------------------------------------------------------------
def load(kit):
    """{part name: {slot, side, parent, pivot, end, V, N, L}} - parents first."""
    if kit in _CACHE:
        return _CACHE[kit]
    with np.load(os.path.join(KIT_DIR, kit + '.npz'), allow_pickle=False) as z:
        meta = json.loads(str(z['meta']))
        raw = {p['name']: dict(p, V=z[p['name'] + '_V'].astype(np.float64), N=np.array(z[p['name'] + '_N']),
                               L=np.array(z[p['name'] + '_L'])) for p in meta['parts']}
    order = []

    def add(n):
        if n in order:
            return
        par = raw[n]['parent']
        if par:
            add(par)
        order.append(n)
    for n in raw:
        add(n)
    _CACHE[kit] = {n: raw[n] for n in order}
    return _CACHE[kit]


def frame(pivot, end):
    """A part's axis (pivot -> end), front (-Y as near as it goes; up for a part pointing forward), side, hinge (the
    turn that takes the axis toward the front) and rest length."""
    X = Vector(end) - Vector(pivot)
    rl = max(X.length, 1e-6)
    X.normalize()
    F = Vector((0.0, -1.0, 0.0))
    F = F - X * F.dot(X)
    if F.length < 0.35:
        F = Vector((0.0, 0.0, 1.0)) - X * X.z
    F.normalize()
    S = F.cross(X).normalized()
    K = X.cross(F).normalized()
    return X, S, F, K, rl


def _smooth(x, lo, hi):
    t = min(max((x - lo) / (hi - lo), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def deform(p, prm, fr):
    """Where a point of a part (its own space, round its pivot) goes - the graph below does the same (the muscle and
    definition aside: they only push the surface)."""
    X, S, F, K, rl = fr
    p = Vector(p)
    a, s, f = p.dot(X), p.dot(S), p.dot(F)
    t = a / rl
    tc = min(max(t, 0.0), 1.0)
    m = _smooth(t, *TIP_ZONE)
    w = prm['w0'] + (prm['w1'] - prm['w0']) * tc
    d = prm['d0'] + (prm['d1'] - prm['d0']) * tc
    w = w + (prm['tip'] - w) * m
    d = d + (prm['tip'] - d) * m
    a2 = min(max(a, 0.0), rl) * prm['length'] + min(a, 0.0) + max(a - rl, 0.0) * prm['tip']
    q = (X * a2 + S * (s * w) + F * (f * d)) * prm['size']
    l3 = rl * prm['length'] * prm['size']
    ca = prm['bend_at'] * l3
    ang = prm['bend'] * _smooth((q.dot(X) - ca) / l3, -BEND_W, BEND_W)
    if ang:
        c = X * ca
        q = c + Quaternion(K, ang) @ (q - c)
    return q, ang


def group():
    """The deform every part wears (its inputs: the part's frame and the sliders)."""
    from .creature_fur import _B, _socket
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.get('mch_v') == GROUP_VERSION:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP, 'GeometryNodeTree')
    else:
        ng.nodes.clear()
        ng.interface.clear()
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    for name, kind, val in (('Axis', 'VECTOR', (0, 0, 1)), ('Side', 'VECTOR', (1, 0, 0)), ('Front', 'VECTOR', (0, -1, 0)),
                            ('Hinge', 'VECTOR', (1, 0, 0)), ('Rest Length', 'FLOAT', 1.0), ('Length', 'FLOAT', 1.0),
                            ('Width 0', 'FLOAT', 1.0), ('Width 1', 'FLOAT', 1.0), ('Depth 0', 'FLOAT', 1.0),
                            ('Depth 1', 'FLOAT', 1.0), ('Tip', 'FLOAT', 1.0), ('Size', 'FLOAT', 1.0),
                            ('Muscle', 'FLOAT', 0.0), ('Definition', 'FLOAT', 0.0), ('Bend', 'FLOAT', 0.0),
                            ('Bend At', 'FLOAT', 0.5)):
        _socket(ng, name, kind, val)
    b = _B(ng)
    gi = b.node('NodeGroupInput')
    go = b.node('NodeGroupOutput')
    I = {s.name: s for s in gi.outputs}

    def smooth(x, lo, hi):
        n = b.node('ShaderNodeMapRange', data_type='FLOAT', interpolation_type='SMOOTHSTEP', clamp=True)
        b.feed(n.inputs[0], x)
        b.feed(n.inputs[1], lo)
        b.feed(n.inputs[2], hi)
        n.inputs[3].default_value = 0.0
        n.inputs[4].default_value = 1.0
        return n.outputs[0]

    pos = b.node('GeometryNodeInputPosition').outputs[0]
    nrm = b.node('GeometryNodeInputNormal').outputs[0]
    blur = b.node('GeometryNodeBlurAttribute', data_type='FLOAT_VECTOR')
    b.feed(blur.inputs['Value'], pos)
    blur.inputs['Iterations'].default_value = 14
    # the sculpted forms (the surface against its blurred self), along the surface's normal only (no sliding)
    detail = b.vec('DOT_PRODUCT', b.vec('SUBTRACT', pos, blur.outputs['Value']), nrm)
    cap = b.math('MULTIPLY', I['Rest Length'], 0.025)                  # (never more than that: no spikes)
    detail = b.math('MINIMUM', b.math('MAXIMUM', detail, b.math('MULTIPLY', cap, -1.0)), cap)
    t0 = b.math('DIVIDE', b.vec('DOT_PRODUCT', pos, I['Axis']), I['Rest Length'])
    ends = b.math('MULTIPLY', smooth(t0, 0.0, 0.18), smooth(t0, 1.0, 0.82))   # (off at the joints: the parts overlap there)
    p0 = b.vec('ADD', pos, b.vec('SCALE', nrm, scale=b.math('MULTIPLY', b.math('MULTIPLY', detail, I['Definition']),
                                                             ends)))
    a = b.vec('DOT_PRODUCT', p0, I['Axis'])
    s = b.vec('DOT_PRODUCT', p0, I['Side'])
    f = b.vec('DOT_PRODUCT', p0, I['Front'])
    rl = I['Rest Length']
    t = b.math('DIVIDE', a, rl)
    tc = b.math('MINIMUM', b.math('MAXIMUM', t, 0.0), 1.0)

    def lerp(x, y, k):
        return b.math('ADD', x, b.math('MULTIPLY', b.math('SUBTRACT', y, x), k))
    m = smooth(t, TIP_ZONE[0], TIP_ZONE[1])
    w = lerp(lerp(I['Width 0'], I['Width 1'], tc), I['Tip'], m)
    d = lerp(lerp(I['Depth 0'], I['Depth 1'], tc), I['Tip'], m)
    a_in = b.math('MINIMUM', b.math('MAXIMUM', a, 0.0), rl)
    a2 = b.math('ADD', b.math('ADD', b.math('MULTIPLY', a_in, I['Length']), b.math('MINIMUM', a, 0.0)),
                b.math('MULTIPLY', b.math('MAXIMUM', b.math('SUBTRACT', a, rl), 0.0), I['Tip']))
    q = b.vec('ADD', b.vec('ADD', b.vec('SCALE', I['Axis'], scale=a2), b.vec('SCALE', I['Side'], scale=b.math(
        'MULTIPLY', s, w))), b.vec('SCALE', I['Front'], scale=b.math('MULTIPLY', f, d)))
    bell = b.math('MULTIPLY', b.math('POWER', b.math('MAXIMUM', b.math('SINE', b.math('MULTIPLY', tc, math.pi)), 0.0),
                                     0.7), b.math('SUBTRACT', 1.0, m))
    bulge = b.math('MULTIPLY', b.math('MULTIPLY', I['Muscle'], b.math('MULTIPLY', rl, MUSCLE_K)), bell)
    q = b.vec('SCALE', b.vec('ADD', q, b.vec('SCALE', nrm, scale=bulge)), scale=I['Size'])
    l3 = b.math('MULTIPLY', b.math('MULTIPLY', rl, I['Length']), I['Size'])
    ca = b.math('MULTIPLY', I['Bend At'], l3)
    k = smooth(b.math('DIVIDE', b.math('SUBTRACT', b.vec('DOT_PRODUCT', q, I['Axis']), ca), l3), -BEND_W, BEND_W)
    rot = b.node('ShaderNodeVectorRotate', rotation_type='AXIS_ANGLE')
    b.feed(rot.inputs['Vector'], q)
    b.feed(rot.inputs['Center'], b.vec('SCALE', I['Axis'], scale=ca))
    b.feed(rot.inputs['Axis'], I['Hinge'])
    b.feed(rot.inputs['Angle'], b.math('MULTIPLY', I['Bend'], k))
    sp = b.node('GeometryNodeSetPosition')
    b.feed(sp.inputs['Geometry'], I['Geometry'])
    b.feed(sp.inputs['Position'], rot.outputs['Vector'])
    b.feed(go.inputs[0], sp.outputs['Geometry'])
    ng['mch_v'] = GROUP_VERSION
    return ng


# -----------------------------------------------------------------------------
# a body in the scene
# -----------------------------------------------------------------------------
def info(ob):
    try:
        return json.loads(ob.get(PART_KEY, ''))
    except (TypeError, ValueError, ReferenceError):
        return None


def is_part(ob):
    return ob is not None and getattr(ob, 'type', '') == 'MESH' and PART_KEY in ob


def root_of(ob):
    while is_part(ob) and is_part(ob.parent):
        ob = ob.parent
    return ob if is_part(ob) else None


def parts_of(root):
    out = []

    def walk(o):
        out.append(o)
        for c in o.children:
            if is_part(c):
                walk(c)
    if root is not None:
        walk(root)
    return out


def active_part(context):
    ob = getattr(context, 'active_object', None)
    return ob if is_part(ob) else None


def twin(ob):
    d = info(ob)
    if not d or not d['side']:
        return None
    other = d['name'][:-1] + ('R' if d['side'] == 'L' else 'L')
    for o in parts_of(root_of(ob)):
        if info(o)['name'] == other:
            return o
    return None


def effective(ob, d, kp):
    pp = ob.mch_bodypart
    slot = d['slot']
    length = pp.length * (kp.legs if slot in LEGS else kp.arms if slot in ARMS else kp.torso if slot == 'Torso' else 1.0)
    g = kp.build if slot in GIRTH else 1.0
    w0 = pp.width * g
    d0 = pp.depth * g
    w1, d1 = w0 * pp.taper, d0 * pp.taper
    if slot == 'Torso':
        w1 *= kp.shoulders
    elif slot == 'Pelvis':
        w0 *= kp.hips
        w1 *= kp.hips
    size = pp.size * (getattr(kp, SIZE_OF[slot]) if slot in SIZE_OF else 1.0)
    tip = kp.head if (slot == 'Torso' and not d.get('has_head')) else 1.0
    return {'length': length, 'w0': w0, 'w1': w1, 'd0': d0, 'd1': d1, 'tip': tip, 'size': size,
            'muscle': pp.muscle + (kp.muscle if slot in GIRTH else 0.0), 'definition': pp.definition + kp.definition,
            'bend': pp.bend, 'bend_at': pp.bend_at}


def _frame_of(d):
    X, S, F, K = (Vector(v) for v in d['frame'][:4])
    return X, S, F, K, d['frame'][4]


def _world(ob):
    """A part's world matrix from its own and its parents' transforms (no depsgraph update needed)."""
    m = ob.matrix_basis.copy()
    o = ob
    while o.parent is not None:
        m = o.parent.matrix_basis @ o.matrix_parent_inverse @ m
        o = o.parent
    return m


def refresh(root):
    """Every part's sliders onto its deform; the parts after each to where its end went; the feet on the ground."""
    if root is None or _BUSY[0]:
        return
    _BUSY[0] = True
    try:
        from .geo_sculpt import set_input
        kp = root.mch_bodykit
        for ob in parts_of(root):
            d = info(ob)
            prm = effective(ob, d, kp)
            fr = _frame_of(d)
            md = ob.modifiers.get(MOD)
            if md is not None and md.node_group is not None:
                for name, key in (('Length', 'length'), ('Width 0', 'w0'), ('Width 1', 'w1'), ('Depth 0', 'd0'),
                                  ('Depth 1', 'd1'), ('Tip', 'tip'), ('Size', 'size'), ('Muscle', 'muscle'),
                                  ('Definition', 'definition'), ('Bend', 'bend'), ('Bend At', 'bend_at')):
                    try:
                        set_input(md, name, float(prm[key]))
                    except (KeyError, TypeError, AttributeError):
                        pass
            for c in ob.children:
                if not is_part(c):
                    continue
                q, ang = deform(Vector(info(c)['rest_loc']), prm, fr)
                if (c.location - q).length > 1e-7:
                    c.location = q
                rot = Quaternion(fr[3], ang).to_euler() if ang else (0.0, 0.0, 0.0)
                if (Vector(c.delta_rotation_euler) - Vector(rot)).length > 1e-7:
                    c.delta_rotation_euler = rot
        h = kp.height
        if (Vector(root.scale) - Vector((h, h, h))).length > 1e-7:
            root.scale = (h, h, h)
        if kp.ground:
            ground(root)
    finally:
        _BUSY[0] = False
    _SURF.clear()
    try:
        from . import muscle_gen as mg
        if any(mg.is_muscle(c) and mg.data(c).get('part_spec') for o in parts_of(root) for c in o.children):
            _refit_later(root)
    except (ImportError, AttributeError):
        pass


def ground(root):
    """The lowest foot on the floor the body was put on."""
    kp = root.mch_bodykit
    low = None
    for ob in parts_of(root):
        d = info(ob)
        if d['slot'] != 'Foot':
            continue
        n = len(ob.data.vertices)
        V = np.empty(n * 3)
        ob.data.vertices.foreach_get('co', V)
        V = V.reshape(-1, 3) * effective(ob, d, kp)['size']
        M = np.array(_world(ob))
        z = (V @ M[2, :3] + M[2, 3]).min()
        low = z if low is None else min(low, z)
    if low is None:
        return
    dz = kp.floor - low
    if abs(dz) > 1e-7:
        root.location.z += dz


def _material(kit):
    name = f'MCH Body {KIT_LABEL[kit]}'
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        try:
            from .muscle_gen import _principled
            col = (0.78, 0.56, 0.47) if kit == 'human' else (0.62, 0.55, 0.5)
            _principled(m, col, 0.55, 0.0, sss=0.08)
        except (ImportError, AttributeError):
            pass
    return m


def _mesh(name, p):
    me = bpy.data.meshes.new(name)
    V, N, L = p['V'], p['N'], p['L']
    me.vertices.add(len(V))
    me.vertices.foreach_set('co', V.astype(np.float32).ravel())
    me.loops.add(len(L))
    me.loops.foreach_set('vertex_index', L.astype(np.int32))
    me.polygons.add(len(N))
    starts = np.concatenate([[0], np.cumsum(N)[:-1]]).astype(np.int32)
    me.polygons.foreach_set('loop_start', starts)
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    try:
        me.shade_smooth()
    except AttributeError:
        me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    return me


def make_kit(context, kit, height=None, location=None):
    """The kit's parts in the scene, their feet at ``location`` (the 3D cursor); the root (pelvis) picked."""
    parts = load(kit)
    st = context.scene.mch_bodykit_new
    height = height if height is not None else st.height
    location = Vector(location if location is not None else context.scene.cursor.location)
    coll = bpy.data.collections.new(COLLECTION)
    context.scene.collection.children.link(coll)
    mat = _material(kit)
    ng = group()
    has_head = any(p['slot'] == 'Head' for p in parts.values())
    obs = {}
    from .geo_sculpt import set_input
    for n, p in parts.items():
        me = _mesh(f'Body {n}', p)
        me.materials.append(mat)
        ob = bpy.data.objects.new(f'Body {n}', me)
        coll.objects.link(ob)
        X, S, F, K, rl = frame(p['pivot'], p['end'])
        par = p['parent']
        rest = (Vector(p['pivot']) - Vector(parts[par]['pivot'])) if par else Vector(p['pivot'])
        ob[PART_KEY] = json.dumps({'kit': kit, 'name': n, 'slot': p['slot'], 'side': p['side'],
                                   'frame': [list(X), list(S), list(F), list(K), rl], 'rest_loc': list(rest),
                                   'has_head': has_head, 'variant': f'{kit}:{n}'})
        if par:
            ob.parent = obs[par]
            ob.matrix_parent_inverse = Matrix.Identity(4)
            ob.location = rest
        else:
            ob.location = location + Vector(p['pivot']) * height
        md = ob.modifiers.new(MOD, 'NODES')
        md.node_group = ng
        for name, v in (('Axis', X), ('Side', S), ('Front', F), ('Hinge', K)):
            set_input(md, name, tuple(v))
        set_input(md, 'Rest Length', float(rl))
        obs[n] = ob
    root = next(iter(obs.values()))
    _BUSY[0] = True
    try:
        kp = root.mch_bodykit
        kp.height = height
        kp.floor = location.z
    finally:
        _BUSY[0] = False
    refresh(root)
    for o in context.selected_objects:
        o.select_set(False)
    root.select_set(True)
    context.view_layer.objects.active = root
    return root


# -----------------------------------------------------------------------------
# swapping a part
# -----------------------------------------------------------------------------
def my_dir():
    if MY_DIR[0]:
        return MY_DIR[0]
    return os.path.join(bpy.utils.user_resource('CONFIG', path='mecha_lab', create=False), 'body_parts')


def my_parts(slot):
    d = os.path.join(my_dir(), slot)
    try:
        return sorted(f[:-4] for f in os.listdir(d) if f.endswith('.npz'))
    except OSError:
        return []


def variants(slot):
    """The parts that can go in a slot: (id, label) - both kits' and yours."""
    out = []
    for kit, label, _d in KITS:
        try:
            names = [n for n, p in load(kit).items() if p['slot'] == slot and p['side'] in ('', 'L')]
        except (OSError, KeyError, ValueError):
            continue
        for n in names:
            out.append((f'{kit}:{n}', f'{label} {SLOT_LABEL[slot]}'))
    for n in my_parts(slot):
        out.append((f'mine:{n}', f'My {n}'))
    return out


def _local(V, fr):
    """Points in a part's space as (along / its length, side, front) / its length."""
    X, S, F, K, rl = fr
    M = np.array([list(X), list(S), list(F)])
    return (V @ M.T) / rl


def _place(A, fr):
    X, S, F, K, rl = fr
    M = np.array([list(X), list(S), list(F)])
    return (A * rl) @ M


def swap(ob, vid):
    """Put a variant in a part's place: its length to the part's, along the part's axis (mirrored for the other
    side)."""
    d = info(ob)
    fr = _frame_of(d)
    if vid.startswith('mine:'):
        path = os.path.join(my_dir(), d['slot'], vid[5:] + '.npz')
        with np.load(path, allow_pickle=False) as z:
            A, N, L = z['A'].astype(np.float64), np.array(z['N']), np.array(z['L'])
            side = str(z['side']) if 'side' in z else ''
    else:
        kit, n = vid.split(':', 1)
        p = load(kit)[n]
        if d['side'] and p['side'] and p['side'] != d['side']:
            n = n[:-1] + d['side']
            p = load(kit).get(n, p)
        A = _local(p['V'], frame(p['pivot'], p['end']))
        N, L, side = p['N'], p['L'], p['side']
    if side and d['side'] and side != d['side']:
        A = A * (1.0, -1.0, 1.0)                    # (the side axis points the same way on both sides)
        L = _flip(N, L)
    V = _place(A, fr)
    old = ob.data
    me = _mesh(old.name, {'V': V, 'N': N, 'L': L})
    for m in old.materials:
        me.materials.append(m)
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    d['variant'] = vid
    ob[PART_KEY] = json.dumps(d)


def _flip(N, L):
    """Faces turned round (a mirrored part keeps its outside out)."""
    out = np.empty_like(L)
    i = 0
    for k in N:
        out[i:i + k] = L[i:i + k][::-1]
        i += k
    return out


def save_mine(ob, src, name):
    """``src`` (a mesh placed over the part ``ob``) kept as your own part for its slot."""
    d = info(ob)
    me = src.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    try:
        M = np.array(_world(ob).inverted() @ src.matrix_world)
        V = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', V)
        V = V.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        N = np.array([len(p.vertices) for p in me.polygons], np.int32)
        L = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get('vertex_index', L)
    finally:
        src.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
    A = _local(V, _frame_of(d))
    folder = os.path.join(my_dir(), d['slot'])
    os.makedirs(folder, exist_ok=True)
    safe = ''.join(c for c in name if c.isalnum() or c in ' _-').strip() or 'Part'
    np.savez_compressed(os.path.join(folder, safe + '.npz'), A=A.astype(np.float32), N=N, L=L,
                        side=np.array(d['side']))
    return safe


def join(context, root, remesh=False, voxel=0.006):
    """The parts as one mesh (the kit hidden, kept): its sliders applied; Remesh: fused into one skin."""
    dg = context.evaluated_depsgraph_get()
    import bmesh
    bm = bmesh.new()
    for ob in parts_of(root):
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
        me.transform(ob.matrix_world)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new('Body')
    bm.to_mesh(me)
    bm.free()
    out = bpy.data.objects.new('Body', me)
    (root.users_collection[0] if root.users_collection else context.scene.collection).objects.link(out)
    skin = root.data.materials[0] if root.data.materials else _material('human')
    me.materials.append(skin)
    if remesh:
        md = out.modifiers.new('Remesh', 'REMESH')
        md.mode = 'VOXEL'
        md.voxel_size = voxel * root.mch_bodykit.height
        dg = context.evaluated_depsgraph_get()
        me2 = bpy.data.meshes.new_from_object(out.evaluated_get(dg), depsgraph=dg)
        out.modifiers.remove(md)
        out.data = me2
        bpy.data.meshes.remove(me)
        if not me2.materials:
            me2.materials.append(skin)
    try:
        out.data.shade_smooth()
    except AttributeError:
        pass
    for ob in parts_of(root):
        ob.hide_set(True)
        ob.hide_render = True
    for o in context.selected_objects:
        o.select_set(False)
    out.select_set(True)
    context.view_layer.objects.active = out
    return out


# -----------------------------------------------------------------------------
# muscles on a part (user: "둘 다" - the kit, and a part's muscles put on it with a click)
# -----------------------------------------------------------------------------
# each muscle: (Muscle preset, its points [(part, along 0 .. 1 from the joint, round it: 0 front, 90 outside, 180 back,
# -90 inside)], its sliders) - part 'self' or another slot on the same side; a torso / pelvis muscle made on each side
_F, _B_, _O, _I = 0, 180, 90, -90
PART_SETS = {
    'Thigh': (('Quads', 'QUAD', (('self', 0.1, 8), ('self', 0.96, 0)), {'width': 1.5, 'thickness': 1.2}),
              ('Hamstrings', 'HAMSTRING', (('self', 0.12, 178), ('self', 0.92, 182)), {'width': 1.4}),
              ('Inner', 'SPINDLE', (('self', 0.06, -95), ('self', 0.78, -55)), {'width': 1.6}),
              ('Outer', 'SPINDLE', (('self', 0.1, 95), ('self', 0.95, 85)), {'width': 1.4})),
    'Shin': (('Calf', 'CALF', (('self', 0.04, 180), ('self', 0.72, 180)), {'width': 1.4, 'thickness': 1.3}),
             ('Front', 'SPINDLE', (('self', 0.06, 18), ('self', 0.86, 10)), {'width': 1.2}),
             ('Outer', 'SPINDLE', (('self', 0.08, 100), ('self', 0.82, 125)), {})),
    'UpperArm': (('Biceps', 'BICEPS', (('self', 0.18, 0), ('self', 0.94, 6)), {'width': 1.3, 'thickness': 1.2}),
                 ('Triceps', 'TRICEPS', (('self', 0.08, 180), ('self', 0.96, 180)), {'width': 1.4}),
                 ('Shoulder', 'DELTOID', (('self', -0.02, 25), ('self', -0.02, 160), ('self', 0.48, 95)), {})),
    'Forearm': (('Flexors', 'FOREARM', (('self', 0.04, -35), ('self', 0.8, -10)), {'width': 1.3}),
                ('Extensors', 'FOREARM', (('self', 0.04, 150), ('self', 0.8, 170)), {'width': 1.3}),
                ('Top', 'SPINDLE', (('self', -0.02, 75), ('self', 0.7, 55)), {})),
    'Arm': (('Biceps', 'BICEPS', (('self', 0.08, 0), ('self', 0.47, 4)), {'width': 1.3, 'thickness': 1.2}),
            ('Triceps', 'TRICEPS', (('self', 0.05, 180), ('self', 0.5, 180)), {'width': 1.4}),
            ('Shoulder', 'DELTOID', (('self', -0.01, 25), ('self', -0.01, 160), ('self', 0.25, 95)), {}),
            ('Forearm', 'FOREARM', (('self', 0.53, -30), ('self', 0.95, -10)), {'width': 1.3}),
            ('Back of Forearm', 'FOREARM', (('self', 0.53, 150), ('self', 0.95, 170)), {'width': 1.3})),
    'Torso': (('Chest', 'PEC', (('self', 0.92, 6), ('self', 0.38, 6), ('arm', 0.16, 30)), {'thickness': 1.3}),
              ('Abs', 'ABS', (('self', 0.55, 0), ('self', 0.04, 0)), {}),
              ('Lats', 'LAT', (('self', 0.18, 150), ('self', 0.62, 176), ('arm', 0.1, 150)), {}),
              ('Traps', 'TRAP', (('self', 1.04, 178), ('self', 0.5, 179), ('arm', -0.02, 120)), {})),
    'Pelvis': (('Glutes', 'GLUTE', (('self', 1.1, 125), ('self', 0.15, 172), ('thigh', 0.22, 125)), {'thickness': 1.4}),),
}
CENTRED = {'Torso', 'Pelvis'}


def part_sets(slot):
    """The muscles that go on a part: [(id, label)] - 'ALL' first."""
    sets = PART_SETS.get(slot, ())
    return ([('ALL', 'All')] if len(sets) > 1 else []) + [(m[0], m[0]) for m in sets]


def _kit_part(root, slot, side):
    for o in parts_of(root):
        d = info(o)
        if d['slot'] == slot and d['side'] == side:
            return o
    return None


def surface_point(context, ob, t, ang, sgn=1.0):
    """The outside of part ``ob`` at ``t`` along it and ``ang`` round it (degrees; ``sgn`` -1: the other side's
    way round): (world point, world normal) - the ray from outside in, so the skin, not what is inside."""
    from mathutils.bvhtree import BVHTree
    d = info(ob)
    X, S, F, K, rl = _frame_of(d)
    kp = root_of(ob).mch_bodykit
    prm = effective(ob, d, kp)
    a = X * (t * rl * prm['length'] * prm['size'])
    side = 1.0 if d['side'] != 'R' else -1.0
    r = math.radians(ang)
    dirn = (F * math.cos(r) + S * (math.sin(r) * side * sgn)).normalized()
    key = (ob.name, round(prm['length'], 5), round(prm['w0'], 5), round(prm['w1'], 5), round(prm['muscle'], 5),
           round(prm['size'], 5), round(prm['d0'], 5), round(prm['d1'], 5), round(prm['definition'], 5))
    hit = _SURF.get(ob.name)
    if hit is None or hit[0] != key:
        dg = context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            V = [v.co.copy() for v in me.vertices]
            T = [tuple(p.vertices) for p in me.polygons]
        finally:
            ev.to_mesh_clear()
        hit = (key, BVHTree.FromPolygons(V, T))
        _SURF[ob.name] = hit
    bvh = hit[1]
    far = a + dirn * (rl * 3.0)
    loc, nrm, _i, _d = bvh.ray_cast(far, -dirn, rl * 3.0)
    if loc is None:
        loc, nrm, _i, _d = bvh.find_nearest(a + dirn * rl * 0.3)
    if loc is None:
        return None
    M = _world(ob)
    return M @ loc, (M.to_3x3().inverted().transposed() @ nrm).normalized()


_SURF = {}


def muscle_points(context, part, spec, sgn=1.0):
    """[(object name, world point, world normal)] of one muscle's points on the kit."""
    root = root_of(part)
    d = info(part)
    side = d['side'] or ('L' if sgn > 0 else 'R')
    out = []
    for where, t, ang in spec:
        ob = part
        if where == 'arm':
            ob = _kit_part(root, 'UpperArm', side) or _kit_part(root, 'Arm', side)
        elif where == 'thigh':
            ob = _kit_part(root, 'Thigh', side)
        if ob is None:
            return None
        s = sgn if info(ob)['side'] == '' else 1.0
        hit = surface_point(context, ob, t, ang, s)
        if hit is None:
            return None
        out.append((ob.name, tuple(hit[0]), tuple(hit[1])))
    return out


def put_muscles(context, part, which='ALL'):
    """The part's muscles (the picked one / all) made with the Muscle tool's presets, on the kit - each its own
    object, its own sliders; they know where on the part they go (moved with its sliders)."""
    from . import muscle_gen as mg
    d = info(part)
    sets = PART_SETS.get(d['slot'], ())
    st = context.scene.mch_muscle
    keep = {k: getattr(st, k) for k in ('preset', 'width', 'thickness', 'shape', 'sculpt', 'style')}
    made = []
    try:
        for label, preset, spec, vals in sets:
            if which not in ('ALL', label):
                continue
            sides = (1.0, -1.0) if d['slot'] in CENTRED and preset != 'ABS' else (1.0,)
            for sgn in sides:
                pts = muscle_points(context, part, spec, sgn)
                if pts is None:
                    continue
                st.style = 'CREATURE'
                st.shape = 'SCULPT'
                st.sculpt = 'AUTO'
                st.preset = preset
                for k, v in vals.items():
                    setattr(st, k, v)
                ob, _msg = mg.make(context, 'MUSCLE', pts)
                side = d['side'] or ('L' if sgn > 0 else 'R')
                ob.name = (f'{label}.{side}' if d['slot'] in CENTRED and preset != 'ABS' else
                           f'{SLOT_LABEL[d["slot"]]} {label}' + (f'.{d["side"]}' if d['side'] else ''))
                md = mg.data(ob)
                md['part_spec'] = {'part': part.name, 'spec': [list(x) for x in spec], 'sgn': sgn}
                ob[mg.KEY] = json.dumps(md)
                made.append(ob)
    finally:
        for k, v in keep.items():
            try:
                setattr(st, k, v)
            except (TypeError, AttributeError):
                pass
    return made


_REFIT = {'roots': set()}


def _refit_later(root):
    """The muscles on a kit put again where their points went (after its sliders stop moving)."""
    _REFIT['roots'].add(root.name)
    if not bpy.app.timers.is_registered(_refit_now):
        bpy.app.timers.register(_refit_now, first_interval=0.4)


def _refit_now():
    from . import muscle_gen as mg
    names = set(_REFIT['roots'])
    _REFIT['roots'].clear()
    ctx = bpy.context
    for o in list(bpy.data.objects):
        if not mg.is_muscle(o):
            continue
        md = mg.data(o)
        ps = md.get('part_spec')
        if not ps:
            continue
        part = bpy.data.objects.get(ps['part'])
        root = root_of(part) if part is not None else None
        if root is None or root.name not in names:
            continue
        try:
            refit(ctx, o)
        except (RuntimeError, ValueError, KeyError) as ex:
            print('Body Kit muscles:', ex)
    return None


def refit(context, mob):
    """One kit muscle's points from where its part is now; laid again."""
    from . import muscle_gen as mg
    md = mg.data(mob)
    ps = md['part_spec']
    part = bpy.data.objects[ps['part']]
    pts = muscle_points(context, part, [tuple(x) for x in ps['spec']], ps['sgn'])
    if pts is None:
        return
    body = bpy.data.objects.get(md['body'])
    inv = body.matrix_world.inverted()
    R = inv.to_3x3()
    md['pts'] = [list(inv @ Vector(p)) for _n, p, _q in pts]
    md['nrm'] = [list((R @ Vector(q)).normalized()) for _n, _p, q in pts]
    md.pop('paths', None)
    md.pop('sheet', None)
    mob[mg.KEY] = json.dumps(md)
    mg._BVH.clear()
    mg.build(mob, context)


# -----------------------------------------------------------------------------
# settings
# -----------------------------------------------------------------------------
def _upd_kit(self, context):
    if _BUSY[0]:
        return
    refresh(root_of(self.id_data))


SYM_KEYS = ('length', 'width', 'depth', 'taper', 'size', 'muscle', 'definition', 'bend', 'bend_at')


def _upd_part(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    root = root_of(ob)
    if root is not None and root.mch_bodykit.symmetry:
        tw = twin(ob)
        if tw is not None:
            _BUSY[0] = True
            try:
                for k in SYM_KEYS:
                    setattr(tw.mch_bodypart, k, getattr(self, k))
            finally:
                _BUSY[0] = False
    refresh(root)


def _f(name, default, lo, hi, desc, update=_upd_kit, soft=None):
    kw = {'name': name, 'default': default, 'min': lo, 'max': hi, 'description': desc, 'update': update}
    if soft:
        kw['soft_min'], kw['soft_max'] = soft
    return FloatProperty(**kw)


class MCH_PG_BodyKit(bpy.types.PropertyGroup):
    """The whole body (on its root, the pelvis)."""
    height: FloatProperty(name='Height', default=1.8, min=0.05, max=100.0, soft_max=10.0, unit='LENGTH',
                          update=_upd_kit, description='How tall the body stands')
    legs: _f('Legs', 1.0, 0.3, 3.0, 'Leg length (thighs and shins)', soft=(0.5, 1.8))
    arms: _f('Arms', 1.0, 0.3, 3.0, 'Arm length', soft=(0.5, 1.8))
    torso: _f('Torso', 1.0, 0.3, 3.0, 'Torso length', soft=(0.6, 1.6))
    shoulders: _f('Shoulders', 1.0, 0.3, 3.0, 'Shoulder width (the arms move with them)', soft=(0.6, 1.8))
    hips: _f('Hips', 1.0, 0.3, 3.0, 'Hip width (the legs move with them)', soft=(0.6, 1.8))
    build: _f('Build', 1.0, 0.3, 3.0, 'Slim to heavy: the torso, the pelvis and the limbs thicker or thinner',
              soft=(0.6, 1.6))
    muscle: _f('Muscle', 0.0, -2.0, 4.0, 'The bellies of the torso and the limbs fuller', soft=(-1.0, 2.0))
    definition: _f('Definition', 0.0, -1.0, 3.0, 'The sculpted muscles sharper (minus: softer)', soft=(-0.5, 1.5))
    head: _f('Head', 1.0, 0.3, 3.0, 'Head size', soft=(0.6, 1.6))
    hands: _f('Hands', 1.0, 0.3, 3.0, 'Hand size', soft=(0.6, 1.6))
    feet: _f('Feet', 1.0, 0.3, 3.0, 'Foot size', soft=(0.6, 1.6))
    symmetry: BoolProperty(name='Symmetry', default=True,
                           description='A part\'s sliders on the other side too (left and right the same)')
    ground: BoolProperty(name='Feet on Ground', default=True, update=_upd_kit,
                         description='The lowest foot kept on the floor the body was put on (longer legs: taller)')
    floor: FloatProperty(name='Floor', default=0.0, update=_upd_kit, unit='LENGTH',
                         description='Where the feet stand')


class MCH_PG_BodyPart(bpy.types.PropertyGroup):
    """One part."""
    length: _f('Length', 1.0, 0.2, 4.0, 'Longer along its axis (the parts after it move to its end)',
               update=_upd_part, soft=(0.4, 2.0))
    width: _f('Width', 1.0, 0.2, 4.0, 'Side to side', update=_upd_part, soft=(0.4, 2.0))
    depth: _f('Depth', 1.0, 0.2, 4.0, 'Front to back', update=_upd_part, soft=(0.4, 2.0))
    taper: _f('Taper', 1.0, 0.2, 4.0, 'Its end thicker or thinner than its start', update=_upd_part, soft=(0.4, 2.0))
    size: _f('Size', 1.0, 0.2, 4.0, 'The whole part bigger or smaller', update=_upd_part, soft=(0.4, 2.0))
    muscle: _f('Muscle', 0.0, -2.0, 4.0, 'Its belly fuller', update=_upd_part, soft=(-1.0, 2.0))
    definition: _f('Definition', 0.0, -1.0, 3.0, 'Its sculpted muscles sharper', update=_upd_part, soft=(-0.5, 1.5))
    bend: FloatProperty(name='Bend', default=0.0, min=-math.pi, max=math.pi, subtype='ANGLE', update=_upd_part,
                        description='Bent along its length (an elbow in one-piece arms); the parts after it follow')
    bend_at: _f('Bend At', 0.5, 0.05, 0.95, 'Where along it it bends', update=_upd_part)


class MCH_PG_BodyKitNew(bpy.types.PropertyGroup):
    kit: EnumProperty(name='Body', items=[(k, l, d) for k, l, d in KITS], default='human')
    height: FloatProperty(name='Height', default=1.8, min=0.05, max=100.0, soft_max=10.0, unit='LENGTH',
                          description='How tall the new body stands')


# -----------------------------------------------------------------------------
# operators
# -----------------------------------------------------------------------------
class MCH_OT_bodykit_add(bpy.types.Operator):
    bl_idname = 'mch.bodykit_add'
    bl_label = 'Add Body'
    bl_description = 'The body picked, its parts each a mesh of its own, standing on the 3D cursor'
    bl_options = {'REGISTER', 'UNDO'}
    kit: StringProperty(default='')

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        kit = self.kit or context.scene.mch_bodykit_new.kit
        try:
            root = make_kit(context, kit)
        except (OSError, KeyError, ValueError) as e:
            self.report({'ERROR'}, f'Body Kit: {e}')
            return {'CANCELLED'}
        self.report({'INFO'}, f'{KIT_LABEL[kit]} body: {len(parts_of(root))} parts - pick one to shape it, R turns '
                              'it at its joint')
        return {'FINISHED'}


class MCH_OT_bodykit_pick(bpy.types.Operator):
    bl_idname = 'mch.bodykit_pick'
    bl_label = 'Body'
    bl_description = 'The body the next Add Body makes'
    bl_options = {'INTERNAL'}
    kit: StringProperty(default='human')

    def execute(self, context):
        context.scene.mch_bodykit_new.kit = self.kit
        return {'FINISHED'}


class MCH_OT_bodykit_reset(bpy.types.Operator):
    bl_idname = 'mch.bodykit_reset'
    bl_label = 'Reset'
    bl_description = 'Back to the body as sculpted (Shape: the whole body\'s sliders; Part: this part\'s; Pose: every '
    bl_options = {'REGISTER', 'UNDO'}
    what: EnumProperty(items=(('SHAPE', 'Shape', ''), ('PART', 'Part', ''), ('POSE', 'Pose', '')))

    @classmethod
    def poll(cls, context):
        return active_part(context) is not None

    def execute(self, context):
        ob = active_part(context)
        root = root_of(ob)
        _BUSY[0] = True
        try:
            if self.what == 'SHAPE':
                kp = root.mch_bodykit
                for k in ('legs', 'arms', 'torso', 'shoulders', 'hips', 'build', 'head', 'hands', 'feet'):
                    setattr(kp, k, 1.0)
                kp.muscle = kp.definition = 0.0
            elif self.what == 'PART':
                for o in [ob] + ([twin(ob)] if root.mch_bodykit.symmetry and twin(ob) else []):
                    pp = o.mch_bodypart
                    for k in ('length', 'width', 'depth', 'taper', 'size'):
                        setattr(pp, k, 1.0)
                    pp.muscle = pp.definition = pp.bend = 0.0
                    pp.bend_at = 0.5
            else:
                for o in parts_of(root):
                    o.rotation_euler = (0.0, 0.0, 0.0)
        finally:
            _BUSY[0] = False
        refresh(root)
        return {'FINISHED'}


MCH_OT_bodykit_reset.bl_description += 'part\'s turn)'


class MCH_OT_bodykit_mirror_pose(bpy.types.Operator):
    bl_idname = 'mch.bodykit_mirror_pose'
    bl_label = 'Mirror Pose'
    bl_description = 'The picked side\'s pose onto the other side (the parts you picked, or that whole side)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_part(context) is not None

    def execute(self, context):
        ob = active_part(context)
        root = root_of(ob)
        side = info(ob)['side'] or 'L'
        src = [o for o in parts_of(root) if info(o)['side'] == side]
        n = 0
        for o in src:
            tw = twin(o)
            if tw is None:
                continue
            e = o.rotation_euler
            tw.rotation_mode = o.rotation_mode
            tw.rotation_euler = (e.x, -e.y, -e.z)
            n += 1
        refresh(root)
        self.report({'INFO'}, f'Mirror Pose: {n} parts, {"left" if side == "L" else "right"} onto '
                              f'{"right" if side == "L" else "left"}')
        return {'FINISHED'}


def _variant_items(self, context):
    ob = active_part(context)
    if ob is None:
        return [('NONE', 'No part picked', '')]
    items = [(vid, label, f'This part made the {label}') for vid, label in variants(info(ob)['slot'])]
    _ITEMS[:] = items or [('NONE', 'Nothing for this part', '')]
    return _ITEMS


_ITEMS = []


class MCH_OT_bodykit_swap(bpy.types.Operator):
    bl_idname = 'mch.bodykit_swap'
    bl_label = 'Swap Part'
    bl_description = ('This part swapped for the other body\'s or for one of yours (its length to this one\'s, the '
                      'sliders kept)')
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = 'variant'
    variant: EnumProperty(name='Part', items=_variant_items)

    @classmethod
    def poll(cls, context):
        return active_part(context) is not None

    def execute(self, context):
        ob = active_part(context)
        if self.variant == 'NONE':
            return {'CANCELLED'}
        root = root_of(ob)
        done = [ob]
        swap(ob, self.variant)
        tw = twin(ob)
        if root.mch_bodykit.symmetry and tw is not None:
            swap(tw, self.variant)
            done.append(tw)
        refresh(root)
        self.report({'INFO'}, f'Swapped: {", ".join(info(o)["name"] for o in done)}')
        return {'FINISHED'}


class MCH_OT_bodykit_use_mesh(bpy.types.Operator):
    bl_idname = 'mch.bodykit_use_mesh'
    bl_label = 'Use Selected Mesh as This Part'
    bl_description = ('Your mesh (placed over the part, selected with it - the part last) takes the part\'s place '
                      'and moves with it from now on; Save: kept as your own part too')
    bl_options = {'REGISTER', 'UNDO'}
    save: BoolProperty(name='Save as My Part', default=True)
    name: StringProperty(name='Name', default='My Part')

    @classmethod
    def poll(cls, context):
        ob = active_part(context)
        return ob is not None and any(o.type == 'MESH' and o is not ob and not is_part(o)
                                      for o in context.selected_objects)

    def invoke(self, context, event):
        src = next(o for o in context.selected_objects if o.type == 'MESH' and not is_part(o))
        self.name = src.name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        ob = active_part(context)
        src = next(o for o in context.selected_objects if o.type == 'MESH' and o is not ob and not is_part(o))
        old = MY_DIR[0]
        tmp = None
        if not self.save:                           # (still through the library format, in a scratch folder)
            import tempfile
            tmp = tempfile.mkdtemp()
            MY_DIR[0] = tmp
        try:
            name = save_mine(ob, src, self.name)
            swap(ob, 'mine:' + name)
        finally:
            if tmp:
                MY_DIR[0] = old
        src.hide_set(True)
        refresh(root_of(ob))
        context.view_layer.objects.active = ob
        self.report({'INFO'}, f'{info(ob)["name"]}: your mesh "{name}"' + (' (saved as your part)' if self.save else ''))
        return {'FINISHED'}


class MCH_OT_bodykit_muscles(bpy.types.Operator):
    bl_idname = 'mch.bodykit_muscles'
    bl_label = 'Muscles on This Part'
    bl_description = ('The part\'s muscles (your sculpted shapes) put on it - each its own object with its own '
                      'sliders (the Muscle window); the torso\'s and pelvis\' on both sides')
    bl_options = {'REGISTER', 'UNDO'}
    which: StringProperty(default='ALL')

    @classmethod
    def poll(cls, context):
        ob = active_part(context)
        return ob is not None and info(ob)['slot'] in PART_SETS

    def execute(self, context):
        part = active_part(context)
        tw = twin(part)
        root = root_of(part)
        targets = [part] + ([tw] if tw is not None and root.mch_bodykit.symmetry else [])
        made = []
        for p_ in targets:
            made += put_muscles(context, p_, self.which)
        for o in context.selected_objects:
            o.select_set(False)
        part.select_set(True)
        context.view_layer.objects.active = part
        self.report({'INFO'} if made else {'WARNING'},
                    f'{len(made)} muscles: {", ".join(o.name for o in made)}' if made else 'No muscle could be put')
        return {'FINISHED'} if made else {'CANCELLED'}


class MCH_OT_bodykit_join(bpy.types.Operator):
    bl_idname = 'mch.bodykit_join'
    bl_label = 'Join to One Mesh'
    bl_description = 'The body\'s parts as one mesh, as shaped and posed (the kit hidden, kept); Remesh: fused, to sculpt'
    bl_options = {'REGISTER', 'UNDO'}
    remesh: BoolProperty(name='Remesh (fuse)', default=False)

    @classmethod
    def poll(cls, context):
        return active_part(context) is not None

    def execute(self, context):
        out = join(context, root_of(active_part(context)), self.remesh)
        self.report({'INFO'}, f'{out.name}: {len(out.data.polygons)} faces')
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# the window
# -----------------------------------------------------------------------------
def draw(layout, context):
    from . import panel_capture as pc
    st = context.scene.mch_bodykit_new
    entries = []
    for kid, label, _d in KITS:
        path, icon = pc.thumb('bodykit', kid)
        entries.append((label, path, icon, st.kit == kid, 'mch.bodykit_pick', {'kit': kid}))
    pc.tiles(layout, entries, columns=2, scale=4.0)
    row = layout.row(align=True)
    row.prop(st, 'height')
    row.operator('mch.bodykit_add', text='Add Body', icon='ADD')
    ob = active_part(context)
    if ob is None:
        layout.label(text='Pick a body part to shape it')
        return
    root = root_of(ob)
    kp = root.mch_bodykit
    d = info(ob)
    col = layout.column(align=True)
    col.label(text=f'Body Shape ({KIT_LABEL.get(d["kit"], d["kit"])})')
    col.prop(kp, 'height')
    for k in ('legs', 'arms', 'torso', 'shoulders', 'hips', 'build', 'muscle', 'definition', 'head', 'hands', 'feet'):
        col.prop(kp, k, slider=True)
    row = layout.row(align=True)
    row.prop(kp, 'symmetry', toggle=True, icon='MOD_MIRROR')
    row.prop(kp, 'ground', toggle=True, icon='SNAP_FACE')
    row.operator('mch.bodykit_reset', text='Reset Shape').what = 'SHAPE'
    pp = ob.mch_bodypart
    side = {'L': ' (left)', 'R': ' (right)'}.get(d['side'], '')
    col = layout.column(align=True)
    col.label(text=f'Part: {SLOT_LABEL[d["slot"]]}{side}')
    for k in ('length', 'width', 'depth', 'taper', 'size', 'muscle', 'definition'):
        col.prop(pp, k, slider=True)
    row = col.row(align=True)
    row.prop(pp, 'bend')
    row.prop(pp, 'bend_at', slider=True)
    layout.operator('mch.bodykit_reset', text='Reset Part').what = 'PART'
    col = layout.column(align=True)
    col.label(text='Pose: R turns the part at its joint')
    row = col.row(align=True)
    row.operator('mch.bodykit_mirror_pose', icon='MOD_MIRROR')
    row.operator('mch.bodykit_reset', text='Reset Pose').what = 'POSE'
    col = layout.column(align=True)
    col.label(text='Swap')
    col.operator_menu_enum('mch.bodykit_swap', 'variant', text='Swap Part', icon='FILE_REFRESH')
    col.operator('mch.bodykit_use_mesh', icon='IMPORT')
    sets = part_sets(d['slot'])
    if sets:
        col = layout.column(align=True)
        col.label(text='Muscles on this part (your sculpts)')
        g = col.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
        for sid, label in sets:
            g.operator('mch.bodykit_muscles', text=label).which = sid
        col.operator('mch.muscle_skin', text='Skin Over All', icon='MOD_SKIN').look = 'CREATURE'
    row = layout.row(align=True)
    row.operator('mch.bodykit_join', icon='OBJECT_DATA').remesh = False
    row.operator('mch.bodykit_join', text='Join + Remesh').remesh = True


HELP = ('Pick Human or Creature, Add Body: its parts stand on the 3D cursor',
        'Body Shape: height, legs, arms, shoulders, build ...; Part: the one picked (the other side too)',
        'R turns a part at its joint; Mirror Pose; Join to One Mesh when done')


class MCH_TOOL_body_kit(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.body_kit'
    bl_label = 'Body Kit'
    bl_description = ('A body made of parts (Human / Creature): shape it with sliders (legs, arms, build ...), each '
                      'part on its own, turn the parts at their joints')
    bl_icon = 'ops.generic.select'
    bl_widget = None
    bl_keymap = (('view3d.select', {'type': 'LEFTMOUSE', 'value': 'CLICK'}, None),
                 ('view3d.select', {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': True},
                  {'properties': [('toggle', True)]}))

    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return


CLASSES = (MCH_PG_BodyKit, MCH_PG_BodyPart, MCH_PG_BodyKitNew, MCH_OT_bodykit_add, MCH_OT_bodykit_pick,
           MCH_OT_bodykit_reset, MCH_OT_bodykit_mirror_pose, MCH_OT_bodykit_swap, MCH_OT_bodykit_use_mesh,
           MCH_OT_bodykit_muscles, MCH_OT_bodykit_join)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_bodykit = PointerProperty(type=MCH_PG_BodyKit)
    bpy.types.Object.mch_bodypart = PointerProperty(type=MCH_PG_BodyPart)
    bpy.types.Scene.mch_bodykit_new = PointerProperty(type=MCH_PG_BodyKitNew)
    try:
        bpy.utils.register_tool(MCH_TOOL_body_kit, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_body_kit)
    except (ValueError, RuntimeError, KeyError):
        pass
    for T, attr in ((bpy.types.Object, 'mch_bodykit'), (bpy.types.Object, 'mch_bodypart'),
                    (bpy.types.Scene, 'mch_bodykit_new')):
        if hasattr(T, attr):
            delattr(T, attr)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
