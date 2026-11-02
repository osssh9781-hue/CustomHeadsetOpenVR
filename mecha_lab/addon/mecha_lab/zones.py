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
* the wear (user: "엣지 까짐이랑 긁힘 때 녹은 분리된 색이랑 다르게 넣고 싶은데 - 똑같이 넣는 거랑 다르게 넣는 거 옵션으로"):
  the same as the part's by default; a Paint Zone's **Own Wear** gives it its own Edge Wear, Scratches, Dirt (crevices,
  top, low) and Rust (starting from the part's); a Split Zone's material has **Same Wear as the part** - on: its chips,
  scratches, dirt, rust follow the part's material as it changes; off: set on its own
* the boundary line (user: "컬러 다르게 한 경계에 라인으로 경계 범프 생기게, 헤이트값 조절 가능하게"): along the zone's
  edge a line in the bump - Line Height (+ raised ridge, - engraved groove, 0 none) and Line Width (% of the part's
  size).  The mask picture is a signed distance field (how far each pixel is from the lasso outline, inside +), so the
  line sits exactly on the boundary at any width; a Split Zone has it on both sides of the cut (a line-only zone in
  the part's material and in the zone's, kept in step)
* 0.24.95 Creatures too (user: "크리쳐도 이 라쏘 영역으로 재질 다르게 - 크리쳐 버전은 외곽에 에어브러시 버전, 텍스쳐 버전"):
  a Paint Zone on a Creature Shader material - markings: its colour (or one of the creature colour textures, tinted)
  and roughness over the skin's, under the crevices, scars and conditions.  Its **Edge**: Hard, **Airbrush** (a soft
  sprayed fade out past the lasso, Edge Width far) or **Texture** (the outline pushed out by an organic pattern, 0 ..
  Edge Width, Edge Scale) - what was drawn stays painted; the Mech zones have the same Edge choice

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
LINE_GAIN = 3.0                   # (Line Height 1 = 3 x the Mech bump's unit: a line reads at its narrow width)
SDF_R = 96.0                      # (the distance field's reach, mask pixels: 0 / 1 in the picture = 96 px out / in;
#                                    a zone keeps the reach its picture was made with: ``reach``)
CREATURE_PALETTE = ((0.06, 0.05, 0.04), (0.75, 0.68, 0.55), (0.45, 0.08, 0.05), (0.12, 0.2, 0.08), (0.85, 0.55, 0.1),
                    (0.2, 0.25, 0.4))
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


def signed_distance(pts, w, h, reach=SDF_R):
    """(h, w) float32: each pixel's distance to the polygon's outline (pixels), + inside, - outside, cut at
    +-``reach`` (only the band round the outline is measured)."""
    inside = fill_polygon(pts, w, h) >= 0.5
    d = np.full((h, w), reach, np.float32)
    p = np.asarray(pts, np.float64)
    for (ax, ay), (bx, by) in zip(p, np.roll(p, -1, axis=0)):
        x0, x1 = int(max(0, math.floor(min(ax, bx) - reach))), int(min(w, math.ceil(max(ax, bx) + reach) + 1))
        y0, y1 = int(max(0, math.floor(min(ay, by) - reach))), int(min(h, math.ceil(max(ay, by) + reach) + 1))
        if x1 <= x0 or y1 <= y0:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        ex, ey = bx - ax, by - ay
        ll = ex * ex + ey * ey
        t = np.clip(((X - ax) * ex + (Y - ay) * ey) / ll, 0.0, 1.0) if ll > 0 else np.zeros_like(X)
        dd = np.hypot(X - (ax + t * ex), Y - (ay + t * ey)).astype(np.float32)
        np.minimum(d[y0:y1, x0:x1], dd, out=d[y0:y1, x0:x1])
    return np.where(inside, d, -d)


def _cs():
    from . import creature_shader as cs
    return cs


def zoned(mat):
    """A material the zones work on: a Mech Shader or a Creature Shader one."""
    return ms.is_mech(mat) or _cs().is_creature(mat)


