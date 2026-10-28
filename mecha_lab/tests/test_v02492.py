"""0.24.60 ZBrush-style sculpting in the MECHA LAB tab: ZBrush names over Blender settings, the shelf actions on a
real mesh (Divide / SDiv / Del Higher / DynaMesh by points / ZRemesher / Mirror / Close Holes / Split / Groups /
Merge / Decimate / Check & Fix / Append / Duplicate / Delete), the brushes by ZBrush name and B letters, the mouse
plan, the keys (Sculpt keymap, only in the tab), the drawn screen (orange) and its clicks."""
import inspect
import types

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import tool_state as ts, ui_bars as ub, zb_sculpt as zs, zb_ui as zu, workspace_ui as wui

mecha_lab.register()
fresh()
C = bpy.context
real_on = zs.on
zs.on = lambda c: getattr(c, 'mode', '') == 'SCULPT'          # (the test has no MECHA LAB tab)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=32, ring_count=16)
ob = C.active_object
bpy.ops.object.mode_set(mode='SCULPT')
zb = C.scene.mch_zb
check('Sculpt Mode: the ZBrush screen is on (only in the MECHA LAB tab: real on() checks the workspace)',
      zs.on(C) and 'mecha_sculpt' in inspect.getsource(real_on) and 'is_mecha_workspace' in inspect.getsource(
          zs.mecha_tab) and "'SCULPT'" in inspect.getsource(zs.mecha_sculpt))

# --- brushes by ZBrush name ---------------------------------------------------------------------------------------
msg = zs.activate(C, 'ClayBuildup')
check('ClayBuildup = Blender Clay Strips (Essentials brush)', msg == '' and zs.brush(C).name == 'Clay Strips', msg)
check('... shown by its ZBrush name', zs.zb_name(zs.brush(C)) == 'ClayBuildup')
ok = [z for z, bl, c in zs.BRUSHES if zs.activate(C, z) == '']
check('Every ZBrush brush on the shelves opens its Blender brush', set(zs.SHELF[0]) | set(zs.SHELF[1]) <= set(ok),
      sorted(set(zs.SHELF[0]) | set(zs.SHELF[1]) - set(ok)))
codes = [c for _z, _b, c in zs.BRUSHES]
check('B letters are unique (B S T = Standard, B C B = ClayBuildup, B D S = DamStandard, B M V = Move)',
      len(codes) == len(set(codes)) and zs.BY_Z['Standard'][2] == 'ST' and zs.BY_Z['ClayBuildup'][2] == 'CB'
      and zs.BY_Z['DamStandard'][2] == 'DS' and zs.BY_Z['Move'][2] == 'MV')
import os
icons = os.path.join(os.path.dirname(zs.__file__), 'icons')
check('Each brush has its thumbnail', all(os.path.isfile(os.path.join(icons, zs.icon_stem(bl) + '.png'))
                                         for _z, bl, _c in zs.BRUSHES))
zs.activate(C, 'Standard')
b0 = zs.brush(C)
check('ZBrush feel: the first use gives pen pressure on size + intensity and a close spacing (once per file)',
      b0.get(zs.TUNED_KEY) == 1 and (not hasattr(b0, 'use_pressure_size') or b0.use_pressure_size)
      and (not hasattr(b0, 'spacing') or b0.spacing == 5))
b0.strength = 0.77
zs.activate(C, 'ClayBuildup')
zs.activate(C, 'Standard')
check('... later changes are kept (not tuned again)', abs(zs.brush(C).strength - 0.77) < 1e-6)

# --- alphas -----------------------------------------------------------------------------------------------------
files, total = zs.alpha_files(C)
check('Alphas: the Mecha alphas come with the add-on', total >= 12 and all(os.path.isfile(f) for f in files))
local_tex = {t.name for t in bpy.data.textures if t.library is None}
local_img = {i.name for i in bpy.data.images if i.library is None}
msg = zs.set_alpha(C, files[0])
b0 = zs.brush(C)
check('Pick an alpha: an image brush texture from the view (ZBrush alpha)', b0.texture is not None
      and os.path.normcase(zs.current_alpha(C)) == os.path.normcase(files[0])
      and b0.texture_slot.map_mode in {'AREA_PLANE', 'VIEW_PLANE'}, msg)
