"""One random feature-combination scenario (run by run_fuzz.py in its own Blender process).

    <python with bpy> scenario.py <seed> <steps>

Builds a random part and runs a random sequence of ZBrush shelf actions (DynaMesh, Decimate, Quad Remesh, Hard
Edges, Divide, Mirror, masks / split / extract, groups, holes ...), mode switches, High Poly and Ctrl+Z / Ctrl+Shift+Z
on it.  Every step is logged (flushed) before it runs, so a crash names the step.  A Python error in a step is
logged as ERROR and the scenario goes on; the process dying is the crash run_fuzz.py looks for.

No bare ``ed.undo_push`` steps: three identical undo steps in a row (nothing changed between them), then any
operator and Ctrl+Z take the headless bpy module down even without the add-on (Blender 5.2 bpy) - a harness
artefact, not a user action.
"""
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from _harness import bpy, fresh  # noqa: E402

import numpy as np  # noqa: E402

import mecha_lab  # noqa: E402
from mecha_lab import zb_sculpt as zs  # noqa: E402

seed, nsteps = int(sys.argv[-2]), int(sys.argv[-1])
rng = random.Random(seed)
mecha_lab.register()
fresh()
C = bpy.context
zs.on = lambda c: getattr(c, 'mode', '') == 'SCULPT'


class _Settings:
    """scene.mch_zb read fresh every time: Ctrl+Z reloads the scene, a reference kept from before points at freed
    memory (setting a value through it took Blender down - a harness bug, the add-on's panels read it fresh)."""

    def __getattr__(self, k):
        return getattr(C.scene.mch_zb, k)

    def __setattr__(self, k, v):
        setattr(C.scene.mch_zb, k, v)


zb = _Settings()


def log(msg):
    sys.stdout.write(msg + '\n')
    sys.stdout.flush()


def part():
    kind = rng.choice(['cube', 'sphere', 'cyl', 'torus', 'monkey', 'boolean', 'thin'])
    s = 10 ** rng.uniform(-1, 0.5)
    if kind == 'cube':
        bpy.ops.mesh.primitive_cube_add(size=2 * s)
    elif kind == 'sphere':
        bpy.ops.mesh.primitive_uv_sphere_add(radius=s, segments=rng.randint(8, 48), ring_count=rng.randint(6, 24))
    elif kind == 'cyl':
        bpy.ops.mesh.primitive_cylinder_add(radius=s, depth=s * rng.uniform(0.2, 3), vertices=rng.randint(6, 64))
    elif kind == 'torus':
        bpy.ops.mesh.primitive_torus_add(major_radius=s, minor_radius=s * rng.uniform(0.1, 0.5))
    elif kind == 'monkey':
        bpy.ops.mesh.primitive_monkey_add(size=2 * s)
    elif kind == 'thin':
        bpy.ops.mesh.primitive_cube_add(size=2 * s)
        C.active_object.scale = (1, 1, rng.uniform(0.01, 0.1))
        bpy.ops.object.transform_apply(scale=True)
    else:
        bpy.ops.mesh.primitive_cube_add(size=2 * s)
        ob = C.active_object
        for _i in range(rng.randint(1, 3)):
            bpy.ops.mesh.primitive_cylinder_add(radius=s * rng.uniform(0.1, 0.5), depth=4 * s,
                                                location=(rng.uniform(-s, s), rng.uniform(-s, s), 0),
                                                rotation=(rng.uniform(0, 3), rng.uniform(0, 3), 0))
            cut = C.active_object
            m = ob.modifiers.new('b', 'BOOLEAN')
            m.object = cut
            m.operation = rng.choice(['DIFFERENCE', 'UNION'])
            m.solver = 'EXACT'
            with C.temp_override(object=ob, active_object=ob):
                bpy.ops.object.modifier_apply(modifier=m.name)
            bpy.data.objects.remove(cut)
        C.view_layer.objects.active = ob
    ob = C.active_object
    ob.name = 'Part'
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob
    return kind


def sculpt():
    if C.mode != 'SCULPT':
        bpy.ops.object.mode_set(mode='SCULPT')


def act(name):
    sculpt()
    r = bpy.ops.mch.zb_action(action=name)
    return r


def random_mask():
    ob = C.active_object
    me = ob.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    axis = rng.randint(0, 2)
    cut = np.median(co[:, axis]) if len(co) else 0.0
    a = me.attributes.get('.sculpt_mask') or me.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
    a.data.foreach_set('value', (co[:, axis] > cut).astype(np.float32))
    me.update()


def faces():
    ob = C.active_object
    return len(ob.data.polygons) if ob is not None and ob.type == 'MESH' else 0


