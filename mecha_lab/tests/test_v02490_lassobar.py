"""0.24.78 One place for the lasso: every drawing tool's top bar shows the lasso settings right after the shapes
(LASSO = the shape's own options, CORNERS = the 2D corners), and the bevel of the new cut edges (GN Edge, Edge
Finish, Split sides; Base Mesh edge bevel) - the side panel no longer repeats them.  Concept Move / Path Move /
Silhouette Move leave Blender's tool header empty like every other tool.  Lasso settings are kept per tool.

Not verified here (no window in bpy): how the bar looks and the 0.2 s watcher (tool changes made outside the Mecha
tool buttons)."""
import types

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import (bottom_bar, concept_move as cm, lasso_memory as lm, side_panel as sp, tool_state as ts,
                       top_bar as tb, ui_bars as ub)

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
W, H, HP = 2560, 1440, 1440


class Ctx:
    region = types.SimpleNamespace(width=W, height=H, x=0, y=0, type='WINDOW')
    area = None

    def __getattr__(self, n):
        return getattr(bpy.context, n)


CTX = Ctx()
TOOL = ['CUT']
real_eff, real_ws = ts.effective_tool, ts.is_mecha_workspace
ts.effective_tool = lambda c: TOOL[0]
ts.is_mecha_workspace = lambda ws: True
real_side_on = sp.on
sp.on = lambda c: True
B = S.mch_brush
cut = S.mch_cut


def bar(tool):
    TOOL[0] = tool
    sp.dirty()
    return tb.items(CTX, W, H, 1.0)


def groups(tool):
    TOOL[0] = tool
    return [t for t, _c in tb.groups(CTX, tool)]


def labels(items, kind=None):
    return {i.label for i in items if kind is None or i.kind == kind}


def side(tool):
    TOOL[0] = tool
    sp.dirty()
    return sp.items(CTX, W, HP, 1.0)


# --- the same place in every drawing tool -----------------------------------------------------------------------
B.shape = 'LASSO'
order_ok = []
for tool in sorted(ts.SHAPE_TOOLS):
    g = groups(tool)
    order_ok.append(g[:3] == ['Shape', 'Lasso', 'Corners'] if tool not in {'MASK', 'BASE', 'CBASE'}
                    else g[:2] == ['Shape', 'Corners'])
check(f'Every drawing tool ({len(ts.SHAPE_TOOLS)}): SHAPE, then LASSO / CORNERS right after it (the same place)',
      all(order_ok), [t for t, ok in zip(sorted(ts.SHAPE_TOOLS), order_ok) if not ok])
for shape, want in (('CIRCLE', {'circle_segments'}), ('ELLIPSE', {'circle_segments'}),
                    ('CURVE_LASSO', {'curve_resolution'}), ('STROKE', {'stroke_spacing', 'stroke_smooth',
                                                                       'stroke_simplify'}),
                    ('CUSTOM', {'custom_size', 'custom_rotation'})):
    B.shape = shape
    got = {i.prop for i in bar('CUT') if i.kind == 'mini'}
    check(f'{shape}: its own options in the bar ({", ".join(sorted(want))})', want <= got, sorted(got))
B.shape = 'STROKE'
check('Free Draw on Mask: + its brush radius', 'mask_brush_radius' in {i.prop for i in bar('MASK')})
B.shape = 'LASSO'
it = bar('CUT')
check('Lasso: Open Line + CORNERS Sharp / Round / Chamfer', {'Open Line', 'Sharp', 'Round', 'Chamfer'}
      <= labels(it, 'seg'))
B.outline_corner = 'ROUND'
it = bar('CUT')
check('... Round: its Width and Segments join', {'outline_radius', 'outline_segments'}
      <= {i.prop for i in it if i.kind == 'mini'})
corner = next(i for i in it if i.kind == 'seg' and i.label == 'Chamfer')
ub.run(CTX, corner)
check('... a click on Chamfer: the corners chamfered (the segments go)', B.outline_corner == 'CHAMFER'
      and 'outline_segments' not in {i.prop for i in bar('CUT')})
B.outline_corner = 'NONE'
B.shape = 'RECT'
check('Rectangle: CORNERS too (no LASSO group)', groups('CUT')[:2] == ['Shape', 'Corners'])
B.shape = 'LASSO'

