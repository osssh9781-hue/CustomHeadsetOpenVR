"""0.24.241 Rig (user: "리깅 툴" - 사람 / 크리쳐 몸, 메카 (딱딱한 부품), 꼬리 / 촉수 / 머리카락 체인).

Body (Human / Quadruped)
    Select the body mesh (standing on the ground, facing -Y; a quadruped's head toward -Y), Make Rig: the joints are
    found on the mesh (the middle of its cross-sections at the usual heights: hips, chest, neck, shoulders, elbows,
    wrists, hips, knees, ankles - measured, not guessed: an arm in T or A pose, long legs or short), an armature
    ``<body>_Rig`` is built (deform bones + IK: a hand / foot target and an elbow / knee pole for every limb, the
    pole angle chosen so the rest pose does not move), the body bound to it (automatic weights; where Blender's
    heat weights fail - an open or broken mesh - every point gets the nearest bones by distance instead).  Edit
    Bones moves the joints (Blender's own edit mode), Bind again after.

Mecha (rigid parts)
    Select the parts, Make Rig: one bone per part (from its middle along its longest side), all under a root;
    a part already parented to another keeps that order.  Each part rides its bone rigidly (bone parent, no
    weights).  With the Rig tool, click a part: its joint (the bone's start) moves to where you clicked - into the
    middle of the part along the view (the halfway point between where the ray goes in and out).  Link to Active:
    the selected parts' bones under the active part's bone.

Chain (tail, tentacle, hair lock)
    Select the long mesh (or a curve), Make Rig: ``Bones`` bones along it (the middle of its cross-sections from the
    thick end to the thin end), the mesh bound to them.  With an armature selected too the chain goes into it,
    under its bone nearest the chain's root.  Jiggle: during playback the chain lags and swings after the
    movement (Stiffness, Damping).
"""
import math

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty
from mathutils import Matrix, Vector

RIG_KEY = 'mch_rig'            # on the armature: 'BODY' / 'QUAD' / 'MECHA' / 'CHAIN'
BODY_KEY = 'mch_rig_body'      # on the armature: the bound body's name
PART_KEY = 'mch_rig_bone'      # on a mecha part: its bone's name
SPRING_KEY = 'mch_spring'      # on the armature: {chain root bone: [stiffness, damping]} (as a string list)

KINDS = [('BODY', 'Human', 'A standing body (feet on the ground, facing -Y): spine, arms, legs, IK'),
         ('QUAD', 'Quadruped', 'A four-legged body (head toward -Y): spine, neck, head, four legs, tail, IK'),
         ('MECHA', 'Mecha', 'Rigid parts: one bone per selected part, the parts ride their bones'),
         ('CHAIN', 'Chain', 'A tail / tentacle / hair lock: bones along it, Jiggle')]


class MCH_PG_Rig(bpy.types.PropertyGroup):
    kind: EnumProperty(name='Rig', items=KINDS, default='BODY')
    ik: BoolProperty(name='IK', default=True, description='Hand / foot targets and elbow / knee poles on the limbs')
    bind: BoolProperty(name='Bind', default=True, description='Bind the mesh to the rig (weights) right away')
    bones: IntProperty(name='Bones', default=8, min=2, max=64, description='Bones in a chain')
    jiggle: BoolProperty(name='Jiggle', default=False, description='The chain lags and swings after the movement '
                         'during playback')
    stiffness: FloatProperty(name='Stiffness', default=0.25, min=0.01, max=1.0, subtype='FACTOR',
                             description='How hard the chain pulls back to its pose')
    damping: FloatProperty(name='Damping', default=0.25, min=0.0, max=0.95, subtype='FACTOR',
                           description='How fast the swing dies down')


def settings(context):
    return getattr(context.scene, 'mch_rig', None)


def is_rig(ob):
    return ob is not None and ob.type == 'ARMATURE' and RIG_KEY in ob


def rig_of(ob):
    """The rig ``ob`` belongs to (itself, its armature modifier's, its bone parent's), or None."""
    if ob is None:
        return None
    if is_rig(ob):
        return ob
    if ob.parent is not None and is_rig(ob.parent):
        return ob.parent
    for m in getattr(ob, 'modifiers', ()):
        if m.type == 'ARMATURE' and is_rig(m.object):
            return m.object
    return None


# --- the mesh, measured --------------------------------------------------------------------------------------------

def world_points(context, ob):
    dg = context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        co = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get('co', co)
    finally:
        ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def _centre(V, mask, fallback):
    return V[mask].mean(0) if mask.sum() >= 3 else np.asarray(fallback, np.float64)


def _slab(V, axis, at, half):
    return np.abs(V[:, axis] - at) < half


