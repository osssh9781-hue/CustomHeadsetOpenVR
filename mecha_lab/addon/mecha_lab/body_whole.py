"""0.24.186 One-piece body (user: "그전에 보냈던 붙어 있는 모델로 만들어 줘, 이건 예시 모델이잖아" - after "다즈 스튜디오처럼 ...
슬라이더로 조절하고 크기 키우고 관절도 꺾어서 자세 잡고"): the user's whole human body as ONE mesh on bones - its skin
bends at the joints (no seams between parts), the same sliders as the Body Kit:

* Body Size (scaled, not fattened): Height, Head, Arms Size, Hands, Legs Size, Feet; Proportions: Legs, Arms, Torso,
  Build - the feet kept on the floor.
* The joint picked (a list): Scale (it and all after it), Length, Width, Bend / Twist / Side - the other side the same.
* Poses (the Body Kit's) and your own saved ones.

The bones are the part-split human kit's joints (the same sculpt) - and a neck under the head, a shoulder (collarbone)
before each upper arm; each point follows the bones nearest it (weights
worked out here - no operators), smoothed over the mesh so the skin bends softly.  Everything is live (an Armature
modifier and the bones' pose); Apply: Blender's own (the Armature modifier).
"""
from __future__ import annotations

import json
import math
import os

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty
from mathutils import Matrix, Quaternion, Vector

DIR = os.path.join(os.path.dirname(__file__), 'body_kits')
KEY = 'mch_bodywhole'                    # on the body mesh and its bones object: json {'rig': name, 'body': name}
ARM_MOD = 'MCH Body Bones'
# (bone, slot, parent, from, to) - "from" / "to": a kit part's pivot / end, a midpoint, or a point
BONES = (('Pelvis', 'Pelvis', None), ('Waist', 'Waist', 'Pelvis'), ('Chest', 'Chest', 'Waist'),   # (user: "허리도 두 단계로")
         ('Neck', 'Neck', 'Chest'), ('Head', 'Head', 'Neck'), ('Shoulder', 'Shoulder', 'Chest'),           # 0.24.187 (user: "머리랑 목도 나눠 주고 어깨랑 윗팔도 나눠 주라")
         ('UpperArm', 'UpperArm', 'Shoulder'), ('Forearm', 'Forearm', 'UpperArm'), ('Hand', 'Hand', 'Forearm'),
         ('Thigh', 'Thigh', 'Pelvis'), ('Shin', 'Shin', 'Thigh'), ('Foot', 'Foot', 'Shin'))
SIDED = {'Shoulder', 'UpperArm', 'Forearm', 'Hand', 'Thigh', 'Shin', 'Foot'}
WAIST_AT = 0.45                          # where the waist ends and the chest starts (share of the torso)
HEAD_BASE = 0.868                        # where the head sits on the neck (the body 1 tall)
LEGS, ARMS = {'Thigh', 'Shin'}, {'UpperArm', 'Forearm'}
GIRTH = {'Waist', 'Chest', 'Pelvis', 'Thigh', 'Shin', 'UpperArm', 'Forearm'}
REGION = {'UpperArm': 'arm_size', 'Thigh': 'leg_size', 'Head': 'head', 'Hand': 'hands', 'Foot': 'feet'}
SHOULDER_SHARE = 0.22                    # how much of an upper arm's lift its collarbone takes
JOINT_KEYS = ('scale', 'length', 'width', 'bend', 'twist', 'side')
_BUSY = [False]
_CACHE = {}


KINDS = (('human', 'Human', 'Your human body'), ('creature', 'Creature', 'Your creature (the big-headed one)'),
         ('creature2', 'Creature 2', 'Your lanky creature (long arms, raised heels)'))


