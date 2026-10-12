"""PNG -> vector Custom Cut Shape regression.

Synthetic masks cover the cases from docs/05: concave cross, ring, vent grid
(25 holes), 1 px slots, diagonal-only pixel contacts (the v0.5.9 bow-tie
cause), island inside a hole, specks, staircase diagonal.  Each mask is run
through the new vectorizer and cut into a cube (through + surface pocket);
the v0.5.9 pipeline is run on the same masks for comparison.
"""
import importlib.util
import json
import math
import os
import sys

from _harness import bpy, check, cube, fresh, non_manifold, summary, volume, ADDON_PARENT
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, cut_presets as cp

N = 64
TOP = cg.OrthoProjector(Quaternion())
C = bpy.context


def blank():
    return [0] * (N * N)


def put(m, x, y, v=1):
    if 0 <= x < N and 0 <= y < N:
        m[y * N + x] = v


def rect(m, x0, y0, x1, y1, v=1):
    for y in range(y0, y1):
        for x in range(x0, x1):
            put(m, x, y, v)


def disc(m, cx, cy, r, v=1):
    for y in range(N):
        for x in range(N):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                put(m, x, y, v)


def masks():
    out = {}
    m = blank(); rect(m, 26, 6, 38, 58); rect(m, 6, 26, 58, 38); out['cross'] = m
    m = blank(); disc(m, 32, 32, 26); disc(m, 32, 32, 14, 0); out['ring'] = m
    m = blank(); rect(m, 4, 4, 60, 60)
    for i in range(5):
        for j in range(5):
            rect(m, 8 + i * 10, 8 + j * 10, 14 + i * 10, 14 + j * 10, 0)
    out['vent_grid_25'] = m
    m = blank(); rect(m, 4, 4, 60, 60)
    for i in range(6):
        rect(m, 10 + i * 8, 10, 11 + i * 8, 54, 0)           # 1 px slots
    out['thin_slots'] = m
    m = blank()
    for i in range(20):
        put(m, 10 + i, 10 + i)                                  # pixels touching only at corners
    rect(m, 40, 40, 50, 50); put(m, 50, 50); put(m, 51, 51)
    out['diagonal_touch'] = m
    m = blank()
    for y in range(16, 48):
        for x in range(16, 48):
            if (x + y) % 2 == 0:
                put(m, x, y)                                    # full checkerboard: every pixel a saddle
    out['checker_saddles'] = m
    m = blank(); disc(m, 32, 32, 28); disc(m, 32, 32, 18, 0); disc(m, 32, 32, 8); out['island_in_hole'] = m
    m = blank(); disc(m, 32, 32, 20)
    import random
    rnd = random.Random(5)
    for _ in range(60):
        put(m, rnd.randrange(N), rnd.randrange(N), rnd.randrange(2))
    out['noisy_disc'] = m
    m = blank()
    for i in range(48):
        rect(m, 8 + i, 8 + i // 2, 10 + i, 12 + i // 2)       # staircase band
    out['staircase'] = m
    return out


def load_old():
    path = os.path.join(os.path.dirname(ADDON_PARENT), 'reference', 'RELEASE_v0_5_9', 'mecha_lab', 'cut_presets.py')
    spec = importlib.util.spec_from_file_location('old_cut_presets', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def shared_vertices(loops):
    seen = {}
    for li, lp in enumerate(loops):
        for p in lp:
            key = (round(p[0], 6), round(p[1], 6))
            seen.setdefault(key, set()).add(li)
    return sum(1 for v in seen.values() if len(v) > 1)


fresh()
mecha_lab.register()
old = load_old()
old_results = {}
for name, mask in masks().items():
    # --- new pipeline -----------------------------------------------------
    try:
        loops, tol, sm = cp.vectorize_mask(mask, N, N, 0.8, 1, 4 if name == 'noisy_disc' else 0)
        ok = True
    except Exception as ex:
        ok = False
        loops = []
        print('vectorize error', name, ex)
    check(f'{name}: vectorized', ok and loops, f'{len(loops)} loops')
    if not loops:
        continue
    check(f'{name}: no self/mutual intersections', not cg.find_intersections(loops))
    check(f'{name}: no vertex shared between loops', shared_vertices(loops) == 0)
    for depth_mode in ('THROUGH', 'SURFACE'):
        fresh_scene = bpy.data.objects.get('Target')
        if fresh_scene:
            bpy.data.objects.remove(fresh_scene, do_unlink=True)
        C.scene.mch_cut.depth_mode = depth_mode
        C.scene.mch_cut.depth = 0.3
        C.scene.mch_settings.auto_apply = True
        t = cube('Target')
        v0 = volume(t)
        screen = ce.custom_loops(loops, (500, 500), 80, 0.0)
        try:
            ce.perform_closed(C, 'CUT', [t], screen, TOP)
            res = 'ok'
        except cg.CutError as ex:
            res = str(ex)
        check(f'{name} [{depth_mode}]: cut applied', res == 'ok', res)
        check(f'{name} [{depth_mode}]: result manifold', non_manifold(t) == 0, non_manifold(t))
        check(f'{name} [{depth_mode}]: volume reduced', volume(t) < v0)
    # --- v0.5.9 pipeline (for the report only) -------------------------------
    bpy.data.objects.remove(bpy.data.objects['Target'], do_unlink=True)
    t = cube('Target')
    try:
        old_loops = old.vectorize_mask(mask, N, N, 0.8)
        shared = shared_vertices(old_loops)
        old.apply_stamp(C, t, old_loops, Vector((0, 0, 1)), Quaternion(), 1.6, 0.3, True)
        old_results[name] = f'ok (shared vertices {shared}, non-manifold {non_manifold(t)})'
    except Exception as ex:
        old_results[name] = f'FAILED: {ex}'
    bpy.data.objects.remove(bpy.data.objects['Target'], do_unlink=True)
    for o in [o for o in bpy.data.objects if o.name.startswith('MCH_PNG')]:
        bpy.data.objects.remove(o, do_unlink=True)

# Full import path with a real PNG on disk (temp config dir) + schema upgrade
img = bpy.data.images.new('mch_test', 64, 64, alpha=True)
px = [0.0] * (64 * 64 * 4)
ring = masks()['ring']
for i, v in enumerate(ring):
    px[i * 4:i * 4 + 4] = [1.0, 1.0, 1.0, 1.0] if v else [0.0, 0.0, 0.0, 0.0]
img.pixels = px
png = os.path.join(cp.preset_folder(), '..', 'ring_src.png')
img.filepath_raw = png
img.file_format = 'PNG'
img.save()
out = cp.import_png(png, 'Ring Test', 'ALPHA', 0.5, False, 0.8, 1, 4)
rec = json.loads(out.read_text())
check('import_png wrote schema 2 preset', rec['schema'] == 2 and len(rec['loops']) == 2)
check('preset listed', any(stem == out.stem for stem, _ in cp.list_presets()))
check('load_loops returns valid loops', not cg.find_intersections(cp.load_loops(out.stem)))
# Simulate a v0.5.9 schema-1 file with touching loops -> auto re-vectorized from source PNG
bad = dict(rec)
bad['schema'] = 1
bad['loops'] = [[[0, 0], [0.2, 0], [0.2, 0.2], [0, 0.2]], [[0.2, 0.2], [0.4, 0.2], [0.4, 0.4], [0.2, 0.4]],
                [[0.1, -0.1], [0.3, 0.3], [0.3, -0.1], [0.1, 0.3]]]
out.write_text(json.dumps(bad))
upgraded = cp.load_loops(out.stem)
check('schema-1 invalid preset upgraded from stored PNG', not cg.find_intersections(upgraded) and
      json.loads(out.read_text())['schema'] == 2)

print('\nv0.5.9 pipeline on the same masks (reference, not a pass/fail):')
for k, v in old_results.items():
    print(f'  {k:<18} {v}')
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
