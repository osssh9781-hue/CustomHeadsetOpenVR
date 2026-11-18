"""0.24.214 (user: "상단 바도 매번 배치랑 구성이 달라지고 헷갈린단 말이야 - 모든 툴 공통으로 배치 유지해 놓고 툴마다 달라지는
설정만 추가로 아래에다가 배치" / "기능이나 이상은 없게"), 0.24.216 ("해상도 표시 위치가 다 다르잖아 - 사용 안 하는 게 있으면
거기를 그냥 블랭크로 비워 놓고 모든 위치는 똑같이 만들어 줘, 계속 찾아야 되잖아"): every group that more than one tool
shows has one place in the top bar, the same for every tool and state (Shape, Draw, Target, Depth, Auto Apply, Ortho,
Resolution, Corners, Surface / Through, Lasso); a place a tool does not use is empty; the tool's own groups come after,
from the left - and every cell the bar had in 0.24.213 (data/top_bar_cells_0.24.213.json: 80 tools x 10 states) is
still there, the same."""
import collections
import json
import os
import types

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import side_panel as sp, tool_state as ts, top_bar as tb  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context; S = C.scene
TOOL = ['CUT']
ts.effective_tool = lambda c: TOOL[0]
ts.is_mecha_workspace = lambda ws: True
sp.on = lambda c: True


def jsonable(v):
    if isinstance(v, (str, int, float, bool)) or v is None: return v
    if isinstance(v, (list, tuple)): return [jsonable(x) for x in v]
    if isinstance(v, dict): return {str(k): jsonable(x) for k, x in sorted(v.items())}
    return type(v).__name__


def grab():
    its = tb.items(C, 2560, 1440, 1.0, left=0.0, right=2560.0)
    # 0.24.226 the bar is in three places now: the LASSO bar at the top, the tool's box at the bottom, Options in the dock
    its = its + tb.items(C, 2560, 1440, 1.0, left=0.0, right=2560.0, part='BOTTOM') + [
        types.SimpleNamespace(kind=c['kind'], label=c['label'], on=c['on'], action=c['action'], data=c['data'],
                              prop=c['prop'], icon=c['icon'], enabled=True) for c in tb.option_cells(C)]
    out = []
    for i in its:
        if i.kind in {'card', 'vrule'}: continue
        if not getattr(i, 'enabled', True) and i.action is None: continue      # (a greyed place holder)
        d = i.data
        out.append([i.kind, i.label, bool(i.on), jsonable(i.action), (type(d).__name__ if d is not None else '') + '.' + (i.prop or ''),
                    '' if i.kind == 'glabel' else i.icon])       # (a group name's look is not a function)
    return out


tools = [t[0] if isinstance(t, (tuple, list)) else getattr(t, 'id', None) for t in ts.TOOLS]
tools = [t for t in tools if isinstance(t, str)]
B = S.mch_brush; cut = S.mch_cut
states = {}
def sweep(tag):
    for t in tools:
        TOOL[0] = t
        try: states[f'{t} | {tag}'] = grab()
        except Exception as ex: states[f'{t} | {tag}'] = [['ERROR', repr(ex)[:120]]]
sweep('default')
B.stab_enable = True; B.line_mode = True; cut.depth_mode = 'SURFACE'; cut.gn_finish = 'CHAMFER'; B.surface_mode = True; B.through_mode = True
sweep('line slow surface')
B.stab_enable = False; B.line_mode = False; cut.depth_mode = 'THROUGH'; cut.gn_finish = 'NONE'; B.surface_mode = False; B.through_mode = False
for sh in [s[0] for s in ts.SHAPES]:
    try: B.shape = sh
    except TypeError: continue
    B.outline_corner = 'ROUND'
    sweep('shape ' + sh)
B.shape = 'LASSO'; B.outline_corner = 'NONE'
S.mch_base.profile = 'BEVEL'; S.mch_base.bevel_sides = 'BOTH'; S.mch_base.bevel_link = False
cut.edge_finish = 'BEVEL'; cut.side_a_finish = 'CHAMFER'
sweep('bevels')

HERE = os.path.dirname(os.path.abspath(__file__))
before = json.load(open(os.path.join(HERE, 'data', 'top_bar_cells_0.24.213.json')))['states']
gone, new = [], collections.Counter()
for name, was in before.items():
    cb = collections.Counter(json.dumps(x, sort_keys=True) for x in was)
    ca = collections.Counter(json.dumps(x, sort_keys=True) for x in states.get(name, []))
    gone += [(name, k) for k in (cb - ca)]
    new.update(ca - cb)
n_before = sum(len(v) for v in before.values())
check(f'every cell of 0.24.213 is still in the bar, the same (kind, name, on / off, what a click does, its setting) - '
      f'{n_before:,} checked over {len(before)} tool states, {len(gone)} gone',
      not gone and set(before) <= set(states), gone[:4])        # (0.24.241 a new tool adds states)