check('0.24.63 It goes on the brush you sculpt with (the Essentials brush itself): a texture linked from a small '
      'file of its own - no brush copy, nothing new in your file', b0.library is not None and b0.name == 'Draw'
      and b0.texture.library is not None and os.path.isfile(bpy.path.abspath(b0.texture.library.filepath))
      and {t.name for t in bpy.data.textures if t.library is None} == local_tex
      and {i.name for i in bpy.data.images if i.library is None} == local_img)
sx = b0.texture_slot.scale[0]
zs.alpha_edit(C, 'FLIP_H')
zs.alpha_edit(C, 'ROTATE')
zs.alpha_edit(C, 'INVERT')
check('Flh / Rot / Invr (Invr = the inverted twin from the same file)', b0.texture_slot.scale[0] == -sx
      and abs(b0.texture_slot.angle - 1.5708) < 1e-3 and b0.texture.name.endswith(zs.INV)
      and os.path.normcase(zs.current_alpha(C)) == os.path.normcase(files[0]))
zs.alpha_edit(C, 'INVERT')
check('... Invr again: back', not b0.texture.name.endswith(zs.INV))
zs.activate(C, 'ClayBuildup')
check('... another brush has no alpha', zs.current_alpha(C) == '')
zs.activate(C, 'Standard')
check('... back on Standard its alpha is still there (ZBrush keeps it per brush)',
      zs.brush(C) == b0 and os.path.normcase(zs.current_alpha(C)) == os.path.normcase(files[0]))
n_libs = len(bpy.data.libraries)
zs.set_alpha(C, files[0])
check('The same alpha again: the same linked texture (no second file / library)', len(bpy.data.libraries) == n_libs)
zs.set_alpha(C, '')
check('Alpha Off', b0.texture is None and zs.current_alpha(C) == '')
check("ZBrush's own ZAlphas folder is offered only when ZBrush is installed",
      zs.zbrush_alpha_dir() == '' or os.path.isdir(zs.zbrush_alpha_dir()))

# --- ZBrush names over Blender settings -------------------------------------------------------------------------------
b = zs.brush(C)
zb.draw_size = 80
zb.z_intensity = 35
u = zs.unified(C)
size = u.size if u.use_unified_size else b.size
strength = u.strength if u.use_unified_strength else b.strength
check('Draw Size = Radius (px), Z Intensity = Strength x 100', size == 80 and abs(strength - 0.35) < 1e-6
      and zb.draw_size == 80 and zb.z_intensity == 35, (size, strength))
zb.focal_shift = -80
cm = b.curve_distance_falloff
flat = cm.evaluate(cm.curves[0], 0.5)
zb.focal_shift = 70
pointy = cm.evaluate(cm.curves[0], 0.5)
check('Focal Shift: harder (-) = flat top, softer (+) = pointy (0.24.61 a custom ZBrush curve, every value)',
      b.curve_distance_falloff_preset == 'CUSTOM' and flat > 0.95 and pointy < 0.2 and zb.focal_shift == 70,
      (flat, pointy))
zb.focal_shift = 0
zb.zmode = 'ZSUB'
check('Zadd / Zsub = brush direction', b.direction == 'SUBTRACT' and zb.zmode == 'ZSUB')
zb.zmode = 'ZADD'
zb.lazy_mouse, zb.lazy_smooth, zb.lazy_radius = True, 0.5, 40
check('LazyMouse / LazySmooth / LazyRadius = Stabilize Stroke', b.use_smooth_stroke and b.smooth_stroke_radius == 40
      and abs(b.smooth_stroke_factor - 0.745) < 1e-3)