STEPS = {
    'dynamesh': lambda: (setattr(zb, 'points', rng.choice([2000, 8000, 20000, 60000])), act('DYNAMESH')),
    'decimate': lambda: (setattr(zb, 'decimate', rng.choice([2, 10, 50, 86, 96])),
                         setattr(zb, 'dec_even', rng.random() < 0.5), setattr(zb, 'dec_quads', rng.random() < 0.3),
                         setattr(zb, 'dec_mask', rng.random() < 0.3), setattr(zb, 'dec_groups', rng.random() < 0.3),
                         act('DECIMATE')),
    'quad': lambda: (setattr(zb, 'qr_target', rng.choice([0.2, 1.0, 3.0, 6.0])),
                     setattr(zb, 'qr_mode', rng.choice(['MOSTLY', 'ALL'])),
                     setattr(zb, 'qr_angle', math.radians(rng.choice([15, 30, 45]))), act('QUAD_REMESH')),
    'hard_find': lambda: (setattr(zb, 'he_angle', math.radians(rng.choice([20, 30, 50]))),
                          setattr(zb, 'he_merge', rng.random() < 0.7), act('HE_FIND')),
    'hard_sliders': lambda: (setattr(zb, 'he_width', rng.choice([0.0, 0.005, 0.05, 0.5])),
                             setattr(zb, 'he_segments', rng.randint(1, 6)), setattr(zb, 'he_subdiv', rng.randint(0, 2)),
                             setattr(zb, 'he_outer', rng.random() < 0.3), setattr(zb, 'he_client', rng.random() < 0.8),
                             setattr(zb, 'he_normals', rng.random() < 0.2)),
    'hard_apply': lambda: act('HE_APPLY'),
    'hard_clear': lambda: act('HE_CLEAR'),
    'divide': lambda: act('DIVIDE') if faces() < 60000 else 'skip (big)',
    'del_higher': lambda: act('DEL_HIGHER'),
    'del_lower': lambda: act('DEL_LOWER'),
    'mirror': lambda: act('MIRROR'),
    'mirror_weld': lambda: act('MIRROR_WELD'),
    'close_holes': lambda: act('CLOSE_HOLES'),
    'fix_mesh': lambda: act('FIX_MESH'),
    'inflate': lambda: act('INFLATE'),
    'mask': lambda: (sculpt(), random_mask()),
    'mask_invert': lambda: act('MASK_INVERT'),
    'mask_blur': lambda: act('MASK_BLUR'),
    'groups_from_mask': lambda: act('GROUPS_FROM_MASK'),
    'auto_groups': lambda: act('AUTO_GROUPS'),
    'split_masked': lambda: act('SPLIT_MASKED'),
    'extract': lambda: act('EXTRACT'),
    'del_hidden': lambda: act('DEL_HIDDEN'),
    'duplicate': lambda: act('DUPLICATE'),
    'merge_visible': lambda: act('MERGE_VISIBLE'),
    'object_mode': lambda: bpy.ops.object.mode_set(mode='OBJECT'),
    'edit_mode': lambda: bpy.ops.object.mode_set(mode='EDIT'),
    'highpoly': lambda: (bpy.ops.object.mode_set(mode='OBJECT'), bpy.ops.mch.make_highpoly(level=rng.randint(1, 2)))
    if faces() < 30000 else 'skip (big)',
    'undo': lambda: [bpy.ops.ed.undo() for _i in range(rng.randint(1, 3))],
    'redo': lambda: bpy.ops.ed.redo(),
    'edge_mesh': lambda: (setattr(zb, 'em_detail', rng.choice([200, 1000, 3000])),
                          setattr(zb, 'em_auto', rng.random() < 0.5), setattr(zb, 'he_match', rng.random() < 0.7),
                          setattr(zb, 'he_style', rng.choice(['ROUND', 'CHAMFER'])),
                          setattr(zb, 'he_width', rng.choice([0.002, 0.01, 0.05])), act('EDGE_MESH')),
    'he_style': lambda: setattr(zb, 'he_style', rng.choice(['ROUND', 'CHAMFER'])),
    'he_match': lambda: setattr(zb, 'he_match', not zb.he_match),
}
WEIGHTS = {'dynamesh': 3, 'decimate': 4, 'quad': 4, 'hard_find': 3, 'hard_sliders': 3, 'hard_apply': 2, 'undo': 3,
           'redo': 1, 'divide': 2, 'mask': 2, 'edge_mesh': 3}
names = list(STEPS)
weights = [WEIGHTS.get(n, 1) for n in names]
log(f'SCENARIO {seed}: part {part()} ({faces():,} faces)')
bpy.ops.ed.undo_push(message='start')
t_all = time.perf_counter()
for i in range(nsteps):
    name = rng.choices(names, weights)[0]
    if C.active_object is None or C.active_object.type != 'MESH':       # (deleted / split away: pick a mesh)
        meshes = [o for o in C.view_layer.objects if o.type == 'MESH']
        if not meshes:
            log(f'STEP {i} no mesh left - new part {part()}')
            continue
        if C.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except RuntimeError:
                pass
        C.view_layer.objects.active = meshes[0]
    log(f'STEP {i} {name} on {C.active_object.name} ({faces():,} faces, {C.mode})')
    t = time.perf_counter()
    try:
        STEPS[name]()
        ob = C.active_object
        if ob is not None and ob.type == 'MESH' and len(ob.data.vertices):
            co = np.empty(len(ob.data.vertices) * 3, np.float32)
            ob.data.vertices.foreach_get('co', co)
            if not np.isfinite(co).all():
                log(f'BAD {i} {name}: NaN / infinite positions')
        log(f'  ok {time.perf_counter() - t:.2f}s -> {faces():,} faces')
    except Exception as ex:                                               # (a Python error: logged, go on)
        log(f'ERROR {i} {name}: {type(ex).__name__}: {str(ex).splitlines()[0] if str(ex) else ""}')
log(f'DONE {seed} in {time.perf_counter() - t_all:.1f}s')