kinds = {json.loads(k)[0] for k in new if json.loads(k)[1] != tb.LANG_LABEL}     # (0.24.225 + the 한글 switch)
check(f'the only new things are the 한글 switch and group names shown a second time ({sorted(set(json.loads(k)[1] for k in new))}: Press Cut\'s '
      f'own Line / Lasso switch stays with the tool\'s own groups)', kinds <= {'glabel'})

# --- 0.24.226: the LASSO bar alone at the top (long, in every tool); the rest in the tool's box; Options in the dock ---
BLOCK = {}
slots = tb.common_slots()
for si in tb.BLOCK_SLOTS:
    if isinstance(slots[si][2], list):
        for label, kind, _icon, _w, match in slots[si][2]:
            BLOCK[(kind, label)] = match


def top(t, w=2560):
    TOOL[0] = t
    return tb.items(C, w, 1440, 1.0, left=0.0, right=float(w))


def bottom(t, w=2560):
    TOOL[0] = t
    return tb.items(C, w, 1440, 1.0, left=0.0, right=float(w), part='BOTTOM')


where = collections.defaultdict(set)
always = collections.Counter()
B.shape = 'LASSO'; B.outline_corner = 'NONE'; B.stab_enable = False; cut.depth_mode = 'THROUGH'; B.surface_mode = False
for state in range(3):
    if state == 1:
        B.stab_enable = True; B.outline_corner = 'ROUND'
    if state == 2:
        B.shape = 'CIRCLE'
    for t in tools:
        for i in top(t):
            key = (i.kind, i.label)
            if key in BLOCK and key not in tb.COND and (not i.enabled or BLOCK[key](
                    dict(kind=i.kind, label=i.label, action=i.action, prop=i.prop))):   # (not GN Edge's Chamfer)
                where[key].add((round(i.x, 2), round(1440 - i.y, 2), round(i.w, 2)))
                always[key] += 1
B.shape = 'LASSO'; B.stab_enable = False; B.outline_corner = 'NONE'
moved = {k: v for k, v in where.items() if len(v) != 1}
n_fixed = len([k for k in BLOCK if k not in tb.COND])
check(f'the LASSO bar: every cell that is always there ({n_fixed}: the shapes, Line / Sketch / Slow Line, the corners, Res, '
      f'the targets) is in the bar for EVERY tool ({len(tools)} tools x 3 states) at ONE place; {len(moved)} move',
      not moved and len(where) == n_fixed and all(v == 3 * len(tools) for v in always.values()), moved)
its = top('SMART')
dim = [i.label for i in its if not i.enabled and i.kind in {'ibtn', 'seg', 'mini'}]
check(f'a tool that does not use the lasso (Smart Move) has the bar too - its cells are dim, no click ({len(dim)} dim)',
      len(dim) >= 15 and all(i.action is None for i in its if not i.enabled)
      and not any(i.clickable() for i in its if not i.enabled))
its = top('CUT')
names = [i.label for i in its if i.kind == 'glabel']
cards = [i for i in its if i.kind == 'card']
check(f'the top bar is ONE card - LASSO with its parts named ({names}); no Options / Depth / Surface in it',
      len(cards) == 1 and names[0] == 'LASSO' and all(n in names for n in ('SHAPE', 'DRAW', 'CORNERS', 'RESOLUTION',
                                                                            'TARGET', 'GN EDGE', 'EDGE FINISH'))
      and not {'OPTIONS', 'DEPTH', 'SURFACE'} & set(names)
      and all(cards[0].x <= i.x and i.x + i.w <= cards[0].x + cards[0].w + 0.01 for i in its if i.kind in {'ibtn', 'seg', 'mini'}))
res_cell = next(i for i in its if i.kind == 'mini' and i.label == 'Res')
res_title = next(i for i in its if i.kind == 'glabel' and i.label == 'RESOLUTION')
shape_y = next(i for i in its if i.kind == 'ibtn').y
card = cards[0]
gaps = []
fixed_titles = [i for i in its if i.kind == 'glabel' and i.icon == 'title_s' and abs(i.y - shape_y) < 1.0]
for t_ in fixed_titles[1:]:
    prev = max(i.x + i.w for i in its if i.kind in {'ibtn', 'seg', 'mini'} and abs(i.y - shape_y) < 1.0 and i.x < t_.x)
    gaps.append(round(t_.x - prev, 1))
check(f'0.24.227 the thin bar: a part\'s name at the LEFT of its cells in the same row (no title line), the five fixed '
      f'parts in one row with one gap between them ({sorted(set(gaps))}); the bar is {card.h:.0f} px high',
      abs(res_title.y - res_cell.y) < 1.0 and res_title.x < res_cell.x and abs(res_cell.y - shape_y) < 1.0
      and len(fixed_titles) == 5 and len(set(gaps)) == 1 and card.h <= (3 * tb.ROW + 2 * tb.BAR_GAP + 2 * tb.BAR_PAD) * tb.BAR_SCALE + 0.5)
