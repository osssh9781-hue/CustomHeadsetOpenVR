"""0.24.86 The background worker: a second Blender (or bpy python) that runs one heavy action on one mesh.

    worker <addon parent dir> <job json>
    job = {"kind": "QUAD_REMESH" | "REFIX", "in": "<.blend with the mesh>", "mesh": "<mesh name>", "out": "<.blend>",
           "params": {...}}

It loads the mesh, builds an object for it, runs the action exactly as the add-on would, writes the result mesh to
``out`` (library write, the mesh renamed to the result name) and prints one line ``MCH_RESULT <json>``."""
import json
import os
import sys
import types


def main():
    argv = sys.argv
    if '--' in argv:
        argv = argv[argv.index('--') + 1:]
    else:
        argv = argv[1:]
    parent, job = argv[0], json.loads(argv[1])
    if parent not in sys.path:
        sys.path.insert(0, parent)
    import bpy
    import mecha_lab
    try:
        mecha_lab.register()
    except Exception:
        pass
    from mecha_lab import quad_field as qf, refix, zb_sculpt as zs
    with bpy.data.libraries.load(job['in'], link=False) as (src, dst):
        dst.meshes = [job['mesh']]
    me = dst.meshes[0]
    ob = bpy.data.objects.new('MCH_BG', me)
    bpy.context.scene.collection.objects.link(ob)
    for o in bpy.context.view_layer.objects:
        o.select_set(o is ob)
    bpy.context.view_layer.objects.active = ob
    p = types.SimpleNamespace(**job.get('params', {}))
    kind = job['kind']
    if kind == 'QUAD_REMESH':
        msg = qf.remesh_object(ob, int(p.target), all_quads=bool(p.all_quads), crease_deg=float(p.crease_deg))
        zs.shade_result(ob, p)
    elif kind == 'REFIX':
        try:
            msg = refix.run(bpy.context, ob, p)
        except RuntimeError as ex:
            msg = 'Re-Fix: ' + str(ex)
    else:
        msg = 'unknown job'
    res = ob.data
    res.name = job['mesh'] + '_bg'
    res.use_fake_user = True
    bpy.data.libraries.write(job['out'], {res}, fake_user=True)
    print('MCH_RESULT ' + json.dumps({'message': msg, 'faces': len(res.polygons), 'name': res.name}), flush=True)


if __name__ == '__main__':
    main()
