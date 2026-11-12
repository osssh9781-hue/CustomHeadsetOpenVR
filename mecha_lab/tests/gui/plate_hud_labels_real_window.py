"""Real window (0.24.146, user: "이거 글씨 안 뜨게 해 줘" + a screenshot: an Armor Plate's HUD names floating in the Cut tool):
a live Armor Plate selected - with the Armor Plate tool its HUD words are drawn (with its buttons); in the Cut tool not."""
import os
import sys

import bpy
import blf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'addon'))
import mecha_lab  # noqa: E402
from mathutils import Quaternion  # noqa: E402

OUT = sys.argv[-1]
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')


def log(*a):
    LOG.write(' '.join(str(x) for x in a) + '\n')
    LOG.flush()


mecha_lab.register()
C = bpy.context
DRAWN = []
_real = blf.draw


def _spy(fid, text, *a):
    DRAWN.append(text)
    return _real(fid, text, *a)


blf.draw = _spy


def view3d():
    for w in C.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                return w, a, next(r for r in a.regions if r.type == 'WINDOW')
    return None, None, None


def redraws(n=6):
    w, a, r = view3d()
    for _i in range(n):
        a.tag_redraw()
        yield 0.25


def flow():
    from mecha_lab import armor_plate as ap, core_geometry as cg
    res = {}
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        if ws is None:
            bpy.ops.mch.workspace_open()
            ws = next((x for x in bpy.data.workspaces if x.name.startswith('MECHA LAB')), None)
        w.workspace = ws
    yield 2.0
    w, a, r = view3d()
    with C.temp_override(window=w, area=a, region=r):
        for o in list(C.scene.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=2.0, segments=48, ring_count=24)
        body = C.active_object
        ap.perform_plate(C, [[(420, 420), (580, 420), (580, 580), (420, 580)]], cg.OrthoProjector(Quaternion()))
        plate = C.active_object
        a.spaces.active.show_region_ui = False
        rv = a.spaces.active.region_3d
        rv.view_distance = 9.0
        bpy.ops.mch.bar_tool(tool='PLATE')
    yield 1.0
    DRAWN.clear()
    yield from redraws()
    in_plate = list(DRAWN)
    with C.temp_override(window=w, area=a, region=r):
        bpy.ops.mch.bar_tool(tool='CUT')
        C.view_layer.objects.active = plate
        plate.select_set(True)
    yield 1.0
    DRAWN.clear()
    yield from redraws()
    in_cut = list(DRAWN)
    os.system(f'import -window root "{os.path.join(OUT, "cut_tool.png")}"')
    log('plate tool words', sorted(set(in_plate))[:20])
    log('cut tool words', sorted(set(in_cut))[:20])
    res['the Armor Plate tool: its HUD words drawn (Apply / Remove)'] = 'Remove' in in_plate and 'Apply' in in_plate
    res['the Cut tool, the plate still selected and live: none of them'] = not ({'Remove', 'Apply'} & set(in_cut)) and not any(
        t.startswith('Rims:') or t.startswith('Face Size') for t in in_cut)
    for k, v in res.items():
        log(('PASS ' if v else 'FAIL ') + k)
    log(f'{sum(res.values())}/{len(res)} passed')
    bpy.ops.wm.quit_blender()


gen = None


def run():
    global gen
    try:
        if gen is None:
            gen = flow()
        return next(gen)
    except StopIteration:
        return None
    except Exception as ex:
        import traceback
        traceback.print_exc()
        log('ERROR', repr(ex))
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(run, first_interval=2.0)