def load(kind='human'):
    """(V (n, 3), face sizes, corners, {bone: (head, tail, parent, slot, side)}, each point's bone (an index)) - the
    body 1 tall, feet on 0.  The bones and each point's bone are worked out when the body is built
    (tools_dev/body_whole_build.py)."""
    if kind in _CACHE:
        return _CACHE[kind]
    with np.load(os.path.join(DIR, kind + '_whole.npz'), allow_pickle=False) as z:
        lo, hi = z['Body_box'].astype(np.float64)
        V = z['Body_Q'].astype(np.float64) / 65535.0 * (hi - lo) + lo
        N, L = np.array(z['Body_N']).astype(np.int64), np.array(z['Body_L']).astype(np.int64)
        B = np.array(z['Body_B']).astype(np.int64)
        meta = json.loads(str(z['meta']))
    bones = {b['name']: (np.array(b['head'], float), np.array(b['tail'], float), b['parent'], b['slot'], b['side'])
             for b in meta['bones']}
    _CACHE[kind + ':digits'] = {b['name']: (b['z'], b['u'], b['seg']) for b in meta['bones'] if 'z' in b}
    _CACHE[kind] = (V, N, L, bones, B)
    return _CACHE[kind]


def digits(kind='human'):
    """{bone: (its curl side, where across the hand (-1 .. 1), which joint (0: the root))} of the fingers / toes."""
    load(kind)
    return _CACHE[kind + ':digits']


def kind_of(rig):
    try:
        return json.loads(rig[KEY]).get('kind', 'human')
    except (KeyError, TypeError, ValueError):
        return 'human'


def slot_of(name):
    """'Finger2b.L' -> 'Finger', 'Toes.R' -> 'Toe', 'Thigh.L' -> 'Thigh'."""
    base = name.split('.')[0]
    return 'Finger' if base.startswith('Finger') else 'Toe' if base.startswith('Toe') else base


def weights(B, bones):
    """Each point's bone (n, bones; one each - smoothed over the mesh by the caller)."""
    names = list(bones)
    W = np.zeros((len(B), len(names)))
    W[np.arange(len(B)), B] = 1.0
    return W, names


def smooth_weights(W, edges, passes=6):
    n = len(W)
    deg = np.zeros(n)
    np.add.at(deg, edges[:, 0], 1)
    np.add.at(deg, edges[:, 1], 1)
    for _ in range(passes):
        acc = np.zeros_like(W)
        np.add.at(acc, edges[:, 0], W[edges[:, 1]])
        np.add.at(acc, edges[:, 1], W[edges[:, 0]])
        W = (W + acc / np.maximum(deg, 1)[:, None]) * 0.5
    return W / W.sum(1, keepdims=True)


def is_body(ob):
    return ob is not None and KEY in ob


def pair(ob):
    """(the body mesh, its bones object) of either - or (None, None)."""
    if not is_body(ob):
        return None, None
    d = json.loads(ob[KEY])
    return bpy.data.objects.get(d['body']), bpy.data.objects.get(d['rig'])