def body_joints(V):
    """The joints of a standing body (dict name -> point), the +X side's ('.L'); the -X side mirrored."""
    lo, hi = V.min(0), V.max(0)
    H = hi[2] - lo[2]
    x0 = 0.5 * (lo[0] + hi[0])
    z = lambda f: lo[2] + f * H
    core = np.abs(V[:, 0] - x0) < 0.11 * H
    J = {}
    for name, f in (('hips', 0.5), ('spine', 0.6), ('chest', 0.7), ('neck', 0.815), ('head', 0.875)):
        c = _centre(V, _slab(V, 2, z(f), 0.025 * H) & core, (x0, 0.5 * (lo[1] + hi[1]), z(f)))
        J[name] = np.array([x0, c[1], z(f)])
    J['head_top'] = np.array([x0, J['head'][1], hi[2]])
    side = V[:, 0] > x0
    sh = np.array([x0 + 0.1 * H, J['chest'][1], z(0.795)])
    ring = _slab(V, 2, sh[2], 0.04 * H) & side & (np.abs(V[:, 0] - sh[0]) < 0.05 * H)
    sh = _centre(V, ring, sh)
    sh[0] = max(sh[0], x0 + 0.07 * H)
    # the hand: the point farthest from the shoulder outside the torso and the legs (T pose: out to the side; A pose:
    # hanging beside the thighs) - the legs stay inside 0.12 H of the middle
    out = side & (V[:, 0] - x0 > 0.12 * H) & (V[:, 2] > z(0.3))
    if out.sum() < 3:
        out = side & (V[:, 0] - x0 > 0.08 * H) & (V[:, 2] > z(0.3))
    cand = V[out]
    tip = cand[np.argmax(np.linalg.norm(cand - sh, axis=1))] if len(cand) else np.array([x0 + 0.4 * H, sh[1], z(0.8)])
    arm = tip - sh
    L = np.linalg.norm(arm)
    d = arm / max(L, 1e-9)
    hand_len = min(0.1 * H, 0.3 * L)
    wrist = sh + d * (L - hand_len)
    elbow = sh + d * (0.5 * (L - hand_len))

    def near(p, r, msk):
        m = (np.linalg.norm(V - p, axis=1) < r) & msk
        return _centre(V, m, p)
    elbow = near(elbow, 0.04 * H, out | (side & (V[:, 0] - x0 > 0.1 * H)))
    wrist = near(wrist, 0.03 * H, out)
    J.update({'shoulder.L': np.array([x0 + 0.025 * H, J['chest'][1], sh[2] + 0.01 * H]), 'upper_arm.L': sh,
              'forearm.L': elbow, 'hand.L': wrist, 'hand_tip.L': tip})
    leg = side & (V[:, 0] - x0 > 0.005 * H) & (V[:, 0] - x0 < 0.12 * H)
    th = _centre(V, _slab(V, 2, z(0.42), 0.02 * H) & leg, (x0 + 0.07 * H, J['hips'][1], z(0.42)))
    hip = np.array([x0 + 0.8 * (th[0] - x0), th[1], z(0.465)])
    knee = _centre(V, _slab(V, 2, z(0.275), 0.02 * H) & leg, (th[0], th[1], z(0.275)))
    ankle = _centre(V, _slab(V, 2, z(0.07), 0.015 * H) & leg, (th[0], th[1], z(0.07)))
    feet = leg & (V[:, 2] < z(0.06))
    toe = V[feet][np.argmin(V[feet][:, 1])] if feet.any() else ankle + np.array([0, -0.12 * H, 0])
    toe = np.array([ankle[0], toe[1], z(0.015)])
    knee[1] = min(knee[1], 0.5 * (hip[1] + ankle[1]) - 0.005 * H)   # (a knee bent forward a little: IK knows the way)
    J.update({'thigh.L': hip, 'shin.L': knee, 'foot.L': ankle, 'toe.L': toe})
    return J, H, x0


def mirror(p, x0):
    return np.array([2 * x0 - p[0], p[1], p[2]])


def quad_joints(V):
    """The joints of a four-legged body facing -Y (dict, '.L' = +X side; F / B = front / back)."""
    lo, hi = V.min(0), V.max(0)
    H = hi[2] - lo[2]
    Lg = hi[1] - lo[1]
    x0 = 0.5 * (lo[0] + hi[0])
    y = lambda f: lo[1] + f * Lg
    z = lambda f: lo[2] + f * H
    torso = V[:, 2] > z(0.45)
    J = {}
    spine = []
    for f in (0.85, 0.65, 0.45, 0.3):                  # (pelvis ... chest, toward the head)
        c = _centre(V, _slab(V, 1, y(f), 0.04 * Lg) & torso, (x0, y(f), z(0.7)))
        spine.append(np.array([x0, y(f), c[2]]))
    J['pelvis'], J['spine'], J['chest'], J['neck'] = spine
    head = V[V[:, 1] < y(0.12)]
    hc = head.mean(0) if len(head) else np.array([x0, y(0.05), z(0.85)])
    J['head'] = np.array([x0, y(0.14), max(hc[2], spine[-1][2])])
    J['head_tip'] = np.array([x0, lo[1], hc[2]])
    tail = V[V[:, 1] > y(0.95)]
    J['tail_tip'] = np.array([x0, hi[1], tail[:, 2].mean() if len(tail) else spine[0][2]])
    side = V[:, 0] > x0 + 0.02 * (hi[0] - lo[0])
    for tag, (fa, fb) in (('F', (0.0, 0.5)), ('B', (0.5, 1.0))):
        m = side & (V[:, 1] >= y(fa)) & (V[:, 1] <= y(fb)) & (V[:, 2] < z(0.3))
        c = V[m].mean(0) if m.sum() >= 3 else np.array([x0 + 0.15 * H, y(0.5 * (fa + fb)), z(0.2)])
        col = side & (np.linalg.norm(V[:, :2] - c[:2], axis=1) < 0.12 * H)
        top = np.array([c[0], c[1], z(0.6)])
        knee = _centre(V, _slab(V, 2, z(0.32), 0.03 * H) & col, (c[0], c[1], z(0.32)))
        ankle = _centre(V, _slab(V, 2, z(0.08), 0.03 * H) & col, (c[0], c[1], z(0.08)))
        toe = np.array([ankle[0], ankle[1] - 0.08 * H, lo[2]])
        J[f'leg{tag}.L'] = top
        J[f'shin{tag}.L'] = knee
        J[f'foot{tag}.L'] = ankle
        J[f'toe{tag}.L'] = toe
    return J, H, x0


# --- armature building ------------------------------------------------------------------------------------------------

def _new_armature(context, name, at=None):
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    context.scene.collection.objects.link(ob)
    ob.show_in_front = True
    arm.display_type = 'OCTAHEDRAL'
    return ob


