"""0.17 Random Panels: armour plates scattered over a mesh (controlled randomness).

Select a mesh (or faces of it in Edit Mode) and press Generate.  The surface
is split into panels around random centres (a few Lloyd steps keep them
even), Density picks how many become plates, each plate gets a clean polygon
outline (simplified, inset by the Gap) filled with NEW clean faces laid on
the surface - the same plate builder as Armor Plate, so low-poly meshes work
(a working copy is subdivided first) and the mesh itself is never changed.

Options: Seed (repeat a layout), Density, Panel Size, Gap, Height variation,
Mix Profiles, Edge Pieces (short trims along the panel borders, Edge Molding
engine) and Mirror (our Mirror tool settings: panels are made on one side and
get the Mecha Mirror modifier).

While a layout is open a HUD floats right of the mesh: Reroll, Apply,
Cancel, Edge Pieces, Mirror and sliders for Density and Panel Size; every
change rebuilds the layout.

Pure helpers (``sample_seeds``, ``assign``, ``panel_outline``) are tested
headless; the HUD needs a real viewport.
"""
from __future__ import annotations

import json
import math
import random

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import armor_plate as ap
from . import core_geometry as cg

SESSION = 'mch_random_session'
COLL = 'Random Panels'
MIX = ('CHAMFER', 'STEEP', 'SOFT', 'CHAMFER_BEVEL', 'STEPPED', 'HEAVY')
MAX_WORK_FACES = 40000


# -----------------------------------------------------------------------------
# Pure helpers
# -----------------------------------------------------------------------------


def sample_seeds(centres, areas, count, rng):
    """``count`` seed points picked area-weighted from face centres."""
    total = sum(areas)
    if total <= 0 or not centres:
        return []
    cum, acc = [], 0.0
    for a in areas:
        acc += a
        cum.append(acc)
    import bisect
    out = []
    for _ in range(max(1, count)):
        i = min(bisect.bisect_left(cum, rng.random() * total), len(centres) - 1)
        out.append(Vector(centres[i]))
    return out


def assign(centres, seeds):
    """Index of the nearest seed for every face centre."""
    from mathutils.kdtree import KDTree
    kd = KDTree(len(seeds))
    for i, s in enumerate(seeds):
        kd.insert(s, i)
    kd.balance()
    return [kd.find(c)[1] for c in centres]


def lloyd(centres, areas, seeds, steps=2):
    """Move every seed to the area-weighted centre of its cell (even panels)."""
    for _ in range(steps):
        owner = assign(centres, seeds)
        acc = [Vector() for _ in seeds]
        w = [0.0] * len(seeds)
        for c, a, o in zip(centres, areas, owner):
            acc[o] += Vector(c) * a
            w[o] += a
        seeds = [acc[i] / w[i] if w[i] > 0 else seeds[i] for i in range(len(seeds))]
    return seeds


def _closed_simplify(loop, tol):
    """RDP for a closed loop: split at the two farthest points."""
    if len(loop) < 5 or tol <= 0:
        return list(loop)
    i0 = 0
    i1 = max(range(len(loop)), key=lambda i: math.dist(loop[0], loop[i]))
    a = cg.simplify_open(loop[i0:i1 + 1], tol)
    b = cg.simplify_open(loop[i1:] + [loop[0]], tol)
    out = a[:-1] + b[:-1]
    return out if len(out) >= 3 else list(loop)


def panel_outline(loop2d, simplify, gap):
    """Clean polygon outline: simplified, counter-clockwise, inset by half the
    gap.  None when nothing usable is left."""
    from .cut_engine import offset_loop
    lp = _closed_simplify(list(loop2d), simplify)
    if cg.signed_area(lp) < 0:
        lp = list(reversed(lp))
    base = lp
    if gap > 0:
        lp = offset_loop(lp, -gap / 2.0)
    lp = cg.dedupe_loop(lp, eps=simplify * 0.05 + 1e-9)
    if len(lp) < 3 or cg.signed_area(lp) <= 0:
        return None
    if gap > 0:
        segs = [(base[i], base[(i + 1) % len(base)]) for i in range(len(base))]
        if cg.signed_area(lp) >= cg.signed_area(base) or not all(cg.point_in_loop(q, base) for q in lp) or \
                any(min(ap._seg_dist(q, a, b) for a, b in segs) < gap * 0.49 for q in lp):
            return None                 # the inset turned inside out: the gap is wider than the panel
    if cg.find_intersections([lp]):
        return None
    return lp


