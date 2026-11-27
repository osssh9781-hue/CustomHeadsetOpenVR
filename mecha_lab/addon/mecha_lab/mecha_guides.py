"""0.24.338 Rig > Mecha Guides (user: "메카 리그도 가이드 라인 그을 수 있게 해 줘", "메카 네임도 네임 말고 그냥 가이드로 하게
해 줘", "가이드 그리면 한 덩어리당 본 하나야 명심해").

Select the mecha parts, pick Mecha Guides, drag lines over them with the Rig tool: a line runs through the MIDDLE of
whatever part is under the mouse (half way between where the view ray goes into the part and comes out of it), so it
follows the parts across the screen.  Make Rig:

* a part is a mesh object, or one loose piece of it (0.24.338: the user's spider is one object of 19 pieces - each
  piece its own part, the object stays one object, each piece's points wholly on its bone);
* every part a line passes through gets ONE bone - only one, however many lines cross it or how often;
* along a line the bones follow each other: the joint between two parts is where the line goes from the one into the
  other; a part's bone runs from the joint it is entered by to the joint it is left by (the line's end in the last);
* a line that starts in a part which already has a bone (drawn by an earlier line) hangs off that bone; the first line
  hangs on the root; a line starting in no boned part hangs off the bone nearest its start;
* Leg lines (and, on Auto, a line ending on the ground) get IK on their last part with a knee pole in front, IK lines
  (an arm, a claw) with an elbow pole behind - three parts or more on the line; Plain lines no IK;
* the parts no line crosses ride the bone of the part they are nearest to (no bone of their own);
* Seamless: the parts bend with their cuts shut (as Mecha Names); off: each part stiff on its bone.

The rig is a Mecha rig ('MECHA'): Turn Limit, Link, Auto Animation (the Leg lines walk), the Unreal export all work."""
from __future__ import annotations

import json

import bpy
import numpy as np
from mathutils import Vector

GUIDES = 'Mecha_Guides'
KINDS = [('AUTO', 'Auto', 'The first line the body; a line ending on the ground a leg (IK); the others plain'),
         ('BODY', 'Body', 'The body: the bones everything hangs on'),
         ('LEG', 'Leg', 'A leg: IK on its last part (knee in front), walked by Auto Animation'),
         ('IK', 'IK', 'An arm / a claw: IK on its last part (elbow behind)'),
         ('BONES', 'Plain', 'Plain bones, no IK')]


# --- the lines ---------------------------------------------------------------------------------------------------------

def guides():
    ob = bpy.data.objects.get(GUIDES)
    return ob if ob is not None and ob.type == 'CURVE' else None