def make(context, height=1.8, location=None, kind='human'):
    V, N, L, bones, B = load(kind)
    location = Vector(location if location is not None else context.scene.cursor.location)
    me = bpy.data.meshes.new('Body')
    me.vertices.add(len(V))
    me.vertices.foreach_set('co', V.astype(np.float32).ravel())
    me.loops.add(len(L))
    me.loops.foreach_set('vertex_index', L.astype(np.int32))
    me.polygons.add(len(N))
    me.polygons.foreach_set('loop_start', np.concatenate([[0], np.cumsum(N)[:-1]]).astype(np.int32))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    try:
        me.shade_smooth()
    except AttributeError:
        pass
    body = bpy.data.objects.new('Body', me)
    coll = context.collection or context.scene.collection
    coll.objects.link(body)
    try:
        from .body_kit import _material
        me.materials.append(_material('human' if kind == 'human' else 'creature'))
    except (ImportError, KeyError):
        pass
    # the bones
    arm = bpy.data.armatures.new('Body Bones')
    rig = bpy.data.objects.new('Body Bones', arm)
    coll.objects.link(rig)
    context.view_layer.objects.active = rig
    for o in context.selected_objects:
        o.select_set(False)
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    front = Vector((0.0, -1.0, 0.0))
    dg_ = digits(kind)
    for n, (a, b, par, _slot, _side) in bones.items():
        eb = arm.edit_bones.new(n)
        eb.head, eb.tail = Vector(a), Vector(b)
        if n in dg_:                                  # (a finger: its Z to the palm's inside - Bend curls it)
            f = Vector(dg_[n][0])
        else:
            f = front - eb.y_axis * front.dot(eb.y_axis)
            if f.length < 0.35:
                f = Vector((0.0, 0.0, 1.0))
        eb.align_roll(f)                              # (the bone's Z to the front: Bend turns round its X)
        if par:
            eb.parent = arm.edit_bones[par]
            eb.use_connect = False
        eb.inherit_scale = 'NONE'                     # (sizes are worked out here: no scale handed down twice)
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.display_type = 'STICK'
    rig.show_in_front = True
    # the skin: each point on the bones nearest it
    W, names = weights(B, bones)
    E = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get('vertices', E)
    E = E.reshape(-1, 2)
    fine = np.array([n in dg_ or n.startswith('Hand') for n in names])[B]
    Wf = smooth_weights(W, E, passes=2)               # (the fingers are small: their skin less blurred)
    # how far the skin is shared between two bones - by DISTANCE (the body 1 tall), not by how fine the mesh is: a
    # joint's skin shared too narrowly folds to a sharp corner (user: the bent knee "너무 각지는데")
    el = float(np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1).mean())
    bc = [j for j, n in enumerate(names) if n not in dg_]      # (the body's bones: the fingers' stay as they are)

    def shared(dist, cols=None):
        n_ = int(np.clip((dist / el) ** 2, 2, 320))
        if cols is None:
            return smooth_weights(W0, E, passes=n_)
        out_ = np.zeros_like(W0)
        sub = W0[:, cols]
        out_[:, cols] = smooth_weights(np.hstack([sub, 1.0 - sub.sum(1, keepdims=True)]), E, passes=n_)[:, :-1]
        return out_

    def band(slots, dist=0.02, gain=1.5):
        m_ = np.array([n.split('.')[0] in slots for n in names])[B].astype(float)[:, None]
        n_ = int(np.clip((dist / el) ** 2, 2, 320))
        return np.clip(smooth_weights(np.hstack([m_, 1.0 - m_]), E, passes=n_)[:, :1] * gain, 0.0, 1.0)
    W0 = W
    W = shared(0.018)
    m_ = band(('Thigh', 'Shin', 'UpperArm', 'Forearm'))        # (knees and elbows: a rounder fold)
    W = W * (1.0 - m_) + shared(0.034, bc) * m_
    knee_z, hip_z = float(bones['Shin.L'][0][2]), float(bones['Thigh.L'][0][2])
    m_ = band(('Thigh', 'Pelvis')) * np.clip((V[:, 2] - (knee_z + 0.35 * (hip_z - knee_z))) /
                                             (0.3 * (hip_z - knee_z)), 0.0, 1.0)[:, None]
    W = W * (1.0 - m_) + shared(0.046, bc) * m_       # (the hips: a lifted thigh takes the hip's side and the buttock)
    m_ = band(('Shoulder', 'UpperArm'), 0.03, 1.6)
    zj = float(bones['UpperArm.L'][0][2])
    elbow_z = float(bones['Forearm.L'][0][2])
    m_ = m_ * np.clip((V[:, 2] - (elbow_z + 0.45 * (zj - elbow_z))) / (0.25 * (zj - elbow_z)), 0.0, 1.0)[:, None]
    W = W * (1.0 - m_) + shared(0.052, bc) * m_       # (the shoulders: the widest - the shoulder muscle goes up with the arm)
    W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
    # under the armpit the body's own skin (the ribs' side, the chest's and the back's edge) lets go of the arm: any
    # share of the arm's bones there swings it out like a balloon when the arm lifts - none at the armpit's depth,
    # all of it back by the shoulder's height
    keep = np.clip((V[:, 2] - (zj - 0.085)) / 0.075, 0.0, 1.0)
    keep = keep * keep * (3.0 - 2.0 * keep)
    body_pt = np.array([n.split('.')[0] in ('Pelvis', 'Waist', 'Chest', 'Neck', 'Shoulder') for n in names])[B]
    keep = np.where(body_pt, keep, 1.0)
    for j, n in enumerate(names):
        if n.split('.')[0] in ('UpperArm', 'Forearm'):
            W[:, j] *= keep
    W /= W.sum(1, keepdims=True)
    W[fine] = Wf[fine]
    for j, n in enumerate(names):
        vg = body.vertex_groups.new(name=n)
        idx = np.nonzero(W[:, j] > 0.004)[0]
        for i in idx:
            vg.add([int(i)], float(W[i, j]), 'REPLACE')
    for end in ('Hand', 'Foot'):                      # (a whole hand / foot with its fingers: what a swap hides)
        for sd in ('L', 'R'):
            cols = [j for j, n in enumerate(names) if n.endswith('.' + sd) and
                    (n.startswith(end) or slot_of(n) == ('Finger' if end == 'Hand' else 'Toe'))]
            w = W[:, cols].sum(1)
            vg = body.vertex_groups.new(name=f'MCH End {end}.{sd}')
            for i in np.nonzero(w > 0.004)[0]:
                vg.add([int(i)], float(min(w[i], 1.0)), 'REPLACE')
    md = body.modifiers.new(ARM_MOD, 'ARMATURE')
    md.object = rig
    body.parent = rig
    tag = json.dumps({'body': body.name, 'rig': rig.name, 'kind': kind})
    body[KEY] = tag
    rig[KEY] = tag
    rig['mch_joints'] = json.dumps({})
    rig.location = location
    _BUSY[0] = True
    try:
        rig.mch_bodywhole.height = height
        rig.mch_bodywhole.floor = location.z
    finally:
        _BUSY[0] = False
    refresh(context, rig)
    rig.select_set(False)
    body.select_set(True)
    context.view_layer.objects.active = body
    return body, rig