class _Edit:
    """Edit mode on an armature object for the ``with`` block (the selection and mode put back after)."""

    def __init__(self, context, ob):
        self.c, self.ob = context, ob

    def __enter__(self):
        c = self.c
        self.mode = c.mode
        self.active = c.view_layer.objects.active
        self.sel = list(c.selected_objects)
        if c.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        self.hidden = self.ob.hide_get()
        self.ob.hide_set(False)
        for o in self.sel:
            o.select_set(False)
        self.ob.select_set(True)
        c.view_layer.objects.active = self.ob
        bpy.ops.object.mode_set(mode='EDIT')
        return self.ob.data.edit_bones

    def __exit__(self, *exc):
        bpy.ops.object.mode_set(mode='OBJECT')
        self.ob.select_set(False)
        self.ob.hide_set(self.hidden)
        for o in self.sel:
            try:
                o.select_set(True)
            except (ReferenceError, RuntimeError):
                pass
        try:
            self.c.view_layer.objects.active = self.active
        except (ReferenceError, RuntimeError):
            pass
        return False


def _bone(ebs, name, head, tail, parent=None, connect=False, deform=True, roll_to=None):
    b = ebs.new(name)
    b.head = Vector(head)
    b.tail = Vector(tail)
    if (b.tail - b.head).length < 1e-5:
        b.tail = b.head + Vector((0, 0, 0.01))
    if parent is not None:
        b.parent = ebs[parent] if isinstance(parent, str) else parent
        b.use_connect = connect and (b.parent.tail - b.head).length < 1e-6
    b.use_deform = deform
    if roll_to is not None:
        b.align_roll(Vector(roll_to))
    return b


def build_body(context, body, quad=False, ik=True):
    """The armature for ``body`` (not bound).  Returns the armature object."""
    V = world_points(context, body)
    J, H, x0 = (quad_joints if quad else body_joints)(V)
    ob = _new_armature(context, body.name + '_Rig')
    ob[RIG_KEY] = 'QUAD' if quad else 'BODY'
    ob[BODY_KEY] = body.name
    with _Edit(context, ob) as ebs:
        if quad:
            root = _bone(ebs, 'root', (x0, J['pelvis'][1], V[:, 2].min()), (x0, J['pelvis'][1] - 0.2 * H, V[:, 2].min()),
                         deform=False)
            _bone(ebs, 'pelvis', J['pelvis'], J['spine'], root)
            _bone(ebs, 'spine', J['spine'], J['chest'], 'pelvis', True)
            _bone(ebs, 'chest', J['chest'], J['neck'], 'spine', True)
            _bone(ebs, 'neck', J['neck'], J['head'], 'chest', True)
            _bone(ebs, 'head', J['head'], J['head_tip'], 'neck', True)
            tail = [J['pelvis'] + (J['tail_tip'] - J['pelvis']) * f for f in np.linspace(0, 1, 5)]
            prev = 'pelvis'
            for i in range(4):
                _bone(ebs, f'tail.{i + 1:02d}', tail[i], tail[i + 1], prev, i > 0)
                prev = f'tail.{i + 1:02d}'
            for side, mir in (('L', False), ('R', True)):
                for tag, par in (('F', 'chest'), ('B', 'pelvis')):
                    p = {k: (mirror(J[f'{k}{tag}.L'], x0) if mir else J[f'{k}{tag}.L']) for k in ('leg', 'shin', 'foot', 'toe')}
                    _bone(ebs, f'leg{tag}.{side}', p['leg'], p['shin'], par, roll_to=(0, -1, 0))
                    _bone(ebs, f'shin{tag}.{side}', p['shin'], p['foot'], f'leg{tag}.{side}', True, roll_to=(0, -1, 0))
                    _bone(ebs, f'foot{tag}.{side}', p['foot'], p['toe'], f'shin{tag}.{side}', True)
                    if ik:
                        _limb_ik_bones(ebs, f'shin{tag}.{side}', f'foot{tag}.{side}', p['foot'], p['toe'], p['shin'],
                                       (0, -0.4 * H, 0), 'root')
        else:
            g = V[:, 2].min()
            root = _bone(ebs, 'root', (x0, J['hips'][1], g), (x0, J['hips'][1] - 0.15 * H, g), deform=False)
            _bone(ebs, 'hips', J['hips'], J['spine'], root)
            _bone(ebs, 'spine', J['spine'], J['chest'], 'hips', True)
            _bone(ebs, 'chest', J['chest'], J['neck'], 'spine', True)
            _bone(ebs, 'neck', J['neck'], J['head'], 'chest', True)
            _bone(ebs, 'head', J['head'], J['head_top'], 'neck', True)
            for side, mir in (('L', False), ('R', True)):
                p = {k: (mirror(v, x0) if mir else v) for k, v in J.items() if k.endswith('.L')}
                q = lambda k: p[k + '.L']
                _bone(ebs, f'shoulder.{side}', q('shoulder'), q('upper_arm'), 'chest')
                _bone(ebs, f'upper_arm.{side}', q('upper_arm'), q('forearm'), f'shoulder.{side}', True, roll_to=(0, 1, 0))
                _bone(ebs, f'forearm.{side}', q('forearm'), q('hand'), f'upper_arm.{side}', True, roll_to=(0, 1, 0))
                _bone(ebs, f'hand.{side}', q('hand'), q('hand_tip'), f'forearm.{side}', True)
                _bone(ebs, f'thigh.{side}', q('thigh'), q('shin'), 'hips', roll_to=(0, -1, 0))
                _bone(ebs, f'shin.{side}', q('shin'), q('foot'), f'thigh.{side}', True, roll_to=(0, -1, 0))
                _bone(ebs, f'foot.{side}', q('foot'), q('toe'), f'shin.{side}', True)
                if ik:
                    _limb_ik_bones(ebs, f'forearm.{side}', f'hand.{side}', q('hand'), q('hand_tip'), q('forearm'),
                                   (0, 0.35 * H, 0), 'root')
                    _limb_ik_bones(ebs, f'shin.{side}', f'foot.{side}', q('foot'), q('toe'), q('shin'),
                                   (0, -0.35 * H, 0), 'root')
    if ik:
        pairs = ([(f'shin{t}.{s}', f'foot{t}.{s}') for t in 'FB' for s in 'LR'] if quad else
                 [(f'forearm.{s}', f'hand.{s}') for s in 'LR'] + [(f'shin.{s}', f'foot.{s}') for s in 'LR'])
        for lower, end in pairs:
            _limb_ik(context, ob, lower, end)
    return ob


