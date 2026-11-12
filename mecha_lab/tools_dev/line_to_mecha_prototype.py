"""Line to Mecha prototype (run with Blender's Python / bpy: renders before / after with wireframe next to this file;
L2M_FLAT=0.3 soft panels, 0.8 strong).  Prototype 2: lines drawn on a rough mesh -> hard edges; each region between the lines becomes a clean panel
(a smooth surface fitted to it, flattened by FLAT), neighbouring panels meet exactly on the line (a real crease)."""
import heapq, math, os
import bpy, bmesh
import numpy as np
from mathutils import Vector, kdtree, noise
from mathutils.bvhtree import BVHTree

OUT = os.path.dirname(os.path.abspath(__file__))
FLAT = float(os.environ.get('L2M_FLAT', '0.6'))        # 0 = keep the panel's own bulge, 1 = tight between its lines
CHAMFER = 0.014
bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene

# --- a rough clay pod (a leg / arm armour piece roughed out by hand) ------------------------------------------------
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1.0)
for v in bm.verts:
    p = v.co.copy()
    p.x *= 1.45; p.y *= 0.95; p.z *= 0.78
    p += p.normalized() * (0.05 * noise.noise(p * 2.2) + 0.02 * noise.noise(p * 7.0))
    v.co = p
me = bpy.data.meshes.new('Blob'); bm.to_mesh(me); bm.free()
blob = bpy.data.objects.new('Blob', me); S.collection.objects.link(blob)
before = bpy.data.objects.new('Before', me.copy()); S.collection.objects.link(before)
for f in before.data.polygons:
    f.use_smooth = True
print('blob faces', len(me.polygons))

# --- the lines "drawn" on it (rays onto the surface, as a stroke in the viewport would land) -------------------------
bvh = BVHTree.FromObject(blob, bpy.context.evaluated_depsgraph_get())
def ray_line(origins, dirs):
    out = []
    for o, d in zip(origins, dirs):
        hit = bvh.ray_cast(Vector(o), Vector(d).normalized())
        if hit[0] is not None:
            out.append(np.array(hit[0]))
    return np.array(out)
lines = []
t = np.linspace(0, 2 * math.pi, 241)
for x0 in (-0.95, 0.95):                                            # two rings: the caps
    lines.append(ray_line(np.c_[np.full_like(t, x0), 3 * np.cos(t), 3 * np.sin(t)], np.c_[0 * t, -np.cos(t), -np.sin(t)]))
xs = np.linspace(-0.95, 0.95, 120)
for y0, zs in ((0.42, 1), (-0.42, 1), (0.5, -1), (-0.5, -1)):      # four lengthwise lines: top and bottom strips
    lines.append(ray_line(np.c_[xs, np.full_like(xs, y0), np.full_like(xs, 3 * zs)], np.c_[0 * xs, 0 * xs, -zs + 0 * xs]))
ys = np.linspace(-0.42, 0.42, 50)                                    # a cross line splitting the top strip
lines.append(ray_line(np.c_[np.full_like(ys, 0.15), ys, np.full_like(ys, 3)], np.c_[0 * ys, 0 * ys, -1 + 0 * ys]))
zz = np.linspace(-0.55, 0.62, 60)                                    # a slanted line on the right side: a side panel
lines.append(ray_line(np.c_[0.95 - 1.1 * (zz + 0.55) / 1.17, np.full_like(zz, -3), zz], np.c_[0 * zz, 1 + 0 * zz, 0 * zz]))
print('lines', len(lines), [len(l) for l in lines])

# --- 1. each line onto an edge path; a line's end joins a line already there; the path straightened onto the line -
V = np.array([v.co for v in me.vertices]); nv = len(V)
E = np.array([e.vertices[:] for e in me.edges])
adj = [[] for _ in range(nv)]
for ei, (a, b) in enumerate(E):
    l = float(np.linalg.norm(V[a] - V[b])); adj[a].append((b, l, ei)); adj[b].append((a, l, ei))
kd = kdtree.KDTree(nv)
for i, p in enumerate(V):
    kd.insert(p, i)
kd.balance()
avg_e = float(np.mean([np.linalg.norm(V[a] - V[b]) for a, b in E]))
def seg_dist(x, P):
    a, b = P[:-1], P[1:]; d = b - a
    tt = np.clip(((x - a) * d).sum(1) / np.maximum((d * d).sum(1), 1e-12), 0, 1)
    c = a + d * tt[:, None]; dist = np.linalg.norm(c - x, axis=1); i = int(np.argmin(dist))
    return dist[i], c[i]
