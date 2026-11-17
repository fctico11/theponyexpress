"""Re-rig Marty: weld the scan, fit a skeleton to the puppet, re-skin, retarget the dance, export GLB.

blender --background --python build.py -- <src.fbx> <out_dir> [export.glb]
"""
import bpy, bmesh, sys, os, math
from mathutils import Vector, Quaternion, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo, common

args = sys.argv[sys.argv.index('--') + 1:]
SRC, OUT = args[0], args[1]
EXPORT = args[2] if len(args) > 2 else None
FOOT_FLAT = True          # bend the foot pom forward like a shoe in the reference pose
P = 'mixamorig'

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
scene = bpy.context.scene
src_arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
for o in [o for o in bpy.data.objects if o.type in ('CAMERA', 'LIGHT')]:
    bpy.data.objects.remove(o)
print('FPS', scene.render.fps)

# ---------------------------------------------------------------- mesh clean
me = mesh.data
for m in list(mesh.modifiers):
    mesh.modifiers.remove(m)
mesh.vertex_groups.clear()
mesh.parent = None
me.transform(mesh.matrix_world)
mesh.matrix_world = Matrix.Identity(4)
bm = bmesh.new(); bm.from_mesh(me)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
bm.normal_update()
bm.to_mesh(me); bm.free()
for a in list(me.attributes):
    if a.name in ('custom_normal', 'sharp_face', 'sharp_edge'):
        me.attributes.remove(a)
for p in me.polygons:
    p.use_smooth = True
me.update()
co = [v.co.copy() for v in me.vertices]
NV = len(co)
adj = geo.graph(me, co)
print('VERTS', NV)

# ---------------------------------------------------------------- limbs
CX = 0.023
band = lambda lo, hi: [i for i in range(NV) if lo < co[i].z < hi]
seeds = {
    'armL': max(band(0.76, 0.88), key=lambda i: co[i].x),
    'armR': min(band(0.76, 0.88), key=lambda i: co[i].x),
    'legL': min((i for i in range(NV) if co[i].x > CX), key=lambda i: co[i].z),
    'legR': min((i for i in range(NV) if co[i].x < CX), key=lambda i: co[i].z),
    'tail': max(range(NV), key=lambda i: co[i].y),
}
#            pom_end, attach  (geodesic distance from the tip)
CUTS = {'armL': (0.100, 0.175), 'armR': (0.088, 0.140),
        'legL': (0.095, 0.215), 'legR': (0.100, 0.220), 'tail': (0.115, 0.170)}
dist = {k: geo.dijkstra(adj, [s], limit=0.3) for k, s in seeds.items()}


def cent(limb, d0, w=0.006):
    c = Vector(); n = 0
    for i, d in enumerate(dist[limb]):
        if abs(d - d0) < w:
            c += co[i]; n += 1
    return c / n


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)

in_limb = [False] * NV
for k, (pe, at) in CUTS.items():
    for i, d in enumerate(dist[k]):
        if d < at:
            in_limb[i] = True

# ---------------------------------------------------------------- torso axis
def slab(lo, hi):
    c = Vector(); n = 0
    for i in range(NV):
        if not in_limb[i] and lo < co[i].z < hi:
            c += co[i]; n += 1
    return c / n
lo_c, hi_c = slab(0.80, 0.825), slab(0.895, 0.92)
axis = (hi_c - lo_c).normalized()
at_z = lambda z: lo_c + axis * ((z - lo_c.z) / axis.z)
H0, NECK = at_z(0.79), at_z(0.935)
LT = (NECK - H0).length
print('TORSO axis', tuple(round(v, 3) for v in axis), 'lean deg', round(math.degrees(math.acos(axis.z)), 1),
      'H0', tuple(round(v, 3) for v in H0), 'NECK', tuple(round(v, 3) for v in NECK))
S = lambda p: (p - H0).dot(axis) / LT
spt = lambda s: H0 + axis * (s * LT)

