"""0.24.158 (user: "웨더링 메뉴도 새로 만들자 - 흙이나 먼지, 나뭇잎, 눈 ... 내가 만든 메쉬를 클릭하면 그걸 그런 형태로 바꿔 주는 거야
- 베이스 메쉬, 크리쳐 메쉬, 플레이트들, 서페이스 드로우로 만든 거에"): the Weathering tools - Dirt, Dust, Leaves, Snow - on
shapes made by the add-on's own tools: a live Base Mesh, a Creature Base Mesh lump, an Armor Plate on a part, a Surface
Draw band (the outlines / lines given through a fixed top view).  Measured on the evaluated result.  The real clicks:
tests/gui/weathering_real_window.py."""
import math
import os

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh, core_geometry as cg, tool_state as ts, ui_tool_settings as uts, weathering as wx  # noqa

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
tools = ('WDIRT', 'WDUST', 'WLEAF', 'WSNOW')
icons = os.path.join(os.path.dirname(wx.__file__), 'icons')
check('the Weathering group: Dirt, Dust, Leaves, Snow - each a tool with its icon and window',
      dict(ts.TOOL_GROUPS).get('Weathering') == tools and all(t in ts.TOOL_BY_ID for t in tools)
      and all(os.path.isfile(os.path.join(icons, ts.TOOL_BY_ID[t][3] + '.png')) for t in tools)
      and all(uts.DRAWERS.get(t) is not None for t in tools))

TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)        # (looking down: 100 px = 1)


def blob(cx, cy, r, n=40):
    return [[(500 + (cx + r * math.cos(a) * (1 + 0.2 * math.sin(3 * a))) * 100,
              500 + (cy + r * math.sin(a)) * 100) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


def made(fn):
    before = set(bpy.data.objects)
    fn()
    new = [o for o in bpy.data.objects if o not in before]
    return new[0] if new else None


def ev_mesh(ob):
    dg = C.evaluated_depsgraph_get()
    return bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)


def coords(me):
    a = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', a)
    return a.reshape(-1, 3)


S.mch_base.sketch = False
S.mch_base.profile = 'BEVEL'
S.mch_base.height = 0.4
base = made(lambda: base_mesh.perform_base(C, blob(-2.5, 0, 0.9), TOP))
S.mch_cbase.sketch = False
S.mch_cbase.profile = 'PUFF'
for o in C.selected_objects:
    o.select_set(False)
prev_tool = S.mch_settings.mch_active_tool
S.mch_settings.mch_active_tool = 'CBASE'                            # (Creature Base Mesh's own settings)
lump = made(lambda: base_mesh.perform_base(C, blob(0, 0, 0.8), TOP))
S.mch_settings.mch_active_tool = prev_tool
bpy.ops.mesh.primitive_plane_add(size=1.6, location=(2.6, 0, 0))   # (an open sheet - a band / plate's surface)
sheet = C.active_object
bpy.ops.object.modifier_add(type='SUBSURF')
sheet.modifiers[-1].levels = 3
bpy.ops.object.modifier_apply(modifier=sheet.modifiers[-1].name)
check('shapes to weather: a live Base Mesh (Bevel), a Creature Base Mesh lump (Puff), an open sheet',
      base is not None and base.mch_base.live and lump is not None and lump.mch_base.profile == 'PUFF'
      and sheet is not None, (base and base.name, lump and lump.name))
shapes = {'base': base, 'lump': lump, 'sheet': sheet}
orig = {k: ev_mesh(o) for k, o in shapes.items()}


def mat_of(me):
    """The material most of the faces use."""
    if not len(me.polygons):
        return ''
    idx = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('material_index', idx)
    k = int(np.bincount(idx).argmax())
    m = me.materials[k] if k < len(me.materials) else None
    return m.name if m is not None else ''


def size_of(me):
    p = coords(me)
    return float(np.linalg.norm(np.ptp(p, axis=0)))


def weather(ob, kind):
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob
    return bpy.ops.mch.weather_click('EXEC_DEFAULT', kind=kind)


# Dirt
r = weather(base, 'DIRT')
me = ev_mesh(base)
o = orig['base']
mat = mat_of(me)
islands = len(me.vertices) - len(o.vertices) * 0                    # (more points: subdivided + crumbs)
p, q = coords(me), coords(o)
check(f'Dirt on the Base Mesh: lumpy (its points {len(o.vertices):,} -> {len(me.vertices):,}), crumbs on it, the dirt '
      f'material and colour attribute; the shape about its size (diagonal {size_of(o):.2f} -> {size_of(me):.2f})',
      'FINISHED' in r and wx.kind_of(base) == 'DIRT' and len(me.vertices) > len(o.vertices) * 4 and mat == 'MCH Dirt'
      and 'mch_w_col' in me.attributes and abs(size_of(me) / size_of(o) - 1) < 0.25)
pg = base.mch_wdirt
pg.crumbs = 0.0
n0 = len(ev_mesh(base).vertices)
pg.crumbs = 2.0
n1 = len(ev_mesh(base).vertices)
check(f'... live: Crumbs 0 -> 2: more crumbs ({n0:,} -> {n1:,} points)', n1 > n0 + 400)
base.mch_base.height = 0.8                                           # (the Base Mesh's own slider, under the dirt)
from mecha_lab import live_queue  # noqa: E402
live_queue.flush()
C.view_layer.update()
h = np.ptp(coords(ev_mesh(base))[:, 2])
check(f'... the Base Mesh still live under it: Height 0.4 -> 0.8, the dirt follows (its height {h:.2f})', h > 0.7)

# Dust on the lump
r = weather(lump, 'DUST')
me, o = ev_mesh(lump), orig['lump']
sz = size_of(o)
grow_ = size_of(me) / sz
check(f'Dust on the Creature Base Mesh: smoothed, a thin layer puffed out ({grow_:.3f} x its size), the dust material',
      'FINISHED' in r and mat_of(me) == 'MCH Dust' and 1.0 < grow_ < 1.1)

# Snow on the sheet: more on top than at its edges; Leaves on a copy
r = weather(sheet, 'SNOW')
me = ev_mesh(sheet)
z = coords(me)[:, 2]
check(f'Snow on the open sheet: puffed up (top {z.max():.3f} above the flat sheet), smooth, white', 'FINISHED' in r
      and z.max() > 0.02 and mat_of(me) == 'MCH Snow'
      and np.mean([me.attributes['mch_w_col'].data[i].color[0] for i in range(0, len(me.vertices), 50)]) > 0.6)
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 3, 0))
ground = C.active_object
r = weather(ground, 'LEAVES')


