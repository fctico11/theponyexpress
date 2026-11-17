"""Clean, symmetrical Marty from the scan of the real puppet.

blender --background --python clean.py -- <shuffle.fbx> <out_dir> [export.glb]

1. Find his centre line and straighten him onto x = 0, then mirror one half onto the other.
2. Swap the scan's lumpy pom-pom hands and feet for smooth round ones, and its floppy tail for a
   clean rope tail with a black tuft.
3. Pull the body a little towards a round egg shape and smooth the surface.
4. Re-bake the scan's own texture onto the result, evened out to one off-white all round.
5. Rig it and put the shuffle on it (reusing build.py's retargeting).
Env: SIDE=POSITIVE_X|NEGATIVE_X (half to keep), ROUND (0..1 pull to an egg), SMOOTH (iterations).
"""
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector, Matrix, Quaternion, kdtree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import geo, common
from shapes import ellipsoid, rope, tube, obj_from, taubin, select_only, sstep, to_srgb

args = sys.argv[sys.argv.index('--') + 1:]
SRC, OUT = args[0], args[1]
EXPORT = args[2] if len(args) > 2 else None
SIDE = os.environ.get('SIDE', 'POSITIVE_X')
ROUND = float(os.environ.get('ROUND', 0.3))
SLIM = float(os.environ.get('SLIM', 0.9))     # egg width relative to the fitted one
SMOOTH = int(os.environ.get('SMOOTH', 30))
P = 'mixamorig'
TEX = 2048
KEEP = 1 if SIDE == 'POSITIVE_X' else -1          # +x is his left
KS = 'L' if KEEP > 0 else 'R'

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
scene = bpy.context.scene
src_arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
for o in [o for o in bpy.data.objects if o.type in ('CAMERA', 'LIGHT')]:
    bpy.data.objects.remove(o)

# ================================================================ the scan, welded, in world space
me = mesh.data
for m in list(mesh.modifiers):
    mesh.modifiers.remove(m)
mesh.vertex_groups.clear()
mesh.parent = None
me.transform(mesh.matrix_world)
mesh.matrix_world = Matrix.Identity(4)
bm = bmesh.new(); bm.from_mesh(me)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
bm.to_mesh(me); bm.free()
for a in list(me.attributes):
    if a.name in ('custom_normal', 'sharp_face', 'sharp_edge'):
        me.attributes.remove(a)
old_uv = me.uv_layers.active.name
mat = me.materials[0]
old_node = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
old_img = old_node.image
co = [v.co.copy() for v in me.vertices]
NV = len(co)
adj = geo.graph(me, co)