def edge_pieces(loop3d, normals, rng, density, piece_len):
    """Random open chains along a closed 3D loop: [(pts, nrms)]."""
    n = len(loop3d)
    if n < 3 or piece_len <= 0:
        return []
    lengths = [(Vector(loop3d[(i + 1) % n]) - Vector(loop3d[i])).length for i in range(n)]
    out, i, guard = [], 0, 0
    while i < n and guard < n * 4:
        guard += 1
        if rng.random() < density:
            pts, nrm, run, j = [loop3d[i]], [normals[i]], 0.0, i
            while run < piece_len and j < i + n - 1:
                run += lengths[j % n]
                j += 1
                pts.append(loop3d[j % n])
                nrm.append(normals[j % n])
            if len(pts) >= 2:
                out.append((pts, nrm))
            i = j + 1
        else:
            i += 1
    return out


# -----------------------------------------------------------------------------
# Settings / session
# -----------------------------------------------------------------------------


def _regen(self, context):
    if context.scene.get(SESSION):
        try:
            regenerate(context)
        except cg.CutError as ex:
            print('[Mecha Lab] random panels:', ex)


class MCH_PG_Random(bpy.types.PropertyGroup):
    seed: IntProperty(name='Seed', default=1, min=0, update=_regen, description='Same seed = same layout')
    density: FloatProperty(name='Density', default=0.6, min=0.05, max=1.0, subtype='FACTOR', update=_regen,
                           description='Share of the panels that become plates')
    panel_size: FloatProperty(name='Panel Size', default=0.2, min=0.03, max=0.8, subtype='FACTOR', update=_regen,
                              description='Panel size as a part of the mesh size')
    gap: FloatProperty(name='Gap', default=0.1, min=0.0, max=0.5, subtype='FACTOR', update=_regen,
                       description='Space between plates, as a part of the panel size')
    height_jitter: FloatProperty(name='Height Variation', default=0.35, min=0.0, max=1.0, subtype='FACTOR',
                                 update=_regen)
    mix_profiles: BoolProperty(name='Mix Profiles', default=True, update=_regen,
                               description='Each plate gets a random profile (else the Armor Plate profile)')
    edges: BoolProperty(name='Edge Pieces', default=False, update=_regen,
                        description='Short trims along random parts of the panel borders')
    edge_density: FloatProperty(name='Edge Density', default=0.35, min=0.05, max=1.0, subtype='FACTOR',
                                update=_regen)
    edge_length: FloatProperty(name='Edge Length', default=0.35, min=0.05, max=1.0, subtype='FACTOR', update=_regen,
                               description='Trim length as a part of the panel size')
    mirror: BoolProperty(name='Mirror', default=False, update=_regen,
                         description='Panels on one side, copied with the Mecha Mirror modifier (Mirror tool settings)')


def session(context):
    raw = context.scene.get(SESSION)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return data if data.get('target') in bpy.data.objects else None


def _clear_objects(data):
    for name in data.get('objects', []):
        ob = bpy.data.objects.get(name)
        if ob is None:
            continue
        ex = getattr(ob, 'mch_extract', None)
        meshes = [ob.data] + ([ex.region, ex.surround] if ex is not None and ex.is_part else [])
        bpy.data.objects.remove(ob, do_unlink=True)
        for m in meshes:
            if m is not None and m.users == 0:
                bpy.data.meshes.remove(m)
    data['objects'] = []


# -----------------------------------------------------------------------------
# Generate
# -----------------------------------------------------------------------------


