"""0.24.244 Auto Animation (user: "IK 로 리깅한 김에 언리얼 연동되는 프로시저럴 애니메이팅" - Auto Creature Locomotion):
a rig made by the Rig tool (Human, Reverse Legs, Quadruped) gets a looping cycle made by rule, not by hand -

* Idle    breathing (the chest rises and falls), the head drifting a little, the weight shifting;
* Walk / Run (Human) / Trot (Quadruped)   the feet step on the ground (each foot's IK target planted while it
  carries the body, lifted and swung forward in an arc while it does not - the legs bend by IK), the hips bob
  twice a cycle and sway side to side over the foot that carries them, the spine turns against the hips, the arms
  swing against the legs, the head steadies, the tail swings with a lag down its length.

The stride is worked out from the legs' length and the Speed; the cycle loops (In Place: the root stays - what a
game engine wants; else the root moves forward and the feet stay planted in the world).  Keyframes on the rig's
own bones (an Action ``<rig>_<Gait>``), so Blender plays it, edits it, and the FBX carries it.

Export to Unreal: the rig, its meshes and every action as one FBX made for Unreal (deform bones only, no leaf
bones, the animation baked onto the deform bones - the IK is not needed there).
"""
import math
import os

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from mathutils import Matrix, Vector

GAITS = [('IDLE', 'Idle', 'Breathing and the weight shifting, standing'),
         ('WALK', 'Walk', 'A walk: each foot on the ground most of the time'),
         ('RUN', 'Run', 'A run (Human) / trot (Quadruped): longer steps, both feet off the ground a moment')]


class MCH_PG_Loco(bpy.types.PropertyGroup):
    gait: EnumProperty(name='Gait', items=GAITS, default='WALK')
    speed: FloatProperty(name='Speed', default=1.0, min=0.1, max=5.0, subtype='FACTOR',
                         description='How fast, as a share of a natural pace for the legs\' length (1 = natural)')
    step_height: FloatProperty(name='Step Height', default=1.0, min=0.0, max=3.0, subtype='FACTOR',
                               description='How high the feet lift (x the natural height)')
    bob: FloatProperty(name='Body Bob', default=1.0, min=0.0, max=3.0, subtype='FACTOR',
                       description='How much the body goes up and down and sways (x natural)')
    arms: FloatProperty(name='Arm Swing', default=1.0, min=0.0, max=3.0, subtype='FACTOR',
                        description='How far the arms swing (Human)')
    tail: FloatProperty(name='Tail Sway', default=1.0, min=0.0, max=3.0, subtype='FACTOR',
                        description='How far the tail / chains swing')
    in_place: BoolProperty(name='In Place', default=True,
                           description='The root stays (a game engine moves the character); off: it walks forward')
    loops: IntProperty(name='Loops', default=1, min=1, max=20, description='Cycles to key (In Place: 1 loops for ever)')
    folder: StringProperty(name='Folder', default='//export/', subtype='DIR_PATH',
                           description='Where the Unreal FBX goes (// = next to the .blend)')


def settings(context):
    return getattr(context.scene, 'mch_loco', None)


# --- the rig, read -----------------------------------------------------------------------------------------------------

def legs_of(arm):
    """[(foot ik bone, phase group)] and the kind ('BODY' / 'QUAD')."""
    kind = arm.get('mch_rig')
    b = arm.data.bones
    if kind == 'QUAD':
        return [n for n in ('footF.L_ik', 'footF.R_ik', 'footB.L_ik', 'footB.R_ik') if n in b], 'QUAD'
    return [n for n in ('foot.L_ik', 'foot.R_ik') if n in b], 'BODY'


def leg_length(arm):
    b = arm.data.bones
    hip = b.get('thigh.L') or b.get('legB.L') or b.get('legF.L')
    foot = b.get('foot.L') or b.get('footB.L') or b.get('footF.L')
    if hip is None or foot is None:
        return 1.0
    return max(0.05, (hip.head_local - foot.head_local).length)