# --- the cut edge's bevel ---------------------------------------------------------------------------------------
cut.gn_finish, cut.edge_finish = 'NONE', 'NONE'
g = groups('CUT')
check('Cut: GN EDGE and (GN Edge off) EDGE FINISH in the bar, before Ortho', g[-3:] == ['GN Edge', 'Edge Finish', '']
      and 'Ortho' in labels(bar('CUT'), 'seg'), g)
cut.gn_finish = 'BEVEL'
it = bar('CUT')
check('GN Edge Bevel: Width and Segments; Edge Finish goes (it is skipped while GN Edge is on)',
      {'gn_width', 'gn_segments'} <= {i.prop for i in it if i.kind == 'mini'} and 'Edge Finish' not in groups('CUT'))
cut.gn_finish = 'NONE'
ub.run(CTX, next(i for i in bar('CUT') if i.kind == 'seg' and i.prop == 'edge_finish' and i.label == 'Bevel'))
it = bar('CUT')
check('Edge Finish Bevel from the bar: Width, Segments, Profile, Clamp, Crisp', cut.edge_finish == 'BEVEL'
      and {'finish_width', 'finish_segments', 'finish_profile'} <= {i.prop for i in it if i.kind == 'mini'}
      and {'Clamp', 'Crisp'} <= labels(it, 'seg'))
cut.edge_finish = 'NONE'
g = groups('SPLIT')
check('Split: GN EDGE (+ sides), SIDE A, SIDE B', {'GN Edge', 'Side A', 'Side B'} <= set(g), g)
cut.side_b_finish = 'CHAMFER'
it = bar('SPLIT')
check('... Side B Chamfer: its width', any(i.prop == 'side_b_width' for i in it) and not any(i.prop == 'side_a_width'
                                                                                          for i in it))
cut.gn_finish = 'CHAMFER'
it = bar('SPLIT')
check('... GN Edge on: its Split Sides choice, the per-side finishes go', any(i.kind == 'drop' and i.prop == 'gn_sides'
                                                                              for i in it)
      and 'Side A' not in groups('SPLIT'))
cut.gn_finish, cut.side_b_finish = 'NONE', 'NONE'
S.mch_base.profile = 'BEVEL'
it = bar('BASE')
check('Base Mesh: EDGE Flat / Chamfer / Bevel + sides, width, segments', 'Edge' in groups('BASE')
      and {'bevel_width', 'bevel_segments'} <= {i.prop for i in it if i.kind == 'mini'}
      and any(i.kind == 'drop' and i.prop == 'bevel_sides' for i in it))
flat = next(i for i in it if i.kind == 'seg' and i.label == 'Flat' and i.action and i.action[0] == 'op')
ub.run(CTX, flat)
check('... Flat from the bar: the base mesh profile flat', S.mch_base.profile == 'FLAT')
check('Creature Base Mesh: no edge bevel group (Puff / Ridge / Pillow)', 'Edge' not in groups('CBASE'))
check('Box Hide / Plate: no edge group', 'GN Edge' not in groups('HIDE') and 'Edge' not in groups('PLATE'))

# --- the side panel does not repeat them -----------------------------------------------------------------------
B.shape = 'LASSO'
for tool in ('CUT', 'SPLIT', 'BASE', 'WRINKLE'):
    its = side(tool)
    rep = [i.prop for i in its if i.data is not None and sp.is_top_bar(i.data, i.prop)]
    check(f'Side panel ({tool}): nothing that is in the top bar', not rep, rep)
heads = labels(side('SPLIT'), 'shead')
check('... Split: no GN EDGE / per-side finish sections left with only their titles', not any(
    h.startswith('GN EDGE') or h.startswith('CUT EDGE FINISH') for h in heads), sorted(heads))
check('... Cut: the GN Edge section stays for Ramp', any(h.startswith('GN EDGE') for h in labels(side('CUT'), 'shead')))
S.mch_base.profile = 'FLAT'
prof = [i for i in side('BASE') if i.kind == 'tbtn' and i.action and i.action[:2] == ('op', 'mch.set_profile')]
check('... Base Mesh keeps its own profile row (Flat / Bevel / Chamfer / Dome ...)', len(prof) > 3, len(prof))