def _work_mesh(context, target, faces):
    """World-space bmesh of the candidate faces, subdivided until the faces
    are small enough for the panel size."""
    dg = context.evaluated_depsgraph_get()
    ev = target.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
    finally:
        ev.to_mesh_clear()
    bm.transform(target.matrix_world)
    bm.faces.ensure_lookup_table()
    if faces:
        keep = set(faces)
        doomed = [f for f in bm.faces if f.index not in keep]
        if doomed:
            bmesh.ops.delete(bm, geom=doomed, context='FACES')
    return bm


def _refine(bm, edge_target):
    for _ in range(6):
        if len(bm.faces) > MAX_WORK_FACES / 4:
            break
        long_edges = [e for e in bm.edges if e.calc_length() > edge_target]
        if not long_edges:
            break
        bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])


def _components(faces):
    left = set(faces)
    out = []
    while left:
        f0 = left.pop()
        comp, todo = [f0], [f0]
        while todo:
            f = todo.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g in left:
                        left.discard(g)
                        comp.append(g)
                        todo.append(g)
        out.append(sorted(comp, key=lambda f: f.index))     # stable order: same seed = same layout
    return out


def _mirror_side(context, target):
    """(origin, [axes], [signs]) of the enabled mirror planes, or None."""
    from . import mirror_tools
    mp = context.scene.mch_mirror
    origin, axes = mirror_tools.mirror_frame(target, mp, context.scene)
    sel = []
    for i, (on, flip) in enumerate(((mp.x, mp.flip_x), (mp.y, mp.flip_y), (mp.z, mp.flip_z))):
        if on:
            sel.append((axes[i], -1.0 if flip else 1.0))
    return origin, sel