PHASES = {('BODY', 'WALK'): {'foot.L_ik': 0.0, 'foot.R_ik': 0.5},
          ('BODY', 'RUN'): {'foot.L_ik': 0.0, 'foot.R_ik': 0.5},
          ('QUAD', 'WALK'): {'footB.L_ik': 0.0, 'footF.L_ik': 0.25, 'footB.R_ik': 0.5, 'footF.R_ik': 0.75},
          ('QUAD', 'RUN'): {'footF.L_ik': 0.0, 'footB.R_ik': 0.0, 'footF.R_ik': 0.5, 'footB.L_ik': 0.5}}
DUTY = {'WALK': 0.62, 'RUN': 0.38}            # the share of a cycle each foot carries the body


def foot_offset(p, duty, stride, lift):
    """A foot's (forward, up) offset from its rest place at phase ``p`` (0..1) of the cycle.  Forward = -Y.
    Planted (duty share): from half a stride ahead to half behind, evenly (the body passes over it); then lifted in
    an arc and swung back ahead."""
    p = p % 1.0
    D = stride * duty                                    # (the body goes this far while the foot is down)
    if p < duty:
        t = p / duty
        return (0.5 - t) * D, 0.0
    t = (p - duty) / (1.0 - duty)
    s = 0.5 - 0.5 * math.cos(math.pi * t)              # (eases out of and into the ground)
    return (-0.5 + s) * D, lift * math.sin(math.pi * t)


def plan(arm, st, fps=24.0):
    """The cycle's numbers: frames, stride, lift, bob - from the legs' length and the settings."""
    L = leg_length(arm)
    gait = st.gait
    if gait == 'IDLE':
        return dict(frames=int(round(3.2 * fps)), stride=0.0, lift=0.0, bob=0.012 * L * st.bob, L=L)
    run = gait == 'RUN'
    # a natural pace: Froude-like - walk about 1.0 x sqrt(g L) per ... kept simple: cycle time ~ sqrt(L)
    cycle_s = (0.62 if run else 1.05) * math.sqrt(L / 0.9) / max(0.2, st.speed) ** 0.5
    stride = (1.1 if run else 0.7) * L * max(0.2, st.speed) ** 0.5
    return dict(frames=max(8, int(round(cycle_s * fps))), stride=stride,
                lift=(0.22 if run else 0.12) * L * st.step_height,
                bob=(0.05 if run else 0.025) * L * st.bob, L=L)


# --- keying -------------------------------------------------------------------------------------------------------------

def _rest(arm, name):
    return arm.data.bones[name].matrix_local.copy()


def _key(pb, frame, rot=True):
    pb.keyframe_insert('location', frame=frame, group=pb.name)
    if rot:
        pb.keyframe_insert('rotation_quaternion', frame=frame, group=pb.name)


def _set_world(arm, pb, M):
    """Pose bone ``pb`` to armature-space matrix ``M`` (its parent's pose as it is now)."""
    pb.matrix = M


