"""0.24.33 Cloth Wrap: cloth around a cylinder or a box - a reusable piece to bend and place anywhere.

Select a mesh and press Cylinder / Box: the cloth fits round its bounding box (its place, turn and size); with
nothing selected a new one is made at the 3D cursor (Core adds the cylinder / box inside).  Live sliders:
size, Gap, Cover Top, Hang (cloth falling past the bottom), Flare, Folds (vertical, deeper toward the hem), Fold
Depth, Wrinkles (crumpled across, like a pushed-up sleeve), Top Sag, Thickness, Seed, resolution.  Apply = a plain
mesh.  ``section``, ``profile_rows`` and ``wrap_mesh`` are pure.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty
from mathutils import Matrix, Vector

KIND_ITEMS = [('CYLINDER', 'Cylinder', 'Cloth round a cylinder (a sleeve, a wrapped pole)'),
              ('BOX', 'Box', 'Cloth over a box (a covered crate, a draped block)')]


# -----------------------------------------------------------------------------
# pure parts
# -----------------------------------------------------------------------------


def section(kind, n, a, b, corner):
    """n points (and outward normals) round the cross-section, evenly along it: a circle / ellipse of half sizes
    a, b, or a rounded rectangle of half sizes a, b with corner radius ``corner``."""
    if kind == 'CYLINDER':
        pts = []
        for i in range(n):
            t = 2 * math.pi * i / n
            p = Vector((a * math.cos(t), b * math.sin(t), 0.0))
            nrm = Vector((math.cos(t) / max(a, 1e-9), math.sin(t) / max(b, 1e-9), 0.0)).normalized()
            pts.append((p, nrm))
        return pts
    r = max(0.0, min(corner, a, b))
    ia, ib = a - r, b - r
    segs = [('L', Vector((a, -ib)), Vector((a, ib)), Vector((1, 0))),
            ('C', Vector((ia, ib)), 0.0), ('L', Vector((ia, b)), Vector((-ia, b)), Vector((0, 1))),
            ('C', Vector((-ia, ib)), math.pi / 2), ('L', Vector((-a, ib)), Vector((-a, -ib)), Vector((-1, 0))),
            ('C', Vector((-ia, -ib)), math.pi), ('L', Vector((-ia, -b)), Vector((ia, -b)), Vector((0, -1))),
            ('C', Vector((ia, -ib)), 1.5 * math.pi)]
    lengths = [((s[2] - s[1]).length if s[0] == 'L' else r * math.pi / 2) for s in segs]
    total = sum(lengths) or 1.0
    out = []
    for i in range(n):
        d = total * i / n
        k = 0
        while k < len(segs) - 1 and d > lengths[k]:
            d -= lengths[k]
            k += 1
        s = segs[k]
        if s[0] == 'L':
            t = 0.0 if lengths[k] < 1e-12 else d / lengths[k]
            p, nrm = s[1].lerp(s[2], t), s[3]
        else:
            ang = s[2] + (0.0 if r < 1e-12 else d / r)
            nrm = Vector((math.cos(ang), math.sin(ang)))
            p = s[1] + nrm * r
        out.append((Vector((p.x, p.y, 0.0)), Vector((nrm.x, nrm.y, 0.0)).normalized()))
    return out


def profile_rows(height, top_round, hang, cover_top, rows_side, rows_top, rows_hang):
    """The vertical profile as rows: (kind, s, z, out) - s = 0..1 across the top (scale of the section), z height,
    out = how far outside the section; kind tells top / edge / side / hang (for the folds)."""
    out = []
    z0 = height / 2.0
    rr = max(0.0, min(top_round, height * 0.5))
    if cover_top:
        for k in range(1, rows_top + 1):
            out.append(('TOP', k / rows_top, z0, -rr))
        for k in range(1, 5):
            t = (math.pi / 2) * k / 4
            out.append(('EDGE', 1.0, z0 - rr * (1 - math.cos(t)), -rr + rr * math.sin(t)))
    else:
        out.append(('SIDE', 1.0, z0, 0.0))
    for k in range(1, rows_side + 1):
        top = z0 - (rr if cover_top else 0.0)
        out.append(('SIDE', 1.0, top - (top + height / 2.0) * k / rows_side, 0.0))
    for k in range(1, rows_hang + 1):
        out.append(('HANG', 1.0, -height / 2.0 - hang * k / rows_hang, 0.0))
    return out


def wrap_mesh(p):
    """(verts, faces) of the cloth (object space, centred on the core)."""
    a, b, h = p.size_x / 2.0 + p.gap, p.size_y / 2.0 + p.gap, p.size_z + 2 * p.gap
    n = max(8, p.around)
    corner = p.corner * min(a, b)
    sec = section(p.kind, n, a, b, corner)
    rows = profile_rows(h, p.top_round * min(a, b, h / 2.0), p.hang, p.cover_top, p.rows, max(2, p.rows // 3),
                        max(1, int(p.rows * p.hang / max(h, 1e-9))) if p.hang > 1e-9 else 0)
    rng = random.Random(p.seed)
    ph = [rng.uniform(0, 2 * math.pi) for _ in range(6)]
    total_drop = h + p.hang
    depth = p.fold_depth * min(a, b)
    wr = p.wrinkle_depth * min(a, b)
    outer = []
    for kind, s, z, out in rows:
        down = (h / 2.0 - z) / max(total_drop, 1e-9)            # 0 at the top, 1 at the hem
        ring = []
        for i, (q, nrm) in enumerate(sec):
            u = i / n
            if kind == 'TOP':
                pt = q * s + nrm * out * s
                sag = p.top_sag * min(a, b) * (1.0 - s * s) * (0.6 + 0.4 * math.sin(4 * math.pi * u + ph[0]))
                ring.append(Vector((pt.x, pt.y, z - sag)))
                continue
            env = 0.25 + 0.75 * min(1.0, down * 1.4)
            fold = math.sin(2 * math.pi * p.folds * u + ph[1]) + 0.4 * p.fold_random * math.sin(
                2 * math.pi * p.folds * 2.3 * u + ph[2] + 3.0 * down)
            crumple = math.sin(2 * math.pi * p.wrinkles * down + ph[3] + 2.5 * math.sin(2 * math.pi * 2 * u + ph[4]))
            flare = p.flare * min(a, b) * (down ** 2) if kind in {'SIDE', 'HANG'} else 0.0
            if kind == 'HANG':
                flare += p.flare * min(a, b) * 0.5 * (z < -h / 2.0)
            off = out + depth * env * fold * 0.5 + wr * crumple * 0.5 + flare
            pt = q + nrm * off
            ring.append(Vector((pt.x, pt.y, z)))
        outer.append(ring)
    thick = p.thickness if p.thickness > 0 else min(a, b) * 0.03
    verts = []
    o_idx = []
    for ring in outer:
        o_idx.append(list(range(len(verts), len(verts) + n)))
        verts += ring
    # inner layer: pushed inward along the surface normal
    i_idx = []
    rows_n = len(outer)
    for r in range(rows_n):
        idx = []
        for i in range(n):
            pr = outer[max(r - 1, 0)][i]
            nx = outer[min(r + 1, rows_n - 1)][i]
            pa = outer[r][(i - 1) % n]
            pb = outer[r][(i + 1) % n]
            nrm = (pb - pa).cross(nx - pr)
            if nrm.length < 1e-12:
                nrm = Vector((outer[r][i].x, outer[r][i].y, 0.0))
            nrm.normalize()
            if nrm.dot(Vector((outer[r][i].x, outer[r][i].y, outer[r][i].z * 0.1))) < 0:
                nrm = -nrm
            idx.append(len(verts))
            verts.append(outer[r][i] - nrm * thick)
        i_idx.append(idx)
    faces = []
    for r in range(rows_n - 1):
        for i in range(n):
            j = (i + 1) % n
            faces.append((o_idx[r][i], o_idx[r + 1][i], o_idx[r + 1][j], o_idx[r][j]))
            faces.append((i_idx[r][j], i_idx[r + 1][j], i_idx[r + 1][i], i_idx[r][i]))
    last = rows_n - 1
    for i in range(n):                                       # the hem: outside to inside
        j = (i + 1) % n
        faces.append((o_idx[last][i], i_idx[last][i], i_idx[last][j], o_idx[last][j]))
    if p.cover_top:                                          # the middle of the top: a fan to a centre point
        ci, cj = len(verts), len(verts) + 1
        z_top = outer[0][0].z
        verts.append(Vector((0.0, 0.0, z_top - p.top_sag * min(a, b))))
        verts.append(Vector((0.0, 0.0, z_top - p.top_sag * min(a, b) - thick)))
        for i in range(n):
            j = (i + 1) % n
            faces.append((ci, o_idx[0][i], o_idx[0][j]))
            faces.append((cj, i_idx[0][j], i_idx[0][i]))
    else:                                                    # an open top edge: outside to inside
        for i in range(n):
            j = (i + 1) % n
            faces.append((o_idx[0][j], i_idx[0][j], i_idx[0][i], o_idx[0][i]))
    return verts, faces


# -----------------------------------------------------------------------------
# live object
# -----------------------------------------------------------------------------


def rebuild(ob):
    p = ob.mch_wrap
    verts, faces = wrap_mesh(p)
    bm = bmesh.new()
    try:
        bv = [bm.verts.new(v) for v in verts]
        for f in faces:
            try:
                bm.faces.new([bv[k] for k in f]).smooth = True
            except ValueError:
                pass
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(ob.data)
    finally:
        bm.free()
    ob.data.update()


def _update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.live:
        rebuild(ob)


def _p(prop, **kw):
    kw.setdefault('update', _update)
    return prop(**kw)


class MCH_PG_ClothWrap(bpy.types.PropertyGroup):
    live: BoolProperty(default=False, options={'HIDDEN'})
    kind: _p(EnumProperty, name='Shape', items=KIND_ITEMS, default='CYLINDER')
    size_x: _p(FloatProperty, name='Size X', default=1.0, min=0.001, unit='LENGTH')
    size_y: _p(FloatProperty, name='Size Y', default=1.0, min=0.001, unit='LENGTH')
    size_z: _p(FloatProperty, name='Height', default=2.0, min=0.001, unit='LENGTH')
    corner: _p(FloatProperty, name='Corner Round', default=0.15, min=0.0, max=1.0,
               description='Box: how round the corners are (part of the smaller side)')
    top_round: _p(FloatProperty, name='Top Edge Round', default=0.2, min=0.0, max=1.0)
    gap: _p(FloatProperty, name='Gap', default=0.02, min=0.0, soft_max=0.5, unit='LENGTH', precision=4,
            description='How far the cloth stands off the core')
    cover_top: _p(BoolProperty, name='Cover Top', default=False, description='Cloth over the top too')
    hang: _p(FloatProperty, name='Hang', default=0.0, min=0.0, soft_max=3.0, unit='LENGTH',
             description='Cloth falling on past the bottom')
    flare: _p(FloatProperty, name='Flare', default=0.1, min=0.0, max=2.0, description='Spreads out toward the hem')
    folds: _p(IntProperty, name='Folds', default=8, min=0, max=60, description='Vertical folds round it')
    fold_depth: _p(FloatProperty, name='Fold Depth', default=0.12, min=0.0, max=1.0)
    fold_random: _p(FloatProperty, name='Fold Random', default=0.6, min=0.0, max=1.0)
    wrinkles: _p(FloatProperty, name='Wrinkles', default=3.0, min=0.0, max=20.0,
                 description='Crumpled rings across (a pushed-up sleeve)')
    wrinkle_depth: _p(FloatProperty, name='Wrinkle Depth', default=0.05, min=0.0, max=1.0)
    top_sag: _p(FloatProperty, name='Top Sag', default=0.05, min=0.0, max=1.0, description='Cover Top: it sags a little')
    thickness: _p(FloatProperty, name='Thickness', default=0.0, min=0.0, soft_max=0.1, unit='LENGTH', precision=4,
                  description='0 = Auto (thin)')
    seed: _p(IntProperty, name='Seed', default=1, min=0)
    around: _p(IntProperty, name='Around', default=64, min=8, max=256)
    rows: _p(IntProperty, name='Rows', default=32, min=4, max=200)


class MCH_PG_ClothWrapDefaults(bpy.types.PropertyGroup):
    core: BoolProperty(name='Core', default=True,
                       description='With nothing selected: also add the cylinder / box inside the cloth')


SETTING_KEYS = ('kind', 'corner', 'top_round', 'gap', 'cover_top', 'hang', 'flare', 'folds', 'fold_depth',
                'fold_random', 'wrinkles', 'wrinkle_depth', 'top_sag', 'thickness', 'seed', 'around', 'rows')


def is_wrap(ob):
    return ob is not None and getattr(ob, 'mch_wrap', None) is not None and ob.mch_wrap.live


def make(context, kind, fit=None, core=True):
    """A live cloth wrap: round ``fit`` (its bounding box) or a new one at the 3D cursor."""
    me = bpy.data.meshes.new('ClothWrap')
    ob = bpy.data.objects.new('ClothWrap_' + kind.title(), me)
    coll = context.collection or context.scene.collection
    coll.objects.link(ob)
    p = ob.mch_wrap
    p.live = False
    p.kind = kind
    p.cover_top = kind == 'BOX'
    p.hang = 0.0
    if fit is not None:
        pts = [Vector(c) for c in fit.bound_box]
        lo = Vector([min(q[i] for q in pts) for i in range(3)])
        hi = Vector([max(q[i] for q in pts) for i in range(3)])
        sc = fit.matrix_world.to_scale()
        size = (hi - lo) * 1.0
        p.size_x, p.size_y, p.size_z = abs(size.x * sc.x), abs(size.y * sc.y), abs(size.z * sc.z)
        loc, rot, _s = fit.matrix_world.decompose()
        centre = fit.matrix_world @ ((lo + hi) / 2.0)
        ob.matrix_world = Matrix.Translation(centre) @ rot.to_matrix().to_4x4()
        for m in fit.data.materials:
            me.materials.append(m)
    else:
        p.size_x = p.size_y = 1.0
        p.size_z = 2.0 if kind == 'CYLINDER' else 1.0
        ob.location = context.scene.cursor.location + Vector((0, 0, p.size_z / 2.0))
        if core:
            if kind == 'CYLINDER':
                bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=p.size_z, location=ob.location)
            else:
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=ob.location)
            c = context.active_object
            c.name = 'ClothWrap_Core'
            ob.parent = c
            ob.matrix_parent_inverse = c.matrix_world.inverted()
    p.live = True
    rebuild(ob)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return ob


class MCH_OT_cloth_wrap(bpy.types.Operator):
    """Cloth round the selected meshes (their bounding boxes), or a new one at the 3D cursor"""
    bl_idname = 'mch.cloth_wrap'
    bl_label = 'Cloth Wrap'
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(items=KIND_ITEMS, default='CYLINDER')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        fits = [o for o in context.selected_objects if o.type == 'MESH' and not is_wrap(o)]
        core = context.scene.mch_wrap_defaults.core
        made = [make(context, self.kind, f) for f in fits] if fits else [make(context, self.kind, None, core)]
        for o in context.selected_objects:
            o.select_set(False)
        for o in made:
            o.select_set(True)
        context.view_layer.objects.active = made[-1]
        self.report({'INFO'}, f'Cloth Wrap ({self.kind.title()}): {len(made)} made - change it in the panel')
        return {'FINISHED'}


class MCH_OT_cloth_wrap_apply(bpy.types.Operator):
    bl_idname = 'mch.cloth_wrap_apply'
    bl_label = 'Apply Cloth'
    bl_description = 'Make it a plain mesh (the sliders stop rebuilding it)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_wrap(context.active_object)

    def execute(self, context):
        context.active_object.mch_wrap.live = False
        return {'FINISHED'}


def draw(layout, context):
    ob = context.active_object
    row = layout.row(align=True)
    row.scale_y = 1.4
    row.operator('mch.cloth_wrap', text='Cylinder', icon='MESH_CYLINDER').kind = 'CYLINDER'
    row.operator('mch.cloth_wrap', text='Box', icon='MESH_CUBE').kind = 'BOX'
    layout.prop(context.scene.mch_wrap_defaults, 'core', toggle=True)
    layout.label(text='Selected meshes: cloth fits round them', icon='INFO')
    if not is_wrap(ob):
        return
    p = ob.mch_wrap
    box = layout.box()
    box.label(text='LIVE Cloth Wrap: ' + ob.name, icon='MOD_CLOTH')
    box.row(align=True).prop(p, 'kind', expand=True)
    col = box.column(align=True)
    col.prop(p, 'size_x')
    col.prop(p, 'size_y')
    col.prop(p, 'size_z')
    if p.kind == 'BOX':
        col.prop(p, 'corner', slider=True)
    col.prop(p, 'gap')
    col = box.column(align=True)
    col.prop(p, 'cover_top', toggle=True)
    if p.cover_top:
        col.prop(p, 'top_round', slider=True)
        col.prop(p, 'top_sag', slider=True)
    col.prop(p, 'hang')
    col.prop(p, 'flare', slider=True)
    col = box.column(align=True)
    col.prop(p, 'folds')
    col.prop(p, 'fold_depth', slider=True)
    col.prop(p, 'fold_random', slider=True)
    col.prop(p, 'wrinkles', slider=True)
    col.prop(p, 'wrinkle_depth', slider=True)
    col = box.column(align=True)
    col.prop(p, 'thickness')
    col.prop(p, 'seed')
    r = col.row(align=True)
    r.prop(p, 'around')
    r.prop(p, 'rows')
    box.operator('mch.cloth_wrap_apply', icon='CHECKMARK')


CLASSES = (MCH_PG_ClothWrap, MCH_PG_ClothWrapDefaults, MCH_OT_cloth_wrap, MCH_OT_cloth_wrap_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_wrap = PointerProperty(type=MCH_PG_ClothWrap)
    bpy.types.Scene.mch_wrap_defaults = PointerProperty(type=MCH_PG_ClothWrapDefaults)


def unregister():
    for n, t in (('mch_wrap', bpy.types.Object), ('mch_wrap_defaults', bpy.types.Scene)):
        try:
            delattr(t, n)
        except AttributeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