# ---------------------------------------------------------------- joints
J = {}  # name -> (head, tail, parent)
J[P + 'Hips'] = (spt(0.05), spt(0.3), None)
J[P + 'Spine'] = (spt(0.3), spt(0.5), P + 'Hips')
J[P + 'Spine1'] = (spt(0.5), spt(0.7), P + 'Spine')
J[P + 'Spine2'] = (spt(0.7), spt(0.95), P + 'Spine1')
J[P + 'Neck'] = (spt(0.95), spt(1.08), P + 'Spine2')
J[P + 'Head'] = (spt(1.08), spt(1.08) + Vector((0, 0, 0.12)), P + 'Neck')
for side, k in (('Left', 'armL'), ('Right', 'armR')):
    pe, at = CUTS[k]
    a, e, w, tip = cent(k, at), cent(k, (at + pe) / 2), cent(k, pe), co[seeds[k]]
    sh = spt(S(a))
    sh = sh + (a - sh) * 0.35
    J[P + side + 'Shoulder'] = (sh, a, P + 'Spine2')
    J[P + side + 'Arm'] = (a, e, P + side + 'Shoulder')
    J[P + side + 'ForeArm'] = (e, w, P + side + 'Arm')
    J[P + side + 'Hand'] = (w, tip, P + side + 'ForeArm')
for side, k in (('Left', 'legL'), ('Right', 'legR')):
    pe, at = CUTS[k]
    a, e, w, tip = cent(k, at), cent(k, (at + pe) / 2), cent(k, pe), co[seeds[k]]
    J[P + side + 'UpLeg'] = (a, e, P + 'Hips')
    J[P + side + 'Leg'] = (e, w, P + side + 'UpLeg')
    J[P + side + 'Foot'] = (w, tip, P + side + 'Leg')
pe, at = CUTS['tail']
J['Tail'] = (cent('tail', at), co[seeds['tail']], P + 'Hips')
for n, (h, t, p) in J.items():
    print(f"JOINT {n:24s} {h.x:6.3f} {h.y:6.3f} {h.z:6.3f} -> {t.x:6.3f} {t.y:6.3f} {t.z:6.3f}")

arm_data = bpy.data.armatures.new('Marty')
arm = bpy.data.objects.new('Marty', arm_data)
scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
for n, (h, t, p) in J.items():
    b = arm_data.edit_bones.new(n)
    b.head, b.tail = h, t
    if p:
        b.parent = arm_data.edit_bones[p]
bpy.ops.object.mode_set(mode='OBJECT')
ORDER = list(J.keys())
R0 = {n: arm_data.bones[n].matrix_local.to_quaternion() for n in ORDER}
P0 = {n: arm_data.bones[n].head_local.copy() for n in ORDER}
PARENT = {n: J[n][2] for n in ORDER}

# ---------------------------------------------------------------- weights
W = [dict() for _ in range(NV)]
LIMB_BONES = {'armL': ('LeftArm', 'LeftForeArm', 'LeftHand'), 'armR': ('RightArm', 'RightForeArm', 'RightHand'),
              'legL': ('LeftUpLeg', 'LeftLeg', 'LeftFoot'), 'legR': ('RightUpLeg', 'RightLeg', 'RightFoot')}
SPINE = [(0.0, 'Hips'), (0.3, 'Spine'), (0.5, 'Spine1'), (0.75, 'Spine2'), (1.0, 'Neck'), (1.12, 'Head')]
for i in range(NV):
    w = W[i]
    left = 1.0
    for k, (pe, at) in CUTS.items():
        d = dist[k][i]
        if d > at + 0.03:
            continue
        if k == 'tail':
            f = 1 - smooth(at - 0.02, at + 0.03, d)
            w['Tail'] = f; left -= f
            continue
        up, lowr, hand = (P + b for b in LIMB_BONES[k])
        f_limb = 1 - smooth(at - 0.008, at + 0.022, d)
        mid, half = (at + pe) / 2, (at - pe) * 0.3
        f_low = 1 - smooth(mid - half, mid + half, d)
        f_hand = 1 - smooth(pe - 0.010, pe + 0.012, d)
        f_low = max(f_low, f_hand); f_limb = max(f_limb, f_low)
        w[hand] = f_hand; w[lowr] = f_low - f_hand; w[up] = f_limb - f_low
        left -= f_limb
    left = max(0.0, left)
    if left > 1e-4:
        s = S(co[i])
        if s <= SPINE[0][0]:
            w[P + 'Hips'] = w.get(P + 'Hips', 0) + left
        elif s >= SPINE[-1][0]:
            w[P + 'Head'] = w.get(P + 'Head', 0) + left
        else:
            for (s0, b0), (s1, b1) in zip(SPINE, SPINE[1:]):
                if s0 <= s <= s1:
                    t = smooth(s0, s1, s)
                    w[P + b0] = w.get(P + b0, 0) + left * (1 - t)
                    w[P + b1] = w.get(P + b1, 0) + left * t
                    break
    tot = sum(w.values())
    for b in list(w):
        w[b] /= tot
        if w[b] < 1e-3:
            del w[b]