def make_cycle(context, arm, st):
    """Key one cycle (or Loops cycles) on ``arm``.  Returns (action, info)."""
    kind = arm.get('mch_rig')
    if kind not in {'BODY', 'QUAD'}:
        raise RuntimeError('Auto Animation works on a Human / Quadruped rig made by the Rig tool')
    feet, kind = legs_of(arm)
    if st.gait != 'IDLE' and not feet:
        raise RuntimeError('This rig has no foot IK controls (make it with IK on)')
    fps = context.scene.render.fps / max(1e-6, context.scene.render.fps_base)
    P = plan(arm, st, fps)
    F = P['frames']
    loops = 1 if st.in_place else max(1, st.loops)
    name = f'{arm.name}_{dict((g[0], g[1]) for g in GAITS)[st.gait]}'
    if kind == 'QUAD' and st.gait == 'RUN':
        name = f'{arm.name}_Trot'
    if arm.animation_data is None:
        arm.animation_data_create()
    old = bpy.data.actions.get(name)
    if old is not None:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True                            # (kept in the file when another action is on)
    arm.animation_data.action = act
    pbs = arm.pose.bones
    for pb in pbs:
        pb.rotation_mode = 'QUATERNION'
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)
    context.view_layer.update()
    phases = PHASES.get((kind, 'RUN' if st.gait == 'RUN' else 'WALK'), {})
    duty = DUTY['RUN' if st.gait == 'RUN' else 'WALK']
    L, stride = P['L'], P['stride']
    body = 'hips' if kind == 'BODY' else 'pelvis'
    chest = 'chest'
    tail = sorted(n for n in pbs.keys() if n.startswith('tail.'))
    chain_roots = [b.name for b in arm.data.bones if b.use_deform and not b.use_connect and b.parent is not None
                   and b.parent.name in {body, 'pelvis', 'hips'} and any(c.use_connect for c in b.children)
                   and not b.name.startswith(('thigh', 'leg', 'spine', 'tail'))]
    rest = {n: _rest(arm, n) for n in pbs.keys()}
    crouch = (0.025 if st.gait == 'IDLE' else 0.07 if st.gait == 'WALK' else 0.11) * L    # (legs a little bent:
                                                                    #  the feet always reached)
    total = F * loops
    for f in range(total + 1):
        p = (f % F) / F if F else 0.0
        frame = context.scene.frame_start + f
        cyc = 2 * math.pi * p
        travel = 0.0 if st.in_place else (f / F) * stride
        # the root: forward when not in place
        if 'root' in pbs:
            pr = pbs['root']
            pr.matrix = Matrix.Translation((0, -travel, 0)) @ rest['root']
            _key(pr, frame, rot=False)
        context.view_layer.update()
        # the body
        if body in pbs:
            pb = pbs[body]
            if st.gait == 'IDLE':
                up = -crouch + P['bob'] * math.sin(cyc)
                side = 0.008 * L * st.bob * math.sin(cyc * 0.5)
                M = Matrix.Translation((side, 0, up)) @ rest[body]
            else:
                up = -crouch + P['bob'] * math.cos(2 * cyc)
                side = (0.018 if kind == 'BODY' else 0.008) * L * st.bob * math.sin(cyc)
                tw = Matrix.Rotation(math.radians((4.0 if kind == 'BODY' else 1.5) * st.bob) * math.sin(cyc), 4, 'Z')
                h = rest[body].to_translation()
                M = (Matrix.Translation((side, -travel, up)) @ Matrix.Translation(h) @ tw @ Matrix.Translation(-h)
                     @ rest[body])
            pb.matrix = M
            _key(pb, frame)
        context.view_layer.update()
        if chest in pbs and chest != body:
            pb = pbs[chest]
            if st.gait == 'IDLE':
                ang = math.radians(2.2 * st.bob) * math.sin(cyc)        # (breathing: the chest lifts)
                pb.rotation_quaternion = Matrix.Rotation(-ang, 3, 'X').to_quaternion()
            elif kind == 'BODY':                         # (a standing spine: the chest turns against the hips)
                pb.rotation_quaternion = Matrix.Rotation(math.radians(-6.0 * st.bob) * math.sin(cyc), 3, 'Y'
                                                         ).to_quaternion()
            else:                                        # (a lying spine: turning it would roll the front legs)
                pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            _key(pb, frame, rot=True)
        for hn in ('head', 'neck'):
            if hn in pbs:
                pb = pbs[hn]
                a = (math.radians(1.5) * math.sin(cyc * 0.5 + 0.7) if st.gait == 'IDLE'
                     else math.radians(2.0 * st.bob) * math.cos(2 * cyc))
                pb.rotation_quaternion = Matrix.Rotation(a, 3, 'X').to_quaternion()
                _key(pb, frame)
        # the feet: planted / swung
        for n in feet:
            pb = pbs[n]
            if st.gait == 'IDLE':
                pb.matrix = rest[n]
            else:
                fwd, lift = foot_offset(p + phases.get(n, 0.0), duty, stride, P['lift'])
                pitch = Matrix.Identity(4)
                if lift > 1e-6:                                 # (the toes down a little in the air)
                    h = rest[n].to_translation()
                    pitch = (Matrix.Translation(h) @ Matrix.Rotation(math.radians(-18.0) * lift / max(P['lift'], 1e-6),
                                                                      4, 'X') @ Matrix.Translation(-h))
                pb.matrix = Matrix.Translation((0, -fwd - travel, lift)) @ pitch @ rest[n]
            _key(pb, frame)
        # the arms (Human): against the legs
        if kind == 'BODY':
            for side, sgn in (('L', 1.0), ('R', -1.0)):
                n = f'hand.{side}_ik'
                if n not in pbs:
                    continue
                pb = pbs[n]
                if st.gait == 'IDLE':
                    pb.matrix = Matrix.Translation((0, 0, 0.004 * L * math.sin(cyc))) @ rest[n]
                else:
                    sw = (0.28 if st.gait == 'RUN' else 0.18) * L * st.arms * math.sin(cyc) * sgn
                    lift = abs(sw) * 0.25 + (0.06 * L if st.gait == 'RUN' else 0.0)
                    pb.matrix = Matrix.Translation((0, sw - travel, lift)) @ rest[n]
                _key(pb, frame)
        # tails and chains: a swing that lags down their length
        for chain in ([tail] if tail else []) + [_chain(arm, c) for c in chain_roots]:
            for i, n in enumerate(chain):
                pb = pbs[n]
                amp = math.radians((4.0 if st.gait == 'IDLE' else 9.0) * st.tail) * (0.6 + 0.4 * i / max(1, len(chain) - 1))
                a = amp * math.sin(cyc * (0.5 if st.gait == 'IDLE' else 1.0) - 0.6 * i)
                pb.rotation_quaternion = Matrix.Rotation(a, 3, 'Z').to_quaternion()
                _key(pb, frame)
    for fc in _fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR' if st.gait != 'IDLE' else 'BEZIER'
        if st.in_place and not any(m.type == 'CYCLES' for m in fc.modifiers):
            fc.modifiers.new('CYCLES')
    s = context.scene
    s.frame_end = s.frame_start + total - (1 if st.in_place else 0)
    s.frame_set(s.frame_start)
    return act, dict(frames=F, stride=stride, loops=loops, name=act.name)