def path(a, b, P):
    best = {a: 0.0}; prev = {}; q = [(0.0, a)]
    while q:
        c, u = heapq.heappop(q)
        if u == b:
            break
        if c > best.get(u, 1e18):
            continue
        for w, l, ei in adj[u]:
            nc = c + l + 6.0 * seg_dist(V[w], P)[0]
            if nc < best.get(w, 1e18):
                best[w] = nc; prev[w] = (u, ei); heapq.heappush(q, (nc, w))
    out_e, out_v, u = [], [b], b
    while u != a and u in prev:
        u, ei = prev[u]; out_e.append(ei); out_v.append(u)
    return out_e, out_v
hard_e, line_v = set(), {}
for P in lines:
    closed = np.linalg.norm(P[0] - P[-1]) < 3 * avg_e
    ids = [kd.find(Vector(p))[1] for p in P[::2]]
    for end in (0, -1):                                   # an end near a line already there: onto that line
        if line_v and not closed:
            near = min(line_v, key=lambda v: np.linalg.norm(V[v] - P[end]))
            if np.linalg.norm(V[near] - P[end]) < 2.5 * avg_e:
                ids[end] = near
    if closed:
        ids.append(ids[0])
    ids = [i for j, i in enumerate(ids) if j == 0 or i != ids[j - 1]]
    for a, b in zip(ids[:-1], ids[1:]):
        es, vs = path(a, b, P)
        hard_e.update(es)
        for v in vs:
            line_v.setdefault(v, P)
for v, P in line_v.items():
    V[v] = seg_dist(V[v], P)[1]
print('hard edges', len(hard_e), 'line points', len(line_v))

# --- 2. regions: faces joined across edges that are not lines -----------------------------------------------------
me.vertices.foreach_set('co', V.ravel())
bm = bmesh.new(); bm.from_mesh(me); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
def flood():
    region = [-1] * len(bm.faces); nreg = 0
    for f in bm.faces:
        if region[f.index] >= 0:
            continue
        stack = [f]; region[f.index] = nreg
        while stack:
            g = stack.pop()
            for e in g.edges:
                if e.index in hard_e:
                    continue
                for h in e.link_faces:
                    if region[h.index] < 0:
                        region[h.index] = nreg; stack.append(h)
        nreg += 1
    return region, nreg
MIN_FACES = 24
for _round in range(10):
    region, nreg = flood()
    cnt = np.bincount(region, minlength=nreg)
    tiny = [r for r in range(nreg) if cnt[r] < MIN_FACES]
    if not tiny:
        break
    for r in tiny:
        border = {}
        for f in bm.faces:
            if region[f.index] != r:
                continue
            for e in f.edges:
                if e.index in hard_e:
                    for h in e.link_faces:
                        if region[h.index] != r:
                            border.setdefault(region[h.index], set()).add(e.index)
        if border:
            hard_e -= max(border.values(), key=len)
    print('merged sliver regions', tiny)
reg_v = [set() for _ in range(nreg)]; v_regs = [set() for _ in range(nv)]; reg_f = [[] for _ in range(nreg)]
for f in bm.faces:
    r = region[f.index]; reg_f[r].append(f)
    for v in f.verts:
        reg_v[r].add(v.index); v_regs[v.index].add(r)
print('regions', nreg, 'sizes', sorted((len(x) for x in reg_f), reverse=True))

# --- 3. panels: the line smoothed along itself; each region's clay noise smoothed out (Taubin, lines held), then
#     blended toward the region's tightest surface spanned by its lines (harmonic, lines held) by FLAT: the panels
#     flatten between the lines, so the lines become real creases (like ZBrush's Polish by Groups) -----------------
Vs = np.array([v.co for v in bm.verts])
EA = np.array([[e.verts[0].index, e.verts[1].index] for e in bm.edges])
is_hard = np.array([e.index in hard_e for e in bm.edges])
on_line = np.zeros(nv, bool); on_line[EA[is_hard].ravel()] = True
lnb = [[] for _ in range(nv)]
for a, b in EA[is_hard]:
    lnb[a].append(b); lnb[b].append(a)
mov = np.array([on_line[i] and len(lnb[i]) == 2 and len(v_regs[i]) <= 2 for i in range(nv)])
for it in range(40):                                        # the line: its bumps out, along itself (ends/crossings held)
    lam = 0.5 if it % 2 == 0 else -0.53
    avg = np.array([Vs[lnb[i]].mean(0) if lnb[i] else Vs[i] for i in range(nv)])
    Vs[mov] += lam * (avg[mov] - Vs[mov])
free = ~on_line
deg = np.bincount(EA.ravel(), minlength=nv).astype(float)
def nsum(X):
    out = np.zeros_like(X)
    np.add.at(out, EA[:, 0], X[EA[:, 1]]); np.add.at(out, EA[:, 1], X[EA[:, 0]])
    return out