# per-vertex colour from the scan's texture (linear)
w_, h_ = old_img.size
px = np.empty(w_ * h_ * 4, np.float32); old_img.pixels.foreach_get(px)
k_ = 4
small = px.reshape(h_, w_, 4)[:, :, :3].reshape(h_ // k_, k_, w_ // k_, k_, 3).mean((1, 3)); del px
sw, sh = w_ // k_, h_ // k_


def vertex_colours(me):
    uvd = me.uv_layers[old_uv].data
    n = len(me.vertices)
    c = np.zeros((n, 3)); cnt = np.zeros((n, 1))
    for l in me.loops:
        u, v = uvd[l.index].uv
        c[l.vertex_index] += small[min(sh - 1, int((v % 1) * sh)), min(sw - 1, int((u % 1) * sw))]
        cnt[l.vertex_index] += 1
    c /= np.maximum(cnt, 1)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

VLIN = vertex_colours(me)

# ================================================================ find limbs and tail (geodesic from each tip)
band = lambda lo, hi: [i for i in range(NV) if lo < co[i].z < hi]
CX = 0.023
seeds = {
    'armL': max(band(0.76, 0.88), key=lambda i: co[i].x),
    'armR': min(band(0.76, 0.88), key=lambda i: co[i].x),
    'legL': min((i for i in range(NV) if co[i].x > CX), key=lambda i: co[i].z),
    'legR': min((i for i in range(NV) if co[i].x < CX), key=lambda i: co[i].z),
    'tail': max(range(NV), key=lambda i: co[i].y),
}
CUTS = {'armL': (0.100, 0.175), 'armR': (0.088, 0.140),
        'legL': (0.095, 0.215), 'legR': (0.100, 0.220), 'tail': (0.115, 0.170)}
dist = {k: geo.dijkstra(adj, [s], limit=0.3) for k, s in CUTS and seeds.items()}


def cent(limb, d0, w=0.006):
    c, n = Vector(), 0
    for i, d in enumerate(dist[limb]):
        if abs(d - d0) < w:
            c += co[i]; n += 1
    return c / n

REGION = np.zeros(NV, dtype=int)        # 0 body/head, 1 arm rope, 2 leg rope, 9 cut away
for k in ('armL', 'armR', 'legL', 'legR'):
    pe, at = CUTS[k]
    for i, d in enumerate(dist[k]):
        if d < pe:
            REGION[i] = 9
        elif d < at and REGION[i] == 0:
            REGION[i] = 1 if k.startswith('arm') else 2
REGION[(np.array([c.z for c in co]) < 0.745) & (REGION == 0)] = 9     # scraps of the old tail under him
TAIL_CUT = CUTS['tail'][1] - 0.006
for i, d in enumerate(dist['tail']):
    if d < TAIL_CUT:
        REGION[i] = 9

# colours for the new pieces, taken from the scan itself
pom_ids = [i for k in ('armL', 'armR', 'legL', 'legR') for i, d in enumerate(dist[k]) if d < CUTS[k][0] - 0.015]
POM_COL = np.median(VLIN[pom_ids], axis=0)
TUFT_COL = np.median(VLIN[[i for i, d in enumerate(dist['tail']) if d < 0.07]], axis=0)
ROPE_COL = np.median(VLIN[REGION == 2], axis=0)
print('COLOURS pom', POM_COL.round(3), 'tuft', TUFT_COL.round(3), 'rope', ROPE_COL.round(3))

# pom-pom shapes (kept side), and the joints, before straightening
def pom_fit(k):
    pe = CUTS[k][0]
    pts = np.array([co[i][:] for i, d in enumerate(dist[k]) if d < pe + 0.004])
    c = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - c)
    ext = np.array([(pts - c) @ ax for ax in vt])
    r = (ext.max(1) - ext.min(1)) / 2
    return Vector(c), [Vector(ax) for ax in vt], r

JRAW = {}
for k in ('arm' + KS, 'leg' + KS):
    pe, at = CUTS[k]
    JRAW[k] = [cent(k, at), cent(k, (at + pe) / 2), cent(k, pe), co[seeds[k]].copy()]
    JRAW[k + 'pom'] = pom_fit(k)
JRAW['tail'] = [cent('tail', CUTS['tail'][1]), co[seeds['tail']].copy()]

