"""0.24.95 Lasso Zones on Mech Shader parts (user: "메카닉 할 때 내가 라쏘로 그은 영역 색이랑 재질 다르게 할 수 있나?" ->
picked both ways):

* **Paint Zone** (the mesh as it is): the lasso, as drawn on the screen, becomes a mask picture projected from that view
  onto the part (a hidden projector Empty parented to it - the zone moves with the part).  Inside it the Mech Shader's
  paint is the zone's own: Color, Roughness, Metallic, Paint (coverage); Opacity.  The chips, primer, scratches, dirt,
  rust go over it as over any paint.  Only faces that faced the view when it was drawn, and only as deep as the part
  (Through: the back faces too).  No UVs, no new edges.
* **Split Zone** (a material of its own): edges cut into the mesh along the lasso (projected from the view), the faces
  inside get a second Mech material (a copy to change freely - any preset) - its own material slot, the boundary
  exact, a material ID for a game engine.

The lasso (``MCH_OT_zone_lasso``): drag = freehand; clicks = a straight-edged polygon (Enter / Space / double-click
closes it); Esc / right click cancels."""
from __future__ import annotations

import math

import bpy
import numpy as np
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)
from mathutils import Matrix, Vector

from . import mech_shader as ms

PREFIX = 'mchz:'
MASK_MAX = 1024
PALETTE = ((0.75, 0.42, 0.02), (0.06, 0.06, 0.07), (0.05, 0.16, 0.45), (0.6, 0.04, 0.03), (0.75, 0.75, 0.72),
           (0.12, 0.25, 0.08))


# -----------------------------------------------------------------------------
# the mask picture: the lasso filled (scanlines, 2 x supersampled)
# -----------------------------------------------------------------------------

def fill_polygon(pts, w, h, ss=2):
    """(h, w) float32 0..1: the closed polygon ``pts`` (pixel x, y; y up) filled, its edge anti-aliased."""
    W, H = w * ss, h * ss
    p = np.asarray(pts, np.float64) * ss
    x0, y0 = p[:, 0], p[:, 1]
    x1, y1 = np.roll(x0, -1), np.roll(y0, -1)
    out = np.zeros((H, W), np.float32)
    ys = np.arange(H) + 0.5
    lo, hi = np.minimum(y0, y1), np.maximum(y0, y1)
    for r in range(H):
        y = ys[r]
        m = (lo <= y) & (hi > y)
        if not m.any():
            continue
        xs = x0[m] + (y - y0[m]) * (x1[m] - x0[m]) / (y1[m] - y0[m])
        xs.sort()
        for a, b in zip(xs[0::2], xs[1::2]):
            ia, ib = int(max(0, math.ceil(a - 0.5))), int(min(W, math.floor(b - 0.5) + 1))
            if ib > ia:
                out[r, ia:ib] = 1.0
    return out.reshape(h, ss, w, ss).mean(axis=(1, 3))


