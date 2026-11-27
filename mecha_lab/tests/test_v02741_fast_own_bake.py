"""0.24.341 Fast Bake for No High Poly (user: "노하이폴리도 느려서 만들라는거야"): a mesh's own material baked onto its
own UVs by Mecha Lab's engine - the node tree worked out texel by texel (images, math, mixes, Bevel / AO nodes, Bump,
Normal Map, Mix / Add shaders), the same maps as Cycles' bake, several times faster; a node it does not know: that map
by Cycles; Fast Bake off: Cycles as before.  Also: AO in the high poly fast engine (mbake v3+)."""
import os
import time

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bake_maps as bm, fast_bake as fb, fast_decimate as fd, fast_shade as fsh, mech_shader as ms

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
RES = 256
L = fsh.lib()
dll = open(os.path.join(os.path.dirname(fd.__file__), 'bin', 'mdecim_win_x64.dll'), 'rb').read()
check('the engine has the shader pieces (mbake v4: raster, images, AO, Bevel), here and in the Windows build',
      L is not None and L.mbake_version() == 4 and b'mbake_bevel' in dll and b'mbake_image' in dll)


def panel_cube(name):
    bpy.ops.mesh.primitive_cube_add(size=2)
    ob = C.active_object
    ob.name = name
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=3)
    bpy.ops.mesh.inset(thickness=0.08, depth=-0.06, use_individual=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob


def setup(kinds):
    st = S.mch_bake
    st.res = str(RES)
    st.own = True
    for k in ('normal', 'ao', 'color', 'rough', 'metal', 'curv', 'height', 'emit'):
        setattr(st, k, k in kinds)
    st.save, st.use_on_low, st.new_uv, st.smooth = False, False, False, False
    return st


def run(ob, fast, kinds):
    st = S.mch_bake
    st.fast = fast
    for o in S.objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob
    t0 = time.time()
    info = bm.bake_pair(C, ob, [], st)
    dt = time.time() - t0
    K = {'normal': 'NORMAL', 'ao': 'AO', 'color': 'COLOR', 'rough': 'ROUGH', 'metal': 'METAL', 'emit': 'EMIT'}
    out = {K[k]: np.array(bpy.data.images[f'{ob.name}_{bm.SUFFIX[K[k]]}'].pixels[:]).reshape(RES, RES, 4)[..., :3]
           for k in kinds}
    return dt, out, info


def corr(a, b):
    a, b = a.ravel(), b.ravel()
    if a.std() < 1e-6 or b.std() < 1e-6:
        return 1.0 if np.abs(a - b).mean() < 0.01 else 0.0
    return float(np.corrcoef(a, b)[0, 1])


# 1. the Mech Shader (Battle Worn: box-projected photo maps, Bevel + AO edge masks, chips / rust / dirt, Bump)
ob = panel_cube('MechCube')
mat = ms.new_material('BATTLE')
ms.assign(C, [ob], mat)
n_nodes = len(mat.node_tree.nodes)
kinds = ('normal', 'ao', 'color', 'rough', 'metal')
setup(kinds)
tc, cy, ic = run(ob, False, kinds)
tf, fs, i_f = run(ob, True, kinds)
cs = {k: corr(cy[k], fs[k]) for k in cy}
check(f'Mech Shader: every map by the fast engine ({i_f.get("fast")}), none to Cycles ({i_f.get("fast_why")})',
      set(i_f.get('fast') or []) == {'NORMAL', 'AO', 'COLOR', 'ROUGH', 'METAL'} and ic.get('fast') == [])
check('Mech Shader: the same maps as Cycles (correlation ' + ', '.join(f'{k} {v:.3f}' for k, v in cs.items()) + ')',
      all(v > (0.8 if k == 'METAL' else 0.93) for k, v in cs.items()))   # (Metallic: thin chipped edges, noisy in Cycles)
dev = [float(np.linalg.norm(x['NORMAL'][..., :2] - 0.5, axis=2).mean()) for x in (cy, fs)]
check(f'Mech Shader: the bump as strong as Cycles\' (mean tilt {dev[0]:.4f} vs {dev[1]:.4f})',
      0.75 < dev[1] / max(dev[0], 1e-9) < 1.33)
check(f'Mech Shader: faster than Cycles ({tf:.2f} s vs {tc:.2f} s)', tf < tc * 0.5)
check('the material is not changed by the bake', len(mat.node_tree.nodes) == n_nodes)

# 2. a plain material: UV image, a Normal Map node from an image, a Mix Shader, Emission
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.0, location=(5, 0, 0))
sp = C.active_object
sp.name = 'PlainSphere'
bpy.ops.object.shade_smooth()
W = 128
yy, xx = np.mgrid[0:W, 0:W] / W
pat = np.zeros((W, W, 4), np.float32)
pat[..., 0] = 0.5 + 0.5 * np.sin(xx * 12.566)
pat[..., 1] = 0.5 + 0.5 * np.cos(yy * 18.85)
pat[..., 2] = (xx + yy) / 2
pat[..., 3] = 1
im = bpy.data.images.new('Pat', W, W)
im.pixels.foreach_set(pat.ravel())
im.pack()
nm = np.zeros((W, W, 4), np.float32)
nm[..., 0] = 0.5 + 0.25 * np.sin(xx * 25.13)
nm[..., 1] = 0.5 + 0.25 * np.cos(yy * 25.13)
nm[..., 2] = 0.9
nm[..., 3] = 1
nim = bpy.data.images.new('Nrm', W, W)
nim.colorspace_settings.name = 'Non-Color'
nim.pixels.foreach_set(nm.ravel())
nim.pack()                                            # (kept as written: not regenerated)
m2 = bpy.data.materials.new('Plain')
m2.use_nodes = True
nt = m2.node_tree
P = nt.nodes['Principled BSDF']
tx = nt.nodes.new('ShaderNodeTexImage')
tx.image = im
nt.links.new(tx.outputs['Color'], P.inputs['Base Color'])
sep = nt.nodes.new('ShaderNodeSeparateColor')
nt.links.new(tx.outputs['Color'], sep.inputs['Color'])
nt.links.new(sep.outputs['Green'], P.inputs['Roughness'])
ntx = nt.nodes.new('ShaderNodeTexImage')
ntx.image = nim
nmap = nt.nodes.new('ShaderNodeNormalMap')
nt.links.new(ntx.outputs['Color'], nmap.inputs['Color'])
nt.links.new(nmap.outputs['Normal'], P.inputs['Normal'])
P.inputs['Emission Strength'].default_value = 0.0
em = nt.nodes.new('ShaderNodeEmission')
em.inputs['Color'].default_value = (1.0, 0.4, 0.1, 1.0)
em.inputs['Strength'].default_value = 2.0
mix = nt.nodes.new('ShaderNodeMixShader')
nt.links.new(sep.outputs['Blue'], mix.inputs['Fac'])
nt.links.new(P.outputs['BSDF'], mix.inputs[1])
nt.links.new(em.outputs['Emission'], mix.inputs[2])
out = nt.nodes['Material Output']
nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
sp.data.materials.append(m2)
kinds2 = ('normal', 'color', 'rough', 'emit')
setup(kinds2)
tc2, cy2, _i = run(sp, False, kinds2)
tf2, fs2, i2 = run(sp, True, kinds2)
c2 = {k: corr(cy2[k], fs2[k]) for k in cy2}
check(f'image / normal map / mix shader / emission: all fast ({i2.get("fast")}), the same as Cycles (' +
      ', '.join(f'{k} {v:.3f}' for k, v in c2.items()) + ')',
      set(i2.get('fast') or []) == {'NORMAL', 'COLOR', 'ROUGH', 'EMIT'} and all(v > 0.97 for v in c2.values()))

# 3. a node the engine does not know (Noise texture) -> that map by Cycles, the rest fast
nz = nt.nodes.new('ShaderNodeTexNoise')
nt.links.new(nz.outputs['Fac'], P.inputs['Roughness'])
tf3, fs3, i3 = run(sp, True, kinds2)
why = i3.get('fast_why') or {}
check(f'a Noise texture: its map by Cycles ({why}), the others still fast ({i3.get("fast")})',
      'ROUGH' in why and 'ROUGH' not in (i3.get('fast') or []) and 'COLOR' in (i3.get('fast') or [])
      and float(fs3['ROUGH'].std()) > 0.01)
check('Fast Bake off: Cycles bakes them all, as before', _i.get('fast') == [])

# 4. AO by the high poly fast engine (mbake v3): the high's own occlusion
check('the high poly fast engine bakes AO too (fast_bake VERSION >= 3)', fb.VERSION >= 3 and fb.lib() is not None)
summary()