def joints(rig):
    try:
        return json.loads(rig.get('mch_joints', '{}'))
    except (TypeError, ValueError):
        return {}


def joint(rig, name):
    return dict({'scale': 1.0, 'length': 1.0, 'width': 1.0, 'bend': 0.0, 'twist': 0.0, 'side': 0.0},
                **joints(rig).get(name, {}))


def refresh(context, rig):
    """The sliders onto the bones' pose (sizes worked out down the chain); the feet on the floor."""
    if rig is None or rig.type != 'ARMATURE':
        return
    kp = rig.mch_bodywhole
    J = joints(rig)

    def val(n):
        return dict({'scale': 1.0, 'length': 1.0, 'width': 1.0, 'bend': 0.0, 'twist': 0.0, 'side': 0.0}, **J.get(n, {}))
    size = {}
    dg_ = digits(kind_of(rig))
    for pb in rig.pose.bones:                         # (parents first)
        slot = slot_of(pb.name)
        v = val(pb.name)
        if slot == 'Finger' and pb.name in dg_:       # (all the fingers at once, on top of each one's own)
            _z, u, seg = dg_[pb.name]
            v['bend'] += kp.fingers_curl
            v['length'] *= kp.fingers_length
            v['width'] *= kp.fingers_thick
            if seg == 0:
                v['side'] -= kp.fingers_spread * u
        elif slot == 'Toe':
            v['bend'] += kp.toes_curl
        elif slot == 'Shoulder':                      # (an arm lifted takes its collarbone along: a third of the way)
            up = val('UpperArm' + pb.name[8:])
            v['side'] += up['side'] * SHOULDER_SHARE
            v['bend'] += up['bend'] * SHOULDER_SHARE * 0.6
        elif slot == 'UpperArm':
            v['side'] *= 1.0 - SHOULDER_SHARE
            v['bend'] *= 1.0 - SHOULDER_SHARE * 0.6
        own = v['scale'] * (getattr(kp, REGION[slot]) if slot in REGION else 1.0)
        size[pb.name] = own * (size[pb.parent.name] if pb.parent else 1.0)
        ln = v['length'] * (kp.legs if slot in LEGS else kp.arms if slot in ARMS else kp.torso if slot in ('Waist', 'Chest') else 1.0)
        g = v['width'] * (kp.build if slot in GIRTH else 1.0)
        s = size[pb.name]
        pb.scale = (g * s, ln * s, g * s)
        m = -1.0 if pb.name.endswith('.R') else 1.0
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (Quaternion((1, 0, 0), v['bend']) @ Quaternion((0, 0, 1), v['side'] * m) @
                                  Quaternion((0, 1, 0), v['twist'] * m))
    h = kp.height
    rig.scale = (h, h, h)
    if kp.ground:
        body, _r = pair(rig)
        if body is not None:
            context.view_layer.update()
            dg = context.evaluated_depsgraph_get()
            ev = body.evaluated_get(dg)
            me = ev.to_mesh()
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get('co', co)
            M = np.array(ev.matrix_world)
            low = float((co.reshape(-1, 3) @ M[2, :3] + M[2, 3]).min())
            ev.to_mesh_clear()
            for o in rig.children:                    # (swapped feet stand on the floor too)
                if str(o.get(END_KEY, '')).startswith('Foot'):
                    c2 = np.empty(len(o.data.vertices) * 3)
                    o.data.vertices.foreach_get('co', c2)
                    M2 = np.array(o.matrix_world)
                    low = min(low, float((c2.reshape(-1, 3) @ M2[2, :3] + M2[2, 3]).min()))
            rig.location.z += kp.floor - low


