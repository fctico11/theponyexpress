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
_hf = bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=400)
# the hole under his bottom, where the old tail scraps were cut away: fan it so it can bulge out round
BOT_C = None
for f in _hf['faces']:
    c = f.calc_center_median()
    if 0.75 < c.z < 0.83 and abs(c.x) < 0.05:
        BOT_C = np.array([0.0, c.y, c.z])
        pk = bmesh.ops.poke(bm, faces=[f])
        bmesh.ops.subdivide_edges(bm, edges=list({e for g in pk['faces'] for e in g.edges}), cuts=2,
                                  use_grid_fill=True)
print('BOTTOM hole centre', BOT_C)
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

# close his bottom: the real puppet is open underneath (that's where the finger goes in), so the scan
# has a dent there. Push anything that sinks inside the body egg back out onto it, away from the legs.
CO = np.empty(n * 3); me.vertices.foreach_get('co', CO); CO = CO.reshape(-1, 3)
x, y, z = CO.T
k0 = np.linalg.norm((CO - CEN) / RAD, axis=1)
on_egg = CEN + (CO - CEN) / np.maximum(k0, 1e-6)[:, None]
leg_tree = kdtree.KDTree(int((R == 2).sum()))
for i in np.where(R == 2)[0]:
    leg_tree.insert(CO[i], int(i))
leg_tree.balance()
leg_d = np.array([leg_tree.find(c)[2] for c in CO])
BOT_R = float(os.environ.get('BOT_R', 0.05))
bot_d = np.linalg.norm(CO - BOT_C, axis=1)
bot = (R == 0) * (1 - sstep(BOT_R * 0.6, BOT_R, bot_d)) * sstep(0.004, 0.02, leg_d)
taubin(me, int(os.environ.get('BOT_SMOOTH', 120)), lam=0.5, mu=0.0, weight=bot)
taubin(me, 25, weight=bot)
CO = np.empty(n * 3); me.vertices.foreach_get('co', CO); CO = CO.reshape(-1, 3)
k0 = np.linalg.norm((CO - CEN) / RAD, axis=1)
on_egg = CEN + (CO - CEN) / np.maximum(k0, 1e-6)[:, None]
w = bot * sstep(1.0, 0.94, k0)
print('BOTTOM verts', int((bot > 0.5).sum()), 'inside egg', int((w > 0.5).sum()))
for _ in range(3):
    CO += (on_egg - CO) * w[:, None]
    me.vertices.foreach_set('co', CO.ravel()); me.update()
    taubin(me, 6, weight=np.maximum(bot, 0))
    CO = np.empty(n * 3); me.vertices.foreach_get('co', CO); CO = CO.reshape(-1, 3)
    k0 = np.linalg.norm((CO - CEN) / RAD, axis=1)
    on_egg = CEN + (CO - CEN) / np.maximum(k0, 1e-6)[:, None]
    w = bot * sstep(1.0, 0.94, k0)
tb = Vector((0, JRAW['tail'][0].y, JRAW['tail'][0].z))      # where the old tail joined (repainted later)

# ================================================================ straight rope arms and legs
# The scan's ropes are kinked and lumpy (the puppet's floppy limbs, as they happened to lie), which
# makes them look bent before he moves and wobbly when he does. Lay each one out straight from where
# it's sewn on, keeping its woven surface: every vertex keeps its offset from the rope's centre line,
# carried along as the centre line is pulled straight, and the rope's width is evened out along it.
STRAIGHT = not os.environ.get('NO_STRAIGHT')
ATTACH = {k: JRAW[k + KS][0].copy() for k in ('arm', 'leg')}
from limbs import straighten

if os.environ.get('STRAIGHT_DUMP'):
    Ed = np.empty(len(me.edges) * 2, dtype=np.int64); me.edges.foreach_get('vertices', Ed)
    np.savez(os.environ['STRAIGHT_DUMP'], CO=CO, R=R, E=Ed.reshape(-1, 2),
             J=np.array([[list(p) for p in JRAW[k + KS][:3]] for k in ('arm', 'leg')]), KEEP=KEEP)
    sys.exit(0)
