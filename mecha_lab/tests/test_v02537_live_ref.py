"""0.24.132 (user crash logs: access violation inside Python while the drawn UI memo was replaced; crashes on Ctrl+Z)
Cached UI items keep Blender structs as live_ref.Refs (collection, name, path) and look them up fresh - never a struct
that undo may have freed.  Items / panel nodes resolve on every read; a gone data-block reads as None and the value
helpers take it; the caches are dropped before and after undo / redo / load."""
import inspect
import types

from _harness import bpy, check, cube, fresh, summary

import mecha_lab
from mecha_lab import live_ref, mecha_menu, panel_capture as pc, side_panel, top_bar, ui_bars, ui_values  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene

# --- Ref ----------------------------------------------------------------------------------------------------------------
part = cube('Part', size=1.0)
r_pg = live_ref.wrap(S.mch_smart)
r_ob = live_ref.wrap(part)
r_wm = live_ref.wrap(C.window_manager)
r_sc = live_ref.wrap(S)
r_mod = None
part.modifiers.new('MCH Mirror', 'MIRROR')
r_mod = live_ref.wrap(part.modifiers['MCH Mirror'])
check('wrap: a scene PropertyGroup, an object, the window manager, the scene, a modifier become Refs (collection, name, path)',
      all(live_ref.is_ref(r) for r in (r_pg, r_ob, r_wm, r_sc, r_mod)) and (r_pg.coll, r_pg.name, r_pg.path) == ('scenes', S.name, 'mch_smart')
      and (r_ob.coll, r_ob.name, r_ob.path) == ('objects', 'Part', '') and r_wm.coll == 'window_managers' and r_mod.path == 'modifiers["MCH Mirror"]',
      (r_pg, r_ob, r_wm, r_sc, r_mod))
check('resolve: the same live structs come back', live_ref.resolve(r_pg) == S.mch_smart and live_ref.resolve(r_ob) == part
      and live_ref.resolve(r_mod) == part.modifiers['MCH Mirror'] and live_ref.resolve(r_sc) == S)
check('values that are not structs pass through (dict, str, number, None, a Ref itself)',
      live_ref.wrap({'a': 1}) == {'a': 1} and live_ref.wrap('RIGHT') == 'RIGHT' and live_ref.wrap(3) == 3 and live_ref.wrap(None) is None
      and live_ref.wrap(r_pg) is r_pg and live_ref.resolve('x') == 'x')
part.name = 'Renamed'
check('the data-block renamed / gone: the Ref resolves to None instead of a stale pointer', live_ref.resolve(r_ob) is None
      and live_ref.resolve(r_mod) is None)
part.name = 'Part'
bpy.data.objects.remove(part)
check('... removed: None', live_ref.resolve(r_ob) is None and live_ref.resolve(r_pg) == S.mch_smart)
# --- Item / Node hold Refs, read fresh ------------------------------------------------------------------------------
it = mecha_menu.Item('mini', 0, 0, 10, 10, 'Speed', data=S.mch_smart, prop='speed')
check('Item.data is a Ref underneath and the live struct on read; Item.ref is the Ref', live_ref.is_ref(it.ref) and it.data == S.mch_smart
      and it.prop == 'speed' and ui_values.get(it.data, it.prop) == S.mch_smart.speed)
it2 = mecha_menu.Item('seg', 0, 0, 10, 10, 'x', data={'hidden': True})
it3 = mecha_menu.Item('tile', 0, 0, 10, 10, 'x', data='ABOVE')
check('plain data stays plain', it2.data == {'hidden': True} and it3.data == 'ABOVE')
n = pc.Node('prop')
n.data, n.prop = S.mch_brush, 'shape'
check('panel_capture.Node.data: a Ref underneath, the struct on read', live_ref.is_ref(n._data) and n.data == S.mch_brush)
# a captured side panel tree holds no raw structs
from mecha_lab import ui_tool_settings as uts  # noqa: E402
tree = pc.capture(uts.DRAWERS['SMART'], C)
raw = [x for x in pc.walk(tree) if x.kind in {'prop', 'prop_enum'} and isinstance(x._data, bpy.types.bpy_struct)]
refs = [x for x in pc.walk(tree) if x.kind in {'prop', 'prop_enum'} and live_ref.is_ref(x._data)]
check('a captured panel tree keeps Refs only (no raw struct in any prop node)', not raw and len(refs) >= 4, (len(raw), len(refs)))
# the top bar cells become Items with Refs
S.mch_settings.mch_active_tool = 'SMART'
groups = top_bar.groups(C, 'SMART') if hasattr(top_bar, 'groups') else []
check('top bar cells carry the struct for the build only; the Items made from them hold Refs',
      bool(groups) and all(not isinstance(mecha_menu.Item('seg', 0, 0, 1, 1, c['label'], data=c['data'], prop=c['prop'])._data, bpy.types.bpy_struct)
                           for _n, cells in groups for c in cells if c.get('data') is not None), len(groups))
