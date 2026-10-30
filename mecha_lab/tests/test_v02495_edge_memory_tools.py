"""0.24.95 Edge Memory on EVERY tool that makes edges (user: "자르는 행위를 하는 모든 거는 다 남아야 돼 - 디테일 플레이트니
이런 거"): a part a tool builds or rebuilds remembers its own lines (rim + creases), a boolean cutter always leaves the
cut's outline, and the marks ride through a live Solidify."""
import math

import numpy as np
from _harness import bmesh, bpy, check, fresh, mesh_obj, select_only, summary
from mathutils import Euler, Quaternion, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, base_mesh as bmm, bridge_patch as bp, core_geometry as cg, creature_plate as cpl
from mecha_lab import cut_engine as ce, edge_memory as em, plate_detail as pdm, screw_stamp as ss, surface_draw as sd
from mecha_lab import flower_plate as fpl, mech_ridge as mr, scale_brush as sbr

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion())
RESULTS_T = []


def clear():
    if C.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def select(ob):
    if C.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob
    return ob


def body(kind='cube'):
    clear()
    if kind == 'cube':
        bpy.ops.mesh.primitive_cube_add(size=8, location=(0, 0, -4))
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=3, segments=64, ring_count=32, location=(0, 0, -2.6))
    return select(C.active_object)


def evaluated(ob):
    dg = C.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    n = em.count(me)
    k = len(me.edges)
    bpy.data.meshes.remove(me)
    return n, k


def new_objects(before):
    return [o for o in bpy.data.objects if o not in before and o.type == 'MESH']


def tool(name, run, kind='cube', want_target=False):
    """``run()`` on a fresh body: every new mesh object remembers edges (its own mesh and the evaluated one);
    with ``want_target`` the BODY must remember the cut it got."""
    b = body(kind)
    before = set(bpy.data.objects)
    try:
        msg = run(b)
    except Exception as ex:
        check(f'{name}: runs', False, repr(ex))
        return None
    new = new_objects(before)
    if want_target:
        n = em.count(b.data)
        check(f'{name}: the body remembers the cut\'s edges', n > 0 and b.data.attributes.get(cg.CUTTER_ATTR) is None, (n, msg))
        return b
    check(f'{name}: makes a part', len(new) >= 1, (len(new), msg))
    if not new:
        return None
    ob = new[0]
    n_base = em.count(ob.data)
    n_eval, k_eval = evaluated(ob)
    check(f'{name}: the part remembers its lines (base mesh {n_base}, with modifiers {n_eval} of {k_eval} edges)',
          n_base > 0 and n_eval > 0, (n_base, n_eval, k_eval, msg))
    return ob


# ---- Solidify carries the marks (a live plate's rim: top, bottom and the side edges) -------------------------
clear()
grid = mesh_obj('Sheet', lambda bm: bmesh.ops.create_grid(bm, x_segments=4, y_segments=4, size=1.0))
em.mark_generated(grid.data)
n0 = em.count(grid.data)
mod = grid.modifiers.new('S', 'SOLIDIFY')
mod.thickness = 0.2
n1, k1 = evaluated(grid)
check('A flat sheet: mark_generated marks its 16 rim edges; through a live Solidify the marks are on the evaluated '
      'mesh too (the rim copy and the side edges: more than the 16)', n0 == 16 and n1 >= 32, (n0, n1, k1))

# ---- the tools ------------------------------------------------------------------------------------------------
RECT = ce.rect_loop((420, 440), (580, 540))
S.mch_base.profile = 'RECT' if 'RECT' in {i.identifier for i in S.mch_base.bl_rna.properties['profile'].enum_items} else S.mch_base.profile
tool('Base Mesh (a new solid)', lambda b: bmm.perform_base(C, [RECT], TOP))
S.mch_settings.auto_apply = True
S.mch_cut.targets = 'ACTIVE'
tool('Base Mesh as a cutter (subtract from the body)', lambda b: bmm.perform_base(C, [RECT], TOP, cutter=True, targets=[b]),
     want_target=True)