if STRAIGHT:
    J_SCAN = {k: list(JRAW[k + KS]) for k in ('arm', 'leg')}     # both sides start from the scan's joints
    for kind, rid in (('arm', 1), ('leg', 2)):
        for sx in (1, -1):
            ids = np.where((R == rid) & (np.sign(CO[:, 0]) == sx))[0]
            f_ = lambda v: np.array([abs(v.x) * sx, v.y, v.z])
            a_, e_, wr_, _ = (f_(p) for p in J_SCAN[kind])
            CO[ids], info = straighten(CO[ids], a_, e_, wr_, attach=0.035 if kind == 'arm' else 0.03)
            print('STRAIGHT', kind, sx, len(ids), 'verts; width', round(info['rt'] * 2000, 1), 'mm; length',
                  round(info['L'] * 1000, 1), 'mm; dir', info['D'].round(3))
            if sx == KEEP:
                Dv, a0, wr_new = Vector(info['D']), Vector(info['a0']), Vector(info['end_new'])
                c, axes, r = JRAW[kind + KS + 'pom']
                gap = (c - JRAW[kind + KS][2]).length
                a, e_old, wr_old = J_SCAN[kind][:3]
                e_s = (e_old - a).length / ((e_old - a).length + (wr_old - e_old).length)
                JRAW[kind + KS] = [a0, a0.lerp(wr_new, e_s), wr_new, wr_new + Dv * gap * 2]
                JRAW[kind + KS + 'pom'] = (wr_new + Dv * gap, [Dv] + list(axes[1:]), r)
    me.vertices.foreach_set('co', CO.ravel()); me.update()
me.attributes.new('part', 'FLOAT', 'POINT').data.foreach_set('value', [0.0] * n)

# ================================================================ new hands, feet and tail
PART = dict(scan=0, rope=1, pom=2, tuft=5, hair=6)
mirror = lambda v: Vector((-v.x, v.y, v.z))
bm = bmesh.new()
POMS = {}
POM_MINOR = {}
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
    if STRAIGHT and kind == 'arm':                  # sit the hand just over the rope's cut end
        c = wrist + major * min((c - wrist).length, length - float(os.environ.get('HAND_OVER', 0.012)))
    c = Vector((abs(c.x) * KEEP, c.y, c.z))
    for sx in (1, -1):
        cc = Vector((c.x * sx, c.y, c.z))
        mj = Vector((major.x * sx, major.y, major.z))
        rot = Vector((0, 0, 1)).rotation_difference(mj)
        ellipsoid(bm, cc, (minor, minor, length), rot, segs=(40, 26))
        POMS[(kind, sx)] = (cc, mj, length)
    POM_MINOR[kind] = minor
poms = obj_from(bm, 'poms', {'part': PART['pom']})