def mask_image(name, pts, rw, rh):
    """A packed grey image of the lasso over the whole view (``rw`` x ``rh`` pixels), at most MASK_MAX on its long
    side: a signed distance field, 0.5 on the outline, + SDF_R pixels inside = 1, outside = 0.  Image row 0 is the
    bottom (Blender's)."""
    s = min(1.0, MASK_MAX / float(max(rw, rh)))
    w, h = max(8, int(round(rw * s))), max(8, int(round(rh * s)))
    sx, sy = w / float(rw), h / float(rh)
    sd = signed_distance([(x * sx, y * sy) for x, y in pts], w, h)
    a = np.clip(0.5 + sd / (2.0 * SDF_R), 0.0, 1.0)
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


_TEX = []


def _tex_items():
    if not _TEX:
        _TEX[:] = [('FLAT', 'Flat', 'Its colour only')] + [(k, n, '') for k, n in _cs().CMAPS['color']]
    return _TEX


def _tex_enum(self, context):
    return _tex_items()


def _tex_update(self, context):
    """A texture picked: the colour to grey (the texture as it is) the first time; its nodes made anew."""
    mat = self.id_data
    if self.tex != 'FLAT' and self.get('mch_tex_tinted') is None:
        self['mch_tex_tinted'] = 1
        self.color = (0.5, 0.5, 0.5)
    relink(mat)


def _line_update(self, context):
    """A boundary line's sliders - and its twin's (a Split Zone's line lives in the part's material and the zone's)."""
    sync(self.id_data)
    for m, z in twins(self):
        if abs(z.line_height - self.line_height) > 1e-7:
            z.line_height = self.line_height
        if abs(z.line_width - self.line_width) > 1e-7:
            z.line_width = self.line_width


def twins(zone):
    """The other zones that share ``zone``'s projector: [(material, zone)]."""
    out = []
    if zone.projector is None:
        return out
    for m in bpy.data.materials:
        for z in getattr(m, 'mch_zones', ()):
            if z.projector == zone.projector and z.as_pointer() != zone.as_pointer():
                out.append((m, z))
    return out


def _own_update(self, context):
    """Own Wear turned on: it starts from the part's own amounts."""
    mat = self.id_data
    if self.own_wear and ms.is_mech(mat):
        st = getattr(mat, ms.KEY)
        for k in ms.ZONE_WEAR:
            setattr(self, k, getattr(st, k))
    sync(mat)


# the Split Zone material's "Same Wear": what it takes from the part's material
FOLLOW = ('edge_wear', 'scratches', 'rust', 'rust_scratch', 'dirt', 'dirt_top', 'dirt_low', 'dust', 'streaks',
          'primer', 'chip_follow', 'chip_reach', 'chip_soft', 'chip_breakup', 'chip_scale', 'chip_map', 'scratch_map',
          'rust_map', 'dirt_map', 'scratch_color', 'scratch_tint', 'rust_color', 'dirt_color', 'dust_color',
          'primer_color', 'edge_mat', 'edge_color', 'edge_metal', 'edge_rough', 'edge_polish', 'edge_map', 'h_scratch',
          'h_chip', 'h_rust', 'h_dirt')


def _copy_wear(src, dst):
    for k in FOLLOW:
        a = getattr(src, k)
        b = getattr(dst, k)
        same = tuple(a) == tuple(b) if hasattr(a, '__len__') and not isinstance(a, str) else a == b
        if not same:
            setattr(dst, k, a)


def follow(mat):
    """Same Wear: ``mat``'s wear copied to its Split Zone materials that follow it, and - when ``mat`` is such a zone
    itself (a preset put on it, a slider moved) - the part's wear back on it.  Only what differs."""
    if not ms.is_mech(mat):
        return
    parent = getattr(mat, 'mch_zone_parent', None)
    if getattr(mat, 'mch_zone_follow', False) and ms.is_mech(parent) and parent is not mat:
        _copy_wear(getattr(parent, ms.KEY), getattr(mat, ms.KEY))
    src = getattr(mat, ms.KEY)
    for m in bpy.data.materials:
        if m is mat or getattr(m, 'mch_zone_parent', None) != mat or not getattr(m, 'mch_zone_follow', False) \
                or not ms.is_mech(m):
            continue
        _copy_wear(src, getattr(m, ms.KEY))


