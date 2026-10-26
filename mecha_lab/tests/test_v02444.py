"""0.24.34 Targets for every tool (like Cut): Auto Target / Selected Only / Active decide which mesh a tool draws on;
Selected Only / Active look through other meshes in front; after a stroke (the new part is the selection) the next
stroke still lands on the same mesh."""
import math

from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import armor_plate as ap, belt_maker as bmk, cape_gen, core_geometry as cg, cut_engine as ce
from mecha_lab import surface_draw as sd, target_rules as tr, tool_state as ts, ui_tool_settings as uts

mecha_lab.register()
fresh()
C = bpy.context
cut = C.scene.mch_cut
check('default: Auto Target (nothing changes for anyone)', cut.targets == 'AUTO' and tr.allowed(C) is None)
check('every drawing tool gets the row (Cut / Split / Box Hide / Move already have it)',
      tr.PICKING <= set(ts.TOOL_BY_ID) and not (tr.PICKING & tr.OWN_ROW) and hasattr(uts, 'draw_targets'))

bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.0)
back = C.active_object
back.name = 'Back'
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.6, location=(0, -2.5, 0))
front = C.active_object
front.name = 'Front'
proj = cg.OrthoProjector(Euler((math.radians(90), 0, 0)).to_quaternion(), center=Vector((0, 0, 0)),
                         pixels_per_unit=200.0, size=(1000, 1000))
scr = lambda x, z: (500 + x * 200, 500 + z * 200)
o, d = proj.ray(scr(0, 0))
dg = C.evaluated_depsgraph_get()


def hit_name():
    r = tr.scene_ray(C, dg, o, d)
    return r[4].name if r[0] and r[4] is not None else None


def only(*obs, active=None):
    for x in C.scene.objects:
        x.select_set(False)
    for x in obs:
        x.select_set(True)
    C.view_layer.objects.active = active or (obs[-1] if obs else None)


only(back)
check('Auto Target: the ray stops at the front mesh', hit_name() == 'Front')
cut.targets = 'SELECTED'
check('Selected Only: looks through the front mesh to the selected one', hit_name() == 'Back')
only(front)
check('... select the front one: it is used', hit_name() == 'Front')
cut.targets = 'ACTIVE'
only(front, back, active=back)
check('Active: only the active mesh', hit_name() == 'Back')

cut.targets = 'SELECTED'
only(back)
groups = [([scr(-0.2, -0.2), scr(0.2, -0.2), scr(0.2, 0.2), scr(-0.2, 0.2)], [])]
check('Armor / Creature Plate, Flower, Cloth Plate pick (pick_surface): the selected mesh',
      getattr(ap.pick_surface(C, proj, groups), 'name', None) == 'Back')
check('Cape / Clothing / Hood / Scarf / Hair pick (pick_body): the selected mesh',
      getattr(cape_gen.pick_body(C, proj, groups), 'name', None) == 'Back')
line = [scr(-0.3 + 0.03 * i, 0.0) for i in range(21)]
check('Belt / Spike / Scales / Scale Brush / Surface Curve pick: the selected mesh',
      getattr(bmk.pick_target(C, proj, line), 'name', None) == 'Back')
check('Cut-engine pick under the mouse: the selected mesh', getattr(ce.pick_mesh_under(C, proj, scr(0, 0)), 'name', None)
      == 'Back')

C.scene.mch_brush.line_width = 0.1
msg = sd.perform(C, line, proj)
band = C.active_object
check('Surface Draw with Selected Only: drawn on the selected (back) mesh, through the front one',
      sd.source(band) is not None and sd.source(band)['target'] == 'Back', msg)
check('the new band is now the selection, and it lets its base mesh through', band.select_get()
      and 'Back' in tr.allowed(C))
sd.perform(C, [scr(-0.3 + 0.03 * i, 0.15) for i in range(21)], proj)
check('a second stroke still lands on the back mesh (same live object)', C.active_object == band
      and len(sd.source(band)['strokes']) == 2)

cut.targets = 'AUTO'
only()
C.view_layer.objects.active = None
msg = sd.perform(C, [scr(-0.3 + 0.03 * i, -0.2) for i in range(21)], proj)
check('Auto Target again: the front mesh gets it', sd.source(C.active_object)['target'] == 'Front', msg)

cut.targets = 'SELECTED'
only()
try:
    sd.perform(C, [scr(-0.3 + 0.03 * i, 0.3) for i in range(21)], proj)
    ok = False
except cg.CutError:
    ok = True
check('Selected Only with nothing selected: tells, makes nothing', ok)
summary()
