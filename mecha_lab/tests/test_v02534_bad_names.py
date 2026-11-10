"""0.24.129 (user: "지금 왜 아머 플레이트 하는데 계속 꺼지냐" + traceback: layers_panel.content ... o.name ...
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb6) A data-block name that is not UTF-8 (a Korean name written in
CP949 by a Korean Windows tool) made every name read raise, and the drawn UI reads names on every redraw - so every tool
invoke died.  Now: safe reads where the UI met it, and a repair that renames such blocks (CP949 decoded back to the
Korean name) on load / register / the first error."""
import ctypes
import inspect

from _harness import bpy, check, cube, fresh, summary
from mathutils import Vector  # noqa: E402

import mecha_lab
from mecha_lab import curve_tube as ct, groups, layers_panel, name_fix as nf, ui_bars  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def poke_name(ob, raw):
    """Write raw bytes into the ID's name field (what a bad importer leaves behind)."""
    buf = b'OB' + raw + b'\0'
    ctypes.memmove(ob.as_pointer() + nf.NAME_OFFSET, buf, len(buf))


check('the ID name offset is verified against a block whose name reads (before any raw byte is trusted)', nf.offset_ok()
      and nf.raw_name(S) == S.name.encode('utf-8'))
part = cube('Part', size=1.0)
kor = '라메'.encode('cp949')                       # b'\xb6\xf3\xb8\xde' - 0xb6 first, as in the user's traceback
poke_name(part, kor)
raised = False
try:
    part.name
except UnicodeDecodeError as ex:
    raised = 'byte 0xb6' in str(ex)
check('reproduced: a CP949 Korean name makes object.name raise UnicodeDecodeError (byte 0xb6)', raised)
check('safe_name reads it as the fallback instead of raising', nf.safe_name(part) == '?' and nf.safe_name(part, 'x') == 'x')
check('bad_blocks finds it (objects)', [(k, b is part) for k, b in nf.bad_blocks()] == [('objects', True)])
check('raw_name gives the bytes; recover decodes CP949 back to the Korean name', nf.raw_name(part) == kor and nf.recover(kor, 'f') == '라메'
      and nf.recover(b'\xff\xfe', 'f') == 'f' and nf.recover(b'ab\xffc', 'f') == 'abc')
fixed = nf.fix_bad_names(quiet=True)
check('fix_bad_names renames it to the Korean name; the name reads again', fixed == [('objects', '라메')] and part.name == '라메'
      and nf.bad_blocks() == [] and nf.LAST == fixed)
# the readers that died / could die  (a fresh Korean name each time: the name map still holds the repaired one)
poke_name(part, '동체'.encode('cp949'))
coll = bpy.data.collections.new('Grp')
S.collection.children.link(coll)
coll.objects.link(part)
src_lp = inspect.getsource(layers_panel)
check('the Layers panel reads the listed names safely; the UI builder repairs and builds again on the error; the group timer too',
      "name_fix.safe_name(o) in sc['listed']" in src_lp and 'except UnicodeDecodeError' in inspect.getsource(ui_bars.all_items)
      and 'name_fix.on_error' in inspect.getsource(ui_bars.all_items) and 'except UnicodeDecodeError' in inspect.getsource(groups._auto_group_tick))
# the UI error path: on_error repairs
check('on_error (what the UI calls) repairs and says so', nf.on_error() is True and part.name == '동체' and nf.on_error() is False)
# the Mesh Curve selection watcher survives a bad active name (it ran every 0.2 s): it repairs the name, then links
poke_name(part, '머리'.encode('cp949'))
tube = ct.new_tube(C, Vector((0, 0, 0)))
ct.set_points(tube, [(Vector((0, 0, 0)), 1.0), (Vector((1, 0, 0)), 1.0), (Vector((2, 1, 0)), 1.0)])
ct.rebuild(tube)
for o in C.view_layer.objects:
    o.select_set(False)
tube.select_set(True)
C.view_layer.objects.active = tube
ct.select_link_step(C)
part.select_set(True)
C.view_layer.objects.active = part
ok_step = True
try:
    got = ct.select_link_step(C)
except UnicodeDecodeError:
    ok_step, got = False, []
check('the Mesh Curve selection watcher does not raise on a bad active name: it repairs the name (머리) and links the part',
      ok_step and got == [tube] and part.name == '머리' and tube.mch_tube.source == part
      and 'except Exception' in inspect.getsource(ct._select_tick), (ok_step, [o.name for o in got], nf.safe_name(part)))
poke_name(part, '팔'.encode('cp949'))
nerr = []
try:
    ct._on_depsgraph(S, C.evaluated_depsgraph_get())
except UnicodeDecodeError as ex:
    nerr.append(ex)
check('the Repeat source watcher (depsgraph handler) meets a bad source name: repaired, no error', not nerr and part.name == '팔'
      and 'name_fix.safe_name(src, None)' in inspect.getsource(ct._on_depsgraph))
# load_post + register hooks
check('wired: load_post handler, register runs a repair (right away in a background Blender)', nf._on_load in bpy.app.handlers.load_post
      and 'name_fix.register()' in inspect.getsource(mecha_lab._register))
# the undecodable-but-not-CP949 case falls back to a plain name
poke_name(part, b'\xff\xfe\xfdZ')
fixed = nf.fix_bad_names(quiet=True)
check('bytes that are neither UTF-8 nor CP949: the readable part stays, else Object_fixed', fixed and part.name in {'Z', 'Object_fixed'}, (fixed, part.name))
# --- the HUD slider gizmos (Blender 5.2 refused draw_select in a 2D gizmo group: the Mesh Curve bar / Armor Plate HUD /
# Primitive HUD sliders failed to set up - seen in this session's real-window logs)
import types  # noqa: E402
from mathutils import Matrix  # noqa: E402
from mecha_lab import armor_plate, primitive_hud  # noqa: E402
gz = types.SimpleNamespace(matrix_basis=Matrix.Translation((100.0, 50.0, 0.0)) @ Matrix.Diagonal((48.0, 10.0, 1.0, 1.0)),
                           use_draw_scale=False, scale_basis=1.0)
check('rect_hit: inside the slider rectangle = 0, outside = -1', primitive_hud.rect_hit(gz, (100, 50)) == 0
      and primitive_hud.rect_hit(gz, (147, 59)) == 0 and primitive_hud.rect_hit(gz, (150, 50)) == -1 and primitive_hud.rect_hit(gz, (100, 62)) == -1)
check('no HUD slider gizmo defines draw_select any more; all three use test_select',
      all(not hasattr(c, 'draw_select') and hasattr(c, 'test_select')
          for c in (primitive_hud.MCH_GT_hud_slider, ct.MCH_GT_tube_slider, armor_plate.MCH_GT_plate_slider)))
summary()