def regenerate(context):
    """(Re)build the layout of the open session.  Returns a report."""
    from . import edge_molding as em
    data = session(context)
    if data is None:
        raise cg.CutError('No random layout is open.')
    _clear_objects(data)
    st = context.scene.mch_random
    target = bpy.data.objects[data['target']]
    rng = random.Random(st.seed)
    bm = _work_mesh(context, target, data.get('faces'))
    made, skipped = [], 0
    try:
        if not bm.faces:
            raise cg.CutError('No faces to put panels on.')
        lo = Vector([min(v.co[k] for v in bm.verts) for k in range(3)])
        hi = Vector([max(v.co[k] for v in bm.verts) for k in range(3)])
        diag = max((hi - lo).length, 1e-6)
        size = st.panel_size * diag
        _refine(bm, size / 5.0)
        bm.verts.index_update()
        bm.faces.index_update()
        bm.faces.ensure_lookup_table()
        bm.normal_update()
        wv = [q.co.copy() for q in bm.verts]
        polys = [[q.index for q in f.verts] for f in bm.faces]
        faces = list(bm.faces)
        if st.mirror:
            origin, planes = _mirror_side(context, target)
            faces = [f for f in faces if all((f.calc_center_median() - origin).dot(a) * s >= -1e-6
                                             for a, s in planes)]
        if not faces:
            raise cg.CutError('Mirror: no faces on the kept side.')
        centres = [f.calc_center_median() for f in faces]
        areas = [f.calc_area() for f in faces]
        count = max(1, int(round(sum(areas) / (size * size))))
        seeds = lloyd(centres, areas, sample_seeds(centres, areas, count, rng), 2)
        owner = assign(centres, seeds)
        groups = {}
        for f, o in zip(faces, owner):
            groups.setdefault(o, []).append(f)
        cells = [comp for g in groups.values() for comp in _components(g) if len(comp) >= 3]
        cells.sort(key=lambda c: min(f.index for f in c))
        rng.shuffle(cells)
        cells = cells[:max(1, int(round(len(cells) * st.density)))]
        tree = BVHTree.FromBMesh(bm)
        inv = target.matrix_world.inverted_safe()
        rot = inv.to_3x3()
        scale = target.matrix_world.to_scale()
        unit = max(1e-9, (abs(scale.x) + abs(scale.y) + abs(scale.z)) / 3.0)
        chains = []
        from .panel_gen import boundary_loops, PanelError
        for cell in cells:
            try:
                loops = boundary_loops(bm, cell)
            except PanelError:
                skipped += 1
                continue
            outer = max(loops, key=lambda lp: sum((lp[i].co - lp[i - 1].co).length for i in range(len(lp))))
            k0 = min(range(len(outer)), key=lambda i: outer[i].index)
            outer = outer[k0:] + outer[:k0]
            n = sum((f.normal * f.calc_area() for f in cell), Vector())
            if n.length < 1e-12:
                skipped += 1
                continue
            n.normalize()
            c = sum((v.co for v in outer), Vector()) / len(outer)
            u = n.orthogonal().normalized()
            v_ = n.cross(u).normalized()
            loop2d = [((p.co - c).dot(u), (p.co - c).dot(v_)) for p in outer]
            outline = panel_outline(loop2d, size * 0.06, st.gap * size)
            if outline is None:
                skipped += 1
                continue
            pts, tris, nb = ap.screen_patch([(outline, [])], size / 10.0, min_spacing=1e-6)
            if not tris:
                skipped += 1
                continue
            cos, nrms = [], []
            for x, y in pts:
                p0 = c + u * x + v_ * y
                hit = None
                for d in (-n, n):
                    loc, nn, _i, dist = tree.ray_cast(p0 - d * size, d, size * 2)
                    if loc is not None and (hit is None or (loc - p0).length < (hit[0] - p0).length):
                        hit = (loc, nn)
                if hit is None:
                    loc, nn, _i, _d = tree.find_nearest(p0)
                    hit = (loc if loc is not None else p0, nn if nn is not None else n)
                nn = hit[1] if hit[1].dot(n) >= 0 else -hit[1]
                cos.append(hit[0])
                nrms.append(nn.normalized())
            region = ap.build_region(pts, tris, [inv @ q for q in cos], [(rot @ q).normalized() for q in nrms])
            pad = Vector((size * 0.3,) * 3)
            lo2 = Vector([min(q[k] for q in cos) for k in range(3)]) - pad
            hi2 = Vector([max(q[k] for q in cos) for k in range(3)]) + pad
            surround = ap.surround_mesh(wv, polys, inv, lo2, hi2)
            preset = rng.choice(MIX) if st.mix_profiles else context.scene.mch_plate.preset
            hs = 1.0 + st.height_jitter * (rng.random() * 2.0 - 1.0)
            try:
                part = ap.create_plate(context, target, region, surround, preset, size / unit, True, COLL, hs)
            except cg.CutError:
                for m in (region, surround):
                    try:
                        if m.users == 0:
                            bpy.data.meshes.remove(m)
                    except ReferenceError:        # already removed with the failed part
                        pass
                skipped += 1
                continue
            made.append(part)
            if st.edges:
                ring = [cos[i] for i in range(nb)]
                rn = [nrms[i] for i in range(nb)]
                for cpts, cn in edge_pieces(ring, rn, rng, st.edge_density, st.edge_length * size):
                    chains.append({'pts': [tuple(inv @ q) for q in cpts], 'nrm': [tuple((rot @ q).normalized())
                                                                                    for q in cn], 'closed': False})
        objects = list(made)
        if chains:
            mold = em.create_molding(context, json.dumps(chains), target.matrix_world, target.name + '_EdgePieces',
                                     source=target, kind='RANDOM')
            mp = mold.mch_molding
            mp.is_molding = False
            mp.width = size * 0.06 / unit
            mp.height = size * 0.04 / unit
            mp.is_molding = True
            em.rebuild(mold)
            objects.append(mold)
        if st.mirror:
            from . import mirror_tools
            for ob in objects:
                mirror_tools.setup_mirror(ob, context.scene.mch_mirror, context.scene)
        data['objects'] = [o.name for o in objects]
    finally:
        bm.free()
        context.scene[SESSION] = json.dumps(data)
    return (f'{len(made)} random panel(s) on {target.name}' + (' + edge pieces' if st.edges else '') +
            (' (mirrored)' if st.mirror else '') + (f' | {skipped} cell(s) skipped' if skipped else ''))


