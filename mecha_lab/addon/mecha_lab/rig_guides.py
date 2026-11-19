"""0.24.258 Rig > Guides (user: "리그 만들기 전에 내가 표면에다가 가이드 라인을 그을 수는 없나?").

With the Rig tool and "Guides" picked, drag over the creature: the line is drawn through the MIDDLE of the body
under the mouse (where the view ray goes in and comes out), kept as a curve beside the mesh ("<mesh>_Guides").
Make Rig turns the lines into bones, as the Auto Creature does but where the user drew them:

* the first line is the body (spine / neck / head): a "body" bone at its start, bones along it;
* each other line hangs off the bone nearest to its start (drawn from the tip toward the body: turned round);
* a line that ends on the ground is a leg: split where it bends, a foot with IK and a knee pole - Auto Animation
  walks on those; the other lines are chains (arms, jaws, tails, tentacles) that sway.

The rig is an Auto Creature rig ('AUTO'): Bind, Mirror, Add / Remove IK, Auto Animation and the Unreal export all
work on it.
"""
import json

import bpy
import numpy as np
from mathutils import Vector

GUIDE_SUFFIX = '_Guides'


def guides_of(mesh):
    if mesh is None:
        return None
    ob = bpy.data.objects.get(mesh.name + GUIDE_SUFFIX)
    return ob if ob is not None and ob.type == 'CURVE' else None