def _rig_of(context):
    _b, rig = pair(getattr(context, 'active_object', None))
    return rig


def _upd(self, context):
    if _BUSY[0]:
        return
    refresh(context, self.id_data)


def _upd_joint(self, context):
    """The picked joint's sliders -> its record (and its twin's)."""
    if _BUSY[0]:
        return
    rig = self.id_data
    J = joints(rig)
    names = [self.joint]
    if self.symmetry and self.joint[-2:] in ('.L', '.R'):
        names.append(self.joint[:-1] + ('R' if self.joint.endswith('L') else 'L'))
    for n in names:
        J[n] = {k: float(getattr(self, 'j_' + k)) for k in JOINT_KEYS}
    rig['mch_joints'] = json.dumps(J)
    refresh(context, rig)


def _upd_pick(self, context):
    """Another joint picked: its values into the sliders."""
    rig = self.id_data
    v = joint(rig, self.joint)
    _BUSY[0] = True
    try:
        for k in JOINT_KEYS:
            setattr(self, 'j_' + k, v[k])
    finally:
        _BUSY[0] = False


def _joint_items(self, context):
    bones = load(kind_of(self.id_data))[3]
    _JOINT_ITEMS[:] = [(n, _joint_label(n), '') for n in bones]
    return _JOINT_ITEMS


_JOINT_ITEMS = []


def _joint_label(n):
    base, _d, sd = n.partition('.')
    if base.startswith('Finger'):
        base = f'Finger {base[6:-1]} - {("root", "middle", "tip")["abc".index(base[-1])]}'
    return base.replace('UpperArm', 'Upper Arm') + (f' ({sd})' if sd else '')


def _f(name, default, lo, hi, desc, update=_upd, soft=None):
    kw = {'name': name, 'default': default, 'min': lo, 'max': hi, 'description': desc, 'update': update}
    if soft:
        kw['soft_min'], kw['soft_max'] = soft
    return FloatProperty(**kw)


def _ang(name, desc):
    return FloatProperty(name=name, default=0.0, min=-math.pi, max=math.pi, subtype='ANGLE', update=_upd_joint,
                         description=desc)