def start(context, target, faces=None):
    """Open a layout on ``target`` (all faces or the given face indices)."""
    old = session(context)
    if old is not None:
        _clear_objects(old)
    context.scene[SESSION] = json.dumps({'target': target.name, 'faces': list(faces or []), 'objects': []})
    return regenerate(context)


def finish(context, keep=True):
    data = session(context)
    if data is None:
        return 0
    n = len(data.get('objects', []))
    if not keep:
        _clear_objects(data)
    del context.scene[SESSION]
    return n


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------


class MCH_OT_random_panels(bpy.types.Operator):
    """Random armour plates on the selected mesh (Edit Mode: on the selected faces).
    The layout stays open: Reroll / sliders / Apply in the HUD next to the mesh"""
    bl_idname = 'mch.random_panels'
    bl_label = 'Generate Random Panels'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH' and not ap.is_plate_or_part(ob)

    def execute(self, context):
        ob = context.active_object
        faces = None
        if context.mode == 'EDIT_MESH':
            ob.update_from_editmode()
            faces = [p.index for p in ob.data.polygons if p.select]
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            msg = start(context, ob, faces)
        except cg.CutError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        self.report({'INFO'}, msg + '  | Reroll / Apply in the HUD')
        return {'FINISHED'}


class MCH_OT_random_reroll(bpy.types.Operator):
    """New random layout (next seed)"""
    bl_idname = 'mch.random_reroll'
    bl_label = 'Reroll'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return session(context) is not None

    def execute(self, context):
        context.scene.mch_random.seed += 1          # update -> regenerate
        return {'FINISHED'}


class MCH_OT_random_finish(bpy.types.Operator):
    """Apply: keep the plates and close the layout.  Cancel: remove them"""
    bl_idname = 'mch.random_finish'
    bl_label = 'Finish Random Panels'
    bl_options = {'REGISTER', 'UNDO'}
    keep: BoolProperty(default=True, options={'SKIP_SAVE'})

    @classmethod
    def description(cls, context, properties):
        return 'Keep the plates (they stay live parts)' if properties.keep else 'Remove the plates of this layout'

    @classmethod
    def poll(cls, context):
        return session(context) is not None

    def execute(self, context):
        n = finish(context, self.keep)
        self.report({'INFO'}, f'{n} object(s) kept' if self.keep else 'Random panels removed')
        return {'FINISHED'}


class MCH_OT_random_toggle(bpy.types.Operator):
    """HUD toggle"""
    bl_idname = 'mch.random_toggle'
    bl_label = 'Random Panels Option'
    bl_options = {'REGISTER', 'UNDO'}
    option: bpy.props.EnumProperty(items=[('edges', 'Edge Pieces', ''), ('mirror', 'Mirror', ''),
                                          ('mix_profiles', 'Mix Profiles', '')], default='edges')

    @classmethod
    def description(cls, context, properties):
        return {'edges': 'Edge pieces on / off', 'mirror': 'Mirror (Mirror tool settings) on / off',
                'mix_profiles': 'Mixed profiles on / off'}[properties.option]

    def execute(self, context):
        st = context.scene.mch_random
        setattr(st, self.option, not getattr(st, self.option))
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# HUD next to the mesh
# -----------------------------------------------------------------------------

HUD_BUTTONS = (('reroll', 'FILE_REFRESH', 'mch.random_reroll', {}, 'Reroll'),
               ('apply', 'CHECKMARK', 'mch.random_finish', {'keep': True}, 'Apply'),
               ('cancel', 'X', 'mch.random_finish', {'keep': False}, 'Cancel'),
               ('edges', 'MOD_EDGESPLIT', 'mch.random_toggle', {'option': 'edges'}, 'Edge Pieces'),
               ('mirror', 'MOD_MIRROR', 'mch.random_toggle', {'option': 'mirror'}, 'Mirror'))
SLIDERS = (('density', 'Density', 5, 100), ('panel_size', 'Panel Size', 3, 80))


def slider_spec(context, key):
    st = context.scene.mch_random
    label, lo, hi = next((l, a, b) for k, l, a, b in SLIDERS if k == key)
    return (label, int(round(getattr(st, key) * 100)), lo, hi,
            lambda v, k=key: setattr(st, k, v / 100.0))


