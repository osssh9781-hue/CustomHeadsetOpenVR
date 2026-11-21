from _harness import bmesh, bpy, fresh
fresh()
C = bpy.context
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=2.0); box = C.active_object
bpy.ops.mesh.primitive_cylinder_add(radius=0.4, depth=3.0); cyl = C.active_object
me = bpy.data.meshes.new('c'); car = bpy.data.objects.new('car', me); C.scene.collection.objects.link(car)
def islands_detail(me):
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    seen = set(); out = []
    for f in bm.faces:
        if f.index in seen: continue
        comp = []; st = [f]; seen.add(f.index)
        while st:
            g = st.pop(); comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen: seen.add(h.index); st.append(h)
        vol = sum(fc.calc_center_median().dot(fc.normal) * fc.calc_area() for fc in comp) / 3.0
        cen = sum((fc.calc_center_median() for fc in comp), comp[0].calc_center_median() * 0) / len(comp)
        out.append((len(comp), round(vol, 3), tuple(round(x, 2) for x in cen)))
    bm.free(); return out
def islands(me):
    return islands_detail(me)
def _unused(me):
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    seen = set(); n = 0
    for f in bm.faces:
        if f.index in seen: continue
        n += 1; st = [f]; seen.add(f.index)
        while st:
            g = st.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen: seen.add(h.index); st.append(h)
    v = bm.calc_volume(); bm.free(); return n, v
def run(kind, k=0.3, band=12):
    ng = bpy.data.node_groups.new('g', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    go = N.new('NodeGroupOutput')
    gs = []
    for o in (box, cyl):
        oi = N.new('GeometryNodeObjectInfo'); oi.transform_space = 'RELATIVE'; oi.inputs['Object'].default_value = o
        m = N.new('GeometryNodeMeshToSDFGrid'); m.inputs['Voxel Size'].default_value = 0.04; m.inputs['Band Width'].default_value = band
        L.new(oi.outputs['Geometry'], m.inputs['Mesh']); gs.append(m.outputs[0])
    b = N.new('GeometryNodeSDFGridBoolean'); b.operation = 'UNION'; L.new(gs[1], b.inputs[1]); L.new(gs[0], b.inputs[1]); sharp = b.outputs[0]
    def mth(op, a, bb=None, c=None):
        n = N.new('ShaderNodeMath'); n.operation = op
        for i, v in enumerate((a, bb, c)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[i].default_value = float(v)
            else: L.new(v, n.inputs[i])
        return n.outputs[0]
    if kind == 'corr':
        h = mth('MAXIMUM', mth('SUBTRACT', k, mth('ABSOLUTE', mth('SUBTRACT', gs[0], gs[1]))), 0.0)
        g = mth('SUBTRACT', sharp, mth('DIVIDE', mth('MULTIPLY', h, h), 4 * k))
    elif kind == 'smin':
        g = mth('SMOOTH_MIN', gs[0], gs[1], k)
    else:
        g = sharp
    if kind.startswith('prune'):
        h = mth('MAXIMUM', mth('SUBTRACT', k, mth('ABSOLUTE', mth('SUBTRACT', gs[0], gs[1]))), 0.0)
        g = mth('SUBTRACT', sharp, mth('DIVIDE', mth('MULTIPLY', h, h), 4 * k))
        pr = N.new('GeometryNodeGridPrune'); L.new(g, pr.inputs['Grid'])
        pr.inputs['Mode'].default_value = kind.split(':')[1]
        g = pr.outputs[0]
    if kind == 'fillet':
        f = N.new('GeometryNodeSDFGridFillet'); L.new(sharp, f.inputs[0]); f.inputs['Iterations'].default_value = 4; g = f.outputs[0]
    t = N.new('GeometryNodeGridToMesh'); t.inputs['Threshold'].default_value = 0.0
    L.new(g, t.inputs['Grid']); L.new(t.outputs[0], go.inputs[0])
    mod = car.modifiers.new('m', 'NODES'); mod.node_group = ng
    ev = car.evaluated_get(C.evaluated_depsgraph_get()).data
    print('RES', kind, band, len(ev.polygons), islands(ev))
    car.modifiers.remove(mod)
run('corr'); run('smin')