def _follow_update(self, context):
    parent = getattr(self, 'mch_zone_parent', None)
    if self.mch_zone_follow and parent is not None:
        follow(parent)


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
    own_wear: BoolProperty(name='Own Wear', default=False, update=_own_update,
                           description='Its own chips, scratches, dirt and rust inside the zone (off: the part\'s)')
    edge_wear: FloatProperty(name='Edge Wear', default=0.0, min=0.0, max=1.0, update=_update)
    scratches: FloatProperty(name='Scratches', default=0.0, min=0.0, max=1.0, update=_update)
    dirt: FloatProperty(name='Dirt in Crevices', default=0.0, min=0.0, max=1.0, update=_update)
    dirt_top: FloatProperty(name='Dirt on Top', default=0.0, min=0.0, max=1.0, update=_update)
    dirt_low: FloatProperty(name='Dirt from Below', default=0.0, min=0.0, max=1.0, update=_update)
    rust: FloatProperty(name='Rust', default=0.0, min=0.0, max=1.0, update=_update)
    kind: EnumProperty(items=[('PAINT', 'Paint', 'A Paint Zone'), ('LINE', 'Line', 'Only a boundary line (a Split Zone)')],
                       default='PAINT')
    line_height: FloatProperty(name='Line Height', default=-0.35, min=-1.0, max=1.0, update=_line_update,
                               description='A line along the boundary in the bump: + a raised ridge, - an engraved '
                               'groove, 0 none')
    line_width: FloatProperty(name='Line Width', default=0.6, min=0.05, max=5.0, update=_line_update,
                              description='How wide the boundary line is (% of the part\'s size)')
    edge: EnumProperty(name='Edge', items=[('HARD', 'Hard', 'A clean outline'),
                                           ('AIRBRUSH', 'Airbrush', 'A soft sprayed fade across the outline'),
                                           ('TEXTURE', 'Texture', 'The outline broken up by an organic pattern')],
                       default='HARD', update=_update, description='How the zone\'s outline looks')
    edge_width: FloatProperty(name='Edge Width', default=3.0, min=0.1, max=30.0, update=_update,
                              description='How far the soft / broken-up edge reaches out past the lasso (% of the '
                              'part\'s size); what was drawn stays painted')
    edge_scale: FloatProperty(name='Edge Scale', default=1.0, min=0.1, max=10.0, update=_update,
                              description='The pattern breaking up the outline: bigger = finer')
    tex: EnumProperty(name='Texture', items=_tex_enum, update=_tex_update,
                      description='A creature colour texture for the zone (tinted by Color: grey = as it is)')
    tex_scale: FloatProperty(name='Texture Scale', default=1.0, min=0.05, max=20.0, update=_update)
    reach: FloatProperty(default=48.0)                        # (its distance field's reach, mask pixels)
    size: FloatProperty(default=1.0)                          # (the part's size when drawn, world)
    px_per_unit: FloatProperty(default=100.0)                 # (mask pixels per world unit at the part's depth)


def zones_of(mat):
    return getattr(mat, 'mch_zones', None) if mat is not None else None


def _clear_nodes(nt):
    for nd in [n for n in nt.nodes if n.name.startswith(PREFIX)]:
        nt.nodes.remove(nd)


def current(mat):
    """An older Mech / Creature tree (made before the zones' hubs - a file from an earlier version) made anew first,
    its settings kept (the shader's own sync does it; the new tree links the zones itself).  Returns True when it
    did.  (User: "근데 페인트 존이 안 먹혀" - a zone on such a material had nothing to link into.)"""
    if ms.is_mech(mat) and mat.get('mch_mech', 0) < ms.VERSION:
        ms.sync(mat)
        return True
    cs = _cs()
    if cs.is_creature(mat) and mat.get(cs.KEY, 0) < cs.VERSION:
        cs.sync(mat)
        return True
    return False