# ================================================================ straighten him onto x = 0
core_ids = np.where(REGION == 0)[0]
CO = np.array([c[:] for c in co])
sample = CO[core_ids[::max(1, len(core_ids) // 1500)]]
cen = CO[core_ids].mean(0)
tree = kdtree.KDTree(len(sample))
for i, p in enumerate(sample):
    tree.insert(p, i)
tree.balance()


def rot_mat(rz, ry):
    return np.array(Matrix.Rotation(ry, 3, 'Y') @ Matrix.Rotation(rz, 3, 'Z'))


def transform(pts, rz, ry, dx):
    return (pts - cen) @ rot_mat(rz, ry).T + np.array([dx, cen[1], cen[2]])


def untransform(pts, rz, ry, dx):
    return (pts - np.array([dx, cen[1], cen[2]])) @ rot_mat(rz, ry) + cen


def cost(rz, ry, dx):
    q = transform(sample, rz, ry, dx)
    q[:, 0] *= -1
    back = untransform(q, rz, ry, dx)
    return sum(tree.find(p)[2] for p in back) / len(back)

best = (1e9, 0, 0, 0)
for rz in np.radians(np.arange(-8, 8.1, 2)):
    for ry in np.radians(np.arange(-8, 8.1, 2)):
        for dx in np.arange(-0.012, 0.0121, 0.004):
            c_ = cost(rz, ry, dx)
            if c_ < best[0]:
                best = (c_, rz, ry, dx)
_, brz, bry, bdx = best
for rz in brz + np.radians(np.arange(-1.5, 1.6, 0.5)):
    for ry in bry + np.radians(np.arange(-1.5, 1.6, 0.5)):
        for dx in bdx + np.arange(-0.003, 0.0031, 0.001):
            c_ = cost(rz, ry, dx)
            if c_ < best[0]:
                best = (c_, rz, ry, dx)
_, RZ, RY, DX = best
print('MIRROR fit', round(best[0] * 1000, 2), 'mm  yaw', round(math.degrees(RZ), 1), 'roll', round(math.degrees(RY), 1), 'dx', round(DX, 4))
TM = Matrix.Translation(Vector((DX, cen[1], cen[2]))) @ Matrix(rot_mat(RZ, RY).tolist()).to_4x4() @ \
    Matrix.Translation(-Vector(cen))
me.transform(TM)
T3 = TM.to_3x3()
for k, v in JRAW.items():
    if k.endswith('pom'):
        c, axes, r = v
        JRAW[k] = (TM @ c, [T3 @ a for a in axes], r)
    else:
        JRAW[k] = [TM @ p for p in v]

# ================================================================ cut away poms and tail, mirror
TC = np.empty(NV * 3); me.vertices.foreach_get('co', TC); TC = TC.reshape(-1, 3)
scrap = (TC[:, 2] < 0.745) & (np.abs(TC[:, 0]) < 0.016)          # bits of the old tail between his legs
print('SCRAP verts', int(scrap.sum()))
REGION[scrap] = 9
reg = me.attributes.new('region', 'FLOAT', 'POINT')
reg.data.foreach_set('value', REGION.astype(float))
bm = bmesh.new(); bm.from_mesh(me)
lay = bm.verts.layers.float['region']
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v[lay] > 8], context='VERTS')
# drop any loose bits left over
bm.verts.ensure_lookup_table()
seen, islands = set(), []
for v in bm.verts:
    if v.index in seen:
        continue
    stack, isl = [v], []
    seen.add(v.index)
    while stack:
        u = stack.pop(); isl.append(u)
        for e in u.link_edges:
            o = e.other_vert(u)
            if o.index not in seen:
                seen.add(o.index); stack.append(o)
    islands.append(isl)
biggest = max(len(i) for i in islands)
bmesh.ops.delete(bm, geom=[v for i in islands if len(i) < biggest for v in i], context='VERTS')
print('ISLANDS dropped', [len(i) for i in islands if len(i) < biggest])
bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=400)
bm.to_mesh(me); bm.free()
select_only(mesh)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.symmetrize(direction=SIDE, threshold=0.0008)
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')
n = len(me.vertices)
R = np.empty(n); reg = me.attributes['region']; reg.data.foreach_get('value', R)
R = np.rint(R).astype(int)
print('SCAN after mirror', n, 'verts')

# ================================================================ smooth, and round the body
taubin(me, SMOOTH)
CO = np.empty(n * 3); me.vertices.foreach_get('co', CO); CO = CO.reshape(-1, 3)
x, y, z = CO.T
HIP_Z, NECK_Z = 0.79, 0.935
torso = (R == 0) & (z > HIP_Z - 0.03) & (z < NECK_Z)
A = np.stack([x[torso] ** 2, y[torso] ** 2, z[torso] ** 2, y[torso], z[torso]], 1)
sol = np.linalg.lstsq(A, np.ones(torso.sum()), rcond=None)[0]
a2, b2, c2, d, e = sol
y0, z0 = -d / (2 * b2), -e / (2 * c2)
k = 1 + d * d / (4 * b2) + e * e / (4 * c2)
RAD = np.sqrt(k / np.array([a2, b2, c2]))
RAD[:2] *= SLIM
CEN = np.array([0.0, y0, z0])
print('BODY egg centre', CEN.round(3), 'radii', RAD.round(3))
q = (CO - CEN) / RAD
k0 = np.linalg.norm(q, axis=1)
on_egg = CEN + (CO - CEN) / np.maximum(k0, 1e-6)[:, None]
w = ROUND * (R == 0) * (1 - sstep(NECK_Z - 0.07, NECK_Z + 0.005, z)) * sstep(HIP_Z - 0.08, HIP_Z - 0.03, z)
CO += (on_egg - CO) * w[:, None]
me.vertices.foreach_set('co', CO.ravel()); me.update()
taubin(me, 8)
# smooth out the back of his neck and upper back, where the scan has a flat, creased patch
CO = np.empty(n * 3); me.vertices.foreach_get('co', CO); CO = CO.reshape(-1, 3)
x, y, z = CO.T
BACKMASK = (R == 0) * sstep(0.83, 0.87, z) * (1 - sstep(0.985, 1.02, z)) * sstep(CEN[1] - 0.01, CEN[1] + 0.035, y)
print('BACK smooth verts', int((BACKMASK > 0.5).sum()))
taubin(me, int(os.environ.get('BACKSMOOTH', 30)), lam=0.5, mu=0.0, weight=BACKMASK)
taubin(me, 10, weight=BACKMASK)
me.attributes.new('part', 'FLOAT', 'POINT').data.foreach_set('value', [0.0] * n)

