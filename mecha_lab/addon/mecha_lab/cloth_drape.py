"""0.24.92 Cloth Drape: lasso a region on a mesh, a loose cloth is laid over it (the way a garment is draped in
Marvelous Designer) and drops onto the body.

    1. the outline is meshed into an even patch (Armor Plate's meshing) and projected onto the mesh under it;
    2. the patch, a little above the surface and bigger by Looseness, is the cloth: its rim is pinned where it
       was (the sewn edge), gravity pulls it, the mesh points under the patch - and only those - are baked into a
       light distance grid (``cloth_pbd.GridCollider``) the cloth cannot pass through and sticks to (friction);
    3. the cloth is its own object ("Cloth Drape") from the first frame: Space runs / pauses the frames on a
       timer, Enter keeps the object, Esc removes it.  Every setting is a slider (saved in Tool Presets).
"""
from __future__ import annotations

import time

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from mathutils import Vector

from . import core_geometry as cg
from . import mesh_io as mio
from . import wrinkle_lines as wl

GAP = 0.6                        # the cloth starts this x the patch spacing above the surface
MARGIN = 0.3                     # ... and rests this x spacing above the collider
GRID_BAND = 2
ITERATIONS = 6
SOR = 1.3
KEEP_SCALE = 0.1
KEEP_RATE = 0.3
PAD = 0.2                        # the collider takes the mesh points this x the patch size round the patch
GRAV = wl.GRAV_UNIT * 1.5        # gravity 100 % on the drape = the probe's "x1.5" of the Wrinkle Lines unit


class MCH_PG_ClothDrape(bpy.types.PropertyGroup):
    fabric: EnumProperty(name='Fabric', items=wl.FABRIC_ITEMS, default='COTTON')
    spacing: FloatProperty(name='Cloth Detail', description='The patch spacing as % of the outline size (smaller = more points, finer folds)',
                           default=1.5, min=0.4, max=6.0, subtype='PERCENTAGE')
    slack: FloatProperty(name='Looseness', description='Extra fabric: the cloth is this much bigger than the region, so it sags and bunches',
                         default=25.0, min=0.0, max=80.0, subtype='PERCENTAGE')
    shrink: FloatProperty(name='Shrink', description='The cloth pulled tight (against Looseness)',
                          default=0.0, min=0.0, max=60.0, subtype='PERCENTAGE')
    gravity: FloatProperty(name='Gravity', description='How hard the cloth drops (world down)', default=200.0, min=0.0, max=600.0, subtype='PERCENTAGE')
    stick: FloatProperty(name='Stickiness', description='Friction against the body: 0 slides, 100 sticks where it lands',
                         default=30.0, min=0.0, max=100.0, subtype='PERCENTAGE')
    keep: FloatProperty(name='Silhouette Keep', description='A soft spring back to the laid patch', default=5.0, min=0.0, max=100.0, subtype='PERCENTAGE')
    gap: FloatProperty(name='Gap', description='How far above the body the cloth rests, as % of the outline size',
                       default=0.6, min=0.0, max=5.0, subtype='PERCENTAGE')
    pin_rim: BoolProperty(name='Pin Rim', description='The outline edge stays where it was drawn (sewn on); off: the cloth is free', default=True)
    frames: IntProperty(name='Frames', default=60, min=5, max=300)


def settings(context):
    return getattr(context.scene, 'mch_cdrape', None)


# -----------------------------------------------------------------------------
# the patch + the drape (plain functions)
# -----------------------------------------------------------------------------