def relink(mat):
    """The zone nodes made anew in ``mat`` (after its Mech Shader tree was made, or a zone added / removed) and linked
    into the Mech Shader's zone hubs."""
    if not zoned(mat):
        return
    if current(mat):                            # (made anew: the zones are linked already)
        return
    nt = mat.node_tree
    _clear_nodes(nt)
    zs = zones_of(mat)
    hub = {k: nt.nodes.get('mch:zone_' + k) for k in ('mask', 'cover', 'rough', 'metal', 'color')}
    if hub['mask'] is None or hub['color'] is None:     # (cover / metal: the Mech Shader's only)
        return
    live = [z for z in zs if z.projector is not None and z.mask is not None] if zs else []
    hub['own'] = nt.nodes.get('mch:zone_own')
    hub['height'] = nt.nodes.get('mch:zone_height')
    for k in ms.ZONE_WEAR:
        hub['w_' + k] = nt.nodes.get('mch:zone_w_' + k)
    for k, nd in hub.items():
        if k != 'color' and nd is not None:
            for lk in list(nd.inputs[0].links):
                nt.links.remove(lk)
    csock = {sk.identifier: sk for sk in hub['color'].inputs}['A_Color']
    for lk in list(csock.links):
        nt.links.remove(lk)
    if not live:
        return
    before = {nd.as_pointer() for nd in nt.nodes}
    b = ms.Builder(nt)
    mask_t = col_t = rough_t = metal_t = cover_t = line_t = None
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
        # (the distance field: mask pixels from the outline, + inside)
        sd = b.math('MULTIPLY', b.math('SUBTRACT', tex.outputs['Color'], 0.5), 2.0 * z.reach)
        m = _edge(b, z, sd, tco.outputs['Object'], tag)
        # (in front of the view, only as deep as the part was)
        sep = b.node('ShaderNodeSeparateXYZ')
        b.link(q, sep.inputs['Vector'])
        depth = b.math('MULTIPLY', sep.outputs['Z'], -1.0)
        gate = b.math('MULTIPLY', b.math('GREATER_THAN', depth, z.near), b.math('LESS_THAN', depth, z.far))
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
        gate = b.math('MULTIPLY', gate, b.math('MAXIMUM', facing, thr))
        # (the boundary line: a smooth ridge across the outline, Line Width wide, x Line Height)
        lw = b.value(f'z{i}_lw', _half_width_px(z))
        lw.node.name = tag + 'lw'
        lh = b.value(f'z{i}_lh', z.line_height)
        lh.node.name = tag + 'lh'
        prof = b.maprange(b.math('ABSOLUTE', sd), 0.0, lw, 1.0, 0.0)
        prof.node.interpolation_type = 'SMOOTHSTEP'
        ln = b.math('MULTIPLY', b.math('MULTIPLY', prof, gate), b.math('MULTIPLY', lh, LINE_GAIN))
        line_t = ln if line_t is None else b.math('ADD', line_t, ln)
        if z.kind == 'LINE':
            continue
        m = b.math('MULTIPLY', m, gate)
        op = b.value(f'z{i}_opacity', z.opacity)
        op.node.name = tag + 'opacity'
        m = b.math('MULTIPLY', m, op, clamp=True)
        col = b.node('ShaderNodeRGB')
        col.name = tag + 'color'
        col.outputs[0].default_value = (*z.color, 1.0)
        zcol = col.outputs[0]
        if z.tex != 'FLAT':                     # (a creature colour texture, tinted by Color: grey = as it is)
            timg = b.node('ShaderNodeTexImage')
            timg.name = tag + 'tex'
            timg.image = _cs().cmap_image('color', z.tex)
            tsc = b.value(f'z{i}_tsc', _tex_tiles(z))
            tsc.node.name = tag + 'tsc'
            b.link(b.vmath('SCALE', tco.outputs['Object'], fac=tsc), timg.inputs['Vector'])
            zcol = b.vmath('SCALE', b.mixc(1.0, timg.outputs['Color'], col.outputs[0], 'MULTIPLY'), fac=2.0)
        vals = {}
        for k, val in (('rough', z.roughness), ('metal', z.metallic), ('cover', z.cover)):
            vals[k] = b.value(f'z{i}_{k}', val)
            vals[k].node.name = tag + k
        ow = b.value(f'z{i}_own', 1.0 if z.own_wear else 0.0)
        ow.node.name = tag + 'own'
        om = b.math('MULTIPLY', m, ow)
        wv = {}
        for k in ms.ZONE_WEAR:
            wv[k] = b.value(f'z{i}_w_{k}', getattr(z, k))
            wv[k].node.name = tag + 'w_' + k
        if mask_t is None:
            mask_t, col_t = m, zcol
            rough_t, metal_t, cover_t = vals['rough'], vals['metal'], vals['cover']
            own_t, wear_t = om, dict(wv)
        else:                                   # (a later zone over the earlier ones)
            col_t = b.mixc(m, col_t, zcol)
            rough_t = b.mixf(m, rough_t, vals['rough'])
            metal_t = b.mixf(m, metal_t, vals['metal'])
            cover_t = b.mixf(m, cover_t, vals['cover'])
            mask_t = b.math('MAXIMUM', mask_t, m)
            wear_t = {k: b.mixf(om, wear_t[k], wv[k]) for k in ms.ZONE_WEAR}
            own_t = b.math('MAXIMUM', own_t, om)
    for nd in nt.nodes:                         # (only what was made here is the zones': named so it can go again)
        if nd.as_pointer() not in before and not nd.name.startswith(PREFIX):
            nd.name = PREFIX + nd.name
    if line_t is not None and hub['height'] is not None:
        nt.links.new(line_t, hub['height'].inputs[0])
    if mask_t is None:                          # (only lines: nothing painted)
        return
    nt.links.new(mask_t, hub['mask'].inputs[0])
    for k, sock in (('cover', cover_t), ('rough', rough_t), ('metal', metal_t)):
        if hub[k] is not None:
            nt.links.new(sock, hub[k].inputs[0])
    nt.links.new(col_t, csock)
    if hub['own'] is not None:
        nt.links.new(own_t, hub['own'].inputs[0])
        for k in ms.ZONE_WEAR:
            if hub['w_' + k] is not None:
                nt.links.new(wear_t[k], hub['w_' + k].inputs[0])