def _fcurves(act):
    try:
        return list(act.fcurves)
    except AttributeError:                               # (5.x layered actions)
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out += list(bag.fcurves)
        return out


def _chain(arm, root):
    out = [root]
    b = arm.pose.bones.get(root)
    while b is not None:
        kids = [c for c in b.children if c.bone.use_connect]
        if not kids:
            break
        b = kids[0]
        out.append(b.name)
    return out


# --- Unreal -------------------------------------------------------------------------------------------------------------

def export_unreal(context, arm, path):
    """The rig, its meshes and its actions -> ``path`` (FBX for Unreal).  Returns the path."""
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and (o.parent is arm or any(
        m.type == 'ARMATURE' and m.object is arm for m in o.modifiers))]
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    keep_sel = list(context.selected_objects)
    keep_act = context.view_layer.objects.active
    for o in keep_sel:
        o.select_set(False)
    for o in [arm] + meshes:
        o.hide_set(False)
        o.select_set(True)
    context.view_layer.objects.active = arm
    try:
        r = bpy.ops.export_scene.fbx(
            filepath=path, use_selection=True, object_types={'ARMATURE', 'MESH'},
            apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', axis_forward='-Z', axis_up='Y',
            add_leaf_bones=False, use_armature_deform_only=True, primary_bone_axis='Y', secondary_bone_axis='X',
            bake_anim=True, bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
            bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0, mesh_smooth_type='FACE',
            use_mesh_modifiers=True)
    finally:
        for o in list(context.selected_objects):
            o.select_set(False)
        for o in keep_sel:
            try:
                o.select_set(True)
            except ReferenceError:
                pass
        context.view_layer.objects.active = keep_act
    if 'FINISHED' not in r:
        raise RuntimeError('FBX export did not finish')
    return path, len(meshes)