def hud_layout(screen_pts, region_w, region_h, btn=30.0, gap=6.0, slider_w=104.0, slider_h=20.0):
    pts = [p for p in screen_pts if p is not None]
    if not pts:
        return {}
    x = min(max(max(p[0] for p in pts) + btn * 1.2, btn), region_w - slider_w - btn)
    step = btn + gap
    total = step * len(HUD_BUTTONS) + (slider_h + gap) * len(SLIDERS)
    top = min(max((max(p[1] for p in pts) + min(p[1] for p in pts)) / 2 + total / 2, total), region_h - btn)
    out = {}
    y = top
    for name, *_ in HUD_BUTTONS:
        out[name] = (x, y)
        y -= step
    for key, *_ in SLIDERS:
        out['slider_' + key] = (x - btn / 2 + slider_w / 2, y + btn / 2 - slider_h / 2)
        y -= slider_h + gap
    return out


def _current(context):
    from .primitive_hud import anchored, release_anchor
    data = session(context)
    if data is None or context.mode != 'OBJECT':
        release_anchor('random')
        return None, {}
    from bpy_extras import view3d_utils
    target = bpy.data.objects[data['target']]
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return None, {}
    ui = context.preferences.system.ui_scale
    pts = []
    for c in target.bound_box:
        p = view3d_utils.location_3d_to_region_2d(region, rv3d, target.matrix_world @ Vector(c))
        pts.append(None if p is None else (p[0] / ui, p[1] / ui))
    return data, anchored('random', data['target'], region, hud_layout(pts, region.width / ui, region.height / ui))


class MCH_GT_random_slider(bpy.types.Gizmo):
    bl_idname = 'MCH_GT_random_slider'
    __slots__ = ('shape', 'init_x', 'init_value', 'key')

    def setup(self):
        if not hasattr(self, 'shape'):
            from .primitive_hud import _RECT
            self.shape = self.new_custom_shape('TRIS', _RECT)

    def draw(self, context):
        self.draw_custom_shape(self.shape)

    def draw_select(self, context, select_id):
        self.draw_custom_shape(self.shape, select_id=select_id)

    def invoke(self, context, event):
        self.init_x = event.mouse_region_x
        self.init_value = slider_spec(context, self.key)[1]
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        from .primitive_hud import slider_value
        label, cur, lo, hi, setter = slider_spec(context, self.key)
        v = slider_value(self.init_value, event.mouse_region_x - self.init_x, step_px=6.0, lo=lo, hi=hi)
        if v != cur:
            setter(v)
        if context.area:
            context.area.header_text_set(f'{label}: {v} %')
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        if context.area:
            context.area.header_text_set(None)
        if cancel:
            slider_spec(context, self.key)[4](self.init_value)