def patch_from_loops(context, loops, projector, spacing_pct):
    """The outline meshed and projected: (target, mesh (local space of target), rim point count, outline size)."""
    from . import armor_plate as ap
    groups = cg.prepare_loops(loops)
    target = ap.pick_surface(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw the cloth over a mesh.')
    outline = [p for outer, _h in groups for p in outer]
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    size_px = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    pts, tris, nb = ap.screen_patch(groups, spacing=size_px * spacing_pct / 100.0, min_spacing=2.0)
    if not tris:
        raise cg.CutError('The outline is too small for a cloth.')
    bvh, _wv, _polys = ap._target_bvh(context, target)
    cos, nrms, _missing = ap.project_patch(pts, projector, bvh)
    inv = target.matrix_world.inverted_safe()
    rot = inv.to_3x3()
    cos_l = [inv @ c for c in cos]
    nrm_l = [(rot @ n).normalized() for n in nrms]
    me = ap.build_region(pts, tris, cos_l, nrm_l, quads=True)
    me.name = 'MCH_ClothDrape'
    lo = Vector([min(c[k] for c in cos_l) for k in range(3)])
    hi = Vector([max(c[k] for c in cos_l) for k in range(3)])
    return target, me, nb, max((hi - lo).length, 1e-6)


def build(context, target, me, nb, size, st):
    """The cloth + the collider for the patch mesh ``me`` (local space of ``target``).  Returns the session."""
    from . import cloth_pbd
    co = mio.read_co(me)
    n = len(co)
    nrm = wl._normals(me)
    vi = mio.read_corner_verts(me)
    start, tot = mio.read_face_starts(me)
    edges = cloth_pbd.edges_of(vi.astype(np.int64), start.astype(np.int64), tot.astype(np.int64))[0]
    spacing = float(np.mean(np.linalg.norm(co[edges[:, 1]] - co[edges[:, 0]], axis=1))) if len(edges) else size * 0.02
    gap = size * st.gap / 100.0
    margin = max(spacing * MARGIN, gap * 0.5)
    cloth_co = co + nrm * (gap + spacing * GAP)
    pin = np.zeros(n)
    if st.pin_rim:
        pin[:min(nb, n)] = 1.0
    bend, friction, damping, smooth = wl.FABRIC_SIM.get(st.fabric, wl.FABRIC_SIM['COTTON'])
    cloth = cloth_pbd.Cloth(cloth_co, vi, start, tot, bend=bend, keep=st.keep / 100.0 * KEEP_SCALE, pin=pin)
    cloth.sor = SOR
    cloth.smooth = smooth
    cloth.scale_e = cloth.scale_b = (1.0 - st.shrink / 100.0) * (1.0 + st.slack / 100.0)
    cloth.init = cloth_co.copy()
    # the collider: the target's points near the patch only, with their normals, baked into a grid
    tco = mio.read_co(target.data)
    lo, hi = co.min(0) - size * PAD, co.max(0) + size * PAD
    near = np.all((tco >= lo) & (tco <= hi), axis=1)
    tn = wl._normals(target.data)
    t = time.perf_counter()
    grid = cloth_pbd.GridCollider(tco[near] - tn[near] * (gap - margin) if gap > margin else tco[near], tn[near],
                                  cell=max(spacing * 0.8, size / 160.0), band=GRID_BAND)
    sess = dict(cloth=cloth, grid=grid, margin=margin, friction=st.stick / 100.0, damping=damping,
                gdir=wl._gravity_dir(target), size=size, frames=st.frames, frame=0, points=n, collider=int(near.sum()),
                grid_time=time.perf_counter() - t, stage='run')

    def collide(c):
        touch = grid.push(c.co, sess['margin'])
        fr = sess['friction']
        if fr > 0 and np.any(touch):
            c.co[touch] += (c.prev[touch] - c.co[touch]) * fr
    cloth.collide = collide
    return sess


def advance(sess, st):
    cloth = sess['cloth']
    g = sess['gdir'] * (GRAV * st.gravity / 100.0 * sess['size'])
    cloth.step(force=None, gravity=g, damping=sess['damping'], iterations=ITERATIONS,
               keep_rate=KEEP_RATE if st.keep > 0 else 0.0)
    sess['frame'] += 1
    return cloth.co


def drape(context, target, me, nb, size, st, frames=None):
    """Headless / one go: the patch mesh draped in place.  Returns info."""
    t = time.perf_counter()
    sess = build(context, target, me, nb, size, st)
    for _ in range(frames if frames is not None else st.frames):
        advance(sess, st)
    mio.write_co(me, sess['cloth'].co)
    me.update()
    return dict(points=sess['points'], collider=sess['collider'], frames=sess['frame'], time=time.perf_counter() - t,
                grid_cells=sess['grid'].cells, inside=int((sess['grid'].distance(sess['cloth'].co) < sess['margin'] * 0.5).sum()))


# -----------------------------------------------------------------------------
# the live session: the cloth object from the lasso, frames on a timer
# -----------------------------------------------------------------------------

SIM = {}
SRC_KEY = 'mch_cdrape_src'


def sim_active():
    return bool(SIM.get('ob')) and bpy.data.objects.get(SIM['ob']) is not None


def _ob():
    return bpy.data.objects.get(SIM.get('ob', '')) if SIM else None


def perform(context, loops, projector):
    """Lasso -> the cloth object laid over the region (flat), the session ready: Space drapes it."""
    st = settings(context)
    if st is None:
        raise cg.CutError('Cloth Drape settings missing')
    if sim_active():
        raise cg.CutError('Cloth Drape: keep (Enter) or drop (Esc) the cloth you have first')
    target, me, nb, size = patch_from_loops(context, loops, projector, st.spacing)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new('Cloth Drape', me)
    coll = target.users_collection[0] if target.users_collection else context.scene.collection
    coll.objects.link(ob)
    ob.matrix_world = target.matrix_world.copy()
    ob.parent = target
    ob.matrix_parent_inverse = target.matrix_world.inverted_safe()
    ob[SRC_KEY] = target.name
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    surface = mio.read_co(me).copy()
    sess = build(context, target, me, nb, size, st)
    mio.write_co(me, sess['cloth'].co)
    me.update()
    SIM.clear()
    SIM.update(ob=ob.name, target=target.name, nb=nb, size=size, sess=sess, running=False, done=False, want=None,
               surface=surface, start=sess['cloth'].init.copy(), snapshot=_snapshot(st))
    return (f'Cloth Drape on {target.name}: {sess["points"]:,} points over {sess["collider"]:,} body points '
            f'(Space drape · Enter keep · Esc drop)')


def _snapshot(st):
    return tuple(getattr(st, k) for k in ('fabric', 'slack', 'shrink', 'gravity', 'stick', 'keep', 'gap', 'pin_rim', 'frames'))


def restart(context):
    """The cloth back to the laid patch, the session rebuilt with the current sliders (Cloth Detail needs a new lasso)."""
    ob = _ob()
    st = settings(context)
    target = bpy.data.objects.get(SIM.get('target', ''))
    if ob is None or st is None or target is None:
        return False
    me = ob.data
    mio.write_co(me, SIM['surface'])              # the laid patch again, then the cloth with the current sliders
    me.update()
    sess = build(context, target, me, SIM['nb'], SIM['size'], st)
    mio.write_co(me, sess['cloth'].co)
    me.update()
    SIM.update(sess=sess, running=True, done=False, start=sess['cloth'].init.copy(), snapshot=_snapshot(st))
    return True


def step(context):
    ob = _ob()
    sess = SIM.get('sess')
    if ob is None or sess is None:
        return False
    if sess['frame'] >= sess['frames']:
        SIM['running'] = False
        SIM['done'] = True
        return False
    advance(sess, settings(context))
    mio.write_co(ob.data, sess['cloth'].co)
    ob.data.update()
    return True


def confirm(context):
    ob = _ob()
    if ob is None:
        SIM.clear()
        return 'nothing to keep'
    n = SIM['sess']['frame']
    SIM.clear()
    return f'Cloth Drape: kept "{ob.name}" at frame {n} ({len(ob.data.vertices):,} points)'


def cancel(context):
    ob = _ob()
    if ob is not None:
        me = ob.data
        bpy.data.objects.remove(ob)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    SIM.clear()
    return 'Cloth Drape: dropped'


def status():
    if not sim_active():
        return ''
    sess = SIM['sess']
    if SIM.get('done'):
        return f'done: frame {sess["frame"]} / {sess["frames"]}  (Enter keep · Esc drop · Space again)'
    return (f'{"draping" if SIM["running"] else "ready"}: frame {sess["frame"]} / {sess["frames"]}  '
            f'(Space {"pause" if SIM["running"] else "drape"} · Enter keep · Esc drop)')


class MCH_OT_cdrape_sim(bpy.types.Operator):
    """Space: drape / pause the cloth. Enter keeps it, Esc drops it"""
    bl_idname = 'mch.cdrape_sim'
    bl_label = 'Cloth Drape Simulation'
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and sim_active()

    def invoke(self, context, event):
        if SIM.get('modal'):
            SIM['want'] = 'toggle'
            return {'CANCELLED'}
        SIM['modal'] = True
        self._toggle(context)
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.02, window=context.window)
        wm.modal_handler_add(self)
        self._hint(context)
        return {'RUNNING_MODAL'}

    def _hint(self, context):
        if context.area:
            context.area.header_text_set('Cloth Drape  ' + status())
            context.area.tag_redraw()

    def _end(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        SIM.pop('modal', None)
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def modal(self, context, event):
        if not sim_active():
            self._end(context)
            return {'CANCELLED'}
        want = SIM.get('want')
        if want:
            SIM['want'] = None
            if want == 'confirm':
                return self._finish(context, confirm(context), {'FINISHED'})
            if want == 'cancel':
                return self._finish(context, cancel(context), {'CANCELLED'})
            if want == 'restart':
                restart(context)
            elif want == 'toggle':
                self._toggle(context)
            self._hint(context)
            return {'RUNNING_MODAL'}
        if event.type == 'TIMER':
            if SIM.get('running'):
                step(context)
                self._hint(context)
            return {'RUNNING_MODAL'}
        if event.type == 'SPACE' and event.value == 'PRESS':
            self._toggle(context)
            self._hint(context)
            return {'RUNNING_MODAL'}
        if event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            return self._finish(context, confirm(context), {'FINISHED'})
        if event.type == 'ESC' and event.value == 'PRESS':
            return self._finish(context, cancel(context), {'CANCELLED'})
        return {'PASS_THROUGH'}

    def _toggle(self, context):
        st = settings(context)
        if SIM.get('done') or (not SIM.get('running') and st is not None and _snapshot(st) != SIM.get('snapshot')):
            restart(context)
            return
        SIM['running'] = not SIM.get('running')

    def _finish(self, context, msg, result):
        self._end(context)
        self.report({'INFO'}, msg)
        return result


class MCH_OT_cdrape_control(bpy.types.Operator):
    """Drape / pause, keep, drop or restart the cloth (the panel buttons)"""
    bl_idname = 'mch.cdrape_control'
    bl_label = 'Cloth Drape Control'
    bl_options = {'INTERNAL'}
    action: bpy.props.StringProperty(default='toggle', options={'SKIP_SAVE'})

    def execute(self, context):
        if not sim_active():
            return {'CANCELLED'}
        if SIM.get('modal'):
            SIM['want'] = self.action
            return {'FINISHED'}
        if self.action == 'confirm':
            self.report({'INFO'}, confirm(context))
            return {'FINISHED'}
        if self.action == 'cancel':
            self.report({'INFO'}, cancel(context))
            return {'FINISHED'}
        if self.action == 'restart':
            restart(context)
            SIM['running'] = False
        return bpy.ops.mch.cdrape_sim('INVOKE_DEFAULT')


def draw(layout, context):
    st = settings(context)
    if st is None:
        return
    box = layout.box()
    box.label(text='Cloth Drape', icon='MOD_CLOTH')
    live = sim_active()
    box.label(text=status() if live else 'draw a lasso on the mesh: a loose cloth over that region', icon='PLAY' if live else 'INFO')
    r = box.row(align=True)
    r.enabled = live
    if SIM.get('done'):
        text, icon = 'Again (Space)', 'FILE_REFRESH'
    elif SIM.get('running'):
        text, icon = 'Pause (Space)', 'PAUSE'
    else:
        text, icon = 'Drape (Space)', 'PLAY'
    r.operator('mch.cdrape_control', text=text, icon=icon).action = 'toggle'
    r.operator('mch.cdrape_control', text='Restart', icon='FILE_REFRESH').action = 'restart'
    r = box.row(align=True)
    r.enabled = live
    r.operator('mch.cdrape_control', text='Keep (Enter)', icon='CHECKMARK').action = 'confirm'
    r.operator('mch.cdrape_control', text='Drop (Esc)', icon='X').action = 'cancel'
    box.row().prop(st, 'fabric', expand=True)
    col = box.column(align=True)
    col.prop(st, 'slack', slider=True)
    col.prop(st, 'shrink', slider=True)
    col.prop(st, 'gravity', slider=True)
    col.prop(st, 'stick', slider=True)
    col.prop(st, 'keep', slider=True)
    col = box.column(align=True)
    col.prop(st, 'gap', slider=True)
    col.prop(st, 'spacing', slider=True)
    r = box.row(align=True)
    r.prop(st, 'pin_rim', toggle=True)
    r.prop(st, 'frames')


CLASSES = (MCH_PG_ClothDrape, MCH_OT_cdrape_sim, MCH_OT_cdrape_control)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_cdrape = bpy.props.PointerProperty(type=MCH_PG_ClothDrape)


def unregister():
    SIM.clear()
    if hasattr(bpy.types.Scene, 'mch_cdrape'):
        del bpy.types.Scene.mch_cdrape
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