def _guide_object(context, mesh):
    ob = guides_of(mesh)
    if ob is None:
        cu = bpy.data.curves.new(mesh.name + GUIDE_SUFFIX, 'CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = 0.0
        ob = bpy.data.objects.new(mesh.name + GUIDE_SUFFIX, cu)
        for coll in mesh.users_collection:
            coll.objects.link(ob)
        if not ob.users_collection:
            context.scene.collection.objects.link(ob)
        ob.show_in_front = True
        ob.hide_render = True
        ob.color = (1.0, 0.55, 0.1, 1.0)
        ob['mch_guides_for'] = mesh.name
    return ob


def strokes(mesh):
    """The guide lines (world points), in the order drawn."""
    ob = guides_of(mesh)
    if ob is None:
        return []
    M = ob.matrix_world
    out = []
    for sp in ob.data.splines:
        P = np.array([tuple(M @ Vector(p.co[:3])) for p in sp.points])
        if len(P) >= 2 and np.linalg.norm(np.diff(P, axis=0), axis=1).sum() > 0:
            out.append(P)
    return out


KINDS = [('AUTO', 'Auto', 'The first line the body; a line ending on the ground a leg; the others plain bones'),
         ('BODY', 'Body', 'The body / spine / neck / head: the bones everything hangs on'),
         ('LEG', 'Leg', 'A leg: IK on its foot, walked by Auto Animation'),
         ('IK', 'IK', 'Bones with IK at the end (an arm, a claw, a jaw): grab the end, the rest follows; not walked'),
         ('BONES', 'Plain Bones', 'Plain bones, no IK (a tail, a tentacle: they sway in Auto Animation)')]


def line_kinds(mesh):
    """The kind of each guide line ('AUTO' for the ones drawn before kinds)."""
    ob = guides_of(mesh)
    if ob is None:
        return []
    try:
        ks = json.loads(ob.get('mch_guide_kinds', '[]'))
    except (TypeError, ValueError):
        ks = []
    n = len(ob.data.splines)
    return (ks + ['AUTO'] * n)[:n]


def _set_kinds(ob, ks):
    ob['mch_guide_kinds'] = json.dumps(list(ks))


def add_stroke(context, mesh, P, kind='AUTO'):
    ob = _guide_object(context, mesh)
    _set_kinds(ob, line_kinds(mesh) + [kind])
    Mi = ob.matrix_world.inverted()
    sp = ob.data.splines.new('POLY')
    sp.points.add(len(P) - 1)
    for p, q in zip(sp.points, P):
        v = Mi @ Vector(tuple(q))
        p.co = (v.x, v.y, v.z, 1.0)
    return ob


def joints(P, kind, size):
    """Joints along a drawn line: as the Auto Creature's, but smoothed only lightly - a drawn line's corners are
    meant (the Auto Creature's heavy smoothing cut a knuckle-walking arm's wrist 19 cm off it)."""
    from . import auto_creature as ac
    from .rigging import bends
    P = ac._smooth(ac._resample(np.asarray(P, float), 40), 1)
    L = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
    if kind == 'LEG':
        bd = sorted(bends(P, 2, gap=6, lo=0.15, hi=0.88), key=lambda x: x[0])
        idx = [i for i, a in bd if a > 20.0] or [len(P) // 2]
        return np.array([P[0]] + [P[i] for i in idx] + [P[-1]]), L
    nb = int(max(2, min(8, round(L / max(1e-6, 0.08 * size)))))
    return ac._resample(P, nb), L


def _seg_dist(p, a, b):
    d = b - a
    t = float(np.clip((p - a) @ d / max(d @ d, 1e-12), 0.0, 1.0))
    return float(np.linalg.norm(p - (a + t * d)))


def build(context, body, lines, kinds=None):
    """The armature from the guide ``lines`` (world (n, 3) arrays, the first the body).  Returns (arm, info)."""
    from . import auto_creature as ac
    from . import rigging as rg
    if not lines:
        raise RuntimeError('Draw the guide lines first (Rig > Guides: drag over the creature; the first one is the body)')
    kinds = list(kinds or []) + ['AUTO'] * len(lines)
    kinds = kinds[:len(lines)]
    # 0.24.258 (user: "가장 베이스가 되는 몸, 뼈, IK 위치를 내가 잡으면") the user's kinds; the body lines first (the
    # first of them the root), the rest in the order drawn
    order = sorted(range(len(lines)), key=lambda i: (0 if kinds[i] == 'BODY' else 1, i))
    if kinds[order[0]] not in {'BODY', 'AUTO'}:
        raise RuntimeError('The first line (or one marked Body) is the body: draw it with Auto or Body')
    lines = [lines[i] for i in order]
    kinds = [kinds[i] for i in order]
    ik_ends = []
    V = rg.world_points(context, body)
    ground = float(V[:, 2].min())
    H = float(np.ptp(V[:, 2])) or 1.0
    size = max(H, float(np.ptp(V[:, 0])), float(np.ptp(V[:, 1])))
    arm = rg._new_armature(context, body.name + '_Rig')
    arm[rg.RIG_KEY] = 'AUTO'
    arm['mch_guides'] = 1
    arm.data.display_type = 'STICK'
    arm[rg.BODY_KEY] = body.name
    core = np.array(lines[0][0], float)
    legs, chains, trunk = [], [], []
    made = []                                        # [(bone name, head, tail)] to hang the next lines on
    with rg._Edit(context, arm) as ebs:
        rb = rg._bone(ebs, 'root', (core[0], core[1], ground), (core[0], core[1] - 0.15 * size, ground), deform=False)
        bb = rg._bone(ebs, 'body', core, core + np.array([0, 0, 0.06 * size]), rb)
        li = ci = ti = 0
        for k, P in enumerate(lines):
            P = np.asarray(P, float)
            parent = bb.name
            if k > 0 and made:
                ds = min((_seg_dist(P[0], h, t), n) for n, h, t in made)
                de = min((_seg_dist(P[-1], h, t), n) for n, h, t in made)
                if de[0] < ds[0]:                    # (drawn from the tip toward the body)
                    P = P[::-1]
                    ds = de
                parent = ds[1]
            onground = k > 0 and float(P[-1][2]) - ground < 0.05 * H
            want = kinds[k]
            if k == 0 or want == 'BODY':
                kind = 'TRUNK'
            elif want == 'LEG' or (want == 'AUTO' and onground):
                kind = 'LEG'
            else:
                kind = 'CHAIN'                       # (IK / Bones / Auto off the ground)
            J, ln = joints(P, kind, size)
            if kind == 'LEG':
                li += 1
                base = f'leg{li}'
                legs.append(base)
            elif kind == 'CHAIN':
                ci += 1
                base = f'limb{ci}'
                if want != 'IK':                     # (an IK line is held by its target, not swayed)
                    chains.append(base)
            else:
                ti += 1
                base = f'trunk{ti}'
                trunk.append(base)
            prev = parent
            names = []
            for i in range(len(J) - 1):
                b = rg._bone(ebs, f'{base}.{i + 1:02d}', J[i], J[i + 1], prev, connect=i > 0)
                names.append(b.name)
                made.append((b.name, np.array(J[i]), np.array(J[i + 1])))
                prev = b.name
            if kind == 'CHAIN' and want == 'IK':
                ik_ends.append((prev, len(names)))
            if kind == 'LEG':
                tip = J[-1]
                fwd = np.array([0.0, -1.0, 0.0])
                foot = rg._bone(ebs, f'{base}.foot', tip, tip + fwd * 0.03 * size, prev, connect=True)
                line_a, line_b = J[0], J[-1]
                mid = max(J[1:-1], key=lambda p: np.linalg.norm(np.cross(p - line_a, line_b - line_a))) \
                    if len(J) > 2 else 0.5 * (line_a + line_b)
                ab = line_b - line_a
                t = float((mid - line_a) @ ab / max(ab @ ab, 1e-12))
                off = mid - (line_a + t * ab)
                if np.linalg.norm(off) < 1e-4 * size:
                    off = np.array([0.0, -1.0, 0.0])
                off = off / np.linalg.norm(off) * 0.35 * ln
                rg._limb_ik_bones(ebs, names[-1], foot.name, tip, tip + fwd * 0.03 * size, mid, tuple(off), 'root')
    arm['mch_legs'] = json.dumps(legs)
    arm['mch_chains'] = json.dumps(chains)
    arm['mch_x0'] = float(core[0])
    offs, lens = {}, []
    for base in legs:
        names = sorted(n for n in arm.data.bones.keys() if n.startswith(base + '.') and n[len(base) + 1:].isdigit())
        lower = names[-1]
        b = arm.data.bones.get(lower + '_pole')
        if b is not None:
            offs[lower] = list(b.head_local - arm.data.bones[lower].head_local)
    arm['mch_pole_off'] = offs
    for base in legs:
        names = sorted(n for n in arm.data.bones.keys() if n.startswith(base + '.') and n[len(base) + 1:].isdigit())
        lower = names[-1]
        err, _deg = rg._limb_ik(context, arm, lower, base + '.foot', len(names))
        if len(names) > 2 and err > 0.01:
            pb = arm.pose.bones[lower]
            for c in [c for c in pb.constraints if c.type in {'IK', 'COPY_ROTATION'}]:
                pb.constraints.remove(c)
            fb = arm.pose.bones[base + '.foot']
            for c in [c for c in fb.constraints if c.type == 'COPY_ROTATION']:
                fb.constraints.remove(c)
            rg._limb_ik(context, arm, lower, base + '.foot', 2)
        lens.append(sum(arm.data.bones[n].length for n in names))
    arm['mch_leg_len'] = float(np.min(lens)) if lens else 0.3 * H
    for end, n in ik_ends:                           # (IK lines: the end grabbed, up to 3 bones bend)
        rg.add_ik(context, arm, [end], min(3, n))
    rg.controls(arm)
    return arm, dict(legs=len(legs), chains=len(chains), trunk=len(trunk), bones=len(arm.data.bones))


# --- drawing -----------------------------------------------------------------------------------------------------------

def _target_mesh(context):
    ob = context.active_object
    if ob is not None and ob.type == 'CURVE' and ob.get('mch_guides_for'):
        ob = bpy.data.objects.get(ob['mch_guides_for'])
    return ob if ob is not None and ob.type == 'MESH' else None


class MCH_OT_rig_guide_draw(bpy.types.Operator):
    """Rig tool, Guides: drag over the creature - a guide line through the middle of the body (Esc: drop it)"""
    bl_idname = 'mch.rig_guide_draw'
    bl_label = 'Draw Guide'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        st = getattr(context.scene, 'mch_rig', None)
        if st is None or st.kind != 'GUIDE' or context.region is None or context.region_data is None:
            return {'PASS_THROUGH'}
        try:
            from . import ui_bars
            if ui_bars.over_ui(context, event.mouse_region_x, event.mouse_region_y):
                return {'PASS_THROUGH'}
        except (ImportError, AttributeError):
            pass
        self.mesh = _target_mesh(context)
        if self.mesh is None:
            self.report({'WARNING'}, 'Select the creature mesh first')
            return {'CANCELLED'}
        self.size = max(self.mesh.dimensions) or 1.0
        self.pts = []
        self.guide = None
        self._add(context, event)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _add(self, context, event):
        from . import rigging as rg
        p = rg.through_middle(context, context.region, context.region_data, self.mesh,
                              (event.mouse_region_x, event.mouse_region_y))
        if p is None:
            return
        p = np.array(tuple(p))
        if self.pts and np.linalg.norm(p - self.pts[-1]) < 0.006 * self.size:
            return
        self.pts.append(p)
        if len(self.pts) >= 2:                       # (shown while drawing)
            if self.guide is None:
                self.guide = add_stroke(context, self.mesh, self.pts, context.scene.mch_rig.guide_kind)
                self.spline = self.guide.data.splines[-1]
            else:
                Mi = self.guide.matrix_world.inverted()
                self.spline.points.add(1)
                v = Mi @ Vector(tuple(p))
                self.spline.points[-1].co = (v.x, v.y, v.z, 1.0)
            context.area.tag_redraw()

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            self._add(context, event)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            if self.guide is None:
                return {'CANCELLED'}
            n = len(self.guide.data.splines)
            k = line_kinds(self.mesh)[-1]
            self.report({'INFO'}, f'Guide {n} ({dict((a, b) for a, b, _c in KINDS)[k]}): {len(self.pts)} points')
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            if self.guide is not None:
                ks = line_kinds(self.mesh)
                self.guide.data.splines.remove(self.spline)
                _set_kinds(self.guide, ks[:-1])
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_rig_guide_edit(bpy.types.Operator):
    """Guides: take the last one off, or all of them"""
    bl_idname = 'mch.rig_guide_edit'
    bl_label = 'Guides'
    bl_options = {'REGISTER', 'UNDO'}
    mode: bpy.props.EnumProperty(items=[('LAST', 'Take Last Off', 'The last line drawn taken off'),
                                        ('ALL', 'Clear All', 'All the lines taken off')])

    @classmethod
    def poll(cls, context):
        return guides_of(_target_mesh(context)) is not None

    def execute(self, context):
        g = guides_of(_target_mesh(context))
        sps = g.data.splines
        if self.mode == 'LAST' and len(sps):
            ks = line_kinds(_target_mesh(context))
            sps.remove(sps[-1])
            _set_kinds(g, ks[:-1])
        elif self.mode == 'ALL':
            sps.clear()
            _set_kinds(g, [])
        if not len(sps):
            cu = g.data
            bpy.data.objects.remove(g)
            if cu.users == 0:
                bpy.data.curves.remove(cu)
        return {'FINISHED'}


def draw(layout, context, st):
    mesh = _target_mesh(context)
    n = len(guides_of(mesh).data.splines) if guides_of(mesh) is not None else 0
    col = layout.column(align=True)
    col.label(text='Next line:')
    col.row(align=True).prop(st, 'guide_kind', expand=True)
    r = col.row(align=True)
    r.prop(st, 'bind', toggle=True)
    r = col.row(align=True)
    r.operator('mch.rig_guide_edit', text='Undo Last Line', icon='LOOP_BACK').mode = 'LAST'
    r.operator('mch.rig_guide_edit', text='Clear Guide Lines', icon='X').mode = 'ALL'
    if n:
        names = dict((a, b) for a, b, _c in KINDS)
        layout.label(text=', '.join(f'{i + 1} {names[k]}' for i, k in enumerate(line_kinds(mesh)))[:120], icon='CURVE_PATH')
    layout.label(text=f'{n} line(s): pick the kind, then drag over the creature', icon='INFO')


CLASSES = (MCH_OT_rig_guide_draw, MCH_OT_rig_guide_edit)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