groups = {n: mesh.vertex_groups.new(name=n) for n in ORDER}
for i, w in enumerate(W):
    for b, x in w.items():
        groups[b].add([i], x, 'REPLACE')
mesh.parent = arm
mod = mesh.modifiers.new('Armature', 'ARMATURE')
mod.object = arm

# debug colours: dominant bone
PAL = {}
def colour(name):
    if name not in PAL:
        h = (len(PAL) * 0.381966) % 1.0
        import colorsys
        PAL[name] = (*colorsys.hsv_to_rgb(h, 0.75, 1.0), 1.0)
    return PAL[name]
ca = me.color_attributes.new('seg', 'FLOAT_COLOR', 'POINT')
for i, w in enumerate(W):
    col = Vector((0, 0, 0, 0))
    for b, x in w.items():
        col += Vector(colour(b)) * x
    ca.data[i].color = col
me.color_attributes.active_color = ca

# ---------------------------------------------------------------- reference-pose corrections
def to_dir(name, target):
    h, t, _ = J[name]
    return (t - h).normalized().rotation_difference(Vector(target).normalized())
# The dance's rotations are already relative to the scan pose, so only the feet need a
# reference correction: the poms hang toe-down in the scan but should sit flat like shoes.
C = {n: Quaternion() for n in ORDER}
if FOOT_FLAT:
    for side in ('Left', 'Right'):
        C[P + side + 'Foot'] = to_dir(P + side + 'Foot', (0, -1, -0.12))

# ---------------------------------------------------------------- sample the source animation
F0, F1 = int(scene.frame_start), int(scene.frame_end)
act = bpy.data.actions[0]
F0, F1 = int(act.frame_range[0]), int(act.frame_range[1])
SRCNAME = {n: n.replace(P, P + ':') for n in ORDER if n != 'Tail'}
smw = src_arm.matrix_world
rest_q = {n: (smw @ src_arm.data.bones[s].matrix_local).to_3x3().normalized().to_quaternion() for n, s in SRCNAME.items()}
D, HIPS, SRCLOW = {}, {}, {}
for f in range(F0, F1 + 1):
    scene.frame_set(f)
    d = {}
    for n, s in SRCNAME.items():
        q = (smw @ src_arm.pose.bones[s].matrix).to_3x3().normalized().to_quaternion()
        d[n] = q @ rest_q[n].inverted()
    D[f] = d
    HIPS[f] = (smw @ src_arm.pose.bones[P + ':Hips'].matrix).translation.copy()
    SRCLOW[f] = min((smw @ src_arm.pose.bones[P + ':' + b].matrix).translation.z
                    for b in ('LeftFoot', 'RightFoot', 'LeftToeBase', 'RightToeBase'))
src_stand = SRCLOW[F0]
print('SRC hips standing', tuple(round(v, 3) for v in HIPS[F0]), 'low', round(src_stand, 3))

# ---------------------------------------------------------------- FK on the new skeleton
FEET = {}
for side, k in (('Left', 'legL'), ('Right', 'legR')):
    pe, _ = CUTS[k]
    ids = [i for i, d in enumerate(dist[k]) if d < pe - 0.01]
    FEET[P + side + 'Foot'] = [co[i] for i in ids[::4]]


def fk(rot, hips_pos):
    pos = {}
    for n in ORDER:
        p = PARENT[n]
        if p is None:
            pos[n] = hips_pos
        else:
            pos[n] = pos[p] + (rot[p] @ R0[p].inverted()) @ (P0[n] - P0[p])
    return pos


def low_point(rot, pos):
    z = 1e9
    for n, pts in FEET.items():
        m = rot[n] @ R0[n].inverted()
        for v in pts:
            z = min(z, (pos[n] + m @ (v - P0[n])).z)
    return z