def _limb_ik_bones(ebs, lower, end, at, tip, mid, pole_off, root):
    """The IK target (a copy of the end bone, free) and the pole (off the middle joint) for one limb."""
    t = ebs.new(end + '_ik')
    t.head, t.tail = Vector(at), Vector(tip)
    t.roll = ebs[end].roll
    t.parent = ebs[root]
    t.use_deform = False
    p = ebs.new(lower + '_pole')
    p.head = Vector(mid) + Vector(pole_off)
    p.tail = p.head + Vector((0, 0, 0.05 * Vector(pole_off).length + 1e-3))
    p.parent = ebs[root]
    p.use_deform = False


def _limb_ik(context, ob, lower, end):
    """IK on ``lower`` (2 bones) to ``end``_ik with the pole; the end bone turns with its target.  The pole angle
    that keeps the rest pose still is chosen."""
    pbs = ob.pose.bones
    c = pbs[lower].constraints.new('IK')
    c.target, c.subtarget = ob, end + '_ik'
    c.pole_target, c.pole_subtarget = ob, lower + '_pole'
    c.chain_count = 2
    cr = pbs[end].constraints.new('COPY_ROTATION')
    cr.target, cr.subtarget = ob, end + '_ik'
    upper = pbs[lower].parent
    best = None
    for deg in (-90.0, 90.0, 0.0, 180.0, -45.0, 45.0, -135.0, 135.0):
        c.pole_angle = math.radians(deg)
        context.view_layer.update()
        err = sum((pb.matrix.to_translation() - pb.bone.matrix_local.to_translation()).length +
                  (pb.matrix.col[1].xyz - pb.bone.matrix_local.col[1].xyz).length +
                  (pb.matrix.col[0].xyz - pb.bone.matrix_local.col[0].xyz).length
                  for pb in (upper, pbs[lower]) if pb is not None)
        if best is None or err < best[0]:
            best = (err, deg)
    c.pole_angle = math.radians(best[1])
    context.view_layer.update()
    return best


# --- binding -------------------------------------------------------------------------------------------------------

def bind(context, mesh, arm):
    """Weights for ``mesh`` from ``arm``'s deform bones (Blender's automatic weights; nearest bones where they
    fail).  Returns 'auto' / 'nearest'."""
    for m in [m for m in mesh.modifiers if m.type == 'ARMATURE']:
        mesh.modifiers.remove(m)
    deform = [b.name for b in arm.data.bones if b.use_deform]
    for vg in [vg for vg in mesh.vertex_groups if vg.name in deform]:
        mesh.vertex_groups.remove(vg)
    keep_active, keep_sel = context.view_layer.objects.active, list(context.selected_objects)
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in keep_sel:
        o.select_set(False)
    mw = mesh.matrix_world.copy()
    mesh.select_set(True)
    arm.select_set(True)
    context.view_layer.objects.active = arm
    how = 'auto'
    try:
        with context.temp_override(active_object=arm, object=arm, selected_objects=[mesh, arm],
                                   selected_editable_objects=[mesh, arm]):
            bpy.ops.object.parent_set(type='ARMATURE_AUTO', keep_transform=True)
    except RuntimeError:
        how = 'nearest'
    mesh.matrix_world = mw
    if how == 'auto' and _unweighted(mesh, deform) > 0.02:
        how = 'nearest'
    if how == 'nearest':
        if mesh.parent is not arm:
            mesh.parent = arm
            mesh.matrix_parent_inverse = arm.matrix_world.inverted()
            mesh.matrix_world = mw
        nearest_weights(context, mesh, arm)
        if not any(m.type == 'ARMATURE' for m in mesh.modifiers):
            m = mesh.modifiers.new('Armature', 'ARMATURE')
            m.object = arm
    for o in list(context.selected_objects):
        o.select_set(False)
    for o in keep_sel:
        try:
            o.select_set(True)
        except (ReferenceError, RuntimeError):
            pass
    context.view_layer.objects.active = keep_active
    return how


def _unweighted(mesh, names):
    idx = {vg.index for vg in mesh.vertex_groups if vg.name in names}
    if not idx or not len(mesh.data.vertices):
        return 1.0
    miss = sum(1 for v in mesh.data.vertices if not any(g.group in idx and g.weight > 1e-4 for g in v.groups))
    return miss / len(mesh.data.vertices)