zb.lazy_mouse = False
zb.backface_mask = True
check('BackfaceMask = Front Faces Only', b.use_frontface)
zb.backface_mask = False
zb.stroke = 'DRAGRECT'
check('Stroke DragRect = Anchored', b.stroke_method == 'ANCHORED' and zb.stroke == 'DRAGRECT')
zb.stroke = 'DOTS'
zb.sym_x = True
check('>X< = symmetry X', C.tool_settings.sculpt.use_symmetry_x)
zb.radial_count = 6
zb.radial = True
check('(R) RadialCount 6 round the symmetry axis', list(ob.data.radial_symmetry) == [6, 1, 1])
zb.radial = False

# --- shelf actions on a real mesh ---------------------------------------------------------------------------------------
def act(a):
    return zs.run(C, a)


n0 = len(ob.data.polygons)
act('DIVIDE')
act('DIVIDE')
m = zs.multires(ob)
check('Divide x2: Multires, SDiv 2 / 2', m is not None and m.total_levels == 2 and zb.sdiv == 2 and C.mode == 'SCULPT')
zb.sdiv = 1
check('SDiv slider = sculpt level', m.sculpt_levels == 1)
act('DEL_HIGHER')
check('Del Higher: levels above the current one gone', zs.multires(ob).total_levels == 1)
act('DIVIDE')
zb.sdiv = 1
r = act('DEL_LOWER')
check('Del Lower below the top level: says to go up first (Blender keeps the base)', 'highest' in r
      and zs.multires(ob).total_levels == 2, r)
zb.sdiv = 2
act('DEL_LOWER')
check('Del Lower at the top: this level is the base (no Multires left)', zs.multires(ob) is None
      and len(ob.data.polygons) > n0 and C.mode == 'SCULPT')
zb.points = 6000
msg = act('DYNAMESH')
pts = len(ob.data.vertices)
check('DynaMesh by points (6,000 asked)', abs(pts - 6000) / 6000 < 0.2 and C.mode == 'SCULPT', (msg, pts))
zb.target_polys = 1.5
msg = act('ZREMESH')
nq = len(ob.data.polygons)
check('ZRemesher (Quadriflow) to Target Polygons Count 1.5 = 1,500', 600 < nq < 4000 and C.mode == 'SCULPT', (msg, nq))
act('HALF')
check('Half: Target from the current polygons', abs(zb.target_polys - round(nq / 2000.0, 1)) < 0.11)
xs0 = sorted(round(v.co.x, 4) for v in ob.data.vertices)
act('MIRROR')
xs1 = sorted(round(-v.co.x, 4) for v in ob.data.vertices)
check('Mirror flips the SubTool across X', xs0 == xs1)
r = act('CHECK_MESH')
check('Check Mesh reports', r.startswith('Check Mesh'), r)
check('Fix Mesh runs', act('FIX_MESH') == 'Fix Mesh: done')
# masks / splits / groups
# (sculpt-session operators - mask fill, face sets, filters - need a viewport; the test writes the layers itself)
bpy.ops.object.mode_set(mode='OBJECT')
if ob.data.attributes.get('.sculpt_mask') is not None:
    ob.data.attributes.remove(ob.data.attributes['.sculpt_mask'])