base = Vs.copy()
for it in range(60):                                        # the clay noise out, the lines held
    lam = 0.55 if it % 2 == 0 else -0.57
    avg = nsum(base) / deg[:, None]
    base[free] += lam * (avg[free] - base[free])
# harmonic: L x = 0 on the free points, the line points fixed (conjugate gradients, matrix free)
def Lf(X):                                                  # the Laplacian restricted to free points
    Y = np.zeros((nv, X.shape[1])); Y[free] = X
    return (deg[:, None] * Y - nsum(Y))[free]
Y0 = Vs.copy(); Y0[free] = 0
rhs = nsum(Y0)[free]                                         # (the fixed neighbours' sum)
x = base[free].copy(); r = rhs - Lf(x); d = r.copy(); rr = (r * r).sum(0)
for it in range(600):
    Ad = Lf(d); a = rr / np.maximum((d * Ad).sum(0), 1e-30)
    x += d * a; r -= Ad * a; rn = (r * r).sum(0)
    if rn.max() < 1e-20:
        break
    d = r + d * (rn / np.maximum(rr, 1e-30)); rr = rn
harm = Vs.copy(); harm[free] = x
print('harmonic CG iterations', it)
# the bubble: L b = 1 on the free points, 0 on the lines - a smooth dome over each region, highest in its middle
def cg(rhs_, x0):
    x_ = x0.copy(); r_ = rhs_ - Lf(x_); d_ = r_.copy(); rr_ = (r_ * r_).sum(0)
    for _k in range(800):
        Ad = Lf(d_); a_ = rr_ / np.maximum((d_ * Ad).sum(0), 1e-30)
        x_ += d_ * a_; r_ -= Ad * a_; rn_ = (r_ * r_).sum(0)
        if rn_.max() < 1e-22:
            break
        d_ = r_ + d_ * (rn_ / np.maximum(rr_, 1e-30)); rr_ = rn_
    return x_
bub = np.zeros(nv); bub[free] = cg(np.ones((free.sum(), 1)), np.zeros((free.sum(), 1)))[:, 0]
# normals: the smoothed base's vertex normals
for v in bm.verts:
    v.co = base[v.index]
bm.normal_update()
N = np.array([list(v.normal) for v in bm.verts])
reg_of = np.array([next(iter(v_regs[i])) if len(v_regs[i]) == 1 else -1 for i in range(nv)])
new = harm.copy()
for r in range(nreg):
    m = free & (reg_of == r)
    if not m.any():
        continue
    hgt = ((base[m] - harm[m]) * N[m]).sum(1)              # how far the smoothed clay stands off the tight surface
    c = hgt.mean() / max(bub[m].mean(), 1e-12)               # the dome that holds the same volume
    new[m] = harm[m] + ((1 - FLAT) * c * bub[m])[:, None] * N[m]
# keep the clay's size: what each panel lost (its mean sink) given back by moving the lines out along their normals
# (a line point: the mean of its panels' loss), carried smoothly into the panels (the harmonic extension)
KEEP = float(os.environ.get('L2M_KEEP', '0.0'))   # (1.0 tried: the lines crumple - off)
loss = np.zeros(nreg)
for r in range(nreg):
    m = free & (reg_of == r)
    if m.any():
        loss[r] = ((base[m] - new[m]) * N[m]).sum(1).mean()
off = np.zeros((nv, 3))
for i in np.nonzero(on_line)[0]:
    rs = list(v_regs[i])
    off[i] = KEEP * np.mean([loss[r] for r in rs]) * N[i]
Yb = off.copy(); Yb[free] = 0
ext = off.copy(); ext[free] = cg(nsum(Yb)[free], np.zeros((free.sum(), 3)))
new = new + ext
print('size kept: line points out by', round(float(np.abs(off[on_line]).max()), 3))
for v in bm.verts:
    v.co = new[v.index]

# --- 4. the lines: hard edges (sharp + crease + Edge Memory), the panels smooth; a chamfer by bevel weight --------
hl = bm.edges.layers.int.new('hard')
for e in bm.edges:
    e[hl] = 1 if e.index in hard_e else 0
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-5)
for f in bm.faces:
    f.smooth = True
for e in bm.edges:
    e.smooth = not e[hl]