# --- a gone block: the value helpers take None -----------------------------------------------------------------------
check('ui_values with a gone block: get None, text the label, fraction 0, kind NONE, set / toggle / reset no-ops',
      ui_values.get(None, 'speed') is None and ui_values.text(None, 'speed', 'Speed') == 'Speed' and ui_values.fraction(None, 'speed') == 0.0
      and ui_values.kind(None, 'speed') == 'NONE' and ui_values.set(None, 'speed', 2.0) is None and ui_values.toggle(None, 'x') is None
      and ui_values.reset(None, 'x') is None and ui_values.drag(None, 'x', 1.5, 10) == 1.5)
# --- the caches are dropped round undo / redo / load -----------------------------------------------------------------
ui_bars._MEMO.update(key=('k',), time=1e12, items=[it])
side_panel._CACHE.update(key=('k',), time=1e12, trees=(tree, None))
ui_bars.EDIT[:] = [it.ref, 'speed']
ui_bars._release_handler(S)
check('release_refs (undo_pre / redo_pre / load_pre and their _post): memo items, side panel trees and the edit target dropped',
      ui_bars._MEMO['items'] == [] and ui_bars._MEMO['key'] is None and side_panel._CACHE['trees'] == (None, None) and ui_bars.EDIT == [None, ''])
hl = bpy.app.handlers
check('wired: the release handler sits in undo_pre, redo_pre, load_pre, undo_post, redo_post, load_post',
      all(ui_bars._release_handler in getattr(hl, n) for n in ('undo_pre', 'redo_pre', 'load_pre', 'undo_post', 'redo_post', 'load_post')))
check('the edit popup resolves its target fresh', 'live_ref.resolve(data)' in inspect.getsource(ui_bars) and 'item.ref' in inspect.getsource(ui_bars))
# --- deep_objects: the collection walk that replaces all_objects -----------------------------------------------------
top = bpy.data.collections.new('Top')
S.collection.children.link(top)
sub = bpy.data.collections.new('Sub')
top.children.link(sub)
a = cube('A', size=1.0)
b = cube('B', size=1.0)
c_ = cube('C', size=1.0)
for o in (a, b, c_):
    S.collection.objects.unlink(o)
top.objects.link(a)
sub.objects.link(b)
sub.objects.link(c_)
top.objects.link(c_)                     # (in two collections: listed once)
check('deep_objects: the same objects as all_objects (own first, then the children), each once',
      [o.name for o in live_ref.deep_objects(top)] == [o.name for o in top.all_objects]
      and sorted(o.name for o in live_ref.deep_objects(top)) == ['A', 'B', 'C'] and live_ref.deep_objects(None) == [],
      ([o.name for o in live_ref.deep_objects(top)], [o.name for o in top.all_objects]))
import os  # noqa: E402
src_dir = os.path.dirname(live_ref.__file__)
users = [f for f in os.listdir(src_dir) if f.endswith('.py') and f != 'live_ref.py'
         and any('.all_objects' in ln and 'not all_objects' not in ln for ln in open(os.path.join(src_dir, f), encoding='utf-8'))]
check('no module reads Collection.all_objects any more (the runtime cache that can be stale after Ctrl+Z)', users == [], users)
# --- 0.24.132 (user: "툴 설명은 디폴트로 접혀 있는 게 좋을 것 같아") the key legend card starts folded --------------------
from mecha_lab import key_legend as kl  # noqa: E402
check('the key legend card is folded by default (the property default and a window manager that never set it)',
      bpy.types.WindowManager.bl_rna.properties['mch_legend_min'].default is True and kl.folded(types.SimpleNamespace()) is True)
summary()