def mask_image(name, pts, rw, rh):
    """A packed grey image of the lasso over the whole view (``rw`` x ``rh`` pixels), at most MASK_MAX on its long
    side.  Image row 0 is the bottom (Blender's)."""
    s = min(1.0, MASK_MAX / float(max(rw, rh)))
    w, h = max(8, int(round(rw * s))), max(8, int(round(rh * s)))
    sx, sy = w / float(rw), h / float(rh)
    a = fill_polygon([(x * sx, y * sy) for x, y in pts], w, h)
    img = bpy.data.images.new(name, w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color'          # (before the pixels: changing it re-makes a new image's buffer)
    px = np.empty((h, w, 4), np.float32)
    px[..., 0] = px[..., 1] = px[..., 2] = a
    px[..., 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    img.update()
    img.pack()
    return img


# -----------------------------------------------------------------------------
# the zones of a material: settings, and their nodes
# -----------------------------------------------------------------------------

def _update(self, context):
    mat = self.id_data
    sync(mat)


class MCH_PG_Zone(bpy.types.PropertyGroup):
    name: StringProperty(default='Zone')
    projector: PointerProperty(type=bpy.types.Object)
    mask: PointerProperty(type=bpy.types.Image)
    win: FloatVectorProperty(size=16)                         # (the view's window matrix, row by row)
    eye: FloatVectorProperty(size=3)                          # (in the part's own space: where the view was ...)
    look: FloatVectorProperty(size=3, default=(0.0, 0.0, -1.0))   # (... and which way it looked)
    persp: BoolProperty(default=True)
    near: FloatProperty(default=0.0)
    far: FloatProperty(default=1e6)
    color: FloatVectorProperty(name='Color', subtype='COLOR', size=3, min=0.0, max=1.0, default=PALETTE[0],
                               update=_update, description='The zone\'s paint colour')
    roughness: FloatProperty(name='Roughness', default=0.45, min=0.0, max=1.0, update=_update)
    metallic: FloatProperty(name='Metallic', default=0.0, min=0.0, max=1.0, update=_update,
                            description='Metallic paint (0: plain paint)')
    cover: FloatProperty(name='Paint', default=1.0, min=0.0, max=1.0, update=_update,
                         description='How much of the zone is painted (0: the bare material shows)')
    opacity: FloatProperty(name='Opacity', default=1.0, min=0.0, max=1.0, update=_update)
    through: BoolProperty(name='Through', default=False, update=_update,
                          description='Paint the faces turned away from the view too (off: only what faced it)')


def zones_of(mat):
    return getattr(mat, 'mch_zones', None) if mat is not None else None


def _clear_nodes(nt):
    for nd in [n for n in nt.nodes if n.name.startswith(PREFIX)]:
        nt.nodes.remove(nd)


def relink(mat):
    """The zone nodes made anew in ``mat`` (after its Mech Shader tree was made, or a zone added / removed) and linked
    into the Mech Shader's zone hubs."""
    if not ms.is_mech(mat):
        return
    nt = mat.node_tree
    _clear_nodes(nt)
    zs = zones_of(mat)
    hub = {k: nt.nodes.get('mch:zone_' + k) for k in ('mask', 'cover', 'rough', 'metal', 'color')}
    if any(v is None for v in hub.values()):
        return
    live = [z for z in zs if z.projector is not None and z.mask is not None] if zs else []
    for k in ('mask', 'cover', 'rough', 'metal'):
        for lk in list(hub[k].inputs[0].links):
            nt.links.remove(lk)
    csock = {sk.identifier: sk for sk in hub['color'].inputs}['A_Color']
    for lk in list(csock.links):
        nt.links.remove(lk)
    if not live:
        return
    before = {nd.as_pointer() for nd in nt.nodes}
    b = ms.Builder(nt)
    mask_t = col_t = rough_t = metal_t = cover_t = None
    geo = b.node('ShaderNodeNewGeometry')
    geo.name = PREFIX + 'geo'
    tco = b.node('ShaderNodeTexCoord')
    tco.name = PREFIX + 'tc'
    nrm = b.node('ShaderNodeVectorTransform')
    nrm.name = PREFIX + 'nrm'
    nrm.vector_type, nrm.convert_from, nrm.convert_to = 'NORMAL', 'WORLD', 'OBJECT'
    b.link(geo.outputs['Normal'], nrm.inputs['Vector'])
    for i, z in enumerate(live):
        tag = f'{PREFIX}{i}:'
        tc = b.node('ShaderNodeTexCoord')
        tc.name = tag + 'tc'
        tc.object = z.projector
        q = tc.outputs['Object']
        P = [list(z.win[r * 4:(r + 1) * 4]) for r in range(4)]

        def row(r):
            d = b.node('ShaderNodeVectorMath')
            d.operation = 'DOT_PRODUCT'
            d.name = f'{tag}row{r}'
            b.link(q, d.inputs[0])
            d.inputs[1].default_value = P[r][:3]
            return b.math('ADD', d.outputs['Value'], P[r][3])
        den = row(3)
        u = b.math('ADD', b.math('MULTIPLY', b.math('DIVIDE', row(0), den), 0.5), 0.5)
        v = b.math('ADD', b.math('MULTIPLY', b.math('DIVIDE', row(1), den), 0.5), 0.5)
        uv = b.node('ShaderNodeCombineXYZ')
        b.link(u, uv.inputs[0])
        b.link(v, uv.inputs[1])
        tex = b.node('ShaderNodeTexImage')
        tex.name = tag + 'mask'
        tex.image = z.mask
        tex.extension = 'CLIP'
        tex.interpolation = 'Linear'
        b.link(uv.outputs['Vector'], tex.inputs['Vector'])
        m = tex.outputs['Color']
        # (in front of the view, only as deep as the part was)
        sep = b.node('ShaderNodeSeparateXYZ')
        b.link(q, sep.inputs['Vector'])
        depth = b.math('MULTIPLY', sep.outputs['Z'], -1.0)
        m = b.math('MULTIPLY', m, b.math('MULTIPLY', b.math('GREATER_THAN', depth, z.near),
                                         b.math('LESS_THAN', depth, z.far)))
        # (facing the view when it was drawn - the part's own space: the zone moves with the part)
        pos = tco.outputs['Object']
        ray = b.vmath('SUBTRACT', pos, tuple(z.eye)) if z.persp else None
        fd = b.node('ShaderNodeVectorMath')
        fd.operation = 'DOT_PRODUCT'
        b.link(nrm.outputs['Vector'], fd.inputs[0])
        if ray is not None:
            b.link(ray, fd.inputs[1])
        else:
            fd.inputs[1].default_value = tuple(z.look)
        facing = b.math('LESS_THAN', fd.outputs['Value'], 0.0)
        thr = b.value(f'z{i}_through', 1.0 if z.through else 0.0)
        thr.node.name = tag + 'through'
        m = b.math('MULTIPLY', m, b.math('MAXIMUM', facing, thr))
        op = b.value(f'z{i}_opacity', z.opacity)
        op.node.name = tag + 'opacity'
        m = b.math('MULTIPLY', m, op, clamp=True)
        col = b.node('ShaderNodeRGB')
        col.name = tag + 'color'
        col.outputs[0].default_value = (*z.color, 1.0)
        vals = {}
        for k, val in (('rough', z.roughness), ('metal', z.metallic), ('cover', z.cover)):
            vals[k] = b.value(f'z{i}_{k}', val)
            vals[k].node.name = tag + k
        if mask_t is None:
            mask_t, col_t = m, col.outputs[0]
            rough_t, metal_t, cover_t = vals['rough'], vals['metal'], vals['cover']
        else:                                   # (a later zone over the earlier ones)
            col_t = b.mixc(m, col_t, col.outputs[0])
            rough_t = b.mixf(m, rough_t, vals['rough'])
            metal_t = b.mixf(m, metal_t, vals['metal'])
            cover_t = b.mixf(m, cover_t, vals['cover'])
            mask_t = b.math('MAXIMUM', mask_t, m)
    for nd in nt.nodes:                         # (only what was made here is the zones': named so it can go again)
        if nd.as_pointer() not in before and not nd.name.startswith(PREFIX):
            nd.name = PREFIX + nd.name
    nt.links.new(mask_t, hub['mask'].inputs[0])
    nt.links.new(cover_t, hub['cover'].inputs[0])
    nt.links.new(rough_t, hub['rough'].inputs[0])
    nt.links.new(metal_t, hub['metal'].inputs[0])
    nt.links.new(col_t, csock)


def sync(mat):
    """A zone's sliders into its nodes (no re-making)."""
    zs = zones_of(mat)
    if not zs or not ms.is_mech(mat):
        return
    nodes = mat.node_tree.nodes
    live = [z for z in zs if z.projector is not None and z.mask is not None]
    if nodes.get(f'{PREFIX}{len(live) - 1}:mask') is None or nodes.get(f'{PREFIX}{len(live)}:mask') is not None:
        relink(mat)
        return
    for i, z in enumerate(live):
        tag = f'{PREFIX}{i}:'
        nodes[tag + 'color'].outputs[0].default_value = (*z.color, 1.0)
        for k, val in (('rough', z.roughness), ('metal', z.metallic), ('cover', z.cover), ('opacity', z.opacity),
                       ('through', 1.0 if z.through else 0.0)):
            nodes[tag + k].outputs[0].default_value = val


# -----------------------------------------------------------------------------
# making a zone
# -----------------------------------------------------------------------------

def _view(region, rv3d):
    return rv3d.view_matrix.copy(), rv3d.window_matrix.copy(), bool(rv3d.is_perspective), region.width, region.height


def _depth_range(ob, view_matrix):
    """How deep the part is along the view (its bounding box's corners in view space): (near, far) with a margin."""
    vm = view_matrix @ ob.matrix_world
    zs = [-(vm @ Vector(c)).z for c in ob.bound_box]
    pad = 0.05 * (max(zs) - min(zs) + 1e-6) + 1e-4
    return max(0.0, min(zs) - pad), max(zs) + pad


def add_paint_zone(context, ob, pts, view_matrix, window_matrix, persp, rw, rh, color=None):
    """A Paint Zone on ``ob``'s Mech material from the lasso ``pts`` (region pixels) drawn in that view.  Returns the
    zone."""
    mat = ob.active_material
    if not ms.is_mech(mat):
        raise RuntimeError('the part has no Mech Shader material - apply one first')
    if len(pts) < 3:
        raise RuntimeError('the lasso needs at least 3 points')
    zs = zones_of(mat)
    n = len(zs) + 1
    img = mask_image(f'.MCH Zone {mat.name} {n}', pts, rw, rh)
    proj = bpy.data.objects.new(f'Zone {n} ({ob.name})', None)
    proj.empty_display_type = 'PLAIN_AXES'
    proj.empty_display_size = 0.01
    cols = ob.users_collection or (context.scene.collection,)
    cols[0].objects.link(proj)
    proj.matrix_world = view_matrix.inverted()
    proj.parent = ob
    proj.matrix_parent_inverse = ob.matrix_world.inverted()
    proj.hide_select = True
    proj.hide_render = True
    proj['mch_zone'] = 1
    z = zs.add()
    z.name = f'Zone {n}'
    z.projector = proj
    z.mask = img
    z.win = [window_matrix[r][c] for r in range(4) for c in range(4)]
    z.persp = persp
    to_part = ob.matrix_world.inverted() @ view_matrix.inverted()
    z.eye = tuple(to_part.translation)
    z.look = tuple((to_part.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized())
    z.near, z.far = _depth_range(ob, view_matrix)
    z.color = color or PALETTE[(n - 1) % len(PALETTE)]
    relink(mat)
    proj.hide_set(True)
    return z


def remove_zone(mat, index):
    zs = zones_of(mat)
    if zs is None or not (0 <= index < len(zs)):
        return False
    z = zs[index]
    proj, img = z.projector, z.mask
    zs.remove(index)
    if proj is not None:
        bpy.data.objects.remove(proj)
    if img is not None and img.users == 0:
        bpy.data.images.remove(img)
    relink(mat)
    return True


# -----------------------------------------------------------------------------
# Split Zone: edges cut along the lasso, the faces inside a material of their own
# -----------------------------------------------------------------------------

def _inside(px, poly):
    """bool per point: inside the closed polygon (even-odd)."""
    x, y = px[:, 0], px[:, 1]
    p = np.asarray(poly, np.float64)
    ins = np.zeros(len(px), bool)
    for (ax, ay), (bx, by) in zip(p, np.roll(p, -1, axis=0)):
        c = ((ay > y) != (by > y)) & (x < (bx - ax) * (y - ay) / np.where(by - ay == 0, 1e-12, by - ay) + ax)
        ins ^= c
    return ins


class _View:
    """The view the lasso was drawn in, in the part's own space: rays through region pixels, pixels of points."""

    def __init__(self, ob, view_matrix, window_matrix, persp, rw, rh):
        self.full = window_matrix @ view_matrix @ ob.matrix_world
        self.inv = self.full.inverted()
        self.rw, self.rh, self.persp = rw, rh, persp
        to_part = ob.matrix_world.inverted() @ view_matrix.inverted()
        self.eye = to_part.translation.copy()
        self.look = (to_part.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()

    def ray(self, px):
        nx, ny = 2.0 * px[0] / self.rw - 1.0, 2.0 * px[1] / self.rh - 1.0
        a = self.inv @ Vector((nx, ny, -1.0, 1.0))
        b = self.inv @ Vector((nx, ny, 1.0, 1.0))
        a, b = a.xyz / a.w, b.xyz / b.w
        return a, (b - a).normalized()

    def to_px(self, co):
        v = self.full @ Vector((co[0], co[1], co[2], 1.0))
        if abs(v.w) < 1e-12:
            return None
        return ((v.x / v.w * 0.5 + 0.5) * self.rw, (v.y / v.w * 0.5 + 0.5) * self.rh)

    def facing(self, co, normal):
        d = (Vector(co) - self.eye) if self.persp else self.look
        return normal.dot(d) < 0.0


def _walls(ob, view, pts):
    """The cutter: a band of quads along the lasso, each lasso point's ray from a little in front of the part's
    surface there to a little behind it (only the side seen is cut, not the back).  Part space: (verts, quads)."""
    from mathutils.bvhtree import BVHTree
    me = ob.data
    bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [p.vertices for p in me.polygons])
    size = max(ob.dimensions) / max(max(ob.matrix_world.to_scale()), 1e-9) or 1.0
    margin = 0.04 * size
    rays, hits = [], []
    for px in pts:
        o, d = view.ray(px)
        rays.append((o, d))
        loc, _n, _i, dist = bvh.ray_cast(o, d)
        hits.append(dist if loc is not None else None)
    known = [h for h in hits if h is not None]
    if not known:                                   # (the lasso misses the part everywhere: through all of it)
        c = sum((Vector(v) for v in ob.bound_box), Vector()) / 8.0
        o, d = rays[0]
        mid = (c - o).dot(d)
        hits = [mid] * len(pts)
        margin = size
    else:                                           # (a point off the part: its nearest neighbour's depth)
        n = len(hits)
        for i in range(n):
            if hits[i] is None:
                for k in range(1, n):
                    for j in ((i - k) % n, (i + k) % n):
                        if hits[j] is not None and hits[i] is None:
                            hits[i] = hits[j]
    verts, quads = [], []
    for (o, d), h in zip(rays, hits):
        verts.append(o + d * max(0.0, h - margin))
        verts.append(o + d * (h + margin))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        quads.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
    return verts, quads


def split_zone(context, ob, pts, view_matrix, window_matrix, persp, rw, rh, preset=None):
    """Cut ``ob``'s mesh along the lasso (seen from the view; Edit-mode Intersect, Exact - the outline as new edges,
    the mesh stays one piece) and give the faces inside that are seen from the view a second Mech material (a copy
    of its own).  Returns (material, faces inside)."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    mat = ob.active_material
    if not ms.is_mech(mat):
        raise RuntimeError('the part has no Mech Shader material - apply one first')
    if len(pts) < 3:
        raise RuntimeError('the lasso needs at least 3 points')
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    view = _View(ob, view_matrix, window_matrix, persp, rw, rh)
    wv, wq = _walls(ob, view, pts)
    me = ob.data
    K = me.copy()
    K.name = '.MCH Zone Knife'
    bm = bmesh.new()
    bm.from_mesh(K)
    lay = bm.faces.layers.int.new('mch_zone_cut')
    for f in bm.faces:
        f[lay] = 1
    nv = [bm.verts.new(c) for c in wv]
    for q in wq:
        try:
            f = bm.faces.new([nv[k] for k in q])
            f[lay] = 2
        except ValueError:
            pass
    bm.to_mesh(K)
    bm.free()
    ko = bpy.data.objects.new('.MCH Zone Knife', K)
    context.scene.collection.objects.link(ko)
    ko.matrix_world = ob.matrix_world.copy()
    vl = context.view_layer
    active = vl.objects.active
    selected = [o for o in vl.objects if o.select_get()]
    try:
        for o in selected:
            o.select_set(False)
        ko.select_set(True)
        vl.objects.active = ko
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            ebm = bmesh.from_edit_mesh(K)
            el = ebm.faces.layers.int.get('mch_zone_cut')
            for v in ebm.verts:
                v.select_set(False)
            for f in ebm.faces:
                f.select_set(f[el] == 2)
            ebm.select_flush_mode()
            bmesh.update_edit_mesh(K)
            bpy.ops.mesh.intersect(mode='SELECT_UNSELECT', separate_mode='NONE', solver='EXACT')
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')
        bm = bmesh.new()
        bm.from_mesh(K)
    finally:
        bpy.data.objects.remove(ko)
        for o in selected:
            try:
                o.select_set(True)
            except (ReferenceError, RuntimeError):
                pass
        try:
            vl.objects.active = active
        except (ReferenceError, RuntimeError):
            pass
    try:
        lay = bm.faces.layers.int.get('mch_zone_cut')
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[lay] == 2], context='FACES')
        bm.faces.layers.int.remove(lay)
        bm.faces.ensure_lookup_table()
        bm.faces.index_update()                     # (the tree's face indices = these)
        bm.normal_update()
        # the faces inside: most of their area inside the lasso (triangle by triangle - a face of the ring round the
        # lasso can have its middle inside it), facing the view and seen (the first hit along the ray)
        tree = BVHTree.FromBMesh(bm)
        size = max(ob.dimensions) / max(max(ob.matrix_world.to_scale()), 1e-9) or 1.0
        inside = []
        tris = {}
        for lt in bm.calc_loop_triangles():
            tris.setdefault(lt[0].face, []).append(lt)
        cands, tri_px, tri_area, owner = [], [], [], []
        for f, lts in tris.items():
            if not view.facing(f.calc_center_median(), f.normal):
                continue
            cands.append(f)
            for lt in lts:
                cc = sum((l.vert.co for l in lt), Vector()) / 3.0
                pc = view.to_px(cc)
                tri_px.append(pc if pc is not None else (-1e9, -1e9))
                tri_area.append((lt[1].vert.co - lt[0].vert.co).cross(lt[2].vert.co - lt[0].vert.co).length / 2)
                owner.append(len(cands) - 1)
        if cands:
            tin = _inside(np.array(tri_px, np.float64), pts)
            area = np.array(tri_area)
            own = np.array(owner)
            a_in = np.bincount(own, weights=area * tin, minlength=len(cands))
            a_all = np.bincount(own, weights=area, minlength=len(cands))
            best = {}
            for k, (o_, ok) in enumerate(zip(own, tin)):        # (a point of the face inside: the largest triangle in)
                if ok and (o_ not in best or area[k] > area[best[o_]]):
                    best[o_] = k
            flat = [lt for f in cands for lt in tris[f]]
            for ci, f in enumerate(cands):
                if a_all[ci] <= 0 or a_in[ci] < 0.5 * a_all[ci]:
                    continue
                lt = flat[best[ci]]
                c = sum((l.vert.co for l in lt), Vector()) / 3.0
                if view.persp:
                    o = view.eye
                    d = (c - o)
                else:
                    d = view.look.copy()
                    o = c - d * (2.0 * size)
                dist = d.length if view.persp else 2.0 * size
                d.normalize()
                _loc, _n, idx, hd = tree.ray_cast(o, d)
                if idx is None or idx == f.index or hd >= dist - 1e-4 * size:
                    inside.append(f)
        zmat = mat.copy()
        zmat.name = mat.name + ' Zone'
        zs = zones_of(zmat)
        if zs is not None:
            while len(zs):
                zs.remove(0)
        st = getattr(zmat, ms.KEY)
        if preset:
            ms.apply_preset(zmat, preset)
        else:                                       # (a painted zone of the part's own material: a colour to start)
            st.paint = max(st.paint, 1.0)
            st.paint_color = PALETTE[0]
        me.materials.append(zmat)
        slot = len(me.materials) - 1
        for f in inside:
            f.material_index = slot
        bm.to_mesh(me)
    finally:
        bm.free()
        bpy.data.meshes.remove(K)
    me.update()
    try:
        ms.store_curvature(me)
    except (AttributeError, RuntimeError, ValueError):
        pass
    relink(zmat)
    ms.sync(zmat)
    ob.active_material_index = slot
    return zmat, len(inside)


# -----------------------------------------------------------------------------
# the lasso
# -----------------------------------------------------------------------------

_DRAW = {}


def _draw_lasso(op, context):
    import gpu
    from gpu_extras.batch import batch_for_shader
    pts = list(op.pts) + ([op.cursor] if op.cursor is not None and op.clicks else [])
    if len(pts) < 2:
        return
    try:
        sh = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        sh.uniform_float('viewportSize', (context.region.width, context.region.height))
        sh.uniform_float('lineWidth', 2.0)
    except (ValueError, AttributeError):
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
    sh.uniform_float('color', (0.25, 0.6, 1.0, 0.95) if op.mode == 'PAINT' else (1.0, 0.55, 0.15, 0.95))
    batch = batch_for_shader(sh, 'LINE_LOOP', {'pos': [(x, y) for x, y in pts]})
    gpu.state.blend_set('ALPHA')
    batch.draw(sh)
    gpu.state.blend_set('NONE')


class MCH_OT_zone_lasso(bpy.types.Operator):
    """Draw a zone on the part: drag a lasso, or click its corners (Enter / Space / double-click: done; Esc: cancel).
    Paint: the zone's own paint (colour, roughness, metallic) projected from this view.  Split: edges cut along it, the
    faces inside a material of their own"""
    bl_idname = 'mch.zone_lasso'
    bl_label = 'Lasso Zone'
    bl_options = {'REGISTER', 'UNDO'}
    mode: EnumProperty(items=[('PAINT', 'Paint Zone', 'Its own paint, projected (the mesh as it is)'),
                              ('SPLIT', 'Split Zone', 'Edges cut along the lasso, a material of its own')],
                       default='PAINT')

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH' and ms.is_mech(ob.active_material)

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, 'Zone: use it in the 3D view')
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        self.pts, self.cursor, self.state, self.press = [], None, 'NONE', None
        self._region = context.region
        self._handle = bpy.types.SpaceView3D.draw_handler_add(_draw_lasso, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window.cursor_modal_set('CROSSHAIR')
        what = 'Paint Zone' if self.mode == 'PAINT' else 'Split Zone'
        context.area.header_text_set(f'{what}: drag a lasso, or click its corners (Enter / Space / double-click / the '
                                     'first point: done; Esc / right click: cancel)')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    @property
    def clicks(self):
        return self.state == 'CLICK'

    def _end(self, context):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        context.window.cursor_modal_restore()
        if context.area is not None:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def _commit(self, context):
        self._end(context)
        region = self._region
        rv3d = region.data
        vm, wm, persp, rw, rh = _view(region, rv3d)
        ob = context.active_object
        try:
            if self.mode == 'PAINT':
                z = add_paint_zone(context, ob, self.pts, vm, wm, persp, rw, rh)
                self.report({'INFO'}, f'{z.name} on {ob.name}')
            else:
                zmat, n = split_zone(context, ob, self.pts, vm, wm, persp, rw, rh)
                self.report({'INFO'}, f'Split Zone: {n} faces -> "{zmat.name}"')
        except RuntimeError as ex:
            self.report({'WARNING'}, f'Zone: {ex}')
            return {'CANCELLED'}
        return {'FINISHED'}

    def modal(self, context, event):
        """NONE --press--> (drag past 6 px) DRAG --release--> done;  NONE / CLICK --release--> a corner (CLICK);
        CLICK: the first corner again / double-click / Enter / Space -> done."""
        if context.area is not None:
            context.area.tag_redraw()
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._end(context)
            return {'CANCELLED'}
        pos = (float(event.mouse_region_x), float(event.mouse_region_y))
        if event.type in {'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS' and len(self.pts) >= 3:
            return self._commit(context)
        if event.type == 'MOUSEMOVE':
            self.cursor = pos
            if self.state in {'PRESSED', 'DRAG'}:
                last = self.pts[-1] if self.pts else self.press
                far = (pos[0] - self.press[0]) ** 2 + (pos[1] - self.press[1]) ** 2 > 36.0
                if self.state == 'PRESSED' and far:
                    self.state = 'DRAG'
                    self.pts = [self.press]
                if self.state == 'DRAG' and (pos[0] - last[0]) ** 2 + (pos[1] - last[1]) ** 2 > 9.0:
                    self.pts.append(pos)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE':
            if event.value == 'DOUBLE_CLICK' and self.clicks and len(self.pts) >= 3:
                return self._commit(context)
            if event.value == 'PRESS':
                self.press = pos
                if self.state == 'NONE':
                    self.state = 'PRESSED'
                return {'RUNNING_MODAL'}
            if event.value == 'RELEASE':
                if self.press is None:                  # (the release of the click that started it: not a corner)
                    return {'RUNNING_MODAL'}
                if self.state == 'DRAG':
                    if len(self.pts) >= 3:
                        return self._commit(context)
                    self.state, self.pts = 'NONE', []
                    return {'RUNNING_MODAL'}
                self.state = 'CLICK'
                if len(self.pts) >= 3 and (pos[0] - self.pts[0][0]) ** 2 + (pos[1] - self.pts[0][1]) ** 2 < 100.0:
                    return self._commit(context)               # (the first corner clicked again: closed)
                if not self.pts or (pos[0] - self.pts[-1][0]) ** 2 + (pos[1] - self.pts[-1][1]) ** 2 > 4.0:
                    self.pts.append(pos)
                return {'RUNNING_MODAL'}
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}                           # (orbit / zoom while drawing)
        return {'RUNNING_MODAL'}


class MCH_OT_zone_remove(bpy.types.Operator):
    """Remove this Paint Zone"""
    bl_idname = 'mch.zone_remove'
    bl_label = 'Remove Zone'
    bl_options = {'REGISTER', 'UNDO'}
    index: IntProperty(default=0)

    def execute(self, context):
        mat = ms.active_mech(context)
        return {'FINISHED'} if mat is not None and remove_zone(mat, self.index) else {'CANCELLED'}


class MCH_OT_zone_slot(bpy.types.Operator):
    """Show this material of the part (its own settings on the Mech page)"""
    bl_idname = 'mch.zone_slot'
    bl_label = 'Material Slot'
    bl_options = {'REGISTER', 'UNDO'}
    index: IntProperty(default=0)

    def execute(self, context):
        ob = context.active_object
        if ob is None or not (0 <= self.index < len(ob.material_slots)):
            return {'CANCELLED'}
        ob.active_material_index = self.index
        return {'FINISHED'}


CLASSES = (MCH_PG_Zone, MCH_OT_zone_lasso, MCH_OT_zone_remove, MCH_OT_zone_slot)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Material.mch_zones = CollectionProperty(type=MCH_PG_Zone)


def unregister():
    if hasattr(bpy.types.Material, 'mch_zones'):
        del bpy.types.Material.mch_zones
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