ident = {n: C[n] @ R0[n] for n in ORDER}
HT = -low_point(ident, fk(ident, Vector((0, 0, 0))))
HS = HIPS[F0].z
SC = HT / HS
print('TARGET hips height', round(HT, 3), 'source', round(HS, 3), 'scale', round(SC, 3))

# The dance was made for a human and pitches his big head a long way forward; stand the
# top half up straighter from the waist so his feet stay flat on the floor.
UPRIGHT = Quaternion((1, 0, 0), -0.24)
UPPER = {P + b for b in ('Spine', 'Spine1', 'Spine2', 'Neck', 'Head')} | \
        {P + s + b for s in ('Left', 'Right') for b in ('Shoulder', 'Arm', 'ForeArm', 'Hand')}
ROT, POS, DZ = {}, {}, {}
for f in range(F0, F1 + 1):
    dh = D[f][P + 'Hips']
    lift = dh @ UPRIGHT @ dh.inverted()      # lean the top half back, in his own frame
    rot = {n: (lift if n in UPPER else Quaternion()) @ D[f][n] @ C[n] @ R0[n] for n in ORDER if n != 'Tail'}
    rot['Tail'] = D[f][P + 'Hips'] @ C['Tail'] @ R0['Tail']
    hp = Vector((HIPS[f].x * SC, HIPS[f].y * SC, HIPS[f].z * SC))
    pos = fk(rot, hp)
    DZ[f] = SC * (SRCLOW[f] - src_stand) - low_point(rot, pos)
    ROT[f], POS[f] = rot, pos
# smooth the grounding correction a touch so it never pops
for f in range(F0, F1 + 1):
    ns = [DZ[g] for g in range(max(F0, f - 1), min(F1, f + 1) + 1)]
    dz = sum(ns) / len(ns)
    for n in ORDER:
        POS[f][n] = POS[f][n] + Vector((0, 0, dz))

# ---------------------------------------------------------------- tail: a lazy pendulum
t_vec0 = J['Tail'][1] - J['Tail'][0]
TL = t_vec0.length
K, DAMP, SUB = 140.0, 7.0, 6
tip = vel = None
for rnd in range(2):                       # first pass only warms it up
    for f in range(F0, F1 + 1):
        base = POS[f]['Tail']
        want = (D[f][P + 'Hips'] @ C['Tail']) @ t_vec0
        if tip is None:
            tip, vel = base + want, Vector()
        dt = 1 / 30 / SUB
        for _ in range(SUB):
            acc = (base + want - tip) * K - vel * DAMP
            vel += acc * dt
            tip += vel * dt
            tip = base + (tip - base).normalized() * TL
        if rnd == 1:
            swing = want.normalized().rotation_difference((tip - base).normalized())
            ROT[f]['Tail'] = swing @ D[f][P + 'Hips'] @ C['Tail'] @ R0['Tail']

# ---------------------------------------------------------------- write keys
scene.render.fps = 30
scene.frame_start, scene.frame_end = F0, F1
bpy.data.objects.remove(src_arm)
for a in list(bpy.data.actions):
    bpy.data.actions.remove(a)
prev = {}
for pb in arm.pose.bones:
    pb.rotation_mode = 'QUATERNION'
for f in range(F0, F1 + 1):
    rot = ROT[f]
    for n in ORDER:
        pb = arm.pose.bones[n]
        p = PARENT[n]
        if p is None:
            q = R0[n].inverted() @ rot[n]
            pb.location = R0[n].inverted() @ (POS[f][n] - P0[n])
            pb.keyframe_insert('location', frame=f)
        else:
            q = (R0[p].inverted() @ R0[n]).inverted() @ (rot[p].inverted() @ rot[n])
        if n in prev and prev[n].dot(q) < 0:
            q = -q
        prev[n] = q
        pb.rotation_quaternion = q
        pb.keyframe_insert('rotation_quaternion', frame=f)
if arm.animation_data and arm.animation_data.action:
    arm.animation_data.action.name = 'Shuffle'