# --- operators ----------------------------------------------------------------------------------------------------------

def _rig(context):
    from . import rigging
    return rigging.rig_of(context.active_object)


class MCH_OT_loco_make(bpy.types.Operator):
    """Key a looping cycle on the selected rig (Idle / Walk / Run or Trot): the feet planted by IK, the body bobbing
    and swaying, the arms and the tail swinging"""
    bl_idname = 'mch.loco_make'
    bl_label = 'Make Animation'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        a = _rig(context)
        return a is not None and a.get('mch_rig') in {'BODY', 'QUAD'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        arm = _rig(context)
        try:
            act, info = make_cycle(context, arm, settings(context))
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, f'{info["name"]}: {info["frames"]} frames a cycle'
                    + (f', a stride of {info["stride"]:.2f}' if info['stride'] else '')
                    + (' (loops - Space plays it)' if settings(context).in_place else f', {info["loops"]} cycles forward'))
        return {'FINISHED'}


class MCH_OT_loco_export(bpy.types.Operator):
    """Export the rig, its meshes and its animations as one FBX for Unreal (deform bones only, the motion baked
    onto them)"""
    bl_idname = 'mch.loco_export'
    bl_label = 'Export to Unreal'
    bl_options = {'REGISTER'}
    filepath: StringProperty(default='', options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return _rig(context) is not None

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        arm = _rig(context)
        st = settings(context)
        path = self.filepath
        if not path:
            folder = bpy.path.abspath(st.folder or '//export/')
            if not bpy.data.filepath and folder.startswith('//'):
                folder = os.path.join(os.path.expanduser('~'), 'MechaLab_export')
            path = os.path.join(folder, bpy.path.clean_name(arm.name) + '_UE.fbx')
        try:
            out, n = export_unreal(context, arm, path)
        except (RuntimeError, OSError) as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, f'Unreal FBX: {out} ({n} mesh(es), the rig, its animations)')
        return {'FINISHED'}


def draw(layout, context):
    st = settings(context)
    arm = _rig(context)
    if st is None or arm is None or arm.get('mch_rig') not in {'BODY', 'QUAD'}:
        return
    from . import panel_capture as pc
    box = layout.box()
    box.label(text='AUTO ANIMATION', icon='ARMATURE_DATA')
    r = box.row(align=True)
    r.prop(st, 'gait', expand=True)
    col = box.column(align=True)
    col.prop(st, 'speed', slider=True)
    col.prop(st, 'step_height', slider=True)
    col.prop(st, 'bob', slider=True)
    if arm.get('mch_rig') == 'BODY':
        col.prop(st, 'arms', slider=True)
    col.prop(st, 'tail', slider=True)
    r = box.row(align=True)
    r.prop(st, 'in_place', toggle=True)
    sub = r.row(align=True)
    sub.enabled = not st.in_place
    sub.prop(st, 'loops')
    r = pc.primary(box.row(align=True))
    r.scale_y = 1.3
    r.operator('mch.loco_make', text='Make Animation', icon='PLAY')
    r = box.row(align=True)
    r.operator('mch.loco_export', text='Export to Unreal (FBX)', icon='EXPORT')
    r.prop(st, 'folder', text='')


CLASSES = (MCH_PG_Loco, MCH_OT_loco_make, MCH_OT_loco_export)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_loco = PointerProperty(type=MCH_PG_Loco)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_loco'):
        del bpy.types.Scene.mch_loco
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