hard_now = [e.index for e in bm.edges if e[hl]]
bm.edges.layers.int.remove(hl)
bm.to_mesh(me); bm.free()
w_ = np.zeros(len(me.edges), np.float32); w_[hard_now] = 1.0
cr = me.attributes.get('crease_edge') or me.attributes.new('crease_edge', 'FLOAT', 'EDGE'); cr.data.foreach_set('value', w_)
me.attributes.new('mch_hard', 'BOOLEAN', 'EDGE').data.foreach_set('value', w_.astype(bool))
me.attributes.new('mch_bevel_chamfer', 'FLOAT', 'EDGE').data.foreach_set('value', w_)
bev = blob.modifiers.new('MCH Bevel Chamfer', 'BEVEL'); bev.limit_method = 'WEIGHT'; bev.edge_weight = 'mch_bevel_chamfer'
bev.width = CHAMFER; bev.segments = 1; bev.harden_normals = True
el = np.array([(me.vertices[e.vertices[0]].co - me.vertices[e.vertices[1]].co).length for e in me.edges])
print('hard edges after', len(hard_now), 'shortest edge', round(float(el.min()), 5))

# --- render: before (with its lines) / after, each with its wireframe ---------------------------------------------
blob.location = (1.75, 0, 0); before.location = (-1.75, 0, 0)
cu = bpy.data.curves.new('Lines', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.009
for P in lines:
    sp = cu.splines.new('POLY'); sp.points.add(len(P) - 1)
    for j, p_ in enumerate(P):
        sp.points[j].co = (*(p_ * 1.004), 1.0)
lob = bpy.data.objects.new('LinesOb', cu); lob.location = before.location; S.collection.objects.link(lob)
lm = bpy.data.materials.new('Orange'); lm.use_nodes = True
pb = lm.node_tree.nodes['Principled BSDF']
pb.inputs['Base Color'].default_value = (1.0, 0.35, 0.02, 1); pb.inputs['Emission Color'].default_value = (1.0, 0.35, 0.02, 1)
pb.inputs['Emission Strength'].default_value = 1.5
cu.materials.append(lm)
mat = bpy.data.materials.new('Clay'); mat.use_nodes = True
bsdf = mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.42, 0.43, 0.45, 1); bsdf.inputs['Roughness'].default_value = 0.35
bsdf.inputs['Metallic'].default_value = 0.4
for o in (blob, before):
    o.data.materials.append(mat)
wmat = bpy.data.materials.new('WireM'); wmat.use_nodes = True
wmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.01, 0.01, 0.015, 1)
dg = bpy.context.evaluated_depsgraph_get(); dg.update()
wires = []
for o in (blob, before):
    wm_ = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); wo = bpy.data.objects.new(o.name + 'Wire', wm_)
    wo.matrix_world = o.matrix_world; S.collection.objects.link(wo)
    md = wo.modifiers.new('W', 'WIREFRAME'); md.thickness = 0.0035; md.use_replace = True; md.use_even_offset = False
    wm_.materials.clear(); wm_.materials.append(wmat); wires.append(wo)
dg = bpy.context.evaluated_depsgraph_get(); dg.update()
for o in wires:
    m = o.evaluated_get(dg).to_mesh(); co = np.array([v.co for v in m.vertices])
    print('wire bounds', o.name, co.min(0).round(2), co.max(0).round(2)); o.evaluated_get(dg).to_mesh_clear()
print('after faces (with the chamfer)', len(blob.evaluated_get(dg).data.polygons))
cam_d = bpy.data.cameras.new('C'); cam_d.lens = 50; cam = bpy.data.objects.new('C', cam_d); S.collection.objects.link(cam); S.camera = cam
cam.location = (0.0, -7.4, 4.0)
cam.rotation_euler = (Vector((0, 0, -0.1)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
for loc, e, sz in (((3, -4, 5), 1400, 5), ((-5, -3, 1), 500, 4), ((0, 5, 4), 900, 4)):
    ld = bpy.data.lights.new('L', 'AREA'); ld.energy = e; ld.size = sz
    lo = bpy.data.objects.new('L', ld); lo.location = loc; S.collection.objects.link(lo)
    lo.rotation_euler = (Vector((0, 0, 0)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
wd = bpy.data.worlds.new('W'); S.world = wd; wd.use_nodes = True; wd.node_tree.nodes['Background'].inputs['Color'].default_value = (0.04, 0.04, 0.045, 1)
S.render.engine = 'CYCLES'; S.cycles.samples = 64; S.cycles.device = 'CPU'
S.render.resolution_x, S.render.resolution_y = 1600, 700
tag = os.environ.get('L2M_TAG', '')
for name, wire in (('l2m_shaded', False), ('l2m_wire', True)):
    for wo in wires:
        wo.hide_render = not wire
    S.render.filepath = os.path.join(OUT, name + tag + '.png'); bpy.ops.render.render(write_still=True)
print('DONE')