class MCH_PG_BodyWhole(bpy.types.PropertyGroup):
    height: FloatProperty(name='Height', default=1.8, min=0.05, max=100.0, soft_max=10.0, unit='LENGTH', update=_upd)
    head: _f('Head', 1.0, 0.3, 3.0, 'Head size', soft=(0.6, 1.6))
    arm_size: _f('Arms Size', 1.0, 0.2, 4.0, 'The arms (and hands) bigger or smaller', soft=(0.5, 2.0))
    hands: _f('Hands', 1.0, 0.3, 3.0, 'Hand size', soft=(0.6, 1.6))
    leg_size: _f('Legs Size', 1.0, 0.2, 4.0, 'The legs (and feet) bigger or smaller', soft=(0.5, 2.0))
    feet: _f('Feet', 1.0, 0.3, 3.0, 'Foot size', soft=(0.6, 1.6))
    legs: _f('Legs', 1.0, 0.3, 3.0, 'Leg length', soft=(0.5, 1.8))
    arms: _f('Arms', 1.0, 0.3, 3.0, 'Arm length', soft=(0.5, 1.8))
    torso: _f('Torso', 1.0, 0.3, 3.0, 'Torso length', soft=(0.6, 1.6))
    build: _f('Build', 1.0, 0.3, 3.0, 'Slim to heavy', soft=(0.6, 1.6))
    fingers_curl: FloatProperty(name='Curl', default=0.0, min=-math.pi / 2, max=math.pi / 2, subtype='ANGLE', update=_upd,
                                description='Every finger joint curled toward the palm (minus: opened back)')
    fingers_spread: FloatProperty(name='Spread', default=0.0, min=-math.pi / 3, max=math.pi / 3, subtype='ANGLE',
                                  update=_upd, description='The fingers fanned apart (minus: together)')
    fingers_length: _f('Length', 1.0, 0.3, 4.0, 'Every finger longer', soft=(0.5, 2.5))
    fingers_thick: _f('Thickness', 1.0, 0.3, 4.0, 'Every finger thicker', soft=(0.5, 2.5))
    toes_curl: FloatProperty(name='Toes', default=0.0, min=-math.pi / 2, max=math.pi / 2, subtype='ANGLE', update=_upd,
                             description='The front of the feet bent down (minus: up - on tiptoe)')
    ground: BoolProperty(name='Feet on Ground', default=True, update=_upd)
    floor: FloatProperty(name='Floor', default=0.0, unit='LENGTH', update=_upd)
    symmetry: BoolProperty(name='Symmetry', default=True, description='A joint\'s sliders on the other side too')
    joint: EnumProperty(name='Joint', items=_joint_items, update=_upd_pick)
    j_scale: _f('Scale', 1.0, 0.1, 6.0, 'This part and every part after it bigger or smaller', update=_upd_joint,
                soft=(0.3, 2.5))
    j_length: _f('Length', 1.0, 0.2, 4.0, 'Longer', update=_upd_joint, soft=(0.4, 2.0))
    j_width: _f('Width', 1.0, 0.2, 4.0, 'Thicker', update=_upd_joint, soft=(0.4, 2.0))
    j_bend: _ang('Bend', 'Turn at its joint toward the front (minus: back)')
    j_twist: _ang('Twist', 'Turn round itself')
    j_side: _ang('Side', 'Turn at its joint to the side')


def set_pose(context, rig, vals):
    """vals: {slot or bone: (bend, twist, side) in degrees} (the Body Kit's poses)."""
    J = joints(rig)
    for pb in rig.pose.bones:
        slot = slot_of(pb.name)
        if slot in ('Finger', 'Toe') and pb.name not in vals and slot not in vals:
            continue                                  # (a body pose leaves the fingers as they are)
        b, t, s_ = vals.get(pb.name, vals.get(slot, vals.get('Knee' if slot == 'Shin' else slot, (0, 0, 0))))
        if slot in ('Waist', 'Chest') and slot not in vals and 'Torso' in vals:
            b, t, s_ = (x * 0.5 for x in vals['Torso'])   # (a kit pose's torso: half at the waist, half at the chest)
        rec = dict(joint(rig, pb.name))
        rec.update(bend=math.radians(b), twist=math.radians(t), side=math.radians(s_))
        J[pb.name] = rec
    rig['mch_joints'] = json.dumps(J)
    _upd_pick(rig.mch_bodywhole, context)
    refresh(context, rig)


# ---- hands and feet swapped (0.24.187, user: "손이랑 발은 프리셋을 바꿀 수가 있나? 크리쳐 손이나 발의 종류를 다양하게") ----
END_KEY = 'mch_bodywhole_end'            # on a swapped hand / foot: its slot and side


def end_variants(slot):
    """[(id, label)] of what a hand / foot can be: the body's own, the kits' (your creature's), your saved parts."""
    from . import body_kit as bk
    out = [('own', 'Own (the body\'s)')]
    for vid, label in bk.variants(slot):
        if not vid.startswith('human:'):
            out.append((vid, label))
    return out