# ================================================================ new hands, feet and tail
PART = dict(scan=0, rope=1, pom=2, tuft=5, hair=6)
mirror = lambda v: Vector((-v.x, v.y, v.z))
bm = bmesh.new()
POMS = {}
for kind in ('arm', 'leg'):
    c, axes, r = JRAW[kind + KS + 'pom']
    major = axes[0]
    wrist = JRAW[kind + KS][2]
    if major.dot(c - wrist) < 0:
        major = -major
    rr = np.sort(r)[::-1]
    minor = (rr[1] + rr[2]) / 2 * 1.02         # round across, same size as his own
    size = 0.86 if kind == 'arm' else 1.0       # his hands read a touch big once smoothed
    minor *= size
    length = rr[0] * size
    c = Vector((abs(c.x) * KEEP, c.y, c.z))
    for sx in (1, -1):
        cc = Vector((c.x * sx, c.y, c.z))
        mj = Vector((major.x * sx, major.y, major.z))
        rot = Vector((0, 0, 1)).rotation_difference(mj)
        ellipsoid(bm, cc, (minor, minor, length), rot, segs=(40, 26))
        POMS[(kind, sx)] = (cc, mj, length)
poms = obj_from(bm, 'poms', {'part': PART['pom']})

# ---- tail: a thicker rope with a full tassel on the end
base, tip = JRAW['tail']
base = Vector((0, base.y, base.z)); tip = Vector((0, tip.y, tip.z))
tdir = (tip - base).normalized()
inside = base - tdir * 0.014
mid = base.lerp(tip, 0.5) + Vector((0, 0, 0.02))
tip_r = tip - tdir * 0.03
bm = bmesh.new()
rope(bm, [inside, base, mid, tip_r], rope_r=0.0095, strand_r=0.0057, pitch=0.032)
tail = obj_from(bm, 'tail', {'part': PART['rope']})
bm = bmesh.new()
end_dir = (tip_r - mid).normalized()
ellipsoid(bm, tip_r, (0.017, 0.017, 0.015), Vector((0, 0, 1)).rotation_difference(end_dir), segs=(28, 18))
u = Vector((1, 0, 0)); v = end_dir.cross(u).normalized()
STRANDS = [(0.0, 0.0, 0.06)] + [(14, 2 * math.pi * k / 6 + 0.5, 0.058) for k in range(6)] + \
          [(28, 2 * math.pi * k / 10, 0.052) for k in range(10)]
for spread, th, L in STRANDS:
    sp = math.radians(spread)
    d = end_dir * math.cos(sp) + (u * math.cos(th) + v * math.sin(th)) * math.sin(sp)
    d = (d + Vector((0, 0, -0.2))).normalized()
    ellipsoid(bm, tip_r + d * L * 0.55, (0.0074, 0.0074, L * 0.55), Vector((0, 0, 1)).rotation_difference(d), segs=(14, 10))
tuft = obj_from(bm, 'tuft', {'part': PART['tuft']})
tt = tip_r + end_dir * 0.03

# ---- hair: little tufts standing up along the black mane on his head
VLs = vertex_colours(me)
SC = np.empty(n * 3); me.vertices.foreach_get('co', SC); SC = SC.reshape(-1, 3)
NS = np.empty(n * 3); me.vertices.foreach_get('normal', NS); NS = NS.reshape(-1, 3)
headv = SC[:, 2] > 0.96
hc = SC[headv].mean(0)
ear_y = SC[headv & (np.abs(SC[:, 0]) > 0.08)][:, 1].mean()           # mane runs from the ears back
headv &= (SC[:, 1] > ear_y - 0.03) & (SC[:, 2] > 0.985)
hc = SC[headv].mean(0)
for thr in (0.05, 0.08, 0.12):
    mane = np.where(headv & (np.abs(SC[:, 0]) < 0.008) & ((VLs @ np.array([0.2126, 0.7152, 0.0722])) < thr))[0]
    if len(mane) > 20:
        break
ang = np.arctan2(SC[mane, 1] - hc[1], SC[mane, 2] - hc[2])        # 0 = straight up, + = towards the back
rad = np.hypot(SC[mane, 1] - hc[1], SC[mane, 2] - hc[2])
lo, hi = np.percentile(ang, 3), np.percentile(ang, 97)
hi = min(hi, math.radians(100))                  # stop before the back of the head, where tufts would stick out
print('EAR y', round(ear_y, 3))
print('MANE', len(mane), 'verts; arc', round(math.degrees(lo)), 'to', round(math.degrees(hi)), 'deg')
step = 0.013 / max(rad.mean(), 1e-3)
bm = bmesh.new()
HAIR = 0
BACK = Vector((0, 1, -0.45)).normalized()          # towards his back, a little downwards