def nearest_weights(context, mesh, arm, falloff=4.0):
    """Every point weighted to its two nearest deform bones (by distance to the bone segment)."""
    bones = [b for b in arm.data.bones if b.use_deform]
    if not bones:
        return
    M = np.array(arm.matrix_world)
    H = np.array([tuple(b.head_local) for b in bones]) @ M[:3, :3].T + M[:3, 3]
    T = np.array([tuple(b.tail_local) for b in bones]) @ M[:3, :3].T + M[:3, 3]
    me = mesh.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    W = np.array(mesh.matrix_world)
    P = co.reshape(-1, 3) @ W[:3, :3].T + W[:3, 3]
    D = np.empty((len(P), len(bones)))
    for j in range(len(bones)):
        d = T[j] - H[j]
        t = np.clip(((P - H[j]) @ d) / max(d @ d, 1e-12), 0.0, 1.0)
        D[:, j] = np.linalg.norm(P - (H[j] + t[:, None] * d), axis=1)
    order = np.argsort(D, axis=1)[:, :2]
    groups = {}
    for b in bones:
        groups[b.name] = mesh.vertex_groups.get(b.name) or mesh.vertex_groups.new(name=b.name)
    for i in range(len(P)):
        a, b = order[i]
        da, db = D[i, a], D[i, b] if len(bones) > 1 else 1e9
        wa = 1.0 / max(da, 1e-6) ** falloff
        wb = 1.0 / max(db, 1e-6) ** falloff if len(bones) > 1 else 0.0
        s = wa + wb
        groups[bones[a].name].add([i], wa / s, 'REPLACE')
        if wb / s > 0.02:
            groups[bones[b].name].add([i], wb / s, 'REPLACE')


# --- mecha -----------------------------------------------------------------------------------------------------------