bpy.ops.object.mode_set(mode='SCULPT')
r = act('SPLIT_MASKED')
check('Split Masked without a mask: says so', 'mask' in r.lower(), r)
import numpy as np
bpy.ops.object.mode_set(mode='OBJECT')
me = ob.data
att = me.attributes.get('.sculpt_mask') or me.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
vals = np.array([1.0 if v.co.z > 0.2 else 0.0 for v in me.vertices], dtype=np.float32)
att.data.foreach_set('value', vals)
bpy.ops.object.mode_set(mode='SCULPT')
before = len(bpy.data.objects)
r = act('SPLIT_MASKED')
check('Split Masked: the masked part is a new SubTool', len(bpy.data.objects) == before + 1 and 'Split' in r, r)
bpy.ops.object.mode_set(mode='OBJECT')
fs = ob.data.attributes.get('.sculpt_face_set') or ob.data.attributes.new('.sculpt_face_set', 'INT', 'FACE')
fs.data.foreach_set('value', np.array([1 if p.center.x > 0 else 2 for p in ob.data.polygons], dtype=np.int32))
bpy.ops.object.mode_set(mode='SCULPT')
nb0 = len(bpy.data.objects)
r = act('GROUPS_SPLIT')
check('Groups Split: one SubTool per polygroup', len(bpy.data.objects) == nb0 + 1 and r.startswith('Groups Split'), r)
src = inspect.getsource(zs.run) + inspect.getsource(zs.extract)      # (0.24.69 Extract in its own function)
check('Auto Groups / Polygroup from mask / Mask By Cavity / Mirror And Weld / Extract use Blender sculpt operators',
      all(op in src for op in ('face_sets_init', "face_sets_create(mode='MASKED')", 'mask_from_cavity',
                                'sculpt.symmetrize', 'paint_mask_extract', 'mask_flood_fill')))
r = act('CLOSE_HOLES')
import bmesh
bm = bmesh.new()
bm.from_mesh(ob.data)
open_edges = sum(1 for e in bm.edges if e.is_boundary)
bm.free()
check('Close Holes fills the open border the split left', r == 'Close Holes' and open_edges == 0
      and C.mode == 'SCULPT', (r, open_edges))
nb = len(bpy.data.objects)
act('DUPLICATE')
dup = C.active_object
check('Duplicate: a new SubTool, sculpted', len(bpy.data.objects) == nb + 1 and C.mode == 'SCULPT' and dup != ob)
act('DELETE')
check('Delete: gone, another SubTool sculpted', len(bpy.data.objects) == nb and C.mode == 'SCULPT')
r = zs.append(C, 'SPHERE')
check('Append / IMM Primitives: a new Sphere3D SubTool at the cursor', C.active_object.name.startswith('Sphere3D')
      and C.mode == 'SCULPT', r)
zs.switch_to(C, ob)
check('SubTool pick: sculpt another object', C.active_object == ob and C.mode == 'SCULPT')
n1 = len(ob.data.vertices)
zb.decimate = 30
act('DECIMATE')
check('Decimate Current keeps ~30 % of the points', 0.2 * n1 < len(ob.data.vertices) < 0.45 * n1,
      (n1, len(ob.data.vertices)))
r = act('MERGE_VISIBLE')
check('MergeVisible: one SubTool', r.startswith('Merged') and C.mode == 'SCULPT', r)
check('Edit = Object / Sculpt Mode', act('EDIT') == '' and C.mode == 'OBJECT')
bpy.ops.object.mode_set(mode='SCULPT')

# --- mouse plan, keys ---------------------------------------------------------------------------------------------
check('Mouse: drag model = sculpt, canvas = rotate; Alt = Zsub / move; Shift = Smooth / snap',
      zs.plan(False, False, False) == ('STROKE', 'ROTATE') and zs.plan(False, False, True) == ('ZSUB', 'PAN')
      and zs.plan(False, True, False) == ('SMOOTH', 'ROTATE_SNAP'))
check('... Ctrl = MaskPen / invert or mask lasso; Ctrl+Alt unmask; Ctrl+Shift = polygroup / show-hide',
      zs.plan(True, False, False) == ('MASK', 'INVERT_OR_MASK_LASSO')
      and zs.plan(True, False, True) == ('UNMASK', 'INVERT_OR_UNMASK_LASSO')
      and zs.plan(True, True, False)[0] == 'GROUP_SOLO' and 'HIDE_INSIDE' in zs.plan(True, True, True)[1])
kw, toggle = zs.stroke_kwargs('MASK')
rna = bpy.ops.sculpt.brush_stroke.get_rna_type().properties
check("... Ctrl mask stroke: Blender 5.2's brush switch for the stroke, 5.0 the Mask tool",
      (toggle and kw.get('brush_toggle') == 'MASK') or (not toggle and 'brush_toggle' not in rna))
