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
         ('BONES', 'Plain Bones', 'Plain bones, no IK (a tail, a tentacle: they sway in Auto Animation)'),
         ('EYE', 'Eye', 'Draw a circle round an eye (on the surface): an eye bone in it, looking at one shared target'),
         ('MOUTH', 'Mouth', 'Draw along the lips (on the surface): small lip bones along the line - the lower ones move '
                            'with the jaw'),
         ('FINGER', 'Finger', 'Draw along a finger (knuckle to tip): 3 bones on the hand; Finger Curl / Spread move all '
                              'the fingers at once')]
FACE = {'EYE', 'MOUTH', 'FINGER'}
SURFACE = {'EYE', 'MOUTH'}                           # (drawn on the skin; the others through the middle)


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


def _surface_normal(body, p):
    """The body's outward normal nearest to world point ``p``."""
    Mi = body.matrix_world.inverted()
    ok, _loc, n, _i = body.closest_point_on_mesh(Mi @ Vector(tuple(p)))
    if not ok:
        return np.array([0.0, -1.0, 0.0])
    w = (body.matrix_world.to_3x3().inverted().transposed() @ n).normalized()
    return np.array(tuple(w))


def _face_bones(ebs, body, face, made, size):
    """0.24.259 (user: "눈은 동그랗게 그리고, 입은 입 경계를 따라 그으면") eye and lip bones from the face lines.
    Returns (eye bone names, [(bone, centre, radius)] for the face weights)."""
    from . import rigging as rg

    def nearest(p, skip=()):
        pool = [m for m in made if m[3] not in skip] or made
        return min(pool, key=lambda m: _seg_dist(p, m[1], m[2]))[0] if pool else 'body'
    eyes, fw, ends, fingers, fj = [], [], [], [], []
    for kind, P in face:
        if kind == 'FINGER':
            # 0.24.259 (user: "손가락 리깅 - 한 번에 오므리고 펼 수 있게") knuckle first, 3 bones each
            if made and min(_seg_dist(P[-1], m[1], m[2]) for m in made) < min(_seg_dist(P[0], m[1], m[2]) for m in made):
                P = P[::-1]
            from . import auto_creature as ac
            fj.append((P, ac._resample(ac._smooth(ac._resample(P, 24), 1), 3)))
            continue
        if kind == 'EYE':
            c = P.mean(0)
            r = float(np.linalg.norm(P - c, axis=1).mean()) or 0.01 * size
            n = _surface_normal(body, c)
            e = c - n * r
            b = rg._bone(ebs, f'eye.{len(eyes) + 1:02d}', e, e + n * r, nearest(e))
            eyes.append(b.name)
            ends.append((e + n * r, n, r, b.parent.name if b.parent else 'body'))
            fw.append((b.name, [float(x) for x in c], 1.25 * r))
        else:
            L = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
            m = int(max(4, min(12, round(L / max(0.012 * size, 1e-6)))))
            from . import auto_creature as ac
            Q = ac._resample(P, m)
            sp = L / m
            # the lower lip (below the line through the mouth corners) rides the jaw - the nearest IK line - the
            # rest the head (the nearest body bone)
            ax = Q[-1] - Q[0]
            cz = lambda q: Q[0][2] + (q - Q[0]) @ ax / max(ax @ ax, 1e-12) * ax[2]
            for q in Q:
                n = _surface_normal(body, q)
                h = q - n * 0.5 * sp
                k_ = sum(1 for x in ebs if x.name.startswith('lip.')) + 1
                lower = q[2] < cz(q) - 0.15 * sp
                par = (nearest(h, skip=('BODY', 'AUTO', 'BONES', 'LEG')) if lower else
                       nearest(h, skip=('IK', 'BONES', 'LEG')))
                b = rg._bone(ebs, f'lip.{k_:02d}', h, q, par)
                b.use_connect = False
                fw.append((b.name, [float(x) for x in q], 0.8 * sp))
    if eyes:
        tip = np.mean([t for t, _n, _r, _p in ends], axis=0)
        nn = np.mean([n for _t, n, _r, _p in ends], axis=0)
        nn = nn / (np.linalg.norm(nn) or 1.0)
        rr = float(np.mean([r for _t, _n, r, _p in ends]))
        t = rg._bone(ebs, 'eyes_target', tip + nn * 8 * rr, tip + nn * 8 * rr + np.array([0, 0, rr]), ends[0][3],
                     deform=False)
        t.use_connect = False
    if fj:
        # the palm: a relaxed finger bows away from it; a straight one - across the row of knuckles, toward the body
        bases = np.array([J[0] for _P, J in fj])
        dirs = np.array([(J[-1] - J[0]) / (np.linalg.norm(J[-1] - J[0]) or 1.0) for _P, J in fj])
        dmean = dirs.mean(0)
        if len(fj) > 1:
            _u, _s, vt = np.linalg.svd(bases - bases.mean(0))
            row = vt[0]
        else:
            row = np.cross(dmean, (0.0, 0.0, 1.0)) if abs(dmean[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        guess = np.cross(row, dmean)
        to_body = np.array(tuple(body.matrix_world.translation)) - bases.mean(0)
        if guess @ to_body < 0:
            guess = -guess
        for P, J in fj:
            chord = J[-1] - J[0]
            mid = P[len(P) // 2]
            bow = mid - (P[0] + chord * float((mid - P[0]) @ chord / max(chord @ chord, 1e-12)))
            palm = -bow if np.linalg.norm(bow) > 0.06 * np.linalg.norm(chord) else guess
            names = []
            k_ = len(fingers) + 1
            parent = nearest(J[0])
            for i in range(3):
                b = rg._bone(ebs, f'finger{k_}.{i + 1:02d}', J[i], J[i + 1], parent if i == 0 else names[-1],
                             connect=i > 0)
                b.align_roll(Vector(tuple(palm)))
                names.append(b.name)
            fingers.append(names)
        # each finger's spread: away from the others, along its own side axis (X)
        c0 = bases.mean(0)
        offs = [float((bases[i] - c0) @ np.array(tuple(ebs[names[0]].x_axis))) for i, names in enumerate(fingers)]
        mx = max(abs(o) for o in offs) or 1.0
        fingers = [(names, -0.35 * o / mx) for names, o in zip(fingers, offs)]
    return eyes, fw, fingers


def finger_drivers(arm, fingers):
    """Finger Curl (-1 open .. 1 a fist) and Finger Spread on the armature drive every finger bone."""
    if not fingers:
        return
    for key, desc in (('mch_curl', 'Finger Curl'), ('mch_spread', 'Finger Spread')):
        arm[key] = 0.0
        try:
            arm.id_properties_ui(key).update(min=-1.0, max=1.0, soft_min=-1.0, soft_max=1.0, description=desc)
        except (AttributeError, TypeError):
            pass
    for names, side in fingers:
        for i, name in enumerate(names):
            pb = arm.pose.bones[name]
            pb.rotation_mode = 'XYZ'
            fc = pb.driver_add('rotation_euler', 0)
            d = fc.driver
            d.type = 'SCRIPTED'
            v = d.variables.new()
            v.name = 'c'
            v.targets[0].id = arm
            v.targets[0].data_path = '["mch_curl"]'
            d.expression = f'c * {1.25 if i else 0.9}'
            if i == 0:
                fc = pb.driver_add('rotation_euler', 2)
                d = fc.driver
                d.type = 'SCRIPTED'
                v = d.variables.new()
                v.name = 's'
                v.targets[0].id = arm
                v.targets[0].data_path = '["mch_spread"]'
                d.expression = f's * {side:.3f}'


def apply_face_weights(mesh, arm):
    """0.24.259 the eye / lip bones take the skin round them (full inside half the radius, fading to the radius),
    the other bones' weights there scaled down by as much."""
    try:
        specs = json.loads(arm.get('mch_face_w', '[]'))
    except (TypeError, ValueError):
        return 0
    if not specs:
        return 0
    me = mesh.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    M = np.array(mesh.matrix_world)
    P = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    gi = {g.name: g for g in mesh.vertex_groups}
    deform = {b.name for b in arm.data.bones if b.use_deform}
    touched = 0
    for name, c, r in specs:
        if name not in arm.data.bones:
            continue
        d = np.linalg.norm(P - np.array(c), axis=1)
        idx = np.nonzero(d < r)[0]
        if not len(idx):
            continue
        g = gi.get(name) or mesh.vertex_groups.new(name=name)
        gi[name] = g
        for i in idx:
            w = float(np.clip((r - d[i]) / max(0.5 * r, 1e-9), 0.0, 1.0))
            v = me.vertices[int(i)]
            for ge in v.groups:
                gn = mesh.vertex_groups[ge.group].name
                if gn != name and gn in deform:
                    ge.weight *= (1.0 - w)
            g.add([int(i)], w, 'REPLACE')
        touched += len(idx)
    return touched


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
    order = sorted(range(len(lines)), key=lambda i: (2 if kinds[i] in FACE else 0 if kinds[i] == 'BODY' else 1, i))
    if kinds[order[0]] not in {'BODY', 'AUTO'} or kinds[order[0]] in FACE:
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
        face = []
        for k, P in enumerate(lines):
            P = np.asarray(P, float)
            if kinds[k] in FACE:
                face.append((kinds[k], P))
                continue
            parent = bb.name
            if k > 0 and made:
                ds = min((_seg_dist(P[0], h, t), n) for n, h, t, _w in made)
                de = min((_seg_dist(P[-1], h, t), n) for n, h, t, _w in made)
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
                made.append((b.name, np.array(J[i]), np.array(J[i + 1]), want))
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
        eyes, fw, fingers = _face_bones(ebs, body, face, made, size)
    arm['mch_legs'] = json.dumps(legs)
    arm['mch_chains'] = json.dumps(chains)
    if fw:
        arm['mch_face_w'] = json.dumps(fw)
    finger_drivers(arm, fingers)
    for e in eyes:                                   # (the eyes look at the shared target)
        c = arm.pose.bones[e].constraints.new('DAMPED_TRACK')
        c.target, c.subtarget = arm, 'eyes_target'
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
    return arm, dict(legs=len(legs), chains=len(chains), trunk=len(trunk), bones=len(arm.data.bones), eyes=len(eyes),
                     lips=sum(1 for n in arm.data.bones.keys() if n.startswith('lip.')), fingers=len(fingers))


# --- drawing -----------------------------------------------------------------------------------------------------------

def _target_mesh(context):
    ob = context.active_object
    if ob is not None and ob.type == 'CURVE' and ob.get('mch_guides_for'):
        ob = bpy.data.objects.get(ob['mch_guides_for'])
    return ob if ob is not None and ob.type == 'MESH' else None


def _surface(context, ob, xy):
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy).normalized()
    Mi = ob.matrix_world.inverted()
    hit, loc, _n, _i = ob.ray_cast(Mi @ o, (Mi.to_3x3() @ d).normalized())
    return ob.matrix_world @ loc if hit else None


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
        xy = (event.mouse_region_x, event.mouse_region_y)
        if context.scene.mch_rig.guide_kind in SURFACE:   # 0.24.259 eyes / lips: on the surface
            p = _surface(context, self.mesh, xy)
        else:
            p = rg.through_middle(context, context.region, context.region_data, self.mesh, xy)
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
    r = col.row(align=True)
    for k_ in ('AUTO', 'BODY', 'LEG', 'IK', 'BONES'):
        r.prop_enum(st, 'guide_kind', k_)
    r = col.row(align=True)
    for k_ in ('EYE', 'MOUTH', 'FINGER'):
        r.prop_enum(st, 'guide_kind', k_)
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
