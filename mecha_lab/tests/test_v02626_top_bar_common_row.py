"""0.24.214 (user: "상단 바도 매번 배치랑 구성이 달라지고 헷갈린단 말이야 - 모든 툴 공통으로 배치 유지해 놓고 툴마다 달라지는
설정만 추가로 아래에다가 배치" / "기능이나 이상은 없게"): the top bar's first row is the same for every tool (Shape,
Draw, Target, Depth, Auto Apply, Ortho - in the same places; what a tool has not is greyed), the tool's own settings in
the rows under it - and every cell the bar had in 0.24.213 (data/top_bar_cells_0.24.213.json: 80 tools x 10 states)
is still there, the same."""
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
check(f'the only new things are group names shown a second time ({sorted(json.loads(k)[1] for k in new)}): a group '
      f'whose common part is in the first row and whose own extras are below', kinds <= {'glabel'})
B.shape = 'LASSO'; B.outline_corner = 'NONE'
S.mch_base.profile = 'FLAT'


def first_row(tool):
    TOOL[0] = tool
    its = tb.items(C, 2560, 1440, 1.0, left=0.0, right=2560.0)
    top = max(i.y for i in its if i.kind not in {'card'})
    return [(i.kind, '' if i.kind == 'glabel' else i.label, round(i.x, 2), round(i.w, 2)) for i in its
            if abs(i.y - top) < 1e-6 and i.kind != 'vrule'], its


ref, _its = first_row('CUT')
same = [t for t in tools if first_row(t)[0] == ref]
check(f'the first row is the same cells in the same places for every tool ({len(same)} of {len(tools)} tools equal to '
      f'Cut\'s: {[c[1] for c in ref if c[0] != "glabel"]})', len(same) == len(tools),
      [t for t in tools if t not in same][:6])
row, its = first_row('SMART')
off = [i.label for i in its if not i.enabled and i.action is None and i.kind in {'seg', 'ibtn'}]
check(f'what a tool does not have is greyed and does nothing (Smart Move: {len(off)} greyed - {off[:4]} ...), never '
      f'clickable', len(off) > 5 and all(not i.clickable() for i in its if not i.enabled))
row, its = first_row('BASE')
top = max(i.y for i in its if i.kind != 'card')
lower = sorted({i.label for i in its if i.y < top - 1 and i.kind == 'glabel'})
check(f'the tool\'s own settings are in the rows under it (Base Mesh: {lower})',
      'EDGE' in lower and 'CORNERS' in lower and 'RESOLUTION' in lower)
def rows_of_bar(its):
    ys = sorted({round(i.y, 2) for i in its if i.kind not in {'card', 'vrule'}}, reverse=True)
    # (a group's name is not compared: the shapes are called SHIFT+DRAW on three tools - same place, same cells)
    return [[(i.kind, '' if i.kind == 'glabel' else i.label, round(i.x, 2), round(i.w, 2)) for i in its
             if round(i.y, 2) == y and i.kind != 'vrule'] for y in ys]


def at(width, tool):
    TOOL[0] = tool
    return tb.items(C, width, 1000, 1.0, left=0.0, right=float(width))


mid = {t: rows_of_bar(at(1300, t))[:2] for t in tools}
check(f'a view too narrow for one common row (1300 px): two common rows, split at the same place, still the same for '
      f'every tool ({[c[1] for c in mid["CUT"][0] if c[0] != "glabel"][:3]} ... | '
      f'{[c[1] for c in mid["CUT"][1] if c[0] != "glabel"]})',
      all(v == mid['CUT'] for v in mid.values()) and any(c[1] == 'Ortho' for c in mid['CUT'][1])
      and any(c[1] == 'Slow Line' for c in mid['CUT'][0]))
its = at(2560, 'BASE')
narrow = at(600, 'BASE')
check('a view too narrow even for that (600 px): the rows are packed as before, nothing lost',
      sorted((i.kind, i.label) for i in narrow if i.kind not in {'card', 'vrule', 'glabel'} and i.enabled) ==
      sorted((i.kind, i.label) for i in its if i.kind not in {'card', 'vrule', 'glabel'} and i.enabled)
      and not any(not i.enabled for i in narrow))
summary()