# A soft cuff where each rope arm meets its hand. The scan's rope ends in a ragged cut, so cut the last bit
# off cleanly and build a smooth new end in its place: it widens as it reaches the hand and runs into it,
# meeting the hand's surface where the two are the same width (painted the rope's colour later).
FLARE = float(os.environ.get('FLARE', 0.6))
CUFF_CUT = float(os.environ.get('CUFF_CUT', 0.016))       # how far before the hand's tip the scan rope stops
if STRAIGHT and FLARE > 0:
    bm = bmesh.new(); bm.from_mesh(me)
    lay_r = bm.verts.layers.float['region']; lay_p = bm.verts.layers.float['part']
    uvl = bm.loops.layers.uv.active
    for sx in (1, -1):
        cc, mj, Lp = POMS[('arm', sx)]
        c_, m_ = Vector(cc), Vector(mj)
        mr = POM_MINOR['arm']
        U = lambda p: -Lp - (p - c_).dot(m_)
        radial = lambda p: (p - c_) - m_ * (p - c_).dot(m_)
        mine = lambda v: round(v[lay_r]) == 1 and (v.co.x > 0) == (sx > 0)
        arm_v = [v for v in bm.verts if mine(v)]
        rt_ = float(np.median([radial(v.co).length for v in arm_v if 0.02 < U(v.co) < 0.05]))
        peak = min(rt_ * (1 + FLARE), 0.6 * mr)
        u_p = Lp * (math.sqrt(1 - (peak / mr) ** 2) - 1)   # where the hand is exactly as wide as the cuff
        bmesh.ops.delete(bm, geom=[v for v in arm_v if U(v.co) < CUFF_CUT], context='VERTS')
        # drop any scraps that came loose, then take the open rim
        rim = [v for v in bm.verts if mine(v) and any(e.is_boundary for e in v.link_edges)]
        loose = [v for v in bm.verts if mine(v) and not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
        rim = [v for v in rim if v.is_valid and v.link_faces and U(v.co) < CUFF_CUT + 0.01]
        # a reference frame round the hand's axis, to order the rim
        e1 = radial(rim[0].co).normalized(); e2 = m_.cross(e1)
        ang = lambda p: math.atan2(radial(p).dot(e2), radial(p).dot(e1))
        rim.sort(key=lambda v: ang(v.co))
        uv_of = {v: next((l[uvl].uv.copy() for l in v.link_loops), Vector((0, 0))) for v in rim}
        for v in rim:                                          # a clean round rim
            d = radial(v.co).normalized()
            v.co = c_ + m_ * (-Lp - CUFF_CUT) + d * rt_
        # rings from the rim into the hand
        K = 10
        u_end = -0.010
        prev = rim
        for k in range(1, K + 1):
            t = k / K
            u = CUFF_CUT + (u_end - CUFF_CUT) * t
            if u > u_p:
                v_ = (u - u_p) / (CUFF_CUT - u_p)
                r = rt_ + (peak - rt_) * (1 - v_) ** 2
            else:
                q_ = (-Lp - u) / Lp
                r = min(peak, 0.97 * mr * math.sqrt(max(0.0, 1 - q_ * q_)))
            ring = []
            for v in rim:
                d = radial(v.co).normalized()
                nv = bm.verts.new(c_ + m_ * (-Lp - u) + d * r)
                nv[lay_r] = 1.0; nv[lay_p] = 0.0
                ring.append(nv)
            for a in range(len(rim)):
                b = (a + 1) % len(rim)
                f = bm.faces.new((prev[a], prev[b], ring[b], ring[a]))
                for l in f.loops:
                    src = rim[(prev.index(l.vert) if l.vert in prev else ring.index(l.vert))]
                    l[uvl].uv = uv_of[src]
            prev = ring
        cv = bm.verts.new(c_ + m_ * (-Lp - u_end)); cv[lay_r] = 1.0; cv[lay_p] = 0.0
        for a in range(len(rim)):
            f = bm.faces.new((prev[a], prev[(a + 1) % len(rim)], cv))
            for l in f.loops:
                l[uvl].uv = uv_of[rim[a]]
        print('CUFF', sx, 'rope r', round(rt_ * 1000, 1), 'mm -> cuff r', round(peak * 1000, 1), 'mm; rim', len(rim),
              'verts; hand r', round(mr * 1000, 1))
    bm.normal_update()
    bm.to_mesh(me); bm.free(); me.update()
    n = len(me.vertices)
    R = np.empty(n); me.attributes['region'].data.foreach_get('value', R); R = np.rint(R).astype(int)
    CO = np.empty(n * 3); me.vertices.foreach_get('co', CO); CO = CO.reshape(-1, 3)

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
RG = np.rint(bake(lambda: attr('region'))[:, :, 0])      # 1: arm rope, 2: leg rope
POS = bake(position) - 0.5


def normal():
    g = nt.nodes.new('ShaderNodeNewGeometry')
    m = nt.nodes.new('ShaderNodeVectorMath'); m.operation = 'MULTIPLY_ADD'
    nt.links.new(g.outputs['Normal'], m.inputs[0])
    m.inputs[1].default_value = (0.5, 0.5, 0.5); m.inputs[2].default_value = (0.5, 0.5, 0.5)
    return m.outputs['Vector']

NRM = bake(normal) * 2 - 1

Am = C * G
tint = target / (target @ LUM)
Lg = Am + (tint * (Am @ LUM)[..., None] - Am) * 0.6
m = sstep(0.07, 0.22, C @ LUM)
col = C + (Lg - C) * m[..., None]
px_, py_, pz_ = np.abs(POS[..., 0]), POS[..., 1], POS[..., 2]
fz = (np.sin(px_ * 2300 + pz_ * 1700) * np.sin(py_ * 2100 - px_ * 900) + np.sin(pz_ * 3100 + py_ * 1300)) * 0.5
fur = target * (1 + 0.06 * fz)[..., None]
# His bottom: the scan there is the puppet's opening, all shadow and inside lining. Repaint it in clean
# white fur, and draw the stripe that runs across under his tail (the lowest stripe on each side curves
# down and the two meet there) as one clean band. Worked out around the hole centre BOT_C: angle a in the
# plane of his bottom (-90 = straight towards the tail, 0/-180 = his sides), r = distance from the centre.
body = (PT == 0)
bu = np.array([1.0, 0, 0])
bn = (BOT_C - CEN) / np.linalg.norm(BOT_C - CEN)
bv = np.cross(bn, bu)
rel3 = POS - BOT_C
r_px = np.linalg.norm(rel3, axis=-1)
a_px = np.degrees(np.arctan2(rel3 @ bv, rel3 @ bu))
fold = np.where(a_px < -90, -180 - a_px, a_px)          # mirror the left half onto the right
back = a_px < 0
# band centre line (angle, radius), measured on the scan, from straight back out to where it meets the side stripe
BAND = np.array([(-90, 0.049), (-60, 0.047), (-40, 0.054), (-25, 0.068), (-12, 0.084), (-4, 0.092)])
rc = np.interp(fold, BAND[:, 0], BAND[:, 1])
BAND_W = float(os.environ.get('BAND_W', 0.0105))      # half width
band = (1 - sstep(BAND_W - 0.003, BAND_W + 0.003, np.abs(r_px - rc) + 0.0022 * fz)) * back * (fold < -6)
# clean area: out to just past the band at the back, smaller at the front so the stripe between the legs stays
clean_r = np.where(back, rc + BAND_W + 0.014, 0.05)
clean_r = np.where(back & (fold > -30), np.minimum(clean_r, 0.07), clean_r)
clean = (1 - sstep(clean_r - 0.012, clean_r, r_px)) * body
col = col + (fur - col) * clean[..., None]
lc = col @ LUM
dark_px = body & (lc > 0.004) & (lc < 0.035) & (POS[..., 2] > 0.8) & (POS[..., 2] < 0.95) & (r_px > 0.1)
STRIPE_COL = np.median(col[dark_px], axis=0)
print('STRIPE colour', STRIPE_COL.round(3), 'from', int(dark_px.sum()), 'px; band px', int((band > 0.5).sum()))
col = col + (STRIPE_COL * (1 + 0.08 * fz)[..., None] - col) * (band * body)[..., None]

# Lower back and tail base: the scan has shadow here (grey fur) and a brown speck where the old tail was
# sewn on. Keep the stripes, lift the grey back to clean white, and give the darkest bits the stripe colour.
rt = np.linalg.norm(POS - np.array(tb), axis=-1)
tidy = np.maximum((1 - sstep(0.03, 0.04, rt)), back * (1 - sstep(0.1, 0.12, r_px))) * body * (1 - band)
relc = (col @ LUM) / (target @ LUM)
# stripes are navy, shadow is neutral grey or brownish: tell them apart by how blue a dark pixel is
blue = col[..., 2] / np.maximum(col[..., :2].mean(-1), 1e-5)
reg = tidy > 0.5
print('TIDY blueness of dark px', np.histogram(blue[reg & (relc < 0.3)], bins=8, range=(0.6, 2.2))[0])
stripe_like = sstep(float(os.environ.get('BLUE_LO', 1.15)), float(os.environ.get('BLUE_HI', 1.35)), blue) * (1 - sstep(0.3, 0.5, relc))
near_t = 1 - sstep(0.03, 0.04, rt)
below = near_t * sstep(tb.z - 0.006, tb.z - 0.016, POS[..., 2])     # just under the rope: no stripe there
level = near_t * (1 - below)
stripe_like = np.maximum(stripe_like, level * (1 - sstep(0.15, 0.3, relc)))   # the stripe right at the rope
def box_blur(a, k=2):
    for ax in (0, 1):
        a = sum(np.roll(a, i, axis=ax) for i in range(-k, k + 1)) / (2 * k + 1)
    return a
stripe_like = box_blur(box_blur(stripe_like))
stripe_like = sstep(0.3, 0.6, stripe_like)                         # solid stripes with soft edges
lift = 1 - stripe_like
dark = np.maximum(level * (1 - sstep(0.15, 0.3, relc)), 0.75 * stripe_like)
col = col + (fur - col) * (tidy * lift)[..., None]
col = col + (STRIPE_COL * (1 + 0.08 * fz)[..., None] - col) * (tidy * dark)[..., None]
# Tone him down: the fur reads blown-out white on the site's stage lights, his face most of all (the
# scan's head fur is about 20% brighter than his body's). Dim all of him, his face more, but only where it
# faces up or out towards the lights: what faces down (under his chin, under his tummy) only gets the
# stage's dim purple ground light, so lift that instead.
BRIGHT = float(os.environ.get('BRIGHT', 0.62))
HEAD_K = float(os.environ.get('HEAD_K', 0.72))
UNDER_K = float(os.environ.get('UNDER_K', 1.45))
nz = NRM[..., 2]
head = sstep(NECK_Z - 0.02, NECK_Z + 0.02, POS[..., 2])
down = sstep(-0.15, -0.75, nz)
dim = BRIGHT * (1 + (HEAD_K - 1) * head * (1 - down)) * (1 + (UNDER_K - 1) * down)
col = np.where(body[..., None], col * dim[..., None], col)
# The cuff where each rope arm runs into its hand is new geometry with no scan texture of its own: give it
# the rope's own weave, copied from the rope just above it at the same angle round the arm (mirrored back
# and forth along the arm, so there's no seam), fading in from the scanned rope.
if STRAIGHT and FLARE > 0:
    armrope = (RG == 1) & body
    for sx in (1, -1):
        cc, mj, Lp = POMS[('arm', sx)]
        c3, m3 = np.array(cc), np.array(mj)
        rel = POS - c3
        ax = rel @ m3
        radv = rel - ax[..., None] * m3
        rad = np.linalg.norm(radv, axis=-1)
        u = -Lp - ax
        mine = armrope & (rad < 0.035) & (u < 0.08)
        # brown scraps of the old cut end: plain rope colour
        brown = sstep(1.15, 1.4, col[..., 0] / np.maximum(col[..., 2], 1e-5)) * mine * (u < 0.045)
        col = col + (fur - col) * brown[..., None]
        e1 = np.cross(m3, [0, 0, 1.0]); e1 /= np.linalg.norm(e1); e2 = np.cross(m3, e1)
        ang = np.arctan2(radv @ e2, radv @ e1)
        U0, P_ = float(os.environ.get('CUFF_B', 0.026)) + 0.001, 0.024
        src = mine & (u > U0) & (u < U0 + P_)
        R0_ = 0.0103
        si = np.argwhere(src)
        tree_ = kdtree.KDTree(len(si))
        for k_i, (yy, xx) in enumerate(si):
            tree_.insert((math.cos(ang[yy, xx]) * R0_, math.sin(ang[yy, xx]) * R0_, u[yy, xx]), k_i)
        tree_.balance()
        k_ = (1 - sstep(float(os.environ.get('CUFF_A', 0.016)), float(os.environ.get('CUFF_B', 0.026)), u)) * mine
        new_col = col.copy()
        for yy, xx in np.argwhere(k_ > 0.002):
            d_ = (U0 - u[yy, xx]) % (2 * P_)
            us = U0 + (d_ if d_ < P_ else 2 * P_ - d_)
            _, j_, _ = tree_.find((math.cos(ang[yy, xx]) * R0_, math.sin(ang[yy, xx]) * R0_, us))
            sy, sx_ = si[j_]
            new_col[yy, xx] = col[sy, sx_]
        col = col + (new_col - col) * k_[..., None]
        print('CUFF weave', sx, 'from', len(si), 'rope px to', int((k_ > 0.002).sum()), 'cuff px')
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
ELBOW_W = float(os.environ.get('ELBOW_W', 0.1))
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
        ew = ELBOW_W if kind == 'arm' else 0.25         # arms: a short bend zone, so a clear elbow
        f1 = smooth(1 - ew, 1 + ew, g); f2 = smooth(1.8, 2.0, g)
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
            dA = (p - Vector((abs(ATTACH[kind].x) * sx, ATTACH[kind].y, ATTACH[kind].z))).length
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
WK = '# ---------------------------------------------------------------- write keys'
rt_a, rt_b = retarget.split(WK)
exec(compile(rt_a, os.path.join(HERE, 'build.py'), 'exec'))

# ================================================================ keep his hands out of his body
# The dance was made for a human, so his pom-pom hands sometimes sink into his round tummy or his
# big head. For each frame, test the hand pom against his body and head (each carried by its own
# bone) and, where they would overlap, swing the arm out at the shoulder just far enough.
NV_ = len(me.vertices)
NRM = np.empty(NV_ * 3); me.vertices.foreach_get('normal', NRM); NRM = NRM.reshape(-1, 3)
CLEAR = float(os.environ.get('HAND_CLEAR', 0.004))          # breathing room, metres


def surface_tree(mask):
    ids = np.where(mask)[0][::2]
    t = kdtree.KDTree(len(ids))
    for j_, i_ in enumerate(ids):
        t.insert(CO[i_], j_)
    t.balance()
    return t, ids

core_m = (part == PART['scan']) & (R == 0)
# body and head overlap around the neck; hits right at either cut edge are ignored
CUT = {P + 'Spine1': (None, NECK_Z + 0.035), P + 'Head': (NECK_Z - 0.035, None)}
SURF = {P + 'Spine1': surface_tree(core_m & (CO[:, 2] < NECK_Z + 0.035)),
        P + 'Head': surface_tree(core_m & (CO[:, 2] >= NECK_Z - 0.035))}


def near_cut(bn, z_):
    lo_, hi_ = CUT[bn]
    return (lo_ is not None and z_ < lo_ + 0.015) or (hi_ is not None and z_ > hi_ - 0.015)


def bone_m(f, n):
    """World matrix taking a rest-pose point on bone n to frame f."""
    return Matrix.Translation(POS[f][n]) @ (ROT[f][n] @ R0[n].inverted()).to_matrix().to_4x4() @ \
        Matrix.Translation(-P0[n])


def hand_points(sx):
    cc, mj, L = POMS[('arm', sx)]
    r_ = (JRAW['arm' + KS + 'pom'][2])
    rr = np.sort(r_)[::-1]
    rad_ = (rr[1] + rr[2]) / 2 * 1.02 * 0.86
    return [cc + mj * (L * t) for t in (-0.55, 0.0, 0.55)], rad_

HANDPTS = {sx: hand_points(sx) for sx in (1, -1)}


def penetration(f, sx):
    """Deepest overlap of this hand with body/head this frame, and the world push direction."""
    side = 'Left' if sx > 0 else 'Right'
    hm = bone_m(f, P + side + 'Hand')
    pts, rad_ = HANDPTS[sx]
    worst, push = 0.0, None
    for bn, (tree, ids) in SURF.items():
        bm_ = bone_m(f, bn)
        inv = bm_.inverted()
        for pt in pts:
            q = inv @ (hm @ pt)
            _, j_, _ = tree.find(q)
            v = Vector(CO[ids[j_]]); nn = Vector(NRM[ids[j_]])
            if near_cut(bn, v.z):
                continue
            d_ = (q - v).dot(nn)
            pen = rad_ + CLEAR - d_
            if pen > worst:
                worst = pen
                push = (bm_.to_3x3() @ nn).normalized()
    return worst, push

ARMCHAIN = {sx: [P + ('Left' if sx > 0 else 'Right') + b for b in ('Arm', 'ForeArm', 'Hand')] for sx in (1, -1)}


def swing(f, sx, q):
    names = ARMCHAIN[sx]
    pivot = POS[f][names[0]].copy()
    for nm in names:
        ROT[f][nm] = q @ ROT[f][nm]
        POS[f][nm] = pivot + q @ (POS[f][nm] - pivot)


def fix_pass(max_iter=40):
    fixes = {}
    for f in range(F0, F1 + 1):
        for sx in (1, -1):
            total = Quaternion()
            for _ in range(max_iter):
                pen, push = penetration(f, sx)
                if pen <= 1e-4:
                    break
                sh = POS[f][ARMCHAIN[sx][0]]
                hand_c = bone_m(f, ARMCHAIN[sx][2]) @ HANDPTS[sx][0][1]
                lever = hand_c - sh
                axis_ = lever.cross(push)
                if axis_.length < 1e-6:
                    break
                ang = min(math.radians(12), pen / max(lever.length, 1e-3) * 1.15)
                q = Quaternion(axis_.normalized(), ang)
                swing(f, sx, q)
                total = q @ total
            fixes[(f, sx)] = total
    return fixes

if os.environ.get('HAND_DEBUG'):
    def pen_detail(f, sx):
        side = 'Left' if sx > 0 else 'Right'
        hm = bone_m(f, P + side + 'Hand'); pts, rad_ = HANDPTS[sx]; out = []
        for bn, (tree, ids) in SURF.items():
            inv = bone_m(f, bn).inverted()
            for k, pt in enumerate(pts):
                q = inv @ (hm @ pt); _, j_, dist_ = tree.find(q)
                v = Vector(CO[ids[j_]]); nn = Vector(NRM[ids[j_]])
                out.append((round((rad_ + CLEAR - (q - v).dot(nn)) * 1000, 1), bn[9:], k, round(dist_ * 1000, 1), tuple(round(c, 3) for c in v), tuple(round(c, 2) for c in nn)))
        return sorted(out, reverse=True)[:2]
    for f in (F0, 30, 50, 80, 110):
        for sx in (1, -1):
            print('DBG', f, sx, pen_detail(f, sx))
def arm_dump():
    return {f: {n: tuple(ROT[f][n]) for n in ORDER if any(k in n for k in ('Shoulder', 'Arm', 'Hand', 'Spine2'))} for f in range(F0, F1 + 1)}
ARM_DUMP = {'pre': arm_dump()} if os.environ.get('ARM_DUMP') else None
before = [max(penetration(f, sx)[0] for sx in (1, -1)) for f in range(F0, F1 + 1)]
print('HANDS before: frames overlapping', sum(b > 1e-4 for b in before), 'of', len(before),
      ' worst', round(max(before) * 1000, 1), 'mm')
# Smoothing the arms works on each joint's rotation relative to its parent, then re-places the forearm and hand.
def chain_fk(f, sx):
    for n in ARMCHAIN[sx][1:]:
        p_ = PARENT[n]
        POS[f][n] = POS[f][p_] + (ROT[f][p_] @ R0[p_].inverted()) @ (P0[n] - P0[p_])


def smooth_arms(passes=2):
    for sx in (1, -1):
        for n in ARMCHAIN[sx]:
            p_ = PARENT[n]
            for _ in range(passes):
                L = {f: ROT[f][p_].inverted() @ ROT[f][n] for f in range(F0, F1 + 1)}
                for f in range(F0 + 1, F1):
                    a_, b_, c_ = L[f - 1], L[f], L[f + 1]
                    if a_.dot(b_) < 0: a_ = -a_
                    if c_.dot(b_) < 0: c_ = -c_
                    ROT[f][n] = ROT[f][p_] @ Quaternion(Vector(a_) * 0.25 + Vector(b_) * 0.5 + Vector(c_) * 0.25).normalized()
        for f in range(F0, F1 + 1):
            chain_fk(f, sx)


FR = list(range(F0, F1 + 1))
# Push the hands clear, then smooth the arms' motion over time, and repeat: the arm settles into one
# smooth path that stays clear of his tummy and head (pushing frame by frame alone made the arms jerk).
if os.environ.get('OLD_HANDS'):
    fixes = fix_pass()
    lift_max = 0.0
else:
    smooth_arms()
    lift_max = 0.0
    for rnd in range(int(os.environ.get('FIX_ROUNDS', 5))):
        fx = fix_pass()
        lift_max = max(lift_max, max(q.angle for q in fx.values()))
        smooth_arms(passes=int(os.environ.get('ARM_SMOOTH', 4)))
        left_ = [max(penetration(f, sx)[0] for sx in (1, -1)) for f in FR]
        print('HANDS round', rnd, 'overlapping', sum(v > 1e-4 for v in left_), 'worst', round(max(left_) * 1000, 1), 'mm')
    fix_pass()                                   # last little nudges, no smoothing after
fixes = {(f, sx): Quaternion() for f in FR for sx in (1, -1)}
print('HANDS push (deg) max', round(math.degrees(lift_max), 1))
after = [max(penetration(f, sx)[0] for sx in (1, -1)) for f in range(F0, F1 + 1)]
print('HANDS after: frames overlapping', sum(a > 1e-4 for a in after), ' worst', round(max(after) * 1000, 1), 'mm')
worst_frames = sorted(range(F0, F1 + 1), key=lambda f: -before[f - F0])[:4]
print('HANDS worst frames before', [(f, round(before[f - F0] * 1000)) for f in worst_frames])
if ARM_DUMP is not None:
    import pickle
    ARM_DUMP['post'] = arm_dump(); ARM_DUMP['fixes'] = {k: tuple(v) for k, v in fixes.items()}
    pickle.dump(ARM_DUMP, open(os.environ['ARM_DUMP'], 'wb'))

exec(compile(WK + rt_b + pictures, os.path.join(HERE, 'build.py'), 'exec'))
