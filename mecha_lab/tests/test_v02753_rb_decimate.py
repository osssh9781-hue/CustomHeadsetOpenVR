"""0.24.353 Retopo + Bake: Decimate method (user: "베이크 할 때도 데시메이트로 하면 잘 되더라", "쿼드 허용도 ...
리토포 베이크에 데시메이트도 넣고 그거도 어제 만든 거처럼 프로젝트도"): the low is the high decimated (Mecha Lab's
engine), with Allow Quads its triangle pairs joined into quads, then snapped onto the high (Project to Original);
then 2 Bake bakes it as usual.  Quad / Wrap unchanged."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import retopo_bake as rb, bake_maps as bm, retopo_project as rp

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
check('the Method has Decimate beside Quad / Wrap, Allow Quads on by default',
      'DECIMATE' in [i.identifier for i in S.bl_rna.properties['mch_rb_method'].enum_items] and S.mch_rb_quads)
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=1.0)
high = C.active_object
high.name = 'Head'
tex = bpy.data.textures.new('bumps', 'CLOUDS'); tex.noise_scale = 0.18
d = high.modifiers.new('D', 'DISPLACE'); d.texture = tex; d.strength = 0.12
nh = len(high.data.polygons)
st = bm.settings(C); st.res = '512'; st.ao_samples = 8; st.save = False


def gap(low):
    tree = rp._high_tree(C, [high])
    M = low.matrix_world
    return max(tree.find_nearest(M @ v.co)[3] for v in low.data.vertices)


S.mch_rb_method, S.mch_rb_faces, S.mch_rb_quads = 'DECIMATE', 2000, True
r = bpy.ops.mch.retopo_make()
low = C.active_object
nf = len(low.data.polygons)
quads = sum(1 for p in low.data.polygons if len(p.vertices) == 4) / max(1, nf)
g = gap(low)
check(f'1 Retopo (Decimate, Allow Quads): about 2000 faces ({nf:,} from {nh:,}), mostly quads ({quads:.0%})',
      r == {'FINISHED'} and low.name == 'Head_Low' and 1400 <= nf <= 2800 and quads > 0.55)
check(f'projected: every point on the high (largest gap {g:.6f})', g < 1e-4)
check('the high hidden, not changed', high.hide_get() and len(high.data.polygons) == nh
      and [m.type for m in high.modifiers] == ['DISPLACE'])
e = [p.area for p in low.data.polygons]
check(f'no faces of no area (smallest {min(e):.2e})', min(e) > 0.0)
r = bpy.ops.mch.retopo_bake()
imgs = [n.image.name for m in low.data.materials if m and m.node_tree for n in m.node_tree.nodes
        if n.type == 'TEX_IMAGE' and n.image]
check(f'2 Bake on the decimated low: Normal and AO ({imgs}), UVs made', r == {'FINISHED'}
      and any('Normal' in n for n in imgs) and any('AO' in n for n in imgs) and len(low.data.uv_layers) > 0)

# Allow Quads off: all triangles, about the face count
for o in S.objects:
    o.select_set(False)
low.select_set(True); C.view_layer.objects.active = low
S.mch_rb_quads, S.mch_rb_faces = False, 1500
r = bpy.ops.mch.retopo_make()
low = C.active_object
nf = len(low.data.polygons)
tris = sum(1 for p in low.data.polygons if len(p.vertices) == 3) / max(1, nf)
check(f'Allow Quads off: triangles ({tris:.0%}), about 1500 ({nf:,}), made again on the same low ({low.name})',
      r == {'FINISHED'} and tris > 0.99 and 1000 <= nf <= 2200 and low.name == 'Head_Low')
check(f'projected again (largest gap {gap(low):.6f})', gap(low) < 1e-4)

# All Quads: every face split into quads, still about the face count, on the high
S.mch_rb_quads, S.mch_rb_allq, S.mch_rb_faces = True, True, 3000
r = bpy.ops.mch.retopo_make()
low = C.active_object
nf = len(low.data.polygons)
q = sum(1 for p in low.data.polygons if len(p.vertices) == 4) / max(1, nf)
check(f'All Quads: all quads ({q:.0%}), about 3000 ({nf:,})', r == {'FINISHED'} and q == 1.0 and 2000 <= nf <= 4200)
check(f'All Quads projected (largest gap {gap(low):.6f})', gap(low) < 1e-4)
S.mch_rb_allq = False

# Quad still the quad remesh
S.mch_rb_method, S.mch_rb_faces = 'QUAD', 2000
r = bpy.ops.mch.retopo_make()
low = C.active_object
q = sum(1 for p in low.data.polygons if len(p.vertices) == 4) / max(1, len(low.data.polygons))
check(f'Quad unchanged: quads ({q:.0%})', r == {'FINISHED'} and q > 0.8)
summary()
