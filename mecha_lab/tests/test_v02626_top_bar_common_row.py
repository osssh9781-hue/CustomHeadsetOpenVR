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
      not gone and set(states) == set(before), gone[:4])
kinds = {json.loads(k)[0] for k in new}
check(f'the only new things are group names shown a second time ({sorted(set(json.loads(k)[1] for k in new))}: Press Cut\'s '
      f'own Line / Lasso switch stays with the tool\'s own groups)', kinds <= {'glabel'})

# one place per cell: over every tool and every state it is shown in
FIXED = {}
for title, sources, specs in tb.common_slots():
    if isinstance(specs, list):
        for label, kind, _icon, _w, match in specs:
            FIXED[(kind, label)] = match
where = collections.defaultdict(set)
seen = collections.Counter()


def bar_h(its):
    cards = [i for i in its if i.kind == 'card' and i.icon != 'outer']
    return max(c.y + c.h for c in cards) - min(c.y for c in cards)


def cell_of(i):
    return dict(kind=i.kind, label=i.label, action=i.action, prop=i.prop, data=i.data, on=i.on, icon=i.icon, width=None)


def record(tag):
    for t in tools:
        TOOL[0] = t
        its = tb.items(C, 2560, 1440, 1.0, left=0.0, right=2560.0)
        for i in its:
            key = (i.kind, i.label)
            if key in FIXED and i.enabled and FIXED[key](cell_of(i)):
                where[key].add((round(i.x, 2), round(1440 - i.y, 2), round(i.w, 2)))    # (x, down from the view's top, w)
                seen[key] += 1


B.shape = 'LASSO'; B.outline_corner = 'NONE'; B.stab_enable = False; cut.depth_mode = 'THROUGH'; B.surface_mode = False
record('default')
moved = {k: v for k, v in where.items() if len(v) != 1}
check(f'every fixed cell is at ONE place for all {len(tools)} tools ({len(where)} cells, e.g. Res seen '
      f'{seen[("mini", "Res")]} times at {sorted(where[("mini", "Res")])}); {len(moved)} move',
      not moved and len(where) >= 18 and seen[('mini', 'Res')] > 30, moved)
B.stab_enable = True; cut.depth_mode = 'SURFACE'; B.outline_corner = 'ROUND'; B.surface_mode = True; B.through_mode = True
record('everything on')
for sh in ('CIRCLE', 'STROKE', 'RECT'):
    B.shape = sh
    record(sh)
B.shape = 'LASSO'; B.stab_enable = False; cut.depth_mode = 'THROUGH'; B.outline_corner = 'NONE'; B.surface_mode = False
B.through_mode = False
side = {k: sorted({p_[0] for p_ in v}) for k, v in where.items() if len({p_[0] for p_ in v}) != 1}
check(f'0.24.218 with everything switched on (Slow Line, From Surface, round corners, Surface, Through) and other '
      f'shapes: no cell moves SIDEWAYS, ever ({len(where)} cells over {len(tools)} tools x 5 states)', not side, side)
COND = {k for k in where if k in tb.COND}
under = {}
for kind, label, parent in (('mini', 'Strength', ('seg', 'Slow Line')), ('mini', 'Depth', ('seg', 'Through All')),
                            ('mini', 'Width', ('seg', 'Sharp')), ('mini', 'Gap', ('seg', 'Surface'))):
    cy_ = min(p_[1] for p_ in where[(kind, label)])
    py_ = min(p_[1] for p_ in where[parent])
    under[label] = cy_ > py_                           # (measured down from the bar's top: further down)
check(f'the cells that come and go have places of their own in a row under their section ({sorted(c[1] for c in COND)}: '
      f'{under})', len(COND) == len(tb.COND) and all(under.values()))