BOX = [[(380, 420), (620, 420), (620, 580), (380, 580)]]
S.mch_plate.preset = 'MRIDGE'
S.mch_mridge.ridge_finish = S.mch_mridge.edge_finish = 'NONE'
tool('Armor Plate profile Mech Ridge', lambda b: ap.perform_plate(C, BOX, TOP))
presets = {i.identifier for i in S.mch_plate.bl_rna.properties['preset'].enum_items}
S.mch_plate.preset = 'BASIC' if 'BASIC' in presets else sorted(presets - {'MRIDGE'})[0]
tool(f'Armor Plate ({S.mch_plate.preset})', lambda b: ap.perform_plate(C, BOX, TOP))
tool('Plate Detail', lambda b: pdm.perform(C, BOX, TOP), kind='cube')
tool('Creature Plate', lambda b: cpl.perform(C, [[(300, 300), (700, 300), (700, 700), (300, 700)]], TOP), kind='sphere')
tool('Scale Brush', lambda b: sbr.perform(C, [[(300, 300), (700, 300), (700, 700), (300, 700)]], TOP), kind='sphere')
tool('Flower Plate', lambda b: fpl.perform(C, [[(300, 300), (700, 300), (700, 700), (300, 700)]], TOP), kind='sphere')
tool('Mech Ridge (tool)', lambda b: mr.perform(C, BOX, TOP))


def draw_band(b):
    proj = cg.OrthoProjector(Euler((math.radians(90), 0, 0)).to_quaternion(), center=Vector((0, 0, 0)),
                             pixels_per_unit=200.0, size=(1000, 1000))
    st = S.mch_sdraw
    st.width, st.height = 0.0, 0.0
    S.mch_brush.line_width = 0.1
    line = [(500 + (-0.5 + 0.05 * i) * 200, 500) for i in range(21)]
    return sd.perform(C, line, proj, 'BAND')


tool('Surface Draw (band)', draw_band, kind='sphere')


def bridge(b):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=48, ring_count=24, location=(0.1, 1.55, 3))
    a = C.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=48, ring_count=24, location=(-0.2, -1.65, 3))
    S.mch_bridge.trim = True
    S.mch_bridge.round = 0.0
    S.mch_bridge.fill = 0.0
    return bp.perform(C, [[(460, 620), (570, 620), (565, 520), (560, 420), (545, 330), (430, 380), (445, 470), (450, 540)]], TOP)


tool('Bridge Patch', bridge)


def screw(b):
    class F:
        remove = False

        def report(self, *a):
            pass
    S.mch_screw.kind = 'SOCKET'
    S.mch_screw.radius = 0.3
    return ss.MCH_OT_screw_stamp.run(F(), C, Vector((0.3, 0.2, 5)), Vector((0, 0, -1)))


tool('Screw stamp', screw)


def extract(b):
    select_only(b)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(b.data)
    for f in bm.faces:
        f.select = f.calc_center_median().z > 0.55 and f.calc_center_median().x > -0.2
    bmesh.update_edit_mesh(b.data)
    S.mch_extract.extract_height, S.mch_extract.resolution = 0.1, 1
    r = bpy.ops.mch.face_extract(mode='BASIC', stay_in_edit=False)
    if C.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    return r


tool('Face Extract (Basic)', extract, kind='sphere')

# a plain cutter mesh made by hand (no flag) through boolean_result: the result still remembers the cut
b = body('cube')
cut = mesh_obj('Cutter', lambda bm: bmesh.ops.create_cube(bm, size=3.0), loc=(0, 0, 0))
check('A hand-made cutter has no cutter flag', cut.data.attributes.get(cg.CUTTER_ATTR) is None)
me, _s = cg.boolean_result(C, b, cut, 'DIFFERENCE', 'EXACT', False)
cg.commit_mesh(b, me)
check('boolean_result flags any cutter (flag_cutter), so commit_mesh leaves Edge Memory marks on the result',
      em.count(b.data) > 0 and b.data.attributes.get(cg.CUTTER_ATTR) is None, em.count(b.data))
summary()