def _guide_object(context):
    ob = guides()
    if ob is None:
        cu = bpy.data.curves.new(GUIDES, 'CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = 0.0
        ob = bpy.data.objects.new(GUIDES, cu)
        context.scene.collection.objects.link(ob)
        ob.show_in_front = True
        ob.hide_select = True
        ob.hide_render = True
    return ob


def _owners(ob):
    try:
        return json.loads(ob.get('mch_guide_parts', '[]'))
    except (TypeError, ValueError):
        return []


def lines():
    """[(points (n, 3) world, kind, the part under each point when drawn or None)] in the order drawn."""
    ob = guides()
    if ob is None:
        return []
    try:
        ks = json.loads(ob.get('mch_guide_kinds', '[]'))
    except (TypeError, ValueError):
        ks = []
    M = ob.matrix_world
    own = _owners(ob)
    out = []
    for i, sp in enumerate(ob.data.splines):
        P = np.array([tuple(M @ Vector(p.co[:3])) for p in sp.points])
        o = own[i] if i < len(own) and own[i] and len(own[i]) == len(P) else None
        if len(P) >= 2:
            out.append((P, ks[i] if i < len(ks) else 'AUTO', o))
    return out


def add_line(context, P, kind, owners=None):
    """A guide line: its points, its kind, and (drawn) the part under each point."""
    ob = _guide_object(context)
    own = _owners(ob)
    own = (own + [None] * len(ob.data.splines))[:len(ob.data.splines)] + [list(owners) if owners else None]
    ob['mch_guide_parts'] = json.dumps(own)
    try:
        ks = json.loads(ob.get('mch_guide_kinds', '[]'))
    except (TypeError, ValueError):
        ks = []
    ks = (ks + ['AUTO'] * len(ob.data.splines))[:len(ob.data.splines)] + [kind]
    ob['mch_guide_kinds'] = json.dumps(ks)
    Mi = ob.matrix_world.inverted()
    sp = ob.data.splines.new('POLY')
    sp.points.add(len(P) - 1)
    for p, q in zip(sp.points, P):
        v = Mi @ Vector(tuple(q))
        p.co = (v.x, v.y, v.z, 1.0)
    return sp


def drop_line(which='LAST'):
    ob = guides()
    if ob is None:
        return 0
    try:
        ks = json.loads(ob.get('mch_guide_kinds', '[]'))
    except (TypeError, ValueError):
        ks = []
    sps = ob.data.splines
    own = _owners(ob)
    if which == 'LAST' and len(sps):
        sps.remove(sps[-1])
        ks, own = ks[:len(sps)], own[:len(sps)]
    elif which == 'ALL':
        sps.clear()
        ks, own = [], []
    ob['mch_guide_kinds'] = json.dumps(ks)
    ob['mch_guide_parts'] = json.dumps(own)
    n = len(sps)
    if not n:
        cu = ob.data
        bpy.data.objects.remove(ob)
        if cu.users == 0:
            bpy.data.curves.remove(cu)
    return n


class Piece:
    """A part: one loose piece of a mesh object (an object made of several pieces - a spider's legs in one mesh - is
    several parts, each its own bone)."""

    def __init__(self, name, obj, verts, V, tree):
        self.name, self.obj, self.verts, self.V, self.tree = name, obj, verts, V, tree


_PIECES = {}


def pieces_of(objs):
    """The parts of the mesh objects ``objs``: [Piece] - an object of one piece is one part named as the object; an
    object of several loose pieces gives one part each ("<object>.p00", ".p01" ... in the order of their points)."""
    from mathutils.bvhtree import BVHTree
    import bmesh
    out = []
    for ob in objs:
        if ob.type != 'MESH':
            continue
        me = ob.data
        key = (ob.name, len(me.vertices), len(me.polygons), tuple(round(x, 6) for r in ob.matrix_world for x in r))
        if key in _PIECES:
            out.extend(_PIECES[key])
            continue
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        seen, isl = set(), []
        for v in bm.verts:
            if v.index in seen:
                continue
            st, comp = [v], []
            seen.add(v.index)
            while st:
                u = st.pop()
                comp.append(u.index)
                for e in u.link_edges:
                    w = e.other_vert(u)
                    if w.index not in seen:
                        seen.add(w.index)
                        st.append(w)
            isl.append(sorted(comp))
        isl.sort(key=lambda c: c[0])
        M = ob.matrix_world
        W = [M @ v.co for v in me.vertices]
        faces_of = {}
        where = {}
        for k, c in enumerate(isl):
            for i in c:
                where[i] = k
        for f in me.polygons:
            faces_of.setdefault(where[f.vertices[0]], []).append(list(f.vertices))
        bm.free()
        mine = []
        for k, c in enumerate(isl):
            fs = faces_of.get(k, [])
            if not fs:
                continue
            remap = {i: j for j, i in enumerate(c)}
            Vk = [W[i] for i in c]
            tree = BVHTree.FromPolygons(Vk, [[remap[i] for i in f] for f in fs])
            name = ob.name if len(isl) == 1 else f'{ob.name}.p{k:02d}'
            mine.append(Piece(name, ob, c, np.array([tuple(v) for v in Vk]), tree))
        if len(mine) == 1:
            mine[0].name = ob.name
        _PIECES[key] = mine
        out.extend(mine)
    return out


def through_part(context, parts, o, d, pieces=None):
    """The middle of the first part the view ray (world ``o``, ``d``) goes through: (point, Piece) or None.
    ``parts``: mesh objects (their loose pieces are the parts)."""
    pcs = pieces if pieces is not None else pieces_of(parts)
    o, d = Vector(tuple(o)), Vector(tuple(d)).normalized()
    best = None
    for pc in pcs:
        loc, _n, _i, t_in = pc.tree.ray_cast(o, d)
        if loc is None or (best is not None and t_in >= best[0]):
            continue
        eps = 1e-6 * max(float(np.ptp(pc.V, axis=0).max()), 1e-6)
        q, depth, t_out = loc + d * eps, 1, None
        for _k in range(32):
            loc2, n2, _i2, _t2 = pc.tree.ray_cast(q, d)
            if loc2 is None:
                break
            depth += 1 if n2.dot(d) < 0 else -1
            if depth <= 0:
                t_out = (loc2 - o).length
                break
            q = loc2 + d * eps
        if t_out is None:
            t_out = t_in
        best = (t_in, 0.5 * (t_in + t_out), pc)
    if best is None:
        return None
    return np.array(tuple(o + d * best[1])), best[2]


# --- the rig -----------------------------------------------------------------------------------------------------------

def _inside(pc, p, tol):
    """Is the world point ``p`` inside the part ``pc`` (or on it)?  (inside, distance off it)"""
    loc, n, _i, dist = pc.tree.find_nearest(Vector(tuple(p)))
    if loc is None:
        return False, np.inf
    inside = (Vector(tuple(p)) - loc).dot(n) < 0
    return inside or dist < tol, (0.0 if inside else dist)


def _resample(P, step):
    P = np.asarray(P, float)
    s = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))))
    n = max(2, int(s[-1] / max(step, 1e-9)) + 1)
    u = np.linspace(0, s[-1], n)
    return np.stack([np.interp(u, s, P[:, i]) for i in range(3)], axis=1)