def set_end(context, rig, slot, vid):
    """Both hands (feet) swapped for a variant: the body's own hidden there (a Mask on its points), the other one hung
    on the bone (it follows the pose and the sizes).  'own': back as it was."""
    from . import body_kit as bk
    body, _r = pair(rig)
    for side in ('L', 'R'):
        bone = f'{slot}.{side}'
        for o in [o for o in rig.children if o.get(END_KEY) == bone]:
            me = o.data
            bpy.data.objects.remove(o)
            if me.users == 0:
                bpy.data.meshes.remove(me)
        mk = body.modifiers.get('MCH Hide ' + bone)
        if vid == 'own':
            if mk is not None:
                body.modifiers.remove(mk)
            continue
        if mk is None:
            mk = body.modifiers.new('MCH Hide ' + bone, 'MASK')
        mk.vertex_group = 'MCH End ' + bone if ('MCH End ' + bone) in body.vertex_groups else bone
        mk.invert_vertex_group = True
        mk.threshold = 0.5
        if vid.startswith('mine:'):
            path = os.path.join(bk.my_dir(), slot, vid[5:] + '.npz')
            with np.load(path, allow_pickle=False) as z:
                A, N, L = z['A'].astype(np.float64), np.array(z['N']), np.array(z['L'])
                vside = str(z['side']) if 'side' in z else ''
        else:
            kit, n = vid.split(':', 1)
            parts = bk.load(kit)
            pp = parts.get(n[:-1] + side, parts[n])
            fr_ = bk.frame(pp['pivot'], pp['end'])
            A = bk._local(pp['V'], fr_)
            N, L, vside = pp['N'], pp['L'], pp['side']
            own_len = fr_[4]                          # (its own size beside the body: both are kept 1 tall)
        if vside and vside != side:
            A = A * (1.0, -1.0, 1.0)
            L = bk._flip(N, L)
        pb = rig.pose.bones[bone]
        ln = pb.bone.length
        # (along, side, front) over its length -> the bone's own space: Y along it, Z its front, X = -side
        V = np.stack([-A[:, 1], A[:, 0], A[:, 2]], 1) * (ln if vid.startswith('mine:') else own_len)
        me = bk._mesh(f'Body {bone}', {'V': V, 'N': N, 'L': L})
        for m in body.data.materials:
            me.materials.append(m)
        ob = bpy.data.objects.new(f'Body {bone}', me)
        (body.users_collection[0] if body.users_collection else context.scene.collection).objects.link(ob)
        ob.parent = rig
        ob.parent_type = 'BONE'
        ob.parent_bone = bone
        ob.location = (0.0, -ln, 0.0)                 # (a bone's children hang on its end: back to its start)
        ob[END_KEY] = bone
    d = json.loads(rig.get('mch_ends', '{}'))
    d[slot] = vid
    rig['mch_ends'] = json.dumps(d)
    refresh(context, rig)


def _end_items(self, context):
    items = [(vid, label, '') for vid, label in end_variants(self.slot)]
    _END_ITEMS[:] = items
    return _END_ITEMS


_END_ITEMS = []


class MCH_OT_bodywhole_end(bpy.types.Operator):
    bl_idname = 'mch.bodywhole_end'
    bl_label = 'Swap Hands / Feet'
    bl_description = ('Both hands (or feet) swapped for another kind - your creature\'s, or a part you saved (Body Kit: '
                      'Use Selected Mesh); they follow the pose and the Hands / Feet size.  Own: the body\'s again')
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = 'variant'
    slot: StringProperty(default='Hand')
    variant: EnumProperty(name='Kind', items=_end_items)

    @classmethod
    def poll(cls, context):
        return _rig_of(context) is not None

    def execute(self, context):
        try:
            set_end(context, _rig_of(context), self.slot, self.variant)
        except (OSError, KeyError, ValueError) as e:
            self.report({'WARNING'}, f'Swap: {e}')
            return {'CANCELLED'}
        return {'FINISHED'}