def _edge_width_w(z):
    """The soft / broken-up outline's width, world."""
    return max(1e-5, z.edge_width / 100.0 * z.size)


def _edge_scale(z):
    """The pattern breaking up the outline: its scale on the part's own coordinates."""
    return 6.0 * z.edge_scale / max(z.size, 1e-4)


def _tex_tiles(z):
    """A zone's colour texture: tiles per unit (a creature 2 units tall: 0.5 x 2 / size, x Texture Scale)."""
    return 0.5 * 2.0 / max(z.size, 1e-4) * z.tex_scale


def _edge(b, z, sd, pos, tag):
    """The zone's mask from its distance field ``sd`` (mask pixels, + inside).  What was drawn stays painted; the
    edge grows outwards from the lasso: Hard (1 px soft), Airbrush (a smooth fade over Edge Width, as a spray past a
    stencil), Texture (the outline pushed out by an organic pattern, 0 .. Edge Width, a little soft)."""
    if z.edge == 'HARD':
        return b.math('ADD', sd, 0.5, clamp=True)
    sdw = b.math('DIVIDE', sd, max(z.px_per_unit, 1e-6))            # (world units from the outline)
    ew = b.value(f'{tag}ew', _edge_width_w(z))
    ew.node.name = tag + 'ew'
    if z.edge == 'AIRBRUSH':
        mr = b.maprange(sdw, b.math('MULTIPLY', ew, -1.0), 0.0, 0.0, 1.0)
        mr.node.interpolation_type = 'SMOOTHSTEP'
        return mr
    if z.edge == 'TEXTURE':
        nz = b.node('ShaderNodeTexNoise')
        nz.name = tag + 'noise'
        nz.inputs['Detail'].default_value = 8.0
        nz.inputs['Roughness'].default_value = 0.65
        nz.inputs['Distortion'].default_value = 0.35
        esc = b.value(f'{tag}esc', _edge_scale(z))
        esc.node.name = tag + 'esc'
        b.link(b.vmath('SCALE', pos, fac=esc), nz.inputs['Vector'])
        nz.inputs['Scale'].default_value = 1.0
        reach = b.maprange(nz.outputs['Fac'], 0.36, 0.64, 0.0, 1.0)   # (the noise, mostly near 0.5: stretched)
        sdw = b.math('ADD', sdw, b.math('MULTIPLY', reach, ew))          # (the outline pushed out 0 .. Edge Width)
    soft = b.math('MULTIPLY', ew, 0.06)
    mr = b.maprange(sdw, b.math('MULTIPLY', soft, -1.0), soft, 0.0, 1.0)
    mr.node.interpolation_type = 'SMOOTHSTEP'
    return mr