def walk(P, pcs, step, tol, owners=None):
    """The parts the line ``P`` runs through, in order, each once: [(Piece, entry point, exit point)]; the joint
    between two parts half way between the line's last point in the one and its first in the next.  ``owners``: the
    part under each point when it was drawn (what the user saw - parts inside parts are not guessed)."""
    by = {pc.name: pc for pc in pcs}
    if owners is not None and any(n in by for n in owners):
        return _runs(np.asarray(P, float), [by.get(n) for n in owners])
    D = _resample(P, step)
    boxes = {pc.name: (pc.V.min(0) - tol, pc.V.max(0) + tol) for pc in pcs}
    owner = []
    for q in D:
        cand = []
        for pc in pcs:
            lo, hi = boxes[pc.name]
            if (q < lo).any() or (q > hi).any():
                continue
            ins, dist = _inside(pc, q, tol)
            if ins:
                cand.append((dist, pc))
        owner.append(min(cand, key=lambda c: c[0])[1] if cand else None)
    return _runs(D, owner)


def _runs(D, owner):
    runs = []                                        # [(part, first index, last index)]
    for i, p in enumerate(owner):
        if p is None:
            continue
        if runs and runs[-1][0] is p:
            runs[-1][2] = i
        else:
            runs.append([p, i, i])
    seen, out = set(), []
    for k, (p, a, b) in enumerate(runs):
        if p.name in seen:                           # (one bone a part: a part met again adds nothing)
            continue
        seen.add(p.name)
        prev = runs[k - 1] if k > 0 else None
        nxt = runs[k + 1] if k + 1 < len(runs) else None
        head = 0.5 * (D[prev[2]] + D[a]) if prev is not None else D[a]
        tail = 0.5 * (D[b] + D[nxt[1]]) if nxt is not None else D[b]
        out.append((p, head, tail))
    return out


