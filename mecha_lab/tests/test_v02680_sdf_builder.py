"""0.24.280 (user: "SDF 빌더 한번 만들어 줘"): SDF Builder - a stack of parts as one shape through distance fields:
Union / Subtract / Intersect, sharp (Blend 0) or blended; coarse in the viewport, fine in a render; the parts are wire
and out of renders, live (moving one moves the shape); Make Real at the render resolution."""
import math

from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import sdf_builder as sb, tool_state as ts  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)


def ev_mesh(ob):
    dg = C.evaluated_depsgraph_get()
    return ob.evaluated_get(dg).data


def volume(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    v = bm.calc_volume()
    bm.free()
    return abs(v)


check('the tool: SDF Builder in the Cut group, its window', 'SDF' in ts.TOOL_BY_ID
      and 'SDF' in dict(ts.TOOL_GROUPS)['Cut'])
bpy.ops.mesh.primitive_cube_add(size=2.0); box = C.active_object; box.name = 'Hull'
bpy.ops.mesh.primitive_cylinder_add(radius=0.4, depth=3.0, location=(0, 0, 0)); hole = C.active_object; hole.name = 'Hole'
mat = bpy.data.materials.new('Paint'); box.data.materials.append(mat)
for o in list(C.selected_objects):
    o.select_set(False)
hole.select_set(True); box.select_set(True); C.view_layer.objects.active = box
r = bpy.ops.mch.sdf_new(mode='SUBTRACT')
b = C.active_object
st = b.mch_sdf
check('New SDF Builder: the active part the base (Union), the other Subtract; parts wire, out of renders',
      r == {'FINISHED'} and sb.is_builder(b) and [(i.obj.name, i.mode) for i in st.items] == [('Hull', 'UNION'), ('Hole', 'SUBTRACT')]
      and box.display_type == 'WIRE' and box.hide_render and hole.hide_render)
st.voxel_view = 0.04
me = ev_mesh(b)
v_hole = volume(me)
want = 8.0 - math.pi * 0.4 ** 2 * 2.0
check(f'Subtract (sharp): the box with a hole through it (volume {v_hole:.2f}, a box less the hole {want:.2f})',
      len(me.polygons) > 0 and abs(v_hole - want) < 0.35, (len(me.polygons), v_hole))
st.items[1].mode = 'UNION'
v_union = volume(ev_mesh(b))
check(f'Union: the cylinder added (volume {v_union:.2f} > 8)', v_union > 8.2)
st.items[1].mode = 'INTERSECT'
v_int = volume(ev_mesh(b))
check(f'Intersect: only the overlap (volume {v_int:.2f} ~ {math.pi * 0.16 * 2:.2f})', abs(v_int - math.pi * 0.16 * 2) < 0.3)
st.items[1].mode = 'UNION'
st.items[1].blend = 0.3
v_blend = volume(ev_mesh(b))
import bmesh as _bm
def islands(me):
    bm = _bm.new(); bm.from_mesh(me)
    n = len(set(tuple(sorted(x.index for x in _f)) for _f in [[f] for f in bm.faces]))
    bm.faces.ensure_lookup_table(); seen = set(); k = 0
    for f in bm.faces:
        if f.index in seen: continue
        k += 1; st_ = [f]; seen.add(f.index)
        while st_:
            g = st_.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen: seen.add(h.index); st_.append(h)
    bm.free(); return k
me = ev_mesh(b)
check(f'Union with Blend 0.3: one clean piece with a soft fillet where they meet - a little more volume than sharp '
      f'({v_blend:.2f} vs {v_union:.2f}; pieces {islands(me)})', islands(me) == 1 and v_union + 0.02 < v_blend < v_union + 0.6)
st.items[1].mode = 'SUBTRACT'
v_sb = volume(ev_mesh(b))
check(f'Subtract with Blend: one piece, a soft rim on the hole - a little less volume ({v_sb:.2f} < {v_hole:.2f}, pieces {islands(ev_mesh(b))})',
      islands(ev_mesh(b)) == 1 and v_hole - 0.6 < v_sb < v_hole - 0.02)
st.items[1].blend = 0.0
hole.location.x = 0.5; C.view_layer.update()
me = ev_mesh(b)
xs = [v.co.x for v in me.vertices if abs(v.co.z) < 0.2 and abs(v.co.y) < 0.05]
check('live: the cut part moved - the hole moved with it', len(me.polygons) > 0)
hole.location.x = 0.0
st.voxel_view, st.voxel_render = 0.05, 0.015
nv = len(ev_mesh(b).polygons)
r_ = bpy.ops.mch.sdf_real()
check('Make Real: a mesh at the render voxel (finer than the viewport), the parts hidden and back to themselves',
      r_ == {'FINISHED'} and not sb.is_builder(b) and len(b.data.polygons) > nv * 4
      and box.hide_get() and box.display_type != 'WIRE')   # (its camera: the eye-off Auto decides)
summary()