def hair_tuft(p, d, L, r):
    """A soft tuft: one smooth tapered tube that leaves the head along d and bends back towards his
    back, ending in a rounded tip (not a point)."""
    n = 14
    pts, pos = [], p - d * 0.005
    pts.append(pos.copy())
    for i in range(1, n + 1):
        t = i / n
        cur = d.lerp(BACK, 0.85 * t ** 1.3).normalized()
        pos = pos + cur * ((L + 0.005) / n)
        pts.append(pos.copy())
    tip_r = r * 0.45
    tube(bm, pts, r, ring=12, taper=lambda t: 1 - 0.55 * t)
    ellipsoid(bm, pts[-1], (tip_r, tip_r, tip_r), segs=(12, 8))


for j, a_ in enumerate(np.arange(lo, hi + 1e-6, step)):
    sel = np.abs(ang - a_) < step / 2
    if not sel.any():
        continue
    k_ = mane[sel][np.argmax(rad[sel])]
    p = Vector((0, SC[k_, 1], SC[k_, 2]))
    nrm = Vector((0, NS[k_, 1], NS[k_, 2])).normalized()
    nrm = (nrm + Vector((0, 0.15, 0.1))).normalized()
    end = (a_ - lo) / max(hi - lo, 1e-6)                             # small at the front, full from there back
    L = (0.032 + 0.005 * math.sin(j * 2.1)) * (0.65 + 0.35 * min(1.0, end * 4))
    hair_tuft(p, nrm, L, 0.0082)
    for sx in (1, -1):
        hair_tuft(p + Vector((0.004 * sx, 0, 0)), (nrm + Vector((0.5 * sx, 0, 0))).normalized(), L * 0.8, 0.007)
    HAIR += 1
    p_last = p
# fill the little gap between the head mane and his back: follow his back outline on round from where
# the head mane stops, and stop where the neck meets the body
NECKHAIR = 0
GAP_END_Z = float(os.environ.get('GAP_END_Z', 0.95))
zs = []
for i_, zb in enumerate(np.arange(p_last.z - 0.009, GAP_END_Z, -0.008)):
    # the back outline at this height: furthest-back point on his centre line (he faces -y)
    cand = np.where((R == 0) & (np.abs(SC[:, 0]) < 0.006) & (np.abs(SC[:, 2] - zb) < 0.004) & (SC[:, 1] > 0.0))[0]
    if not len(cand):
        continue
    k_ = cand[np.argmax(SC[cand, 1])]
    p = Vector((0, SC[k_, 1], SC[k_, 2]))
    nrm = Vector((0, NS[k_, 1], NS[k_, 2])).normalized()
    nrm = (nrm + BACK * 0.6).normalized()
    f = max(0.55, 0.85 - 0.04 * i_)
    L = 0.032 * f
    hair_tuft(p, nrm, L, 0.0082 * (0.55 + 0.45 * f))
    for sx in (1, -1):
        hair_tuft(p + Vector((0.0035 * sx, 0, 0)), (nrm + Vector((0.45 * sx, 0, 0))).normalized(), L * 0.8, 0.007 * (0.55 + 0.45 * f))
    zs.append((round(p.y, 3), round(p.z, 3)))
    NECKHAIR += 1
print('GAP tufts at z', zs, '(head mane ends z', round(p_last.z, 3), ')')
print('MANE tufts', HAIR, '+ neck', NECKHAIR)
hair = obj_from(bm, 'hair', {'part': PART['hair']})

for o in (poms, tail, tuft, hair):
    o.select_set(True)
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
bpy.ops.object.join()
for p in me.polygons:
    p.use_smooth = True
NV = len(me.vertices)
part = np.empty(NV); me.attributes['part'].data.foreach_get('value', part); part = np.rint(part).astype(int)
R = np.empty(NV); me.attributes['region'].data.foreach_get('value', R); R = np.rint(R).astype(int)
R[part != 0] = -1
CO = np.empty(NV * 3); me.vertices.foreach_get('co', CO); CO = CO.reshape(-1, 3)
print('JOINED', NV, 'verts; x range', CO[:, 0].min().round(4), CO[:, 0].max().round(4))