def build(context, parts, glines, seamless=False):
    """The rig from the guide lines ``glines`` [(points, kind, owners)] over the mesh objects ``parts`` (their loose
    pieces are the parts).  Returns (armature, report)."""
    from . import rigging as rg
    objs = [p for p in parts if p.type == 'MESH']
    if not objs:
        raise RuntimeError('Select the mecha parts')
    if not glines:
        raise RuntimeError('Draw guide lines over the parts first (Rig tool, drag)')
    _PIECES.clear()
    pcs = pieces_of(objs)
    allV = np.concatenate([pc.V for pc in pcs])
    ground = float(allV[:, 2].min())
    size = float(np.ptp(allV, axis=0).max()) or 1.0
    H = float(np.ptp(allV[:, 2])) or size
    step, tol = 0.004 * size, 0.002 * size
    bone_of = {}                                     # part name -> bone (= the part's name)
    heads, tails, parent = {}, {}, {}
    chains, order = [], []
    for li, gl in enumerate(glines):
        P, kind = gl[0], gl[1]
        seq = walk(P, pcs, step, tol, gl[2] if len(gl) > 2 else None)
        if not seq:
            continue
        mine, anchor = [], None
        for k, (pc, h, t) in enumerate(seq):
            if pc.name in bone_of:                   # (already boned by an earlier line: hang the rest from it)
                anchor = bone_of[pc.name]
                mine = []
                continue
            b = pc.name
            bone_of[pc.name] = b
            heads[b], tails[b] = h, t
            if mine:
                parent[b] = mine[-1]
            elif anchor is not None:
                parent[b] = anchor
            elif order:                              # (starts in no boned part: off the bone nearest its start)
                def dist(bn, h=h):
                    a_, c_ = heads[bn], tails[bn]
                    d_ = c_ - a_
                    tt = float(np.clip((h - a_) @ d_ / max(d_ @ d_, 1e-12), 0, 1))
                    return float(np.linalg.norm(h - (a_ + tt * d_)))
                parent[b] = min(order, key=dist)
            else:
                parent[b] = None
            mine.append(b)
            order.append(b)
        if mine:
            ends_low = float(P[-1][2]) - ground < 0.06 * H
            k_ = kind if kind != 'AUTO' else ('BODY' if li == 0 else ('LEG' if ends_low else 'BONES'))
            chains.append((k_, mine))
    if not order:
        raise RuntimeError('No guide line runs through the selected parts')
    # IK limbs: the last three own bones of a Leg / IK line (upper, lower, end); a two-part leg: IK on its two
    limbs = []
    for kind, mine in chains:
        if kind in {'LEG', 'IK'} and len(mine) >= 2:
            bend = np.array((0.0, -1.0, 0.0)) if kind == 'LEG' else np.array((0.0, 1.0, 0.0))
            if len(mine) >= 3:
                limbs.append((mine[-3], mine[-2], mine[-1], bend, kind))
            else:
                limbs.append((None, mine[-2], mine[-1], bend, kind))
    for u, l_, e, bend, _k in limbs:                 # (straight: the middle joint a hair the way it bends)
        if u is None:
            continue
        a, m, f = heads[u], heads[l_], heads[e]
        ab = f - a
        t = float((m - a) @ ab / max(ab @ ab, 1e-12))
        off = m - (a + t * ab)
        if float(off @ bend) < 0.02 * np.linalg.norm(ab):
            heads[l_] = m + bend * (0.03 * np.linalg.norm(ab) - float(off @ bend))
            tails[u] = heads[l_]
    for b in order:
        if np.linalg.norm(tails[b] - heads[b]) < 1e-3 * size:
            tails[b] = heads[b] + np.array([0, 0, 0.03 * size])
    ob = rg._new_armature(context, 'Mecha_Rig')
    ob[rg.RIG_KEY] = 'MECHA'
    ob['mch_guided'] = True
    body = order[0]
    ob['mch_body_bone'] = body
    ob['mch_x0'] = float(heads[body][0])
    with rg._Edit(context, ob) as ebs:
        c = heads[body]
        rg._bone(ebs, 'root', (c[0], c[1], ground), (c[0], c[1] - 0.15 * size, ground), deform=False)
        for b in order:
            rg._bone(ebs, b, heads[b], tails[b], 'root')
        for b in order:
            if parent.get(b) is not None:
                ebs[b].parent = ebs[parent[b]]
        for u, l_, e, bend, _k in limbs:
            f = ebs[e]
            mid = heads[l_] if u is not None else tails[l_]
            top = heads[u] if u is not None else heads[l_]
            ab = heads[e] - top if u is not None else tails[e] - top
            tt = float((mid - top) @ ab / max(ab @ ab, 1e-12))
            off = mid - (top + tt * ab)
            if np.linalg.norm(off) < 1e-6 or (u is not None and float(off @ bend) < 0.5 * np.linalg.norm(off)):
                off = bend
            off = off / np.linalg.norm(off) * 0.5 * float(np.linalg.norm(ab))
            rg._limb_ik_bones(ebs, l_, e, f.head.copy(), f.tail.copy(), mid, tuple(off), 'root')
    # the parts no line crosses: on the bone of the part nearest them
    from mathutils.kdtree import KDTree
    boned = [pc for pc in pcs if pc.name in bone_of]
    src = [(bone_of[pc.name], v) for pc in boned for v in pc.V[:: max(1, len(pc.V) // 400)]]
    kd = KDTree(len(src))
    for i, (_b, v) in enumerate(src):
        kd.insert(v, i)
    kd.balance()
    owner = {pc.name: bone_of[pc.name] for pc in boned}
    rode = {}
    for pc in pcs:
        if pc.name in owner:
            continue
        votes = {}
        for v in pc.V[:: max(1, len(pc.V) // 200)]:
            bn = src[kd.find(v)[1]][0]
            votes[bn] = votes.get(bn, 0) + 1
        owner[pc.name] = rode[pc.name] = max(votes, key=votes.get)
    # put the parts on their bones: an object of one part rides its bone (or Seamless); an object of several
    # pieces stays one object, each piece's points wholly on its own bone (an Armature modifier)
    single = [o for o in objs if sum(1 for pc in pcs if pc.obj is o) == 1]
    multi = [o for o in objs if o not in single]
    if seamless and single:
        from . import mecha_named
        mecha_named.skin(context, ob, single, {o.name: owner[o.name] for o in single if o.name in owner})
    else:
        for o in single:
            if o.name in owner:
                rg.attach(o, ob, owner[o.name])
    for o in multi:
        mw = o.matrix_world.copy()
        for m in [m for m in o.modifiers if m.type == 'ARMATURE']:
            o.modifiers.remove(m)
        for pc in [pc for pc in pcs if pc.obj is o]:
            bn = owner.get(pc.name)
            if bn is None:
                continue
            vg = o.vertex_groups.get(bn) or o.vertex_groups.new(name=bn)
            vg.add(pc.verts, 1.0, 'REPLACE')
        m = o.modifiers.new('Armature', 'ARMATURE')
        m.object = ob
        o.parent = ob
        o.parent_type = 'OBJECT'
        o.matrix_parent_inverse = ob.matrix_world.inverted()
        o.matrix_world = mw
        o[rg.PART_KEY] = order[0]
    offs = {}
    for u, l_, e, _b, _k in limbs:
        pb = ob.data.bones.get(l_ + '_pole')
        if pb is not None:
            offs[l_] = list(pb.head_local - ob.data.bones[l_].head_local)
    ob['mch_pole_off'] = offs
    for u, l_, e, _b, _k in limbs:
        rg._limb_ik(context, ob, l_, e, 2 if u is not None else 1)
    legs = [e for _u, _l, e, _b, k in limbs if k == 'LEG']
    ob['mch_legs'] = json.dumps(legs)
    lens = [float(np.linalg.norm(heads[e] - heads[u if u is not None else l_])) for u, l_, e, _b, k in limbs
            if k == 'LEG']
    ob['mch_leg_len'] = float(min(lens)) if lens else 0.3 * H
    rg.controls(ob)
    g = guides()
    if g is not None:
        g.hide_set(True)
    return ob, dict(bones=order, chains=chains, ik=[e for _u, _l, e, _b, _k in limbs], legs=legs, rode=rode,
                    parent={b: parent.get(b) for b in order})


# --- drawing -----------------------------------------------------------------------------------------------------------

class MCH_OT_mecha_guide_draw(bpy.types.Operator):
    """Rig tool, Mecha Guides: drag over the parts - a guide line through the middle of the parts under the mouse
    (Esc / right click: drop it)"""
    bl_idname = 'mch.mecha_guide_draw'
    bl_label = 'Draw Mecha Guide'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        st = getattr(context.scene, 'mch_rig', None)
        if st is None or st.kind != 'MGUIDE' or context.region is None or context.region_data is None:
            return {'PASS_THROUGH'}
        try:
            from . import ui_bars
            if ui_bars.over_ui(context, event.mouse_region_x, event.mouse_region_y):
                return {'PASS_THROUGH'}
        except (ImportError, AttributeError):
            pass
        self.parts = [o for o in context.selected_objects if o.type == 'MESH']
        if not self.parts:
            self.parts = [o for o in context.visible_objects if o.type == 'MESH']
        if not self.parts:
            self.report({'WARNING'}, 'Select the mecha parts first')
            return {'CANCELLED'}
        size = max(max(p.dimensions) for p in self.parts) or 1.0
        self.gap = 0.004 * size
        self.pieces = pieces_of(self.parts)
        self.pts, self.own, self.spline = [], [], None
        self._add(context, event)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _add(self, context, event):
        from bpy_extras import view3d_utils
        xy = (event.mouse_region_x, event.mouse_region_y)
        o = view3d_utils.region_2d_to_origin_3d(context.region, context.region_data, xy)
        d = view3d_utils.region_2d_to_vector_3d(context.region, context.region_data, xy)
        hit = through_part(context, self.parts, o, d, self.pieces)
        if hit is None:
            return
        p = hit[0]
        if self.pts and np.linalg.norm(p - self.pts[-1]) < self.gap:
            return
        self.pts.append(p)
        self.own.append(hit[1].name)
        if len(self.pts) >= 2:
            if self.spline is None:
                self.spline = add_line(context, self.pts, context.scene.mch_rig.mguide_kind, self.own)
            else:
                g = guides()
                own = _owners(g)
                own[-1] = list(self.own)
                g['mch_guide_parts'] = json.dumps(own)
                v = g.matrix_world.inverted() @ Vector(tuple(p))
                self.spline.points.add(1)
                self.spline.points[-1].co = (v.x, v.y, v.z, 1.0)
            context.area.tag_redraw()

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            self._add(context, event)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            if self.spline is None:
                return {'CANCELLED'}
            self.report({'INFO'}, f'Mecha guide {len(guides().data.splines)}: {len(self.pts)} points '
                                  f'({context.scene.mch_rig.mguide_kind.title()})')
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            if self.spline is not None:
                drop_line('LAST')
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_mecha_guide_edit(bpy.types.Operator):
    """Mecha Guides: take the last line off, or all of them"""
    bl_idname = 'mch.mecha_guide_edit'
    bl_label = 'Mecha Guides'
    bl_options = {'REGISTER', 'UNDO'}
    mode: bpy.props.EnumProperty(items=[('LAST', 'Take Last Off', ''), ('ALL', 'Clear All', '')])

    @classmethod
    def poll(cls, context):
        return guides() is not None

    def execute(self, context):
        drop_line(self.mode)
        return {'FINISHED'}


def draw(layout, context, st):
    g = guides()
    n = len(g.data.splines) if g is not None else 0
    col = layout.column(align=True)
    col.label(text='Next line:')
    col.row(align=True).prop(st, 'mguide_kind', expand=True)
    r = col.row(align=True)
    r.prop(st, 'seamless', toggle=True)
    r = col.row(align=True)
    r.operator('mch.mecha_guide_edit', text='Undo Last Line', icon='LOOP_BACK').mode = 'LAST'
    r.operator('mch.mecha_guide_edit', text='Clear Lines', icon='X').mode = 'ALL'
    layout.label(text=f'{n} line(s): select the parts, drag lines through them - one bone a part', icon='INFO')


CLASSES = (MCH_OT_mecha_guide_draw, MCH_OT_mecha_guide_edit)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