B.stab_enable = True
its2 = top('CUT')
B.stab_enable = False
st = next((i for i in its2 if i.kind == 'mini' and i.label == 'Strength'), None)
slow = next(i for i in its2 if i.label == 'Slow Line')
same_x = {(i.kind, i.label): round(i.x, 1) for i in its if i.kind in {'ibtn', 'seg'}} == \
    {(i.kind, i.label): round(i.x, 1) for i in its2 if i.kind in {'ibtn', 'seg'}}
check('a cell that comes and goes (Slow Line: Strength) shows in a row under its part; nothing moves sideways',
      st is not None and st.y < slow.y and same_x)
bt = bottom('CUT')
bn = [i.label for i in bt if i.kind == 'glabel']
check(f'the tool\'s box (bottom): its name and what changes from tool to tool ({bn}) - one card, no Options',
      len([i for i in bt if i.kind == 'card']) == 1 and bn[0] == 'CUT' and 'DEPTH' in bn and 'OPTIONS' not in bn
      and all(i.enabled for i in bt))
sm = [i.label for i in bottom('SMART') if i.kind == 'glabel']
check(f'... Smart Move: its own sections ({sm})', len(sm) >= 3 and sm[0] == 'SMART MOVE')
TOOL[0] = 'CUT'
oc = [c['label'] for c in tb.option_cells(C)]
TOOL[0] = 'SMART'
os_ = [c['label'] for c in tb.option_cells(C)]
check(f'Options (for the dock): Cut {oc}, Smart Move {os_}',
      oc == ['Auto Apply', 'Ortho', tb.LANG_LABEL] and os_ == ['Ortho', tb.LANG_LABEL])
# the row of boxes under the dock
from mecha_lab import bottom_row, mecha_menu as mm, ui_bars  # noqa: E402
TOOL[0] = 'CUT'
bpy.ops.mesh.primitive_cube_add()
bx = bottom_row.boxes(C, 2560, 1440, 1.0)
acts = [i for _w, _h, its_ in bx for i in its_ if i.kind == 'abtn']
want = sum(len(b) for _s, b in mm.ACTIONS)
titles = [[i.label for i in its_ if i.kind == 'glabel' and i.icon == 'title'] for _w, _h, its_ in bx]
check(f'the row of boxes: the tool\'s box first, then the right-click popup\'s actions in three boxes ({titles[1:]}); '
      f'every action of the popup is there ({len(acts)} of {want})',
      len(bx) == 4 and bx[0][2][1].label == 'CUT' and len(acts) >= want
      and all(a.action[0] in {'mop', 'tool'} for a in acts)
      and 'ACTIONS' in titles[1] and 'SYMMETRY' in titles[2] and 'GROUPS' in titles[3])
ob = C.active_object
it = next(i for i in acts if i.action[0] == 'mop' and i.action[1] == 'mch.actions_mirror' and i.action[2].get('axis') == 0)
n0 = len(ob.modifiers)
ui_bars.run(C, it)
check(f'a click on an action button runs it (Symmetry X: {n0} -> {len(C.active_object.modifiers)} modifiers)',
      len(C.active_object.modifiers) == n0 + 1)
import inspect  # noqa: E402
check('a right click opens the Tool Wheel while the row is on (mecha_menu.open_menu); the dock sits above the row',
      'radial_menu' in inspect.getsource(mm.open_menu) and '_row_h' in inspect.getsource(ui_bars.dock_items)
      and '_row_h' in inspect.getsource(ui_bars.dock_top))
# Preferences > Top Bar Sections off: the plain rows of 0.24.216, everything in the top bar
tb.FORCE_SECTIONS[0] = False
its = top('CUT')
check('Top Bar Sections off: the plain rows as before (Ortho in the top bar, nothing at the bottom)',
      any(i.label == 'Ortho' for i in its) and bottom('CUT') == [] and tb.sections_wanted() is False)
tb.FORCE_SECTIONS[0] = None
check('... on by default', tb.sections_wanted() is True)
wide, narrow = top('BASE'), top('BASE', 500)
check('a view too narrow for the bar (500 px): the groups packed as before, nothing lost',
      {'Ortho', 'Res', 'Flat'} <= {i.label for i in narrow} and bottom('BASE', 500) == [])
# 0.24.225 the 한글 / English switch
from mecha_lab import i18n  # noqa: E402
TOOL[0] = 'CUT'
i18n.force('EN')
on_en = next(c for c in tb.option_cells(C) if c['label'] == tb.LANG_LABEL)['on']
bpy.ops.mch.toggle_language()
lang1 = i18n.lang()
on_ko = next(c for c in tb.option_cells(C) if c['label'] == tb.LANG_LABEL)['on']
bpy.ops.mch.toggle_language()
lang2 = i18n.lang()
i18n.force('EN')
check(f'the 한글 switch: a click switches Korean / English (EN -> {lang1} -> {lang2}), lit while Korean',
      not on_en and on_ko and lang1 == 'KO' and lang2 == 'EN')
summary()
