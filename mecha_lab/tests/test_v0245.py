"""0.24.5 Enter applies the live result (Plate Detail, Armor Plate, Cloth Plate, Base Mesh, Mirror, Box Hide, Curve);
double-click with nothing drawn leaves the tool and selects the object under the mouse (a lasso being drawn still
closes on double-click); Screw Stamp double-click takes back the screw of the first click."""
import sys

_src = open(__file__.replace('test_v0245.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
from mathutils import Vector

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import workspace_ui as wui, plate_detail as pd, cut_engine as ce, screw_stamp as ss

check('Enter keymap item registered', any(it.idname == 'mch.enter_apply' for _km, it in wui._keymaps))

MODE[0], NATIVE[0] = 'DETAIL', 'mecha.plate_detail'
S.mch_settings.mch_active_tool = 'DETAIL'
b = cube('B', 4.0)
r, m = lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
d = C.active_object
check('a live detail -> Enter target is Plate Detail', wui.enter_apply_target(C) == ('pdetail_apply', 'Plate Detail'))
res = wui.MCH_OT_enter_apply.execute(types.SimpleNamespace(report=lambda *a: None), C)
check('Enter applies it', res == {'FINISHED'} and not pd.is_detail(d))
check('nothing live selected -> no Enter target', wui.enter_apply_target(C) is None)

# ---- double-click
left = []
ce_orig = ce.object_under
ce.object_under = lambda context, xy, skip=None: b
MODE[0], NATIVE[0] = 'CUT', 'mecha.cut'
S.mch_settings.mch_active_tool = 'CUT'
for o in C.selected_objects:
    o.select_set(False)
ctx, op = Ctx(), Op()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 500, 500))
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 500, 500))
nv = len(b.data.vertices)
res = op.modal(ctx, E('LEFTMOUSE', 'DOUBLE_CLICK', 500, 500))
check('double-click with nothing drawn: the stroke ends, nothing is cut', 'CANCELLED' in res and
      len(b.data.vertices) == nv, res)
check('... the object under the mouse becomes selected / active', b.select_get() and C.view_layer.objects.active == b)
ctx, op = Ctx(), Op()
res = op.invoke(ctx, E('LEFTMOUSE', 'DOUBLE_CLICK', 500, 500))
check('a double-click arriving at a new stroke also leaves', res == {'CANCELLED'})
r, m = lasso([(350, 350), (650, 350), (650, 650)])
ctx, op = Ctx(), Op()
for x, y in ((350, 350), (650, 350), (650, 650)):
    op.invoke(ctx, E('LEFTMOUSE', 'PRESS', x, y)) if (x, y) == (350, 350) else op.modal(ctx, E('LEFTMOUSE', 'PRESS', x, y))
    op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x, y))
res = op.modal(ctx, E('LEFTMOUSE', 'DOUBLE_CLICK', 660, 660))
check('while drawing a lasso, double-click still closes and applies it', res == {'FINISHED'}, (res, op.reports[-1:]))
ce.object_under = ce_orig

# ---- Screw Stamp double-click
f = types.SimpleNamespace(remove=False, leave=False, report=lambda *a: None)
S.mch_screw.radius = 0.1
ss.MCH_OT_screw_stamp.run(f, C, Vector((1.9, 1.9, 5)), Vector((0, 0, -1)))   # outside the cut hole
n = sum(1 for o in bpy.data.objects if ss.is_screw(o))
check('the click placed a screw', n == 1 and ss._LAST[0] is not None, (n, ss._LAST))
ce.object_under = lambda context, xy, skip=None: b
ss.MCH_OT_screw_stamp.leave_tool(f, C, (500, 500))
ce.object_under = ce_orig
check('double-click takes the screw back and leaves', sum(1 for o in bpy.data.objects if ss.is_screw(o)) == 0)
check('Screw keymap: double-click first', ss.TOOL_KEYMAP[0][1]['value'] == 'DOUBLE_CLICK')
# ---- JPEG stamp import
import os, tempfile
from mecha_lab import cut_presets as cp
img = bpy.data.images.new('jpgtest', 64, 64, alpha=False)
px = []
for y in range(64):
    for x in range(64):
        on = (x - 32) ** 2 + (y - 32) ** 2 < 20 ** 2
        px += [1.0, 1.0, 1.0, 1.0] if on else [0.0, 0.0, 0.0, 1.0]
img.pixels = px
jpg = os.path.join(tempfile.mkdtemp(), 'circle.jpg')
img.file_format = 'JPEG'
img.filepath_raw = jpg
img.save()
bpy.data.images.remove(img)
check('a JPEG file was written', os.path.isfile(jpg) and open(jpg, 'rb').read(2) == b'\xff\xd8')
out = cp.import_png(jpg, 'JpgCircle', mode='ALPHA')
loops = cp.load_loops(out.stem)
png_copy = out.with_suffix('.png')
check('JPEG imports as a cut shape (alpha mode falls back to brightness)', len(loops) == 1 and len(loops[0]) > 8,
      [len(l) for l in loops])
check('library keeps a real PNG copy', png_copy.is_file() and open(png_copy, 'rb').read(4) == b'\x89PNG')
check('file browser shows JPG files', '*.jpg' in open(cp.__file__).read().split("filter_glob: StringProperty(default='")[1].split("'")[0])
out.unlink()
png_copy.unlink()
# ---- mouse wheel stamp size
km = wui._tool_keymap('CUT')
check('wheel keys in the tool keymap', any(k[0] == 'mch.stamp_scale' and k[1]['type'] == 'WHEELUPMOUSE' for k in km))
S.mch_brush.shape = 'LASSO'
check('wheel does not take over without a stamp shape (view zoom stays)', not ce.MCH_OT_stamp_scale.poll(C))
S.mch_brush.shape = 'CUSTOM'
S.mch_brush.custom_size = 100.0
fs = types.SimpleNamespace(step=1)
ce.MCH_OT_stamp_scale.execute(fs, C)
up = S.mch_brush.custom_size
fs.step = -1
ce.MCH_OT_stamp_scale.execute(fs, C)
ce.MCH_OT_stamp_scale.execute(fs, C)
check('wheel up = bigger, down = smaller', abs(up - 110.0) < 1e-3 and S.mch_brush.custom_size < 100.0,
      (up, S.mch_brush.custom_size))
S.mch_brush.shape = 'LASSO'
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
