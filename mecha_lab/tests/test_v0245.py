"""0.24.5 / 0.24.6 Enter applies the live result (Plate Detail, Armor Plate, Cloth Plate, Base Mesh, Mirror, Box Hide, Curve);
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

# ---- 0.24.6 several files at once, Auto foreground (alpha PNG with a dark shape on transparency + a JPEG)
d = os.path.dirname(jpg)
img = bpy.data.images.new('alphatest', 64, 64, alpha=True)
px = []
for y in range(64):
    for x in range(64):
        on = abs(x - 32) < 18 and abs(y - 32) < 12
        px += [0.0, 0.0, 0.0, 1.0] if on else [0.0, 0.0, 0.0, 0.0]     # black box on transparency
img.pixels = px
apng = os.path.join(d, 'box_alpha.png')
img.file_format = 'PNG'
img.filepath_raw = apng
img.save()
bpy.data.images.remove(img)
fake = types.SimpleNamespace(directory=d, files=[types.SimpleNamespace(name='box_alpha.png'),
                                                 types.SimpleNamespace(name='circle.jpg')],
                             filepath=apng, shape_name='', mode='AUTO', threshold=0.5, invert=False, simplify=0.8,
                             smooth=1, min_area=4, reports=[])
fake.report = lambda kind, msg: fake.reports.append(msg)
before = set(p.name for p in cp.preset_folder().glob('*.json'))
res = cp.MCH_OT_import_cut_png.execute(fake, C)
new = sorted(set(p.name for p in cp.preset_folder().glob('*.json')) - before)
check('two files imported in one go (Auto: alpha PNG by its alpha, JPEG by brightness)', res == {'FINISHED'} and
      len(new) == 2 and 'Imported 2' in fake.reports[-1], (res, new, fake.reports))
for n in new:
    st = n[:-5]
    check(f'{st.split("_")[0]}: one clean outline', len(cp.load_loops(st)) == 1)
    (cp.preset_folder() / n).unlink()
    (cp.preset_folder() / (st + '.png')).unlink(missing_ok=True)
# ---- 0.24.6 the wheel is the view zoom again (stamp size = drag)
km = wui._tool_keymap('CUT')
check('no wheel keys in the tool keymap (wheel zooms)', not any(k[1]['type'] in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}
                                                             for k in km))
S.mch_brush.shape = 'LASSO'

# ---- Base Mesh: settings changed on the live shape carry to the next shape
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
MODE[0], NATIVE[0] = 'BASE', 'mecha.base_mesh'
S.mch_settings.mch_active_tool = 'BASE'
S.mch_base.sketch = False
S.mch_brush.sketch_first = False
b = cube('B', 4.0)
r, m = lasso([(400, 400), (600, 400), (600, 600), (400, 600)])
first = C.active_object
check('Base Mesh made a live shape', getattr(first, 'mch_base', None) is not None and first.mch_base.live, m)
first.mch_base.height = 0.77
first.mch_base.profile = 'CHAMFER'
first.mch_base.bevel_width = 0.11
r, m = lasso([(420, 420), (580, 420), (580, 580), (420, 580)])
second = C.active_object
check('the next shape keeps the last settings (height / profile / width)', second is not first and
      abs(second.mch_base.height - 0.77) < 1e-6 and second.mch_base.profile == 'CHAMFER' and
      abs(second.mch_base.bevel_width - 0.11) < 1e-6, (second.mch_base.height, second.mch_base.profile))
# ---- Base Mesh Alt = Cut tool (From Surface depth: a pocket, the back is not cut)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
hull = cube('Hull', 2.0)
S.mch_cut.depth_mode = 'SURFACE'
S.mch_cut.depth = 0.3
S.mch_settings.auto_apply = True
r, m = lasso([(450, 450), (550, 450), (550, 550), (450, 550)], alt=True)
zs = sorted({round(v.co.z, 3) for v in hull.data.vertices})
check('Alt in Base Mesh cuts like Cut: From Surface depth makes a pocket, the back stays closed',
      m.startswith('Cut:') and any(abs(z - 0.7) < 0.02 for z in zs) and min(zs) == -1.0 and
      [o.name for o in bpy.data.objects] == ['Hull'], (m, zs))
# ---- 0.24.18 Box Hide tool: Enter applies even when the hidden mesh is not selected (Auto Target)
from mecha_lab import box_hide as _bh
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
MODE[0], NATIVE[0] = 'HIDE', 'mecha.box_hide'
S.mch_settings.mch_active_tool = 'HIDE'
S.mch_cut.targets = 'AUTO'
hb = cube('HideMe', 2.0)
C.view_layer.update()
r, m = lasso([(420, 420), (580, 420), (580, 580), (420, 580)])
for o in C.selected_objects:
    o.select_set(False)
check('Box Hide made, nothing selected', _bh.is_hidden(hb) and not C.selected_objects, m)
check('Box Hide tool: Enter target = Box Hide without a selection', wui.enter_apply_target(C) == ('box_hide_apply', 'Box Hide'))
res = wui.MCH_OT_enter_apply.execute(types.SimpleNamespace(report=lambda *a: None), C)
check('Enter applies it (the hole is real, modifier gone)', res == {'FINISHED'} and not _bh.is_hidden(hb) and
      not hb.modifiers and len(hb.data.polygons) > 6, (res, len(hb.data.polygons)))
hb2 = cube('HideMe2', 2.0)
C.view_layer.update()
r, m = lasso([(420, 420), (580, 420), (580, 580), (420, 580)])
for o in C.selected_objects:
    o.select_set(False)
S.mch_settings.mch_active_tool = 'CUT'
check('another tool + nothing selected: Enter does not apply a hidden mesh by itself',
      _bh.is_hidden(hb2) and wui.enter_apply_target(C) is None, wui.enter_apply_target(C))
S.mch_settings.mch_active_tool = 'HIDE'
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