# --- Concept Move family: Blender's tool header empty ------------------------------------------------------------


class Layout:
    def __init__(self):
        self.calls = 0

    def __getattr__(self, n):
        def f(*a, **k):
            self.calls += 1
            return self
        return f


hdr = types.SimpleNamespace(region=types.SimpleNamespace(type='TOOL_HEADER'), scene=S, active_object=None)
side_ctx = types.SimpleNamespace(region=types.SimpleNamespace(type='UI'), scene=S, active_object=None)
empty = []
for cls in (cm.MCH_TOOL_concept_move, cm.MCH_TOOL_concept_path, cm.MCH_TOOL_silhouette_move):
    lay = Layout()
    cls.draw_settings(hdr, lay, None)
    empty.append(lay.calls == 0)
check('Concept / Path / Silhouette Move: nothing in Blender\'s tool header (it was the whole settings row)',
      all(empty), empty)
lay = Layout()
try:
    cm.MCH_TOOL_concept_path.draw_settings(side_ctx, lay, None)
except AttributeError:
    pass
check('... elsewhere (the sidebar\'s tool tab) still drawn', lay.calls > 0)
TOOL[0] = 'CMOVE'
check('... and the Mecha top bar for them: no lasso groups (only Ortho)', groups('CMOVE') == [''])

# --- lasso settings per tool -----------------------------------------------------------------------------------
ts.effective_tool = real_eff
lm.forget()
from mecha_lab.workspace_ui import activate_mecha_tool
activate_mecha_tool(C, 'CUT')
B.shape, B.line_mode, B.outline_corner = 'RECT', False, 'ROUND'
activate_mecha_tool(C, 'BASE')
check('First time in Base Mesh: it starts with what you had (Rectangle, Round corners)', B.shape == 'RECT'
      and B.outline_corner == 'ROUND')
B.shape, B.line_mode, B.outline_corner = 'CURVE_LASSO', True, 'NONE'
activate_mecha_tool(C, 'CUT')
check('Back to Cut: Cut\'s own (Rectangle, Round, no Line)', B.shape == 'RECT' and B.outline_corner == 'ROUND'
      and not B.line_mode, (B.shape, B.outline_corner, B.line_mode))
activate_mecha_tool(C, 'CMOVE')
activate_mecha_tool(C, 'BASE')
check('Base Mesh again (through Concept Move): its own (Curve Lasso, Line on)', B.shape == 'CURVE_LASSO'
      and B.line_mode)
ok = lm._on_save_pre() is None and lm.KEY in S
import json
saved = json.loads(S[lm.KEY])
check('Saved in the file with the scene (each tool\'s set)', ok and saved.get('CUT', {}).get('shape') == 'RECT'
      and saved.get('BASE', {}).get('shape') == 'CURVE_LASSO', sorted(saved))
lm.forget()
activate_mecha_tool(C, 'CUT')
check('... read back after a reload (memory dropped): Cut\'s from the file', B.shape == 'RECT', B.shape)
from mecha_lab.workspace_ui import pref
prefs = C.preferences.addons['mecha_lab'].preferences if 'mecha_lab' in C.preferences.addons else None
if prefs is not None and hasattr(prefs, 'lasso_per_tool'):
    prefs.lasso_per_tool = False
    B.shape = 'CIRCLE'
    activate_mecha_tool(C, 'BASE')
    check('Preference off: one set for every tool (Base Mesh keeps the Circle)', B.shape == 'CIRCLE')
    prefs.lasso_per_tool = True
else:
    real_en = lm.enabled
    lm.enabled = lambda: False
    B.shape = 'CIRCLE'
    activate_mecha_tool(C, 'BASE')
    check('Preference off: one set for every tool (Base Mesh keeps the Circle)', B.shape == 'CIRCLE')
    lm.enabled = real_en
check('The preference exists (Lasso Settings per Tool, on by default)',
      'lasso_per_tool' in __import__('mecha_lab.workspace_ui', fromlist=['x']).MCH_AddonPreferences.__annotations__
      and pref('lasso_per_tool', True))

sp.on = real_side_on
ts.is_mecha_workspace = real_ws
summary()
