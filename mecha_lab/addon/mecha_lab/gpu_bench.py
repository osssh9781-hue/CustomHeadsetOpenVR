"""0.24.346 GPU Bake check (user's RTX 5090): the same AO bakes with the GPU off and on - the time each took and how
far apart the maps are.  Run from the Bake settings ("Check GPU Bake") or Blender's Python console:
``bpy.ops.mch.gpu_bake_check()`` - the result in the Info report and the System Console, nothing in the file kept."""
from __future__ import annotations

import time

import bpy
import numpy as np


def _grooved_box(context, name, loc, cuts=12):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=loc)
    ob = context.active_object
    ob.name = name
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=cuts)
    bpy.ops.mesh.inset(thickness=0.03, depth=-0.04, use_individual=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob


def run(context, res=2048):
    """[(what, CPU seconds, GPU seconds, used the GPU, mean difference)]; the test objects removed after."""
    from . import bake_maps as bm, gpu_bake as gb, mech_shader as ms
    S = context.scene
    st = bm.settings(context)
    keep = {k: getattr(st, k) for k in ('res', 'own', 'own_one', 'fast', 'gpu', 'save', 'use_on_low', 'normal', 'ao',
                                        'color', 'rough', 'metal', 'curv', 'height', 'emit', 'ray')}
    sel = list(context.selected_objects)
    act = context.view_layer.objects.active
    made = []
    out = []
    try:
        if not gb.available():
            return [('GPU not available: ' + gb.why_not(), 0, 0, False, 0)]
        st.res = str(res)
        st.fast, st.save, st.use_on_low = True, False, False
        st.normal = st.color = st.rough = st.metal = st.curv = st.height = st.emit = False
        st.ao = True
        # 1) high poly -> low (AO from the high)
        hi = _grooved_box(context, 'MCH GPU Check High', (50.0, 0.0, 0.0))
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(50.0, 0.0, 0.0))
        lo = context.active_object
        lo.name = 'MCH GPU Check Low'
        made += [hi, lo]
        st.own, st.ray = False, 4.0
        maps = {}
        for g in (False, True):
            st.gpu = g
            for o in S.objects:
                o.select_set(False)
            t0 = time.time()
            info = bm.bake_pair(context, lo, [hi], st)
            maps[g] = (np.array(bpy.data.images[f'{lo.name}_AO'].pixels[:], np.float32), time.time() - t0,
                       bool(info.get('fast_gpu')))
        out.append(('High Poly AO', maps[False][1], maps[True][1], maps[True][2],
                    float(np.abs(maps[False][0] - maps[True][0]).mean())))
        # 2) No High Poly: a Mech Shader part (AO map + the material's AO / Bevel nodes)
        own = _grooved_box(context, 'MCH GPU Check Mech', (56.0, 0.0, 0.0), cuts=6)
        made.append(own)
        ms.assign(context, [own], ms.new_material('BATTLE'))
        st.own, st.own_one = True, False
        st.color = True
        maps = {}
        for g in (False, True):
            st.gpu = g
            for o in S.objects:
                o.select_set(False)
            own.select_set(True)
            context.view_layer.objects.active = own
            t0 = time.time()
            info = bm.bake_pair(context, own, [], st)
            maps[g] = (np.array(bpy.data.images[f'{own.name}_AO'].pixels[:], np.float32), time.time() - t0,
                       bool(info.get('fast_gpu')))
        from . import fast_shade as F
        out.append((f'No High Poly (Mech) AO + Color (node maths on the GPU: {F.GPU_MATS[0]} material)',
                    maps[False][1], maps[True][1], maps[True][2],
                    float(np.abs(maps[False][0] - maps[True][0]).mean())))
    finally:
        for o in made:
            mats = [s.material for s in o.material_slots if s.material]
            me = o.data
            for img in list(bpy.data.images):
                if img.name.startswith(o.name + '_'):
                    bpy.data.images.remove(img)
            bpy.data.objects.remove(o)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
            for m in mats:
                if m.users == 0:
                    bpy.data.materials.remove(m)
        for k, v in keep.items():
            try:
                setattr(st, k, v)
            except (TypeError, AttributeError):
                pass
        for o in sel:
            try:
                o.select_set(True)
            except ReferenceError:
                pass
        if act is not None:
            try:
                context.view_layer.objects.active = act
            except ReferenceError:
                pass
    return out


class MCH_OT_gpu_bake_check(bpy.types.Operator):
    """Bake the same AO maps with the GPU off and on (test objects, removed after) - how long each took, and that the
    maps are the same.  The result in the Info report and the System Console"""
    bl_idname = 'mch.gpu_bake_check'
    bl_label = 'Check GPU Bake'
    bl_options = {'REGISTER'}

    res: bpy.props.EnumProperty(name='Size', items=[('1024', '1K', ''), ('2048', '2K', ''), ('4096', '4K', '')],
                                default='2048')

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        rows = run(context, int(self.res))
        lines = []
        for what, tc, tg, used, diff in rows:
            if not tc and not tg:
                lines.append(what)
                continue
            lines.append(f'{what}: CPU {tc:.1f} s, GPU {tg:.1f} s ({tc / max(tg, 1e-6):.1f}x)'
                         + ('' if used else ' [the GPU was not used]') + f', difference {diff:.4f}')
        for ln in lines:
            print('Mecha Lab GPU check:', ln)
        self.report({'INFO'}, ' | '.join(lines))
        return {'FINISHED'}


class MCH_OT_gpu_cloth_check(bpy.types.Operator):
    """0.24.359 GPU cloth TEST: the same falling sheet on the CPU (the C engine) and on the graphics card, three sizes
    - how long each took.  Nothing is added to the file.  The result in the Info report and the System Console"""
    bl_idname = 'mch.gpu_cloth_check'
    bl_label = 'Check GPU Cloth'
    bl_options = {'REGISTER'}

    def execute(self, context):
        from . import gpu_cloth as gc
        if not gc.available():
            self.report({'WARNING'}, 'GPU cloth: no GPU here (' + (gc.why_not() or 'no context') + ')')
            return {'CANCELLED'}
        lines = []
        for pts, tc, tg, used, diff, _sz in gc.bench(sizes=(100, 250, 500), frames=30):
            lines.append(f'{pts:,} points: CPU {tc:.2f} s, GPU {tg:.2f} s ({tc / max(tg, 1e-6):.1f}x)'
                         + ('' if used else ' [GPU failed: ' + gc.why_not() + ']'))
        for ln in lines:
            print('Mecha Lab GPU cloth check (30 frames):', ln)
        self.report({'INFO'}, 'GPU cloth (30 frames): ' + ' | '.join(lines))
        return {'FINISHED'}


CLASSES = (MCH_OT_gpu_bake_check, MCH_OT_gpu_cloth_check)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
