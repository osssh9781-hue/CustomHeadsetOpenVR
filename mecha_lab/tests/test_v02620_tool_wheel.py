"""0.24.201 Tool Wheel (user: a radial menu at the cursor, click / hover / flick; "우리는 총 11개고 그 안에 각 메뉴가
있으니까 그렇게"): the bottom menu's groups in a ring, the open group's tools fanned out.  The layout and the pick
are plain functions; the key, the hover and the clicks are in tests/gui/round201."""
import math

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import radial_menu as rm, tool_state as ts  # noqa: E402

fresh()
mecha_lab.register()
grp = rm.groups()
names = [g[0] for g in grp]
ids = [t[0] for _n, rows in grp for t in rows]
check(f'the wheel\'s groups are the bottom menu\'s ({len(grp)}): {names}', len(grp) == 11
      and names == [n for n, _r in ts.grouped_tools()][:11] and len(ids) == len(set(ids)) and 'CUT' in ids, names)
k = 1.0
closed = rm.layout(500, 500, k, grp, -1)
check('closed: eleven group bubbles on one ring, the first at the top, going clockwise, none overlapping',
      len(closed) == 11 and all(i['kind'] == 'group' for i in closed)
      and all(abs(math.hypot(i['x'] - 500, i['y'] - 500) - rm.R_GROUP) < 1e-6 for i in closed)
      and abs(closed[0]['x'] - 500) < 1e-6 and closed[0]['y'] > 500 and closed[1]['x'] > 500
      and min(math.hypot(a['x'] - b['x'], a['y'] - b['y']) for a in closed for b in closed if a is not b) > 2 * rm.B_GROUP)
worst, counts = 1e9, []
for gi in range(len(grp)):
    allb = rm.layout(500, 500, k, grp, gi)
    its = [i for i in allb if i['kind'] == 'tool']
    counts.append(len(its))
    for a in its:
        for b in allb:
            if a is not b:
                worst = min(worst, math.hypot(a['x'] - b['x'], a['y'] - b['y']) - a['r'] - b['r'])
check(f'each group open: all its tools shown ({counts}), no tool bubble on another bubble (nearest gap {worst:.1f} px)',
      counts == [len(r) for _n, r in grp] and worst > 0.0)
ci = names.index('Cut')
its = rm.layout(500, 500, k, grp, ci)
g_cut = next(i for i in its if i['kind'] == 'group' and i['index'] == ci)
t_split = next(i for i in its if i['id'] == 'SPLIT')
check('pick: the middle = nothing; on a group bubble = that group; on a tool bubble = that tool',
      rm.pick(500, 500, k, grp, -1, 505, 503) is None
      and rm.pick(500, 500, k, grp, -1, g_cut['x'], g_cut['y']) == ('group', ci)
      and rm.pick(500, 500, k, grp, ci, t_split['x'], t_split['y']) == ('tool', 'SPLIT'))
a = math.atan2(g_cut['y'] - 500, g_cut['x'] - 500)
between = (500 + math.cos(a) * 70, 500 + math.sin(a) * 70)             # (short of the ring, toward Cut)
far = (t_split['x'] + math.cos(a) * 160, t_split['y'] + math.sin(a) * 160)   # (flicked well past the tools)
other = (500 - math.cos(a) * 300, 500 - math.sin(a) * 300)             # (the other way, far out)
check('flick: toward a group short of its bubble = that group; far past the open group\'s tools = the nearest tool; '
      'far out the other way = the group over there, not a tool',
      rm.pick(500, 500, k, grp, -1, *between) == ('group', ci)
      and rm.pick(500, 500, k, grp, ci, *far)[0] == 'tool'
      and rm.pick(500, 500, k, grp, ci, *other)[0] == 'group' and rm.pick(500, 500, k, grp, ci, *other)[1] != ci)
check('near a region edge the wheel moves in so the ring shows; in the open it is at the mouse',
      rm.fit_centre(5, 5, 1920, 1080, 1.0) == (rm.R_GROUP + rm.B_GROUP + 8.0,) * 2
      and rm.fit_centre(900, 500, 1920, 1080, 1.0) == (900, 500))
check('V (the Tool Pie key) is the wheel: the operator exists and the key item is still there',
      hasattr(bpy.types, 'MCH_OT_radial_menu') and hasattr(bpy.types, 'MCH_OT_tool_pie'))
summary()
