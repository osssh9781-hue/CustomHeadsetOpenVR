"""In-Blender self test (GUI diagnostics for reports that headless tests cannot
reproduce: B01 Mirror, B02 Loft, B03 Smart Fuse ...).

Runs the core operators in a TEMPORARY scene, records PASS / FAIL with the
exception text, then deletes the scene and everything created in it.  The
user's scenes, objects and preferences are not modified.  The report is
printed to the system console and copied to the clipboard so it can be pasted
into a bug report.
"""
from __future__ import annotations

import platform
import traceback

import bmesh
import bpy
from mathutils import Quaternion

SCENE_NAME = 'MCH_SelfTest_TEMP'


def _cube(name, size=2.0, loc=(0, 0, 0), coll=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = loc
    return ob


def _curve(name, pts, coll):
    cu = bpy.data.curves.new(name, 'CURVE')
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, co in zip(sp.points, pts):
        p.co = (*co, 1.0)
    ob = bpy.data.objects.new(name, cu)
    coll.objects.link(ob)
    return ob


def _select(context, *obs):
    for o in context.view_layer.objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    context.view_layer.objects.active = obs[0] if obs else None


def _volume(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume()
    bm.free()
    return v


def view_cut_check(C, coll, region, rv3d):
    """Cut / Alt Cut / Split on temporary cubes at the view centre through
    the projection of ``region`` / ``rv3d`` (a real 3D View in the GUI)."""
    from . import core_geometry as cg, cut_engine as ce
    proj = cg.Projector(region, rv3d)
    size = max(rv3d.view_distance * 0.25, 1e-3)
    out = []
    for mode, invert, dx, dy in (('CUT', False, 0.35, 0.35), ('CUT', True, 0.35, 0.35),
                                 ('SPLIT', False, 0.25, 2.0)):
        t = _cube(f'ST_View{mode}', size, tuple(rv3d.view_location), coll)
        C.view_layer.update()
        _select(C, t)
        c = proj.to_screen(t.matrix_world.translation)
        e = proj.to_screen(t.matrix_world.translation + proj.view_dir.orthogonal().normalized() * size * 0.5)
        assert c is not None and e is not None, 'view centre is not projectable'
        r = max(abs(e[0] - c[0]), abs(e[1] - c[1]), 4.0)
        loop = ce.rect_loop((c[0] - r * dx, c[1] - r * dy), (c[0] + r * dx, c[1] + r * dy))
        v0 = _volume(t)
        ce.perform_closed(C, mode, [t], [loop], proj, invert=invert)
        if mode == 'CUT':
            assert 1e-9 < _volume(t) < v0 * (1 - 1e-4), f'{mode} invert={invert}: volume {v0:.4g} -> {_volume(t):.4g}'
        out.append(f'{mode}{" Alt" if invert else ""} ok')
    return (', '.join(out) + f' | {"PERSP" if rv3d.is_perspective else "ORTHO"} {rv3d.view_perspective} '
            f'{region.width}x{region.height}')


def run(context):
    from . import addon_safety, core_geometry as cg, deform_tools, tool_state as ts
    lines = []
    ok_count = [0, 0]

    def step(name, fn):
        ok_count[1] += 1
        try:
            detail = fn()
            if detail is False:
                raise AssertionError('check failed')
            ok_count[0] += 1
            lines.append(f'PASS  {name}' + (f'  ({detail})' if isinstance(detail, str) else ''))
        except Exception as ex:        # report everything, never stop
            lines.append(f'FAIL  {name}: {type(ex).__name__}: {str(ex).splitlines()[0][:200] if str(ex) else ""}')
            tb = traceback.format_exc().strip().splitlines()
            lines.extend('      ' + t for t in tb[-4:])

    mod = __package__
    lines.append(f'Mecha Lab self test | add-on module {mod} | Blender {bpy.app.version_string} | '
                 f'{platform.system()} {platform.release()} | bg={bpy.app.background}')
    lines.append(f'other Mecha Lab copies unloaded at register: {addon_safety.FOREIGN or "none"}')

    # registration state -------------------------------------------------------
    step('sub-panels registered (Mirror / Radial / Surface)',
         lambda: all(hasattr(bpy.types, n) for n in ('MCH_PT_mirror', 'MCH_PT_radial', 'MCH_PT_surface_conform')))
    kc = context.window_manager.keyconfigs.addon
    step('add-on keymap present (Space / V / B / C)', lambda: kc is None or any(
        ki.idname == 'mch.space_tools' for km in kc.keymaps for ki in km.keymap_items))
    step('effective tool readable', lambda: ts.effective_tool(context))

    window = context.window
    old_scene = context.scene
    pools = (bpy.data.meshes, bpy.data.curves, bpy.data.lattices, bpy.data.node_groups, bpy.data.collections)
    before_colls = set(bpy.data.collections)
    before = [set(pool) for pool in pools]
    scene = bpy.data.scenes.new(SCENE_NAME)
    override = None
    try:
        if window is not None:
            window.scene = scene          # GUI: the temporary scene is shown while the test runs
        else:                             # background: context override instead
            override = bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0])
            override.__enter__()
        ctx_scene = bpy.context.scene
        coll = ctx_scene.collection
        vl = bpy.context.view_layer
        C = bpy.context

        def mirror():
            a, b = _cube('ST_M1', 1.0, (2, 0, 0), coll), _cube('ST_M2', 1.0, (4, 0, 0), coll)
            _select(C, a, b)
            p = ctx_scene.mch_mirror
            p.space, p.center, p.x, p.y, p.z, p.merge = 'WORLD', 'ORIGIN', True, False, False, False
            assert bpy.ops.mch.mesh_mirror() == {'FINISHED'}, 'create'
            assert bpy.ops.mch.mesh_mirror_apply() == {'FINISHED'}, 'apply'
            assert len(a.data.vertices) == 16 and len(b.data.vertices) == 16, 'geometry'
            bpy.ops.mch.mesh_mirror()
            assert bpy.ops.mch.mesh_mirror_remove() == {'FINISHED'}, 'remove'
            return 'create / apply / remove on 2 meshes'
        step('B01 Mirror', mirror)

        def loft():
            c1 = _curve('ST_C1', [(0, 0, 0), (1, 0, 0), (2, 0, 0)], coll)
            c2 = _curve('ST_C2', [(0, 1, 0.3), (1, 1, 0.5), (2, 1, 0.3)], coll)
            vl.update()
            _select(C, c1, c2)
            r = bpy.ops.mch.loft_create()
            assert r == {'FINISHED'}, f'loft_create {r}'
            r = bpy.ops.mch.loft_apply()
            assert r == {'FINISHED'}, f'loft_apply {r}'
            return 'create + apply'
        step('B02 Loft', loft)

        def fuse():
            for i in range(3):
                a = _cube(f'ST_FA{i}', 2.0, (10 + i * 5, 0, 0), coll)
                b = _cube(f'ST_FB{i}', 1.2, (10.9 + i * 5, 0.3, 0.2), coll)
                vl.update()
                _select(C, a, b)
                r = bpy.ops.mch.smart_fuse()
                assert r == {'FINISHED'}, f'run {i + 1}: create {r}'
                r = bpy.ops.mch.smart_fuse_confirm()
                assert r == {'FINISHED'}, f'run {i + 1}: confirm {r}'
            return '3 consecutive runs'
        step('B03 Smart Fuse x3', fuse)

        def boolean():
            a = _cube('ST_BA', 2.0, (30, 0, 0), coll)
            b = _cube('ST_BB', 2.0, (30, 0, 4), coll)
            c = _cube('ST_BC', 1.0, (30.8, 0.8, 2), coll)
            c.scale = (1, 1, 6)
            vl.update()
            _select(C, c, a, b)
            ctx_scene.mch_settings.keep_cutter = True
            assert bpy.ops.mch.boolean(operation='DIFFERENCE') == {'FINISHED'}
            assert _volume(a) < 8.0 - 1e-3 and _volume(b) < 8.0 - 1e-3, 'both targets cut'
            return 'active = cutter, 2 targets'
        step('Boolean (active = cutter)', boolean)

        def cut():
            from . import cut_engine as ce
            t = _cube('ST_Cut', 2.0, (0, 0, 0), coll)
            vl.update()
            _select(C, t)
            proj = cg.OrthoProjector(Quaternion())
            ce.perform_closed(C, 'CUT', [t], [ce.rect_loop((450, 450), (550, 550))], proj)
            assert _volume(t) < 8.0 - 1e-3
            return 'rectangle cut'
        step('Cut engine', cut)

        def cut_real_view():
            # GUI only: Cut / Alt Cut / Split through the projection of a real
            # 3D View (the path interactive strokes use), on temporary cubes
            # placed at the view centre.
            screen = getattr(window, 'screen', None) if window is not None else None
            area = next((a for a in screen.areas if a.type == 'VIEW_3D'), None) if screen else None
            if area is None:
                return 'skipped: no 3D View (background run)'
            region = next(r for r in area.regions if r.type == 'WINDOW')
            rv3d = area.spaces.active.region_3d
            return view_cut_check(C, coll, region, rv3d)
        step('Cut / Alt Cut / Split through the real 3D View projection', cut_real_view)

        def base():
            from . import base_mesh, cut_engine as ce
            proj = cg.OrthoProjector(Quaternion())
            base_mesh.perform_base(C, [ce.rect_loop((300, 300), (380, 380))], proj)
            return C.view_layer.objects.active.name
        step('Base Mesh', base)

        def deform():
            t = _cube('ST_Def', 2.0, (0, -10, 0), coll)
            vl.update()
            _select(C, t)
            assert bpy.ops.mch.deform_lattice(edit=False) == {'FINISHED'}
            lo = C.view_layer.objects.active
            lo.mch_deform.res_x = 5
            assert lo.data.points_u == 5
            return 'lattice + resolution'
        step('Deform', deform)

        def extract_armor():
            t = _cube('ST_Ex', 2.0, (0, -20, 0), coll)
            vl.update()
            _select(C, t)
            bpy.ops.object.mode_set(mode='EDIT')
            bm = bmesh.from_edit_mesh(t.data)
            for f in bm.faces:
                f.select = f.normal.z > 0.9
            bmesh.update_edit_mesh(t.data)
            assert bpy.ops.mch.face_extract(mode='ARMOR', stay_in_edit=False) == {'FINISHED'}, 'extract'
            part = C.view_layer.objects.active
            part.mch_extract.cl_preset = 'Y'
            part.mch_extract.n_thickness = 0.3
            assert len(part.data.polygons) > 0, 'part empty'
            assert bpy.ops.mch.molding_create(source='PART') == {'FINISHED'}, 'molding'
            return 'armor Y + molding'
        step('Face Extract / Armor / Molding', extract_armor)

        def hollow_cable():
            t = _cube('ST_Ho', 2.0, (0, -25, 0), coll)
            vl.update()
            _select(C, t)
            assert bpy.ops.mch.hollow() == {'FINISHED'}, 'hollow'
            from . import cable
            ob = cable.create_cable(C, (0, -25, 1), (0, 0, 1), (3, -25, 1), (0, 0, 1))
            assert len(ob.data.splines) == 1, 'cable'
            return 'shell + cable'
        step('Hollow / Cable', hollow_cable)
    finally:
        if override is not None:
            override.__exit__(None, None, None)
        if window is not None:
            window.scene = old_scene
        # delete everything created in the temporary scene
        # parts collections are linked under the temporary scene, so its objects cover them
        for ob in list(scene.objects):
            data = ob.data
            bpy.data.objects.remove(ob)
            if data is not None and data.users == 0:
                try:
                    if isinstance(data, bpy.types.Mesh):
                        bpy.data.meshes.remove(data)
                    elif isinstance(data, bpy.types.Curve):
                        bpy.data.curves.remove(data)
                    elif isinstance(data, bpy.types.Lattice):
                        bpy.data.lattices.remove(data)
                except (ReferenceError, RuntimeError):
                    pass
        bpy.data.scenes.remove(scene)
        for pool, old in zip(pools, before):     # leftovers of the test only (never user data)
            for block in [b for b in pool if b not in old and b.users == 0]:
                pool.remove(block)
    lines.append(f'RESULT {ok_count[0]}/{ok_count[1]} passed')
    return '\n'.join(lines), ok_count[0] == ok_count[1]


class MCH_OT_self_test(bpy.types.Operator):
    bl_idname = 'mch.self_test'
    bl_label = 'Run Mecha Lab Self Test'
    bl_description = ('Runs Mirror / Loft / Smart Fuse / Boolean / Cut / Base Mesh / Deform in a temporary scene '
                      '(deleted afterwards) and copies the report to the clipboard for a bug report')
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        report, ok = run(context)
        print(report)
        try:
            context.window_manager.clipboard = report
        except (AttributeError, RuntimeError):
            pass
        self.report({'INFO' if ok else 'WARNING'},
                    report.splitlines()[-1] + ' - full report copied to the clipboard (and system console)')
        return {'FINISHED'}


CLASSES = (MCH_OT_self_test,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
