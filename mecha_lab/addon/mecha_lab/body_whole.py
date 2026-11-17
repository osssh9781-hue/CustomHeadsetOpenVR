"""0.24.186 One-piece body (user: "그전에 보냈던 붙어 있는 모델로 만들어 줘, 이건 예시 모델이잖아" - after "다즈 스튜디오처럼 ...
슬라이더로 조절하고 크기 키우고 관절도 꺾어서 자세 잡고"): the user's whole human body as ONE mesh on bones - its skin
bends at the joints (no seams between parts), the same sliders as the Body Kit:

* Body Size (scaled, not fattened): Height, Head, Arms Size, Hands, Legs Size, Feet; Proportions: Legs, Arms, Torso,
  Build - the feet kept on the floor.
* The joint picked (a list): Scale (it and all after it), Length, Width, Bend / Twist / Side - the other side the same.
* Poses (the Body Kit's) and your own saved ones.

The bones are the part-split human kit's joints (the same sculpt); each point follows the bones nearest it (weights
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

FILE = os.path.join(os.path.dirname(__file__), 'body_kits', 'human_whole.npz')
KEY = 'mch_bodywhole'                    # on the body mesh and its bones object: json {'rig': name, 'body': name}
ARM_MOD = 'MCH Body Bones'
# (bone, slot, parent, from, to) - "from" / "to": a kit part's pivot / end, a midpoint, or a point
BONES = (('Pelvis', 'Pelvis', None), ('Torso', 'Torso', 'Pelvis'), ('Head', 'Head', 'Torso'),
         ('UpperArm', 'UpperArm', 'Torso'), ('Forearm', 'Forearm', 'UpperArm'), ('Hand', 'Hand', 'Forearm'),
         ('Thigh', 'Thigh', 'Pelvis'), ('Shin', 'Shin', 'Thigh'), ('Foot', 'Foot', 'Shin'))
SIDED = {'UpperArm', 'Forearm', 'Hand', 'Thigh', 'Shin', 'Foot'}
LEGS, ARMS = {'Thigh', 'Shin'}, {'UpperArm', 'Forearm'}
GIRTH = {'Torso', 'Pelvis', 'Thigh', 'Shin', 'UpperArm', 'Forearm'}
REGION = {'UpperArm': 'arm_size', 'Thigh': 'leg_size', 'Head': 'head', 'Hand': 'hands', 'Foot': 'feet'}
JOINT_KEYS = ('scale', 'length', 'width', 'bend', 'twist', 'side')
_BUSY = [False]
_CACHE = {}


def load():
    """(V (n, 3), face sizes, corners, {bone: (head, tail, parent, slot, side)}) - the body 1 tall, feet on 0."""
    if 'data' in _CACHE:
        return _CACHE['data']
    with np.load(FILE, allow_pickle=False) as z:
        lo, hi = z['Body_box'].astype(np.float64)
        V = z['Body_Q'].astype(np.float64) / 65535.0 * (hi - lo) + lo
        N, L = np.array(z['Body_N']).astype(np.int64), np.array(z['Body_L']).astype(np.int64)
        parts = {p['name']: p for p in json.loads(str(z['meta']))['parts']}
    bones = {}

    def P(name, key):
        return np.array(parts[name][key], float)
    for base, slot, par in BONES:
        for side in (('L', 'R') if base in SIDED else ('',)):
            sfx = f'.{side}' if side else ''
            if base == 'Head':
                head = P('Torso', 'end')
                tail = np.array([0.0, head[1] - 0.01, V[:, 2].max() - 0.01])
            elif base == 'Thigh':                     # (the kit's knee part: the joint in its middle)
                head, tail = P('Thigh' + sfx, 'pivot'), (P('Knee' + sfx, 'pivot') + P('Knee' + sfx, 'end')) * 0.5
            elif base == 'Shin':
                head, tail = (P('Knee' + sfx, 'pivot') + P('Knee' + sfx, 'end')) * 0.5, P('Foot' + sfx, 'pivot')
            else:
                head, tail = P(base + sfx, 'pivot'), P(base + sfx, 'end')
            pname = None if par is None else (par + sfx if par in SIDED else par)
            bones[base + sfx] = (head, tail, pname, slot, side)
    _CACHE['data'] = (V, N, L, bones)
    return _CACHE['data']


def weights(V, bones):
    """Each point's bone (n, bones; one each - smoothed over the mesh by the caller): the bone of the part-split human
    kit's part whose surface the point lies on (the same sculpt, cut in parts by the user) - so a fingertip beside the
    thigh is the hand's, not the thigh's."""
    from mathutils import kdtree
    from . import body_kit as bk
    parts = bk.load('human')
    labels, pts = [], []
    for n, p in parts.items():
        P = p['V'] + np.array(p['pivot'])
        step = max(1, len(P) // 4000)
        pts.append(P[::step])
        labels += [n] * len(P[::step])
    pts = np.concatenate(pts)
    kd = kdtree.KDTree(len(pts))
    for i, q in enumerate(pts):
        kd.insert(q, i)
    kd.balance()
    names = list(bones)
    col = {n: j for j, n in enumerate(names)}
    neck = bones['Head'][0][2]
    W = np.zeros((len(V), len(names)))
    for i, v in enumerate(V):
        part = labels[kd.find(v)[1]]
        base, _dot, side = part.partition('.')
        sfx = ('.' + side) if side else ''
        if base == 'Knee':                            # (the knee part: the thigh above its middle, the shin below)
            mid = bones['Shin' + sfx][0]
            ax = bones['Shin' + sfx][1] - mid
            base = 'Shin' if float((v - mid) @ ax) > 0 else 'Thigh'
        if base == 'Torso' and v[2] > neck:
            base = 'Head'
        W[i, col[base + sfx]] = 1.0
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


def make(context, height=1.8, location=None):
    V, N, L, bones = load()
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
        me.materials.append(_material('human'))
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
    for n, (a, b, par, _slot, _side) in bones.items():
        eb = arm.edit_bones.new(n)
        eb.head, eb.tail = Vector(a), Vector(b)
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
    W, names = weights(V, bones)
    E = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get('vertices', E)
    W = smooth_weights(W, E.reshape(-1, 2), passes=10)
    for j, n in enumerate(names):
        vg = body.vertex_groups.new(name=n)
        idx = np.nonzero(W[:, j] > 0.004)[0]
        for i in idx:
            vg.add([int(i)], float(W[i, j]), 'REPLACE')
    md = body.modifiers.new(ARM_MOD, 'ARMATURE')
    md.object = rig
    body.parent = rig
    tag = json.dumps({'body': body.name, 'rig': rig.name})
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
    for pb in rig.pose.bones:                         # (parents first)
        slot = pb.name.split('.')[0]
        v = val(pb.name)
        own = v['scale'] * (getattr(kp, REGION[slot]) if slot in REGION else 1.0)
        size[pb.name] = own * (size[pb.parent.name] if pb.parent else 1.0)
        ln = v['length'] * (kp.legs if slot in LEGS else kp.arms if slot in ARMS else kp.torso if slot == 'Torso' else 1.0)
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
    _V, _N, _L, bones = load()
    return [(n, n.replace('UpperArm', 'Upper Arm'), '') for n in bones]


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
        slot = pb.name.split('.')[0]
        b, t, s_ = vals.get(pb.name, vals.get(slot, vals.get('Knee' if slot == 'Shin' else slot, (0, 0, 0))))
        rec = dict(joint(rig, pb.name))
        rec.update(bend=math.radians(b), twist=math.radians(t), side=math.radians(s_))
        J[pb.name] = rec
    rig['mch_joints'] = json.dumps(J)
    _upd_pick(rig.mch_bodywhole, context)
    refresh(context, rig)


class MCH_OT_bodywhole_add(bpy.types.Operator):
    bl_idname = 'mch.bodywhole_add'
    bl_label = 'Add One-Piece Body'
    bl_description = ('Your whole human body as one mesh on bones: its skin bends at the joints; the same sliders '
                      '(sizes, proportions, joints, poses)')
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            body, _rig = make(context, context.scene.mch_bodykit_new.height)
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
    from . import body_kit as bk
    col = layout.column(align=True)
    col.label(text='Poses')
    g = col.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
    for pid, label, _v in bk.POSES:
        g.operator('mch.bodywhole_pose', text=label).pose = pid
    col.operator('mch.bodywhole_pose', text='Reset Pose').pose = '__RESET__'
    return True


CLASSES = (MCH_PG_BodyWhole, MCH_OT_bodywhole_add, MCH_OT_bodywhole_pose)


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
