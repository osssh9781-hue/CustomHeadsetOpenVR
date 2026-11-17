"""0.24.215 (user: "다른 툴들도 클로스 드레이프처럼 정리 한번 해 줘 - 공통 기능은 묶어 주고 목록 구별해 주고, 그리고 기능이나
이상은 없게"): every tool's window is big titled sections made from what its panel already is (a box, a block that
starts with a label, the loose rest as Settings / Actions) - and every cell of every tool's window of 0.24.214
(data/side_panel_cells_0.24.214.json: 80 tools, nothing selected / a cube selected, every section open) is still
there, the same, in the same order."""
import collections
import json
import os

from _harness import bpy, check, cube, fresh, summary

import mecha_lab
from mecha_lab import panel_capture as pc, side_panel as sp, tool_state as ts, ui_tool_settings as uts  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context; S = C.scene
TOOL = ['CUT']
ts.effective_tool = lambda c: TOOL[0]
ts.is_mecha_workspace = lambda ws: True
tools = [t[0] for t in ts.TOOLS if isinstance(t, (tuple, list))]


def jsonable(v):
    if isinstance(v, (str, int, float, bool)) or v is None: return v
    if isinstance(v, (list, tuple)): return [jsonable(x) for x in v]
    if isinstance(v, dict): return {str(k): jsonable(x) for k, x in sorted(v.items())}
    return type(v).__name__


def grab(tool):
    TOOL[0] = tool
    sp.dirty()
    # every section open: fold keys are 'TOOL:title'
    for _pass in range(3):
        items, _h = sp.content(C, tool, 0.0, 300.0, 1.0)
        closed = [i for i in items if i.kind == 'shead' and not i.on and i.action and i.action[0] == 'fold']
        if not closed: break
        for i in closed: sp.toggle_fold(i.action[1], i.action[2])
    cells, texts = [], []
    for i in items:
        if i.kind in {'sbg'}: continue
        d = i.data
        if i.kind in {'shead', 'pnote'}:
            texts.append(str(i.label).upper())
            continue
        cells.append([i.kind, str(i.label), bool(i.on), bool(i.enabled), jsonable(i.action),
                      (type(d).__name__ if d is not None else '') + '.' + (i.prop or '')])
    sp.FOLDED.clear(); sp.OPENED.clear()
    return dict(cells=cells, texts=texts)


states = {}
def sweep(tag):
    for t in tools:
        try: states[f'{t} | {tag}'] = grab(t)
        except Exception as ex: states[f'{t} | {tag}'] = dict(cells=[['ERROR', repr(ex)[:160]]], texts=[])
sweep('nothing selected')
cube(); sweep('a cube selected')

HERE = os.path.dirname(os.path.abspath(__file__))
before = json.load(open(os.path.join(HERE, 'data', 'side_panel_cells_0.24.214.json')))
order = [k for k in before if before[k]['cells'] != states[k]['cells']]
n_cells = sum(len(v['cells']) for v in before.values())
check(f'every cell of every tool\'s window is as in 0.24.214 - kind, name, on / off, enabled, what a click does, its '
      f'setting - and in the same order ({n_cells:,} cells, {len(before)} tool states, {len(order)} differ)',
      not order and set(before) == set(states), order[:5])
gone, new = collections.Counter(), collections.Counter()
for k in before:
    cb, ca = collections.Counter(before[k]['texts']), collections.Counter(states[k]['texts'])
    gone.update(cb - ca)
    new.update(ca - cb)
check(f'every title and note is still shown ({sum(len(v["texts"]) for v in before.values()):,} texts, {sum(gone.values())} '
      f'gone); new: only the names of the sections made from loose settings {dict(new)}',
      not gone and all(k.replace('MORE ', '').rstrip(' +') in {'SETTINGS', 'ACTIONS'} for k in new), list(gone.items())[:5])
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
sp.FOLDED.clear(); sp.OPENED.clear()


def heads(tool):
    TOOL[0] = tool
    sp.dirty()
    items, _h = sp.content(C, tool, 0.0, 300.0, 1.0)
    return [i for i in items if i.kind == 'shead'], items


big_tools = [t for t in tools if any(str(i.icon).startswith('big:') for i in heads(t)[0])]
with_panel = [t for t in tools if uts.DRAWERS.get(t) is not None]
check(f'big coloured section titles in {len(big_tools)} of the {len(with_panel)} tools that have a window',
      len(big_tools) >= len(with_panel) - 6, sorted(set(with_panel) - set(big_tools)))
h, _i = heads('FUR')
names = [i.label for i in h if str(i.icon).startswith('big:')]
check(f'Fur: its blocks are sections by the names they had ({names[:8]})',
      all(x in names for x in ('STRANDS', 'SHAPE', 'BEND', 'THICKNESS', 'COLOR')))
h, _i = heads('SPIKE')
names = [i.label for i in h if str(i.icon).startswith('big:')]
check(f'Spike Line (a flat list before): {names}', len(names) >= 2)
cols = [str(i.icon).split('|')[0] for i in heads('FUR')[0] if str(i.icon).startswith('big:')
        and not str(i.icon).startswith('big:9')]          # (the grey ones: Lasso / Presets / Help, at the end)
check(f'neighbouring sections have different colours ({cols[:6]})', all(a_ != b_ for a_, b_ in zip(cols, cols[1:])))
dup = {}
for t in tools:
    names = [i.action[1] for i in heads(t)[0] if i.action and i.action[0] == 'fold' and str(i.icon).startswith('big:')]
    made = [n for n in names if n.split(':', 1)[1].replace('More ', '').rstrip(' +') in {'Settings', 'Actions'}]
    if len(made) != len(set(made)):
        dup[t] = made
check('the sections made here each fold on their own (no two with the same name in a window)', not dup, dup)
h, items = heads('CDRAPE')
check('Cloth Drape keeps the sections and colours it was given (0.24.213)',
      [i.label for i in h if str(i.icon).startswith('big:')][:7] == ['CLOTH DRAPE', 'MAKE', 'FABRIC', 'PINS & STITCHES',
                                                                      'DETAIL & THICKNESS', 'FINISH', 'COLLISION'])
tree = pc.capture(uts.DRAWERS['FUR'], C)
kinds_before = [(n.kind, n.prop or n.opts.get('idname') or n.opts.get('text')) for n in pc.walk(tree) if n.kind in sp.CONTROLS]
out = sp.auto_sections(tree, 'FUR')
kinds_after = [(n.kind, n.prop or n.opts.get('idname') or n.opts.get('text')) for n in pc.walk(out) if n.kind in sp.CONTROLS]
check(f'auto_sections only frames what is there: the {len(kinds_before)} controls of Fur, the same ones in the same order',
      kinds_before == kinds_after and len(kinds_before) > 20)
summary()