class MCH_OT_bodywhole_add(bpy.types.Operator):
    bl_idname = 'mch.bodywhole_add'
    bl_label = 'Add One-Piece Body'
    bl_description = ('A whole body of yours (human or creature) as one mesh on bones: its skin bends at the joints; the same sliders '
                      '(sizes, proportions, joints, poses)')
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(name='Body', items=KINDS, default='human')

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            body, _rig = make(context, context.scene.mch_bodykit_new.height, kind=self.kind)
        except (OSError, KeyError, ValueError) as e:
            self.report({'ERROR'}, f'One-piece body: {e}')
            return {'CANCELLED'}
        self.report({'INFO'}, f'{body.name}: one mesh ({len(body.data.polygons):,} faces) on bones - pick a joint in '
                              'the window')
        return {'FINISHED'}


class MCH_OT_bodywhole_pose(bpy.types.Operator):
    bl_idname = 'mch.bodywhole_pose'
    bl_label = 'Pose'
    bl_description = 'The body in this pose (its joints\' sliders set; change them after)'
    bl_options = {'REGISTER', 'UNDO'}
    pose: StringProperty(default='STAND')

    @classmethod
    def poll(cls, context):
        return _rig_of(context) is not None

    def execute(self, context):
        from . import body_kit as bk
        rig = _rig_of(context)
        if self.pose in bk.POSE:
            vals = dict(bk.POSE[self.pose][2])
            if 'Knee' in vals and 'Shin' not in vals:     # (the kit bends the knee part: here the shin)
                vals['Shin'] = vals['Knee']
            set_pose(context, rig, vals)
        elif self.pose == '__RESET__':
            rig['mch_joints'] = json.dumps({n: dict(v, bend=0.0, twist=0.0, side=0.0) for n, v in joints(rig).items()})
            _BUSY[0] = True
            try:
                rig.mch_bodywhole.fingers_curl = rig.mch_bodywhole.fingers_spread = rig.mch_bodywhole.toes_curl = 0.0
            finally:
                _BUSY[0] = False
            _upd_pick(rig.mch_bodywhole, context)
            refresh(context, rig)
        return {'FINISHED'}


def draw(layout, context):
    rig = _rig_of(context)
    if rig is None:
        return False
    kp = rig.mch_bodywhole
    col = layout.column(align=True)
    col.label(text='One-Piece Body - sizes (scaled)')
    for k in ('height', 'head', 'arm_size', 'hands', 'leg_size', 'feet'):
        col.prop(kp, k, slider=k != 'height')
    col = layout.column(align=True)
    col.label(text='Proportions')
    for k in ('legs', 'arms', 'torso', 'build'):
        col.prop(kp, k, slider=True)
    row = layout.row(align=True)
    row.prop(kp, 'symmetry', toggle=True, icon='MOD_MIRROR')
    row.prop(kp, 'ground', toggle=True, icon='SNAP_FACE')
    col = layout.column(align=True)
    col.label(text='Joint')
    col.prop(kp, 'joint', text='')
    for k in JOINT_KEYS:
        col.prop(kp, 'j_' + k, slider=True)
    col = layout.column(align=True)
    col.label(text='Fingers (all) - one finger: pick it in Joint')
    for k in ('fingers_curl', 'fingers_spread', 'fingers_length', 'fingers_thick', 'toes_curl'):
        col.prop(kp, k, slider=True)
    col = layout.column(align=True)
    col.label(text='Hands / Feet (swap)')
    ends = json.loads(rig.get('mch_ends', '{}'))
    for slot, label in (('Hand', 'Hands'), ('Foot', 'Feet')):
        now = dict(end_variants(slot)).get(ends.get(slot, 'own'), 'Own')
        op = col.operator_menu_enum('mch.bodywhole_end', 'variant', text=f'{label}: {now}')
        op.slot = slot
    from . import body_kit as bk
    col = layout.column(align=True)
    col.label(text='Poses')
    g = col.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
    for pid, label, _v in bk.POSES:
        g.operator('mch.bodywhole_pose', text=label).pose = pid
    col.operator('mch.bodywhole_pose', text='Reset Pose').pose = '__RESET__'
    return True


CLASSES = (MCH_PG_BodyWhole, MCH_OT_bodywhole_end, MCH_OT_bodywhole_add, MCH_OT_bodywhole_pose)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_bodywhole = PointerProperty(type=MCH_PG_BodyWhole)


def unregister():
    if hasattr(bpy.types.Object, 'mch_bodywhole'):
        del bpy.types.Object.mch_bodywhole
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