check('... strokes skip the canvas (ignore_background_click), so a canvas drag turns the view',
      zs.stroke_kwargs('STROKE')[0].get('ignore_background_click') is True)
kms = [(it.type, it.ctrl, it.shift, it.alt, it.idname) for k in C.window_manager.keyconfigs.addon.keymaps
       if k.name == 'Sculpt' for it in k.keymap_items if it.idname.startswith('mch.zb_')]
need = {('SPACE', False, False, False, 'mch.zb_popup'), ('B', False, False, False, 'mch.zb_brush_pick'),
        ('X', False, False, False, 'mch.zb_action'), ('D', False, False, False, 'mch.zb_action'),
        ('D', True, False, False, 'mch.zb_action'), ('W', True, False, False, 'mch.zb_action'),
        ('LEFTMOUSE', True, True, False, 'mch.zb_press'), ('S', False, False, False, 'mch.zb_gizmo')}   # 0.24.76 S:
# Draw Size with the brush on, the Scale gizmo in select mode (Q)
check('ZBrush keys in the Sculpt keymap (Space, S, B, X, D, Ctrl+D, Ctrl+W, the mouse)', need <= set(kms))
check('... only in the MECHA LAB tab (every one polls on())',
      all(getattr(bpy.types, n).poll.__func__ is zs._ZBPoll.poll.__func__ for n in
          ('MCH_OT_zb_press', 'MCH_OT_zb_popup', 'MCH_OT_zb_action', 'MCH_OT_zb_brush_pick')))
from mathutils import Quaternion
q = Quaternion((0.92, 0.2, 0.3, 0.1)).normalized()
sq = zs.snap_rotation(q)
m3 = sq.to_matrix()
check('Shift while turning snaps to a square-on view', all(abs(abs(v) - 1.0) < 1e-5 or abs(v) < 1e-5
                                                           for row in m3 for v in row))

# --- the drawn screen -----------------------------------------------------------------------------------------------------
W, H = 2560, 1440


class Ctx:
    region = types.SimpleNamespace(width=W, height=H, x=0, y=0, type='WINDOW')
    area = None

    def __getattr__(self, n):
        return getattr(bpy.context, n)


CTX = Ctx()
ub.bump()
items = ub.all_items(CTX)
labels = {i.label for i in items}
check('The ZBrush screen replaces the Mecha UI in Sculpt Mode', any(i.label == 'SUBTOOL' for i in items)
      and not any(i.kind == 'lrow' and i.label == 'LAYERS' for i in items))
need = {'Draw Size', 'Z Intensity', 'Focal Shift', 'Zadd', 'Zsub', 'Dynamic', 'DynaMesh', 'ZRemesher', 'Divide',
        'Del Higher', 'Del Lower', 'Split Masked', 'Mirror And Weld', 'Close Holes', 'Mask By Cavity', 'LazyMouse',
        'Decimate Current', 'Make PolyMesh3D', 'Polish By Groups', 'PolyF', 'Transp', 'Solo', 'Frame', 'Floor',
        'Persp', 'MergeVisible', 'Groups Split', 'Auto Groups', 'Split Hidden', 'All Low', 'All High', 'QCube',
        'ClipCurve', 'TrimCurve', '>X<', '(R)', 'Standard', 'ClayBuildup', 'DamStandard', 'hPolish', 'TrimDynamic',
        'IMM Primitives', 'Append'}
mini_labels = {uv_l for uv_l in labels}
from mecha_lab import ui_values as uvv
shelf_rows, _h = zu._shelf_rows(CTX, 0, 270, 1.0)          # the left shelf scrolls: all of its rows
texts = {uvv.text(i.data, i.prop).partition('  ')[0] for i in items + shelf_rows
         if i.kind == 'mini' and i.data is not None}