# ================================================================ texture: the scan's own, evened out
VL = vertex_colours(me)
LUM = np.array([0.2126, 0.7152, 0.0722])
E = np.empty(len(me.edges) * 2, dtype=np.int64); me.edges.foreach_get('vertices', E); E = E.reshape(-1, 2)
deg = np.maximum(np.bincount(E.ravel(), minlength=NV), 1).astype(float)[:, None]


def nb_sum(a):
    out = np.zeros_like(a)
    np.add.at(out, E[:, 0], a[E[:, 1]])
    np.add.at(out, E[:, 1], a[E[:, 0]])
    return out

light = ((VL @ LUM) > 0.14) & (part == 0)
num = np.where(light[:, None], VL, 0.0); den = light.astype(float)[:, None]
for _ in range(120):
    num = (num + nb_sum(num)) / (deg + 1)
    den = (den + nb_sum(den)) / (deg + 1)
field = num / np.maximum(den, 1e-9)
med = np.median(VL[light], axis=0)
target = 0.4 * med + 0.6 * (med @ LUM)
gain = np.clip(target / np.maximum(field, 1e-4), 0.55, 2.0)
legs = R == 2
Al = VL[legs] * gain[legs]
ROPE_COL = np.median(Al + (target / (target @ LUM) * (Al @ LUM)[:, None] - Al) * 0.6, axis=0)
print('ROPE evened', ROPE_COL.round(3))
gain[part != 0] = 1.0
me.attributes.new('gain', 'FLOAT_VECTOR', 'POINT').data.foreach_set('vector', (gain / 2).ravel())

select_only(mesh)
newuv = me.uv_layers.new(name='bake')
me.uv_layers.active = newuv
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003)
bpy.ops.object.mode_set(mode='OBJECT')
while len(me.materials) > 1:
    me.materials.pop()
nt = mat.node_tree
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 1
scene.render.bake.margin = 8
scene.render.bake.use_clear = True