def leaf_list(ob):
    """(leaf shape, height) of each leaf instance (read while the depsgraph iterates - its items do not outlive it)."""
    dg = C.evaluated_depsgraph_get()
    out = []
    for i in dg.object_instances:
        if i.is_instance and i.parent and i.parent.original == ob:
            out.append((i.object.data.name, i.matrix_world.translation.z))
    return out


leaves = leaf_list(ground)
pg = ground.mch_wleaves
check(f'Leaves on a 1 x 1 sheet: {len(leaves)} leaves (Density {pg.density:.0f} a square metre, within 20 %), four leaf '
      f'shapes, the sheet under them as soil', 'FINISHED' in r and abs(len(leaves) - pg.density) < 0.2 * pg.density
      and len({n for n, _z in leaves}) == 4 and mat_of(ev_mesh(ground)) == 'MCH Soil')
lz = np.array([z for _n, z in leaves])
check(f'... piled (lifted up to {lz.max():.3f}, Pile {pg.pile} x Leaf Size {pg.leaf_size}), lying on it (none below it)',
      lz.min() > -0.01 and 0.0 < lz.max() <= pg.pile * pg.leaf_size + 0.01)
pg.show_base = False
check('... Show Base off: only the leaves (the sheet hidden)', len(ev_mesh(ground).vertices) == 0)
pg.density = 50.0
n = len(leaf_list(ground))
check(f'... live: Density 400 -> 50: {n} leaves', abs(n - 50) < 15)

# the same shape 10 x bigger: the same look (sizes are shares of the shape)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, -4, 0))
small = C.active_object
weather(small, 'DIRT')
bpy.ops.mesh.primitive_uv_sphere_add(radius=10.0, location=(40, -4, 0))
big = C.active_object
weather(big, 'DIRT')
ds = size_of(ev_mesh(small)) / 2.0 / math.sqrt(3) * 2
db = size_of(ev_mesh(big)) / 20.0 / math.sqrt(3) * 2
check(f'a sphere and one 10 x bigger: the same dirt to scale (sizes {ds:.3f} / {db:.3f} of the sphere)', abs(ds - db) < 0.02)

# back to the shape; Apply
for o in C.selected_objects:
    o.select_set(False)
lump.select_set(True)
C.view_layer.objects.active = lump
r = bpy.ops.mch.weather_click('EXEC_DEFAULT', kind='DUST', clear=True)
check('Alt + click (Back to Shape): the Creature Base Mesh as it was (no weathering on it)', 'FINISHED' in r
      and wx.kind_of(lump) is None and lump.modifiers.get(wx.MOD) is None
      and len(ev_mesh(lump).vertices) == len(orig['lump'].vertices))
for o in C.selected_objects:
    o.select_set(False)
ground.select_set(True)
C.view_layer.objects.active = ground
ground.mch_wleaves.show_base = True
r = bpy.ops.mch.weather_bake()
col = ground.data.attributes.get('mch_leaf_col')
lc = np.empty(len(col.data) * 4, np.float32) if col is not None else np.zeros(4, np.float32)
if col is not None:
    col.data.foreach_get('color', lc)
check(f'Apply on the leaves: real geometry ({len(ground.data.polygons):,} faces - the 50 leaves made real and the soil, '
      f'each leaf keeping its colour), not live', 'FINISHED' in r and wx.kind_of(ground) is None and not ground.modifiers
      and len(ground.data.polygons) > 50 * 10 and col is not None and lc.reshape(-1, 4)[:, :3].max() > 0.1)
summary()