TOOL[0] = 'CUT'
h0 = bar_h(tb.items(C, 2560, 1440, 1.0, left=0.0, right=2560.0))
B.stab_enable = True
h1 = bar_h(tb.items(C, 2560, 1440, 1.0, left=0.0, right=2560.0))
B.stab_enable = False
check(f'... the bar grows down by a row while one of them shows (Cut: {h0:.0f} -> {h1:.0f} px with Slow Line on) and is '
      f'back after', h1 > h0 and bar_h(tb.items(C, 2560, 1440, 1.0, left=0.0, right=2560.0)) == h0)


def at(width, tool):
    TOOL[0] = tool
    return tb.items(C, width, 1000, 1.0, left=0.0, right=float(width))


its = at(2560, 'SMART')
labels = {i.label for i in its if i.kind in {'seg', 'ibtn', 'mini'}}
check(f'a place the tool does not use is EMPTY, nothing greyed, nothing moved in (Smart Move: no shapes, no Res; it '
      f'has {len(labels)} cells), and every cell shown can be clicked',
      'Lasso' not in labels and 'Res' not in labels and 'Sketch' not in labels and 'Ortho' in labels
      and all(i.enabled for i in its))
hs = {t: bar_h(at(2560, t)) for t in tools}
its = at(2560, 'SMART')
cards = [i for i in its if i.kind == 'card' and i.icon != 'outer']
n_cut = len([i for i in at(2560, 'CUT') if i.kind == 'card' and i.icon != 'outer'])
check(f'0.24.218 every section is a card of its own; a section the tool does not use has NO card (Smart Move: '
      f'{len(cards)} cards, Cut: {n_cut}) - the view shows there, no empty dark place; the bar is as high as the tool '
      f'needs (Smart Move {hs["SMART"]:.0f} px, Cut {hs["CUT"]:.0f} px)',
      1 <= len(cards) < n_cut and hs['SMART'] <= hs['CUT']
      and all(any(c.x <= i.x and i.x + i.w <= c.x + c.w + 0.01 and c.y <= i.y and i.y + i.h <= c.y + c.h + 0.01 for c in cards)
              for i in its if i.kind in {'seg', 'mini', 'ibtn', 'drop', 'glabel'}))
its = at(2560, 'BASE')
left_edge = min(i.x for i in its if i.kind == 'card' and i.icon != 'outer')
own = [i for i in its if i.kind == 'glabel' and i.label in {'EDGE', 'SIDES'}]
fixed_bottom = min(i.y for i in its if (i.kind, i.label) in FIXED and FIXED[(i.kind, i.label)](cell_of(i)))
check('the tool\'s own groups (Base Mesh: Edge) are under the fixed rows, from the left',
      bool(own) and all(i.y < fixed_bottom for i in own) and min(i.x for i in own) - left_edge < 20)
rows_at = {w_: len({round(i.y, 1) for i in at(w_, 'CUT') if (i.kind, i.label) in FIXED}) for w_ in (2560, 1800, 1300)}
same_narrow = {}
for w_ in (1800, 1300):
    pos = collections.defaultdict(set)
    for t in tools:
        its_ = at(w_, t)
        for i in its_:
            if (i.kind, i.label) in FIXED and FIXED[(i.kind, i.label)](cell_of(i)):
                pos[(i.kind, i.label)].add((round(i.x, 1), round(1000 - i.y, 1)))
    same_narrow[w_] = all(len(v) == 1 for v in pos.values())
check(f'a narrower view: the fixed places take more rows ({rows_at}) - how they are split depends on the width alone, '
      f'so they are still the same for every tool ({same_narrow})', all(same_narrow.values())
      and rows_at[1300] >= rows_at[1800] >= rows_at[2560])