def bake(build):
    for nd in list(nt.nodes):
        if nd != old_node:
            nt.nodes.remove(nd)
    col = build()
    em = nt.nodes.new('ShaderNodeEmission'); nt.links.new(col, em.inputs['Color'])
    out = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(em.outputs[0], out.inputs['Surface'])
    img = bpy.data.images.new('b', TEX, TEX, alpha=False, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = img
    nt.nodes.active = tn
    bpy.ops.object.bake(type='EMIT')
    a = np.empty(TEX * TEX * 4, np.float32); img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(TEX, TEX, 4)[:, :, :3].astype(np.float64)


def old_tex():
    u = nt.nodes.new('ShaderNodeUVMap'); u.uv_map = old_uv
    nt.links.new(u.outputs[0], old_node.inputs[0])
    return old_node.outputs['Color']


def attr(name):
    a = nt.nodes.new('ShaderNodeAttribute'); a.attribute_name = name
    return a.outputs['Color'] if name != 'gain' else a.outputs['Vector']


def position():
    g = nt.nodes.new('ShaderNodeNewGeometry')
    m = nt.nodes.new('ShaderNodeVectorMath'); m.operation = 'ADD'
    nt.links.new(g.outputs['Position'], m.inputs[0]); m.inputs[1].default_value = (0.5, 0.5, 0.5)
    return m.outputs['Vector']

C = bake(old_tex)
G = bake(lambda: attr('gain')) * 2
PT = np.rint(bake(lambda: attr('part'))[:, :, 0])
POS = bake(position) - 0.5

Am = C * G
tint = target / (target @ LUM)
Lg = Am + (tint * (Am @ LUM)[..., None] - Am) * 0.6
m = sstep(0.07, 0.22, C @ LUM)
col = C + (Lg - C) * m[..., None]
px_, py_, pz_ = np.abs(POS[..., 0]), POS[..., 1], POS[..., 2]
fz = (np.sin(px_ * 2300 + pz_ * 1700) * np.sin(py_ * 2100 - px_ * 900) + np.sin(pz_ * 3100 + py_ * 1300)) * 0.5
for pid, base_col, amp in ((PART['pom'], POM_COL, 0.10), (PART['tuft'], TUFT_COL, 0.12), (PART['hair'], TUFT_COL * 1.3, 0.14), (PART['rope'], ROPE_COL, 0.0)):
    c_ = base_col * (1 + amp * fz)[..., None]
    if pid == PART['rope']:
        c_ = base_col * (0.86 + 0.14 * np.sin(pz_ * 900 + py_ * 500) ** 2)[..., None]
    col = np.where((PT == pid)[..., None], c_, col)
col = to_srgb(np.clip(col, 0, 1))
img = bpy.data.images.new('marty', TEX, TEX, alpha=False)
img.pixels.foreach_set(np.concatenate([col, np.ones(col.shape[:2] + (1,))], -1).astype(np.float32).ravel())
img.filepath_raw = f"{OUT}/clean-tex.png"; img.file_format = 'PNG'; img.save()
img.pack()
for nd in list(nt.nodes):
    nt.nodes.remove(nd)
tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = img
bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.inputs['Roughness'].default_value = 1.0
nt.links.new(tn.outputs['Color'], bsdf.inputs['Base Color'])
out = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
me.uv_layers.remove(me.uv_layers[old_uv])
bpy.data.images.remove(old_img)
for a in ('gain',):
    me.attributes.remove(me.attributes[a])

# ================================================================ skeleton (symmetrical)
def slab(lo, hi):
    s = CO[(R == 0) & (CO[:, 2] > lo) & (CO[:, 2] < hi)].mean(0)
    return Vector((0, s[1], s[2]))
lo_c, hi_c = slab(0.80, 0.825), slab(0.895, 0.92)
axis = (hi_c - lo_c).normalized()
at_z = lambda zz: lo_c + axis * ((zz - lo_c.z) / axis.z)
H0, NECKP = at_z(0.79), at_z(0.935)
LT = (NECKP - H0).length
S = lambda p: (p - H0).dot(axis) / LT
spt = lambda s: H0 + axis * (s * LT)

J = {}
J[P + 'Hips'] = (spt(0.05), spt(0.3), None)
J[P + 'Spine'] = (spt(0.3), spt(0.5), P + 'Hips')
J[P + 'Spine1'] = (spt(0.5), spt(0.7), P + 'Spine')
J[P + 'Spine2'] = (spt(0.7), spt(0.95), P + 'Spine1')
J[P + 'Neck'] = (spt(0.95), spt(1.08), P + 'Spine2')
J[P + 'Head'] = (spt(1.08), spt(1.08) + Vector((0, 0, 0.12)), P + 'Neck')
CHAIN = {}
for side, sx in (('Left', 1), ('Right', -1)):
    f = lambda v: Vector((abs(v.x) * sx, v.y, v.z))
    a, e, wr, _ = (f(p) for p in JRAW['arm' + KS])
    pc, pm, pl = POMS[('arm', sx)]
    tipp = pc + pm * pl
    sh = spt(S(a)); sh = sh + (a - sh) * 0.35
    J[P + side + 'Shoulder'] = (sh, a, P + 'Spine2')
    J[P + side + 'Arm'] = (a, e, P + side + 'Shoulder')
    J[P + side + 'ForeArm'] = (e, wr, P + side + 'Arm')
    J[P + side + 'Hand'] = (wr, tipp, P + side + 'ForeArm')
    CHAIN[('arm', sx)] = [a, e, wr, tipp]
    a, e, wr, _ = (f(p) for p in JRAW['leg' + KS])
    pc, pm, pl = POMS[('leg', sx)]
    tipp = pc + pm * pl
    J[P + side + 'UpLeg'] = (a, e, P + 'Hips')
    J[P + side + 'Leg'] = (e, wr, P + side + 'UpLeg')
    J[P + side + 'Foot'] = (wr, tipp, P + side + 'Leg')
    CHAIN[('leg', sx)] = [a, e, wr, tipp]
J['Tail'] = (base, tt + tdir * 0.03, P + 'Hips')

for nm, (h, t, _) in J.items():
    print(f"JOINT {nm:24s} {h.x:6.3f} {h.y:6.3f} {h.z:6.3f} -> {t.x:6.3f} {t.y:6.3f} {t.z:6.3f}")

arm_data = bpy.data.armatures.new('Marty')
arm = bpy.data.objects.new('MartyRig', arm_data)
scene.collection.objects.link(arm)
select_only(arm)
bpy.ops.object.mode_set(mode='EDIT')
for nm, (h, t, p) in J.items():
    b = arm_data.edit_bones.new(nm)
    b.head, b.tail = h, t
    if p:
        b.parent = arm_data.edit_bones[p]
bpy.ops.object.mode_set(mode='OBJECT')
ORDER = list(J.keys())
R0 = {nm: arm_data.bones[nm].matrix_local.to_quaternion() for nm in ORDER}
P0 = {nm: arm_data.bones[nm].head_local.copy() for nm in ORDER}
PARENT = {nm: J[nm][2] for nm in ORDER}

# ================================================================ weights
def smooth(a, b, v):
    t = min(1.0, max(0.0, (v - a) / (b - a)))
    return t * t * (3 - 2 * t)


def chain_g(p, pts):
    best = (1e9, 0.0)
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
        dd = (a + ab * t - p).length
        if dd < best[0]:
            best = (dd, i + t)
    return best[1]

SPINE = [(0.0, 'Hips'), (0.3, 'Spine'), (0.5, 'Spine1'), (0.75, 'Spine2'), (1.0, 'Neck'), (1.12, 'Head')]
TOP = {'arm': 'Arm', 'leg': 'UpLeg'}
W = []
for i in range(NV):
    p = Vector(CO[i])
    sx = 1 if p.x > 0 else -1
    sd = 'Left' if sx > 0 else 'Right'
    w = {}
    if part[i] == PART['pom']:
        w[P + sd + ('Hand' if p.z > 0.7 else 'Foot')] = 1.0
    elif part[i] in (PART['rope'], PART['tuft']):
        w['Tail'] = 1.0
    elif part[i] == PART['hair'] and p.z > NECK_Z + 0.04:
        w[P + 'Head'] = 1.0                            # neck hair falls through to the spine below
    elif R[i] in (1, 2):
        kind = 'arm' if R[i] == 1 else 'leg'
        names = [P + sd + b for b in (('Arm', 'ForeArm', 'Hand') if kind == 'arm' else ('UpLeg', 'Leg', 'Foot'))]
        g = chain_g(p, CHAIN[(kind, sx)])
        f1 = smooth(0.75, 1.25, g); f2 = smooth(1.8, 2.0, g)
        w[names[0]] = 1 - f1; w[names[1]] = f1 - f2; w[names[2]] = f2
    else:
        s = S(p)
        if s <= SPINE[0][0]:
            w[P + 'Hips'] = 1.0
        elif s >= SPINE[-1][0]:
            w[P + 'Head'] = 1.0
        else:
            for (s0, b0), (s1, b1) in zip(SPINE, SPINE[1:]):
                if s0 <= s <= s1:
                    t = smooth(s0, s1, s)
                    w[P + b0] = w.get(P + b0, 0) + 1 - t
                    w[P + b1] = w.get(P + b1, 0) + t
                    break
        for kind in ('arm', 'leg'):                      # soften where the ropes are sewn on
            dA = (p - CHAIN[(kind, sx)][0]).length
            lw = 1 - smooth(0.004, 0.022, dA)
            if lw > 0:
                for b in w:
                    w[b] *= 1 - lw
                w[P + sd + TOP[kind]] = w.get(P + sd + TOP[kind], 0) + lw
    W.append({b: v for b, v in w.items() if v > 1e-3})

groups = {nm: mesh.vertex_groups.new(name=nm) for nm in ORDER}
for i, w in enumerate(W):
    for b, v in w.items():
        groups[b].add([i], v, 'REPLACE')
mesh.parent = arm
mod = mesh.modifiers.new('Armature', 'ARMATURE')
mod.object = arm

import colorsys
PAL = {}
ca = me.color_attributes.new('seg', 'FLOAT_COLOR', 'POINT')
for i, w in enumerate(W):
    c = Vector((0, 0, 0, 0))
    for b, v in w.items():
        if b not in PAL:
            PAL[b] = Vector((*colorsys.hsv_to_rgb((len(PAL) * 0.381966) % 1, 0.75, 1), 1))
        c += PAL[b] * v
    ca.data[i].color = c
me.color_attributes.active_color = ca
for a in ('part', 'region'):
    me.attributes.remove(me.attributes[a])

FOOT_FLAT = True
FEET = {}
for side, sx in (('Left', 1), ('Right', -1)):
    FEET[P + side + 'Foot'] = [Vector(CO[i]) for i in range(NV)
                               if part[i] == PART['pom'] and CO[i][2] < 0.7 and (CO[i][0] > 0) == (sx > 0)][::3]

# ================================================================ dance: build.py's retargeting and export
src = open(os.path.join(HERE, 'build.py')).read()
cut = lambda a, b=None: src[src.index(a): src.index(b) if b else None]
retarget = cut('# ---------------------------------------------------------------- reference-pose corrections',
               '# ---------------------------------------------------------------- even him out')
retarget = retarget.replace(cut('FEET = {}\n', 'def fk('), '')
pictures = cut('# ---------------------------------------------------------------- pictures')
scene.render.engine = 'BLENDER_WORKBENCH'
exec(compile(retarget + pictures, os.path.join(HERE, 'build.py'), 'exec'))