class MCH_GGT_random_hud(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_random_hud'
    bl_label = 'Random Panels HUD'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and session(context) is not None

    def setup(self, context):
        self.items = {}
        for name, icon, op, props, _label in HUD_BUTTONS:
            gz = self.gizmos.new('GIZMO_GT_button_2d')
            gz.icon = icon
            gz.draw_options = {'BACKDROP', 'OUTLINE'}
            t = gz.target_set_operator(op)
            for k, v in props.items():
                setattr(t, k, v)
            gz.color = (0.17, 0.19, 0.23)
            gz.alpha = 0.92
            gz.color_highlight = (0.32, 0.35, 0.41)
            gz.alpha_highlight = 1.0
            self.items[name] = gz
        for key, *_ in SLIDERS:
            gz = self.gizmos.new(MCH_GT_random_slider.bl_idname)
            gz.key = key
            gz.color = (0.24, 0.27, 0.32)
            gz.alpha = 0.95
            gz.color_highlight = (0.36, 0.40, 0.47)
            gz.alpha_highlight = 1.0
            gz.use_draw_scale = False
            self.items['slider_' + key] = gz

    def draw_prepare(self, context):
        data, lay = _current(context)
        ui = context.preferences.system.ui_scale
        st = context.scene.mch_random
        for name, gz in self.items.items():
            pos = lay.get(name)
            gz.hide = pos is None
            if pos is None:
                continue
            if name.startswith('slider_'):
                gz.matrix_basis = Matrix.Translation((pos[0] * ui, pos[1] * ui, 0.0)) @ Matrix.Diagonal(
                    (52.0 * ui, 10.0 * ui, 1.0, 1.0))
                continue
            gz.scale_basis = 15.0
            gz.matrix_basis[0][3] = pos[0] * ui
            gz.matrix_basis[1][3] = pos[1] * ui
            on = (name == 'edges' and st.edges) or (name == 'mirror' and st.mirror) or name == 'apply'
            gz.color = (1.0, 0.62, 0.16) if on else (0.17, 0.19, 0.23)


_label_handle = None


def _draw_labels():
    try:
        context = bpy.context
        data, lay = _current(context)
        if data is None or not lay:
            return
        import blf
        ui = context.preferences.system.ui_scale
        blf.size(0, 11 * ui)
        st = context.scene.mch_random
        for name, _i, _o, _p, label in HUD_BUTTONS:
            x, y = lay[name]
            on = (name == 'edges' and st.edges) or (name == 'mirror' and st.mirror)
            blf.color(0, *((1.0, 0.62, 0.16) if on else (0.85, 0.87, 0.9)), 1.0)
            text = label + (f'  (seed {st.seed})' if name == 'reroll' else '')
            blf.position(0, (x + 21) * ui, (y - 4) * ui, 0)
            blf.draw(0, text)
        for key, *_ in SLIDERS:
            x, y = lay['slider_' + key]
            label, v, *_rest = slider_spec(context, key)
            text = f'{label}  {v} %'
            w, _h = blf.dimensions(0, text)
            blf.color(0, 1.0, 1.0, 1.0, 1.0)
            blf.position(0, x * ui - w / 2, (y - 4) * ui, 0)
            blf.draw(0, text)
    except Exception:          # never break viewport drawing
        pass


def draw(layout, context):
    st = context.scene.mch_random
    box = layout.box()
    box.label(text='RANDOM PANELS', icon='MOD_PARTICLES')
    col = box.column(align=True)
    col.prop(st, 'density', slider=True)
    col.prop(st, 'panel_size', slider=True)
    col.prop(st, 'gap', slider=True)
    col.prop(st, 'height_jitter', slider=True)
    row = box.row(align=True)
    row.prop(st, 'seed')
    row.operator('mch.random_reroll', text='', icon='FILE_REFRESH')
    row = box.row(align=True)
    row.prop(st, 'mix_profiles', toggle=True)
    row.prop(st, 'mirror', toggle=True, icon='MOD_MIRROR')
    row.prop(st, 'edges', toggle=True, icon='MOD_EDGESPLIT')
    if st.edges:
        r = box.row(align=True)
        r.prop(st, 'edge_density', slider=True)
        r.prop(st, 'edge_length', slider=True)
    if session(context) is None:
        r = box.row()
        r.scale_y = 1.3
        r.operator('mch.random_panels', icon='MOD_PARTICLES')
        box.label(text='Select a mesh (Edit Mode: faces) first', icon='INFO')
    else:
        r = box.row(align=True)
        r.scale_y = 1.3
        r.operator('mch.random_finish', text='Apply', icon='CHECKMARK').keep = True
        r.operator('mch.random_finish', text='Cancel', icon='X').keep = False


CLASSES = (MCH_PG_Random, MCH_OT_random_panels, MCH_OT_random_reroll, MCH_OT_random_finish, MCH_OT_random_toggle,
           MCH_GT_random_slider, MCH_GGT_random_hud)


def register():
    global _label_handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_random = bpy.props.PointerProperty(type=MCH_PG_Random)
    if not bpy.app.background and _label_handle is None:
        _label_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_labels, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _label_handle
    if _label_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_label_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _label_handle = None
    if hasattr(bpy.types.Scene, 'mch_random'):
        del bpy.types.Scene.mch_random
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