# the look: sections side by side like the tool menu - a title on top, its cells under it, a rule between
its = at(2560, 'CUT')
res_cell = next(i for i in its if i.kind == 'mini' and i.label == 'Res')
res_title = next(i for i in its if i.kind == 'glabel' and i.label == 'RESOLUTION')
apply_cell = next(i for i in its if i.label == 'Apply to Parts')
names = [i.label for i in its if i.kind == 'glabel']
check(f'sections: the title above its cells (Resolution over Res, Apply to Parts beside it), each in its own card; {names}',
      res_title.y > res_cell.y and abs(res_title.x - res_cell.x) < 1.0 and abs(apply_cell.y - res_cell.y) < 1.0
      and apply_cell.x > res_cell.x and len([i for i in its if i.kind == 'card']) >= 6 and 'OPTIONS' in names)
tb.FORCE_SECTIONS[0] = False
its = at(2560, 'CUT')
res_cell = next(i for i in its if i.kind == 'mini' and i.label == 'Res')
res_title = next(i for i in its if i.kind == 'glabel' and i.label == 'RESOLUTION')
check('Preferences > Top Bar Sections off: the plain rows of 0.24.216 (the name beside its cells)',
      abs(res_title.y - res_cell.y) < 1.0 and res_title.x < res_cell.x and tb.sections_wanted() is False)
tb.FORCE_SECTIONS[0] = None
check('... on by default', tb.sections_wanted() is True)
# 0.24.219 Options at the bar's top right; the section names bright and bigger
its = at(2560, 'CUT')
cards = [i for i in its if i.kind == 'card']
opt = next(i for i in its if i.kind == 'seg' and i.label == 'Ortho')
opt_title = next(i for i in its if i.kind == 'glabel' and i.label == 'OPTIONS')
top_band = max(i.y for i in its if i.kind in {'seg', 'ibtn', 'mini'})
right_most = max(i.x + i.w for i in its if i.kind in {'seg', 'ibtn', 'mini'} and abs(i.y - top_band) < 1.0)
check(f'Options (Auto Apply, Ortho) is at the top right of the bar: in the first band, the last cell at its right end '
      f'(x {opt.x + opt.w:.0f} of {right_most:.0f})', abs(opt.y - top_band) < 1.0 and abs(opt.x + opt.w - right_most) < 1.0
      and opt.x > 2560 * 0.5)
pos = set()
for t in tools:
    for i in at(2560, t):
        if i.kind == 'seg' and i.label == 'Ortho':
            pos.add((round(i.x, 1), round(1000 - i.y, 1)))
check(f'... the same place in every tool ({sorted(pos)})', len(pos) == 1)
outer = [i for i in its if i.kind == 'card' and i.icon == 'outer']
inner_cards = [i for i in its if i.kind == 'card' and i.icon != 'outer']
widths = {round(next(i for i in at(2560, t) if i.kind == 'card' and i.icon == 'outer').w, 1) for t in tools}
xs = {round(next(i for i in at(2560, t) if i.kind == 'card' and i.icon == 'outer').x, 1) for t in tools}
check(f'0.24.220 one lighter box holds all the section cards (it is drawn first; every card inside it), the same '
      f'width and left edge for every tool ({sorted(widths)} px at {sorted(xs)})',
      len(outer) == 1 and its[0] is outer[0] and len(widths) == 1 and len(xs) == 1
      and all(outer[0].x <= c.x and c.x + c.w <= outer[0].x + outer[0].w + 0.01 and outer[0].y <= c.y
              and c.y + c.h <= outer[0].y + outer[0].h + 0.01 for c in inner_cards))
check('the section names are drawn as titles (bigger, bright) - every section of the bar',
      all(i.icon == 'title' for i in its if i.kind == 'glabel') and tb.TITLE_H >= 18)
wide, narrow = at(2560, 'BASE'), at(500, 'BASE')
check('a view too narrow for a single place (500 px): the groups are packed as before, nothing lost',
      sorted((i.kind, i.label) for i in narrow if i.kind not in {'card', 'vrule', 'glabel'}) ==
      sorted((i.kind, i.label) for i in wide if i.kind not in {'card', 'vrule', 'glabel'}))
summary()