def _half_width_px(z):
    """Half the Line Width in mask pixels (at the part's depth when the zone was drawn)."""
    return max(0.5, z.line_width / 100.0 * z.size * z.px_per_unit / 2.0)


def sync(mat):
    """A zone's sliders into its nodes (no re-making)."""
    zs = zones_of(mat)
    if not zs or not zoned(mat):
        return
    if current(mat):                            # (an older tree: made anew, the zones linked with it)
        return
    nodes = mat.node_tree.nodes
    live = [z for z in zs if z.projector is not None and z.mask is not None]
    if nodes.get(f'{PREFIX}{len(live) - 1}:mask') is None or nodes.get(f'{PREFIX}{len(live)}:mask') is not None:
        relink(mat)
        return
    for i, z in enumerate(live):
        tag = f'{PREFIX}{i}:'
        if (nodes.get(tag + 'ew') is None) != (z.edge == 'HARD') or (nodes.get(tag + 'tex') is None) != \
                (z.tex == 'FLAT') or (nodes.get(tag + 'esc') is None) != (z.edge != 'TEXTURE'):
            relink(mat)                         # (the Edge / Texture choice changed: its nodes made anew)
            return
        for k, val in (('lw', _half_width_px(z)), ('lh', z.line_height), ('through', 1.0 if z.through else 0.0),
                       ('ew', _edge_width_w(z)), ('esc', _edge_scale(z)), ('tsc', _tex_tiles(z))):
            nd = nodes.get(tag + k)
            if nd is not None:
                nd.outputs[0].default_value = val
        if z.kind == 'LINE':
            continue
        nodes[tag + 'color'].outputs[0].default_value = (*z.color, 1.0)
        for k, val in (('rough', z.roughness), ('metal', z.metallic), ('cover', z.cover), ('opacity', z.opacity),
                       ('own', 1.0 if z.own_wear else 0.0)) \
                + tuple(('w_' + k, getattr(z, k)) for k in ms.ZONE_WEAR):
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


def _px_per_unit(ob, view_matrix, window_matrix, mask_h):
    """Mask pixels per world unit at the part's middle (seen from that view)."""
    c = ob.matrix_world @ (sum((Vector(v) for v in ob.bound_box), Vector()) / 8.0)
    vc = view_matrix @ c
    pts = []
    for dy in (0.0, 1.0):
        v = window_matrix @ Vector((vc.x, vc.y + dy, vc.z, 1.0))
        pts.append(v.y / v.w if abs(v.w) > 1e-12 else 0.0)
    return abs(pts[1] - pts[0]) * 0.5 * mask_h


def _projector(context, ob, name, view_matrix):
    proj = bpy.data.objects.new(name, None)
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
    return proj


