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
        out.append([i.kind, i.label, bool(i.on), jsonable(i.action), (type(d).__name__ if d is not None else '') + '.' + (i.prop or ''), i.icon])
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


def cell_of(i):
    return dict(kind=i.kind, label=i.label, action=i.action, prop=i.prop, data=i.data, on=i.on, icon=i.icon, width=None)


def record(tag):
    for t in tools:
        TOOL[0] = t
        its = tb.items(C, 2560, 1440, 1.0, left=0.0, right=2560.0)
        card = its[0]
        for i in its:
            key = (i.kind, i.label)
            if key in FIXED and i.enabled and FIXED[key](cell_of(i)):
                where[key].add((round(i.x - card.x, 2), round(card.y + card.h - i.y, 2), round(i.w, 2)))
                seen[key] += 1


B.shape = 'LASSO'; B.outline_corner = 'NONE'; B.stab_enable = False; cut.depth_mode = 'THROUGH'; B.surface_mode = False
record('default')
B.stab_enable = True; cut.depth_mode = 'SURFACE'; B.outline_corner = 'ROUND'; B.surface_mode = True; B.through_mode = True
record('everything on')
for sh in ('CIRCLE', 'STROKE', 'RECT'):
    B.shape = sh
    record(sh)
B.shape = 'LASSO'; B.stab_enable = False; cut.depth_mode = 'THROUGH'; B.outline_corner = 'NONE'; B.surface_mode = False
B.through_mode = False
moved = {k: v for k, v in where.items() if len(v) != 1}
check(f'every fixed cell is at ONE place - the same for all {len(tools)} tools and 5 states it was looked at in '
      f'({len(where)} cells, e.g. Res seen {seen[("mini", "Res")]} times at {sorted(where[("mini", "Res")])}); '
      f'{len(moved)} move', not moved and len(where) >= 30 and seen[('mini', 'Res')] > 100, moved)
check('... also the ones that come and go: Slow Line\'s Strength / Radius, the Depth value and floor, the corner Width / '
      'Segments, Surface\'s Gap', all(k in where for k in (('mini', 'Strength'), ('mini', 'Radius'), ('mini', 'Depth'),
                                                            ('seg', 'Follow'), ('mini', 'Width'), ('mini', 'Segments'),
                                                            ('mini', 'Gap'))))


def at(width, tool):
    TOOL[0] = tool
    return tb.items(C, width, 1000, 1.0, left=0.0, right=float(width))


its = at(2560, 'SMART')
labels = {i.label for i in its if i.kind in {'seg', 'ibtn', 'mini'}}
check(f'a place the tool does not use is EMPTY, nothing greyed, nothing moved in (Smart Move: no shapes, no Res; it '
      f'has {len(labels)} cells), and every cell shown can be clicked',
      'Lasso' not in labels and 'Res' not in labels and 'Sketch' not in labels and 'Ortho' in labels
      and all(i.enabled for i in its))
hs = {t: at(2560, t)[0].h for t in tools}
check(f'the bar hangs from the top; the rows under the last place a tool uses are left out, so a tool with few '
      f'settings has a small bar (Smart Move {hs["SMART"]:.0f} px, Cut {hs["CUT"]:.0f} px) - the places above keep '
      f'their distance from the top (the check before)', hs['SMART'] <= hs['CUT'] and len({round(at(2560, t)[0].y + at(2560, t)[0].h, 2) for t in tools}) == 1)
its = at(2560, 'BASE')
card = its[0]
own = [i for i in its if i.kind == 'glabel' and i.label in {'EDGE', 'SIDES'}]
fixed_bottom = min(i.y for i in its if (i.kind, i.label) in FIXED and FIXED[(i.kind, i.label)](cell_of(i)))
check('the tool\'s own groups (Base Mesh: Edge) are under the fixed rows, from the left',
      bool(own) and all(i.y < fixed_bottom for i in own) and min(i.x for i in own) - card.x < 20)
rows_at = {w_: len({round(i.y, 1) for i in at(w_, 'CUT') if (i.kind, i.label) in FIXED}) for w_ in (2560, 1800, 1300)}
same_narrow = {}
for w_ in (1800, 1300):
    pos = collections.defaultdict(set)
    for t in tools:
        its_ = at(w_, t)
        for i in its_:
            if (i.kind, i.label) in FIXED and FIXED[(i.kind, i.label)](cell_of(i)):
                pos[(i.kind, i.label)].add((round(i.x - its_[0].x, 1), round(its_[0].y + its_[0].h - i.y, 1)))
    same_narrow[w_] = all(len(v) == 1 for v in pos.values())
check(f'a narrower view: the fixed places take more rows ({rows_at}) - how they are split depends on the width alone, '
      f'so they are still the same for every tool ({same_narrow})', all(same_narrow.values())
      and rows_at[1300] >= rows_at[1800] >= rows_at[2560])
wide, narrow = at(2560, 'BASE'), at(500, 'BASE')
check('a view too narrow for a single place (500 px): the groups are packed as before, nothing lost',
      sorted((i.kind, i.label) for i in narrow if i.kind not in {'card', 'vrule', 'glabel'}) ==
      sorted((i.kind, i.label) for i in wide if i.kind not in {'card', 'vrule', 'glabel'}))
summary()