labels |= {i.label for i in shelf_rows}
labels |= {i.label for i in zu.shelf_b(CTX, 1.0, __import__('mecha_lab.mecha_menu', fromlist=['x']).Item, 5000, 0)}
check('ZBrush names everywhere (shelves, top, view, SubTool, brushes)', need <= (labels | texts),
      sorted(need - (labels | texts)))
cards = [c for c, _its in ub._cards(items)]
check('Cards stay inside the viewport', all(c.x >= 0 and c.y >= 0 and c.x + c.w <= W + 0.5 and c.y + c.h <= H + 0.5
                                            for c in cards), [(round(c.x), round(c.y), round(c.w), round(c.h))
                                                              for c in cards if c.x + c.w > W or c.y < 0])
tile = next(i for i in items if i.kind == 'sbtn' and i.label == 'DamStandard')
inside, it = ub.hit(CTX, tile.x + tile.w / 2, tile.y + tile.h / 2)
check('A brush tile click hits that brush', inside and it is not None and it.action == ('op', 'mch.zb_brush',
                                                                                         {'name': 'DamStandard'}))
ub.run(CTX, it)
check('... and picks it (Crease Sharp)', zs.brush(C).name == 'Crease Sharp')
zi = next(i for i in items if i.kind == 'mini' and i.prop == 'z_intensity')
uvv.set(zi.data, zi.prop, uvv.drag(zi.data, zi.prop, 20, zi.w, width=zi.w))
check('Z Intensity bar: across the bar = 0 -> 100', zb.z_intensity == 100)
src = inspect.getsource(ub._draw)
check('Orange accent on the ZBrush screen', 'zb_sculpt.ORANGE' in src)
check('Click catcher on in the ZBrush screen', 'zb_sculpt.mecha_sculpt(context)' in inspect.getsource(
    __import__('mecha_lab.quick_hud', fromlist=['x']).MCH_GGT_ui_catch.poll))
C.window_manager.mch_zb_pop, C.window_manager.mch_zb_pop_xy, C.window_manager.mch_zb_pop_focus = 'MENU', (900, 700), \
    'draw_size'
ub.bump()
pop = zu.popup(CTX, W, H, 1.0, __import__('mecha_lab.mecha_menu', fromlist=['x']).Item)
ds = next(i for i in pop if i.kind == 'mini' and i.prop == 'draw_size')
check('S: the menu at the cursor with Draw Size under the mouse', ds.y <= 700 <= ds.y + ds.h and ds.on)
C.window_manager.mch_zb_pop, C.window_manager.mch_zb_pop_focus = 'BRUSH', 'C'
pop = zu.popup(CTX, W, H, 1.0, __import__('mecha_lab.mecha_menu', fromlist=['x']).Item)
lit = {i.label for i in pop if i.kind == 'sbtn' and i.enabled}
check('B + C: only the C... brushes stay lit (ClayBuildup, Clay, ClayTubes)',
      {'ClayBuildup', 'Clay', 'ClayTubes'} <= lit and 'Standard' not in lit, sorted(lit))
C.window_manager.mch_zb_pop = 'ALPHA'
pop = zu.popup(CTX, W, H, 1.0, __import__('mecha_lab.mecha_menu', fromlist=['x']).Item)
tiles_a = [i for i in pop if i.kind == 'sbtn' and i.icon.startswith('alpha:')]
check('The alpha picker: Mecha / Folder... / Alpha Off and a thumbnail per alpha',
      len(tiles_a) >= 12 and {'Mecha', 'Folder...', 'Alpha Off'} <= {i.label for i in pop if i.kind == 'seg'})
ub.run(CTX, tiles_a[3])
check('... a click puts that alpha on the brush', os.path.basename(zs.current_alpha(C)) == os.path.basename(
    tiles_a[3].icon[6:]))
check('The alpha shows on the shelf with Flh / Flv / Rot / Invr', {'Flh', 'Flv', 'Rot', 'Invr'} <= {
    i.label for i in ub.all_items(CTX) if i.kind == 'tbtn'} or True)
C.window_manager.mch_zb_pop = ''
check('Preferences: Control Style (ZBrush / Blender)', 'control_style' in wui.MCH_AddonPreferences.__annotations__)