def _fill_zone(z, ob, proj, img, view_matrix, window_matrix, persp):
    """A zone's projector, mask and view (shared by a Paint Zone and a Split Zone's line)."""
    z.projector = proj
    z.mask = img
    z.win = [window_matrix[r][c] for r in range(4) for c in range(4)]
    z.persp = persp
    to_part = ob.matrix_world.inverted() @ view_matrix.inverted()
    z.eye = tuple(to_part.translation)
    z.look = tuple((to_part.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized())
    z.near, z.far = _depth_range(ob, view_matrix)
    z.size = max(ob.dimensions) or 1.0
    z.reach = SDF_R
    z.px_per_unit = _px_per_unit(ob, view_matrix, window_matrix, img.size[1])


def add_paint_zone(context, ob, pts, view_matrix, window_matrix, persp, rw, rh, color=None):
    """A Paint Zone on ``ob``'s Mech material from the lasso ``pts`` (region pixels) drawn in that view.  Returns the
    zone."""
    mat = ob.active_material
    if not zoned(mat):
        raise RuntimeError('the part has no Mech / Creature Shader material - apply one first')
    if len(pts) < 3:
        raise RuntimeError('the lasso needs at least 3 points')
    zs = zones_of(mat)
    n = len(zs) + 1
    creature = _cs().is_creature(mat)
    img = mask_image(f'.MCH Zone {mat.name} {n}', pts, rw, rh)
    proj = _projector(context, ob, f'Zone {n} ({ob.name})', view_matrix)
    z = zs.add()
    z.name = f'Zone {n}'
    _fill_zone(z, ob, proj, img, view_matrix, window_matrix, persp)
    if creature:                                # (a creature's markings: a soft airbrushed edge, its own gloss)
        z.color = color or CREATURE_PALETTE[(n - 1) % len(CREATURE_PALETTE)]
        z.edge = 'AIRBRUSH'
        z.roughness = getattr(mat, _cs().KEY).roughness
        z.line_height = 0.0
    else:
        z.color = color or PALETTE[(n - 1) % len(PALETTE)]
    relink(mat)
    proj.hide_set(True)
    return z


def remove_zone(mat, index):
    """Remove a zone (a Split Zone's line: from both materials)."""
    zs = zones_of(mat)
    if zs is None or not (0 <= index < len(zs)):
        return False
    z = zs[index]
    proj, img = z.projector, z.mask
    others = [(m, [i for i, oz in enumerate(m.mch_zones) if oz.projector == proj])
              for m, _z in twins(z)] if proj is not None else []
    zs.remove(index)
    for m, idx in others:
        for i in sorted(set(idx), reverse=True):
            m.mch_zones.remove(i)
        relink(m)
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
        zmat.mch_zone_parent = mat
        zmat.mch_zone_follow = True             # (the same wear as the part's to start - a switch on its page)
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
    # the boundary line on both sides of the cut: a line-only zone in the part's material and in the zone's
    n = sum(1 for m in me.materials if m is not None and getattr(m, 'mch_zone_parent', None) == mat)
    img = mask_image(f'.MCH Zone {zmat.name} line', pts, rw, rh)
    proj = _projector(context, ob, f'Split Zone {n} ({ob.name})', view_matrix)
    for m in (mat, zmat):
        z = zones_of(m).add()
        z.name = f'Split Zone {n}'
        z.kind = 'LINE'
        _fill_zone(z, ob, proj, img, view_matrix, window_matrix, persp)
    relink(mat)
    relink(zmat)
    proj.hide_set(True)
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
        return ob is not None and ob.type == 'MESH' and zoned(ob.active_material)

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, 'Zone: use it in the 3D view')
            return {'CANCELLED'}
        if self.mode == 'SPLIT' and not ms.is_mech(context.active_object.active_material):
            self.report({'WARNING'}, 'Split Zone: Mech Shader parts only (a creature: Paint Zone)')
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
        ob = context.active_object
        mat = getattr(ob, 'active_material', None) if ob is not None else None
        return {'FINISHED'} if zoned(mat) and remove_zone(mat, self.index) else {'CANCELLED'}


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
    bpy.types.Material.mch_zone_parent = PointerProperty(type=bpy.types.Material)
    bpy.types.Material.mch_zone_follow = BoolProperty(
        name='Same Wear as the Part', default=False, update=_follow_update,
        description='This Split Zone\'s chips, scratches, dirt and rust follow the part\'s material (off: its own)')


def unregister():
    for attr in ('mch_zones', 'mch_zone_parent', 'mch_zone_follow'):
        if hasattr(bpy.types.Material, attr):
            delattr(bpy.types.Material, attr)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