def _part_axis(context, ob):
    V = world_points(context, ob)
    if not len(V):
        p = np.array(ob.matrix_world.translation)
        return p, p + np.array([0, 0, 0.1])
    c = 0.5 * (V.min(0) + V.max(0))
    X = V - V.mean(0)
    try:
        _u, s, vt = np.linalg.svd(X[:: max(1, len(X) // 5000)], full_matrices=False)
        d = vt[0]
    except np.linalg.LinAlgError:
        d = np.array([0, 0, 1.0])
    proj = X @ d
    if d[2] < 0 or (abs(d[2]) < 1e-6 and d[0] < 0):
        d = -d
    half = 0.5 * (proj.max() - proj.min()) if len(proj) else 0.1
    return c, c + d * max(half, 1e-3)


def build_mecha(context, parts):
    parts = [p for p in parts if p.type == 'MESH']
    if not parts:
        raise RuntimeError('Select the mecha parts (meshes)')
    axes = {p.name: _part_axis(context, p) for p in parts}
    allp = np.array([a for a, _b in axes.values()])
    lo = min(world_points(context, p)[:, 2].min() for p in parts)
    ob = _new_armature(context, 'Mecha_Rig')
    ob[RIG_KEY] = 'MECHA'
    names = {}
    with _Edit(context, ob) as ebs:
        c = allp.mean(0)
        _bone(ebs, 'root', (c[0], c[1], lo), (c[0], c[1] - 0.25 * max(1e-3, np.ptp(allp[:, 1]) + np.ptp(allp[:, 2])), lo),
              deform=False)
        for p in parts:
            h, t = axes[p.name]
            names[p.name] = _bone(ebs, p.name, h, t, 'root').name
        for p in parts:                                        # (an object parent among the parts: kept as the order)
            par = p.parent
            while par is not None and par.name not in names:
                par = par.parent
            if par is not None:
                ebs[names[p.name]].parent = ebs[names[par.name]]
    for p in parts:
        attach(p, ob, names[p.name])
    return ob


def attach(part, arm, bone):
    """``part`` rides ``bone`` rigidly, staying where it is."""
    mw = part.matrix_world.copy()
    part.parent = arm
    part.parent_type = 'BONE'
    part.parent_bone = bone
    part[PART_KEY] = bone
    b = arm.data.bones[bone]
    tail = arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
    part.matrix_parent_inverse = tail.inverted()
    part.matrix_world = mw


def set_pivot(context, part, point):
    """``part``'s joint (its bone's start) to ``point`` (world); its bone keeps its direction and length."""
    arm = rig_of(part)
    bone = part.get(PART_KEY)
    if arm is None or bone not in arm.data.bones:
        raise RuntimeError('This part is not in a mecha rig')
    kids = [o for o in bpy.data.objects if o.parent is arm and o.get(PART_KEY)]
    keep = {o.name: o.matrix_world.copy() for o in kids}
    Mi = arm.matrix_world.inverted()
    with _Edit(context, arm) as ebs:
        b = ebs[bone]
        d = b.tail - b.head
        b.head = Mi @ Vector(point)
        b.tail = b.head + d
    for o in kids:
        attach(o, arm, o[PART_KEY])
        o.matrix_world = keep[o.name]


def through_middle(context, region, rv3d, ob, xy):
    """The point halfway between where the view ray at ``xy`` goes into ``ob`` and comes out (world), or None."""
    from bpy_extras import view3d_utils
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy).normalized()
    Mi = ob.matrix_world.inverted()
    lo, ld = Mi @ o, (Mi.to_3x3() @ d).normalized()
    hit, loc, _n, _i = ob.ray_cast(lo, ld)
    if not hit:
        return None
    first = loc
    out = loc
    p = loc + ld * 1e-4
    for _k in range(64):
        h2, l2, _n2, _i2 = ob.ray_cast(p, ld)
        if not h2:
            break
        out = l2
        p = l2 + ld * 1e-4
        if (out - first).length > 0:
            break
    return ob.matrix_world @ ((first + out) * 0.5)


# --- chain -------------------------------------------------------------------------------------------------------------

def chain_points(context, ob, n):
    """``n`` + 1 points along a long mesh (thick end first) or a curve (its first spline, start first)."""
    if ob.type == 'CURVE':
        dg = context.evaluated_depsgraph_get()
        me = ob.evaluated_get(dg).to_mesh()
        try:
            P = np.array([tuple(ob.matrix_world @ v.co) for v in me.vertices])
        finally:
            ob.evaluated_get(dg).to_mesh_clear()
        if len(P) < 2:
            raise RuntimeError('The curve is too short')
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        u = np.concatenate([[0], np.cumsum(seg)]) / max(seg.sum(), 1e-12)
        t = np.linspace(0, 1, n + 1)
        return np.stack([np.interp(t, u, P[:, d]) for d in range(3)], axis=1)
    V = world_points(context, ob)
    if len(V) < 4:
        raise RuntimeError('The mesh is too small for a chain')
    m = V.mean(0)
    _u, _s, vt = np.linalg.svd((V - m)[:: max(1, len(V) // 8000)], full_matrices=False)
    d = vt[0]
    s = (V - m) @ d
    lo, hi = s.min(), s.max()
    edges = np.linspace(lo, hi, 2 * n + 2)
    cent, size = [], []
    for i in range(2 * n + 1):
        msk = (s >= edges[i]) & (s <= edges[i + 1])
        if msk.sum() >= 3:
            c = V[msk].mean(0)
            cent.append(c)
            size.append(np.linalg.norm(V[msk] - c, axis=1).mean())
        else:
            cent.append(m + d * 0.5 * (edges[i] + edges[i + 1]))
            size.append(0.0)
    cent = np.array(cent)
    cent[0] = cent[0] + (cent[0] - cent[1]) * 0.5            # (out to the very ends)
    cent[-1] = cent[-1] + (cent[-1] - cent[-2]) * 0.5
    if np.mean(size[: len(size) // 3]) < np.mean(size[-(len(size) // 3):]):
        cent = cent[::-1]                                    # (the thick end first: the root)
    seg = np.linalg.norm(np.diff(cent, axis=0), axis=1)
    u = np.concatenate([[0], np.cumsum(seg)]) / max(seg.sum(), 1e-12)
    t = np.linspace(0, 1, n + 1)
    return np.stack([np.interp(t, u, cent[:, k]) for k in range(3)], axis=1)


def build_chain(context, ob, n, into=None):
    P = chain_points(context, ob, n)
    arm = into
    if arm is None:
        arm = _new_armature(context, ob.name + '_Rig')
        arm[RIG_KEY] = 'CHAIN'
    Mi = np.array(arm.matrix_world.inverted())
    L = P @ Mi[:3, :3].T + Mi[:3, 3]
    base = ob.name.replace('.', '_')
    names = []
    with _Edit(context, arm) as ebs:
        parent = None
        if into is not None and len(ebs):
            def dist(b):
                h, t = np.array(b.head), np.array(b.tail)
                d = t - h
                x = np.clip(((L[0] - h) @ d) / max(d @ d, 1e-12), 0, 1)
                return np.linalg.norm(L[0] - (h + x * d))
            parent = min(ebs, key=dist)
        for i in range(n):
            b = _bone(ebs, f'{base}.{i + 1:02d}', L[i], L[i + 1], parent, connect=i > 0)
            names.append(b.name)
            parent = b
    return arm, names


# --- jiggle (playback) ------------------------------------------------------------------------------------------------

_STATE = {}


def set_jiggle(arm, root, on, stiffness=0.25, damping=0.25):
    import json
    d = json.loads(arm.get(SPRING_KEY, '{}'))
    if on:
        d[root] = [float(stiffness), float(damping)]
    else:
        d.pop(root, None)
    arm[SPRING_KEY] = json.dumps(d)
    _ensure_handler()


def _chain_from(arm, root):
    out = [root]
    b = arm.pose.bones.get(root)
    while b is not None:
        kids = [c for c in b.children if c.bone.use_connect]
        if not kids:
            break
        b = kids[0]
        out.append(b.name)
    return out


@bpy.app.handlers.persistent
def _jiggle(scene, *_a):
    import json
    for arm in [o for o in scene.objects if o.type == 'ARMATURE' and o.get(SPRING_KEY)]:
        try:
            chains = json.loads(arm[SPRING_KEY])
        except (ValueError, TypeError):
            continue
        W = arm.matrix_world
        Wi = W.inverted()
        restart = scene.frame_current <= scene.frame_start
        for root, (k, damp) in chains.items():
            names = _chain_from(arm, root)
            for name in names:
                pb = arm.pose.bones.get(name)
                if pb is None:
                    continue
                par = pb.parent
                rel = (par.bone.matrix_local.inverted() @ pb.bone.matrix_local) if par is not None else pb.bone.matrix_local
                pose = (par.matrix @ rel) if par is not None else (pb.matrix if par is None else rel)
                head = W @ pose.to_translation()
                want = W @ (pose @ Vector((0, pb.bone.length, 0)))
                key = (arm.name, name)
                st = _STATE.get(key)
                if restart or st is None:
                    _STATE[key] = [want.copy(), Vector((0, 0, 0))]
                    pb.matrix = pose
                    continue
                pos, vel = st
                vel = (vel + (want - pos) * k) * (1.0 - damp)
                pos = pos + vel
                d0 = (want - head)
                d1 = (pos - head)
                if d1.length < 1e-9 or d0.length < 1e-9:
                    pb.matrix = pose
                    continue
                pos = head + d1.normalized() * d0.length          # (the bone keeps its length)
                _STATE[key] = [pos, vel]
                R = (Wi.to_3x3() @ d0).rotation_difference(Wi.to_3x3() @ (pos - head)).to_matrix().to_4x4()
                t = pose.to_translation()
                pb.matrix = Matrix.Translation(t) @ R @ Matrix.Translation(-t) @ pose


def _ensure_handler():
    if _jiggle not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_jiggle)


# --- operators ---------------------------------------------------------------------------------------------------------

class MCH_OT_rig_make(bpy.types.Operator):
    """Make the rig for the selection (the kind picked in the window: Human, Quadruped, Mecha, Chain)"""
    bl_idname = 'mch.rig_make'
    bl_label = 'Make Rig'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return settings(context) is not None and context.active_object is not None

    def execute(self, context):
        st = settings(context)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        sel = list(context.selected_objects)
        act = context.active_object
        try:
            if st.kind in {'BODY', 'QUAD'}:
                if act.type != 'MESH':
                    raise RuntimeError('Select the body mesh')
                arm = build_body(context, act, st.kind == 'QUAD', st.ik)
                how = bind(context, act, arm) if st.bind else ''
                msg = (f'{arm.name}: {len(arm.data.bones)} bones' + (' with IK' if st.ik else '')
                       + (f', {act.name} bound ({"automatic" if how == "auto" else "nearest-bone"} weights)' if how else ''))
                _show(context, arm)
            elif st.kind == 'MECHA':
                arm = build_mecha(context, sel or [act])
                msg = (f'{arm.name}: {len(arm.data.bones) - 1} parts, each on its bone - click a part with the Rig '
                       f'tool to set its joint')
                _show(context, arm)
            else:
                into = next((o for o in sel if o.type == 'ARMATURE'), None)
                src = act if act.type in {'MESH', 'CURVE'} else next((o for o in sel if o.type in {'MESH', 'CURVE'}), None)
                if src is None:
                    raise RuntimeError('Select the tail / tentacle mesh (or a curve)')
                arm, names = build_chain(context, src, st.bones, into)
                how = bind(context, src, arm) if st.bind and src.type == 'MESH' else ''
                if st.jiggle:
                    set_jiggle(arm, names[0], True, st.stiffness, st.damping)
                msg = (f'{arm.name}: a chain of {len(names)} bones' + (' (Jiggle on playback)' if st.jiggle else '')
                       + (f', {src.name} bound' if how else ''))
                _show(context, arm)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def _show(context, arm):
    for o in list(context.selected_objects):
        o.select_set(False)
    arm.select_set(True)
    context.view_layer.objects.active = arm


class MCH_OT_rig_bind(bpy.types.Operator):
    """Bind the selected mesh to the rig again (after Edit Bones): automatic weights, nearest bones where they fail"""
    bl_idname = 'mch.rig_bind'
    bl_label = 'Bind'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and (is_rig(ob) or rig_of(ob) is not None)

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        ob = context.active_object
        arm = rig_of(ob)
        if arm.get(RIG_KEY) == 'MECHA':
            n = 0
            for o in [o for o in bpy.data.objects if o.parent is arm and o.get(PART_KEY)]:
                mw = o.matrix_world.copy()
                attach(o, arm, o[PART_KEY])
                o.matrix_world = mw
                n += 1
            self.report({'INFO'}, f'{n} parts on their bones again')
            return {'FINISHED'}
        mesh = ob if ob.type == 'MESH' else bpy.data.objects.get(arm.get(BODY_KEY, ''))
        if mesh is None:
            mesh = next((o for o in context.selected_objects if o.type == 'MESH'), None)
        if mesh is None:
            self.report({'WARNING'}, 'Select the mesh to bind (with the rig)')
            return {'CANCELLED'}
        how = bind(context, mesh, arm)
        self.report({'INFO'}, f'{mesh.name} bound to {arm.name} ({"automatic" if how == "auto" else "nearest-bone"} weights)')
        return {'FINISHED'}


class MCH_OT_rig_edit(bpy.types.Operator):
    """Move the joints: the rig's Edit Mode (Tab back, then Bind again)"""
    bl_idname = 'mch.rig_edit'
    bl_label = 'Edit Bones'
    bl_options = {'REGISTER', 'UNDO'}
    mode: EnumProperty(items=[('EDIT', 'Edit', ''), ('POSE', 'Pose', ''), ('OBJECT', 'Done', '')], default='EDIT')

    @classmethod
    def poll(cls, context):
        return rig_of(context.active_object) is not None

    def execute(self, context):
        arm = rig_of(context.active_object)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if self.mode == 'OBJECT':
            return {'FINISHED'}
        for o in list(context.selected_objects):
            o.select_set(False)
        arm.hide_set(False)
        arm.select_set(True)
        context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode=self.mode)
        return {'FINISHED'}


class MCH_OT_rig_link(bpy.types.Operator):
    """Mecha: put the selected parts' bones under the active part's bone (the parts follow it)"""
    bl_idname = 'mch.rig_link'
    bl_label = 'Link to Active'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.get(PART_KEY) and rig_of(ob) is not None

    def execute(self, context):
        act = context.active_object
        arm = rig_of(act)
        kids = [o for o in context.selected_objects if o is not act and o.get(PART_KEY) and rig_of(o) is arm]
        if not kids:
            self.report({'WARNING'}, 'Select the child parts, then the parent part last (active)')
            return {'CANCELLED'}
        keep = {o.name: o.matrix_world.copy() for o in bpy.data.objects if o.parent is arm and o.get(PART_KEY)}
        with _Edit(context, arm) as ebs:
            for o in kids:
                if o[PART_KEY] != act[PART_KEY]:
                    ebs[o[PART_KEY]].parent = ebs[act[PART_KEY]]
        for name, mw in keep.items():
            o = bpy.data.objects[name]
            attach(o, arm, o[PART_KEY])
            o.matrix_world = mw
        self.report({'INFO'}, f'{len(kids)} part(s) under {act.name}')
        return {'FINISHED'}


class MCH_OT_rig_jiggle(bpy.types.Operator):
    """Jiggle on / off for the chains of the selected rig (playback)"""
    bl_idname = 'mch.rig_jiggle'
    bl_label = 'Jiggle'
    bl_options = {'REGISTER', 'UNDO'}
    on: BoolProperty(default=True)

    @classmethod
    def poll(cls, context):
        return rig_of(context.active_object) is not None

    def execute(self, context):
        arm = rig_of(context.active_object)
        st = settings(context)
        roots = [b.name for b in arm.data.bones if b.use_deform and not b.use_connect and
                 any(c.use_connect for c in b.children)]
        if arm.get(RIG_KEY) != 'CHAIN':
            roots = [r for r in roots if not any(r.startswith(p) for p in ('hips', 'pelvis', 'spine', 'thigh', 'upper_arm',
                                                                          'shoulder', 'leg', 'neck', 'chest'))]
        for r in roots:
            set_jiggle(arm, r, self.on, st.stiffness, st.damping)
        self.report({'INFO'}, f'Jiggle {"on" if self.on else "off"}: {len(roots)} chain(s)')
        return {'FINISHED'}


class MCH_OT_rig_click(bpy.types.Operator):
    """Rig tool click: on a mecha part - its joint where you clicked (in the middle of the part)"""
    bl_idname = 'mch.rig_click'
    bl_label = 'Rig Click'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        region, rv3d = context.region, context.region_data
        if region is None or rv3d is None:
            return {'PASS_THROUGH'}
        try:
            from . import ui_bars
            if ui_bars.over_ui(context, event.mouse_region_x, event.mouse_region_y):
                return {'PASS_THROUGH'}
        except (ImportError, AttributeError):
            pass
        from bpy_extras import view3d_utils
        xy = (event.mouse_region_x, event.mouse_region_y)
        o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
        d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
        dg = context.evaluated_depsgraph_get()
        hit, _loc, _n, _i, ob, _m = context.scene.ray_cast(dg, o, d)
        if not hit or ob is None:
            return {'PASS_THROUGH'}
        ob = ob.original
        if ob.get(PART_KEY) and rig_of(ob) is not None:
            p = through_middle(context, region, rv3d, ob, xy)
            if p is None:
                return {'CANCELLED'}
            try:
                set_pivot(context, ob, p)
            except RuntimeError as ex:
                self.report({'WARNING'}, str(ex))
                return {'CANCELLED'}
            for x in list(context.selected_objects):
                x.select_set(False)
            ob.select_set(True)
            context.view_layer.objects.active = ob
            self.report({'INFO'}, f'{ob.name}: joint set')
            return {'FINISHED'}
        for x in list(context.selected_objects):
            x.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {'FINISHED'}


class MCH_TOOL_rig(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.rig'
    bl_label = 'Rig'
    bl_description = 'Rig a body (Human / Quadruped), mecha parts or a chain; click a mecha part to set its joint'
    bl_icon = 'ops.generic.select'
    bl_widget = None
    bl_keymap = (('mch.rig_click', {'type': 'LEFTMOUSE', 'value': 'CLICK'}, None),)

    def draw_settings(context, layout, tool):
        return


def draw(layout, context):
    st = settings(context)
    if st is None:
        return
    from . import panel_capture as pc
    ob = context.active_object
    arm = rig_of(ob)
    box = layout.box()
    box.label(text='RIG', icon='ARMATURE_DATA')
    box.row(align=True).prop(st, 'kind', expand=True)
    col = box.column(align=True)
    if st.kind in {'BODY', 'QUAD'}:
        r = col.row(align=True)
        r.prop(st, 'ik', toggle=True)
        r.prop(st, 'bind', toggle=True)
        box.label(text='Select the body (feet on the ground, facing -Y)', icon='INFO')
    elif st.kind == 'MECHA':
        box.label(text='Select the parts; then click a part: its joint', icon='INFO')
    else:
        r = col.row(align=True)
        r.prop(st, 'bones')
        r.prop(st, 'bind', toggle=True)
        r = col.row(align=True)
        r.prop(st, 'jiggle', toggle=True)
        sub = r.row(align=True)
        sub.enabled = st.jiggle
        sub.prop(st, 'stiffness', slider=True)
        sub.prop(st, 'damping', slider=True)
        box.label(text='Select the tail / tentacle (+ a rig to add it to)', icon='INFO')
    r = pc.primary(box.row(align=True))
    r.scale_y = 1.3
    r.operator('mch.rig_make', text='Make Rig', icon='ARMATURE_DATA')
    if arm is not None:
        box = layout.box()
        box.label(text=f'{arm.name}  ({len(arm.data.bones)} bones)', icon='BONE_DATA')
        r = box.row(align=True)
        r.operator('mch.rig_edit', text='Edit Bones').mode = 'EDIT'
        r.operator('mch.rig_edit', text='Pose').mode = 'POSE'
        r.operator('mch.rig_bind', text='Bind')
        r = box.row(align=True)
        if arm.get(RIG_KEY) == 'MECHA':
            r.operator('mch.rig_link', text='Link to Active')
        r.operator('mch.rig_jiggle', text='Jiggle On').on = True
        r.operator('mch.rig_jiggle', text='Jiggle Off').on = False


CLASSES = (MCH_PG_Rig, MCH_OT_rig_make, MCH_OT_rig_bind, MCH_OT_rig_edit, MCH_OT_rig_link, MCH_OT_rig_jiggle,
           MCH_OT_rig_click)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_rig = PointerProperty(type=MCH_PG_Rig)
    _ensure_handler()
    try:
        bpy.utils.register_tool(MCH_TOOL_rig, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_rig)
    except (ValueError, RuntimeError, KeyError):
        pass
    if _jiggle in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_jiggle)
    if hasattr(bpy.types.Scene, 'mch_rig'):
        del bpy.types.Scene.mch_rig
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