# ---------------------------------------------------------------- even him out
# The scan is lumpy and its texture has one tan side and one bluish side (the room's
# light, baked in). Smooth the surface without shrinking it, then re-bake the texture onto
# a fresh, tidy UV layout with the white fabric pulled to one even off-white all round.
import numpy as np
SMOOTH_ITERS = int(os.environ.get('SMOOTH', 30))
arm.data.pose_position = 'REST'
mod.show_viewport = mod.show_render = False
E = np.array([e.vertices[:] for e in me.edges])
deg = np.bincount(E.ravel(), minlength=NV).astype(np.float64)[:, None]


def nb_sum(a):
    out = np.zeros_like(a)
    np.add.at(out, E[:, 0], a[E[:, 1]])
    np.add.at(out, E[:, 1], a[E[:, 0]])
    return out

# --- per-vertex colour of the old texture
mat = me.materials[0]
old_node = next(n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE')
old_img = old_node.image
w, h = old_img.size
px = np.empty(w * h * 4, np.float32)
old_img.pixels.foreach_get(px)
k = 4
small = px.reshape(h, w, 4)[:, :, :3].reshape(h // k, k, w // k, k, 3).mean((1, 3))
del px
old_uv = me.uv_layers.active.name
uvd = me.uv_layers.active.data
vcol = np.zeros((NV, 3)); cnt = np.zeros((NV, 1))
sw, sh = w // k, h // k
for l in me.loops:
    u, v = uvd[l.index].uv
    vcol[l.vertex_index] += small[min(sh - 1, int((v % 1) * sh)), min(sw - 1, int((u % 1) * sw))]
    cnt[l.vertex_index] += 1
vcol /= np.maximum(cnt, 1)
vlin = np.where(vcol <= 0.04045, vcol / 12.92, ((vcol + 0.055) / 1.055) ** 2.4)
LUM = np.array([0.2126, 0.7152, 0.0722])
light = (vlin @ LUM) > 0.14
num = np.where(light[:, None], vlin, 0.0); den = light.astype(np.float64)[:, None]
for _ in range(120):                                   # spread the local "white" over the surface
    num = (num + nb_sum(num)) / (deg + 1)
    den = (den + nb_sum(den)) / (deg + 1)
field = num / np.maximum(den, 1e-9)
med = np.median(vlin[light], axis=0)
target = 0.4 * med + 0.6 * (med @ LUM)                 # mostly neutral, a little of his own warmth
gain = np.clip(target / np.maximum(field, 1e-4), 0.55, 2.0)
print('WHITE median', np.round(med, 3), 'target', np.round(target, 3), 'gain range', np.round(gain.min(0), 2), np.round(gain.max(0), 2))
ga = me.color_attributes.new('gain', 'FLOAT_COLOR', 'POINT')
ga.data.foreach_set('color', np.concatenate([gain / 2, np.ones((NV, 1))], axis=1).ravel())

# --- smooth the surface (Taubin: knocks out lumps, keeps the volume)
Pn = np.array([c[:] for c in co], dtype=np.float64)
for _ in range(SMOOTH_ITERS):
    for f in (0.5, -0.53):
        Pn += f * (nb_sum(Pn) / deg - Pn)
me.vertices.foreach_set('co', Pn.ravel())
me.update()

# --- new UVs and bake
bpy.context.view_layer.objects.active = mesh
mesh.select_set(True)
new_uv = me.uv_layers.new(name='bake')
me.uv_layers.active = new_uv
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
bpy.ops.object.mode_set(mode='OBJECT')

nt = mat.node_tree
for n in list(nt.nodes):
    if n != old_node:
        nt.nodes.remove(n)
N = nt.nodes.new
def vmath(op, a, b=None, scale=None):
    n = N('ShaderNodeVectorMath'); n.operation = op
    for i, x in enumerate((a, b)):
        if x is None: continue
        if hasattr(x, 'links') or hasattr(x, 'is_linked'): nt.links.new(x, n.inputs[i])
        else: n.inputs[i].default_value = x
    if scale is not None:
        if hasattr(scale, 'is_linked'): nt.links.new(scale, n.inputs['Scale'])
        else: n.inputs['Scale'].default_value = scale
    return n.outputs['Vector']
def bw(x):
    n = N('ShaderNodeRGBToBW'); nt.links.new(x, n.inputs[0]); return n.outputs[0]
uvn = N('ShaderNodeUVMap'); uvn.uv_map = old_uv
nt.links.new(uvn.outputs[0], old_node.inputs[0])
Cc = old_node.outputs['Color']
gn = N('ShaderNodeAttribute'); gn.attribute_name = 'gain'
G = vmath('SCALE', gn.outputs['Color'], scale=2.0)
A = vmath('MULTIPLY', Cc, G)
tint = tuple(float(x) for x in target / (target @ LUM))
Nn = vmath('SCALE', tint, scale=bw(A))
Lg = vmath('ADD', A, vmath('SCALE', vmath('SUBTRACT', Nn, A), scale=0.6))
mr = N('ShaderNodeMapRange'); mr.interpolation_type = 'SMOOTHSTEP'
nt.links.new(bw(Cc), mr.inputs[0]); mr.inputs[1].default_value = 0.07; mr.inputs[2].default_value = 0.22
res = vmath('ADD', Cc, vmath('SCALE', vmath('SUBTRACT', Lg, Cc), scale=mr.outputs[0]))
em = N('ShaderNodeEmission'); nt.links.new(res, em.inputs['Color'])
out_n = N('ShaderNodeOutputMaterial'); nt.links.new(em.outputs[0], out_n.inputs['Surface'])
TEX = int(os.environ.get('TEX', 2048))
new_img = bpy.data.images.new('marty', TEX, TEX, alpha=False)
bake_node = N('ShaderNodeTexImage'); bake_node.image = new_img
for n in nt.nodes: n.select = False
bake_node.select = True; nt.nodes.active = bake_node
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 8
scene.render.bake.margin = 16
scene.render.bake.use_clear = True
bpy.ops.object.bake(type='EMIT')
new_img.filepath_raw = f"{OUT}/marty-tex.png"; new_img.file_format = 'PNG'; new_img.save()

# --- plain material on the new texture
for n in list(nt.nodes):
    if n != bake_node:
        nt.nodes.remove(n)
bsdf = N('ShaderNodeBsdfPrincipled'); bsdf.inputs['Roughness'].default_value = 1.0
nt.links.new(bake_node.outputs['Color'], bsdf.inputs['Base Color'])
out_n = N('ShaderNodeOutputMaterial'); nt.links.new(bsdf.outputs[0], out_n.inputs['Surface'])
nt.nodes.active = bake_node
me.uv_layers.remove(me.uv_layers[old_uv])
me.color_attributes.remove(me.color_attributes['gain'])
bpy.data.images.remove(old_img)
mod.show_viewport = mod.show_render = True
mesh.select_set(False)

# ---------------------------------------------------------------- pictures
cam = common.setup_render(color='VERTEX')
paths = []
arm.data.pose_position = 'REST'
for name, d in (('front', (0, -1, 0)), ('left', (1, 0, 0)), ('back', (0, 1, 0)), ('right', (-1, 0, 0))):
    p = f"{OUT}/new_seg_{name}.png"; common.shot(cam, mesh, p, d); paths.append(p)
common.sheet(paths, f"{OUT}/new_seg_sheet.png", cols=4)
scene.display.shading.color_type = 'TEXTURE'
paths = []
for name, d in (('front', (0, -1, 0)), ('left', (1, 0, 0)), ('back', (0, 1, 0)), ('right', (-1, 0, 0))):
    p = f"{OUT}/new_rest_{name}.png"; common.shot(cam, mesh, p, d); paths.append(p)
common.sheet(paths, f"{OUT}/new_rest_sheet.png", cols=4)
arm.data.pose_position = 'POSE'
paths = []
for f in (35, 50, 65, 80, 95, 110):
    for name, d in (('front', (0, -1, 0.1)), ('left', (1, 0, 0.1))):
        p = f"{OUT}/new_f{f}_{name}.png"; common.shot(cam, mesh, p, d, frame=f); paths.append(p)
common.sheet(paths, f"{OUT}/new_sheet.png", cols=4)

if EXPORT:
    scene.frame_set(F0)
    bpy.data.objects.remove(cam)
    me.color_attributes.remove(me.color_attributes['seg'])
    bpy.ops.export_scene.gltf(filepath=EXPORT, export_format='GLB', export_yup=True,
                              export_animations=True, export_skins=True, export_image_format='JPEG',
                              export_jpeg_quality=88, export_force_sampling=True,
                              export_optimize_animation_size=False, export_all_influences=False)
    print('EXPORTED', EXPORT, os.path.getsize(EXPORT))