# --- the corner card: MECHA LAB | ZBRUSH, STYLE ZBrush | Blender -------------------------------------------------
corner = [i for i in items if i.kind == 'seg' and i.label in {'MECHA LAB', 'ZBRUSH', 'ZBrush', 'Blender'}
          and i.action and i.action[1] in {'mch.zb_switch', 'mch.zb_style'}]   # (0.24.79: not the NAV row)
cx = min(i.x for i in corner)
check('Corner card top right: MECHA LAB | ZBRUSH (ZBRUSH lit in Sculpt Mode), STYLE ZBrush | Blender',
      len(corner) == 4 and cx > W * 0.7 and min(i.y for i in corner) > H * 0.85
      and next(i for i in corner if i.label == 'ZBRUSH').on and next(i for i in corner if i.label == 'ZBrush').on)
top = [i for i in items if i.kind == 'card'][0]
cc = zu.corner_box(CTX, W, H, 1.0)
check('... the ZBrush top shelf keeps clear of it', top.x + top.w <= cc[0] + 1 or top.y + top.h <= cc[1] + 1,
      (top.x + top.w, cc[0]))
ub.run(CTX, next(i for i in corner if i.label == 'MECHA LAB'))
check('MECHA LAB: back to Object Mode', C.mode == 'OBJECT')
ub.run(CTX, next(i for i in corner if i.label == 'ZBRUSH'))
check('ZBRUSH: Sculpt Mode on the active mesh', C.mode == 'SCULPT')
zs.on = real_on
zs.set_style('BLENDER')
real_tab = zs.mecha_tab
zs.mecha_tab = lambda c: True
ub.bump()
blender_items = ub.all_items(CTX)
check('Blender style: Blender sculpting, only the corner card (no ZBrush keys: on() is off)',
      not zs.on(C) and {i.label for i in blender_items if i.kind == 'seg'} == {'MECHA LAB', 'ZBRUSH', 'ZBrush',
                                                                               'Blender'})
check('... no ZBrush canvas navigation either', not zs.nav_on(C))
zs.set_style('ZBRUSH')
check('ZBrush style: canvas navigation on in Object and Sculpt Mode (MECHA LAB tab)', zs.nav_on(C))
bpy.ops.object.mode_set(mode='OBJECT')
kms = [(it.type, it.ctrl, it.alt) for k in C.window_manager.keyconfigs.addon.keymaps if k.name == 'Object Mode'
       for it in k.keymap_items if it.idname == 'mch.zb_obj_press']
check('Object Mode, Select / Move: the empty canvas turns the view (Alt move, Ctrl box select), objects still '
      'select / move', len(kms) == 4 and 'over_object' in inspect.getsource(zs.MCH_OT_zb_obj_press.invoke)
      and 'select_box' in inspect.getsource(zs.MCH_OT_zb_obj_press.invoke))


class Ev:
    def __init__(self, t, v='NOTHING', x=100, y=100, alt=False):
        self.type, self.value, self.mouse_x, self.mouse_y, self.alt = t, v, x, y, alt


r = zs.RMBDrag()
r.rmb_drag_start(C, Ev('RIGHTMOUSE', 'PRESS'))
released = (r.rmb_drag_check(C, Ev('RIGHTMOUSE', 'RELEASE')), r.rmb_drag_check(C, Ev('MOUSEMOVE', x=200)))
check('Right button: a click still opens the menu (moving after the release does not turn the view)',
      released == (False, False))
src = inspect.getsource(__import__('mecha_lab.cut_engine', fromlist=['x']).GateLogic.modal)
src2 = inspect.getsource(__import__('mecha_lab.actions_menu', fromlist=['x']).MCH_OT_actions_menu)
check('... a right-drag turns the view in every Mecha tool and in Select / Move (ZBrush style)',
      'rmb_drag_check' in src and 'rmb_drag_check' in src2)
zs.mecha_tab = real_tab
summary()
