"""Marty in a symmetrical T-pose, as a plain textured mesh (no skeleton) for Mixamo's auto-rigger.

blender --background --python tpose.py -- <marty-shuffle.glb> <out.fbx> [preview.png]

Takes the rigged model, poses it (arms straight out sideways, legs straight down), bakes that pose
into the mesh, drops the skeleton and writes an FBX with the texture embedded.
"""
import bpy, sys, os
from mathutils import Vector, Matrix

args = sys.argv[sys.argv.index('--') + 1:]
src, out = args[0], args[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.vertices))
if arm.animation_data:
    arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.location = (0, 0, 0)
bpy.context.view_layer.update()

P = 'mixamorig'
to_arm = arm.matrix_world.inverted().to_3x3()


def aim(name, world_dir):
    """Turn a bone (and so everything below it) so it points along world_dir."""
    pb = arm.pose.bones[name]
    cur = (pb.tail - pb.head).normalized()
    want = (to_arm @ Vector(world_dir)).normalized()
    q = cur.rotation_difference(want)
    h = pb.head.copy()
    pb.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ pb.matrix
    bpy.context.view_layer.update()


for side, sx in (('Left', 1), ('Right', -1)):
    for b in ('UpLeg', 'Leg'):
        aim(P + side + b, (0, 0, -1))
# the arms are raised below, by hand, with the bend spread over the shoulder: where each arm runs
ARMS = {}
for side, sx in (('Left', 1), ('Right', -1)):
    bn = arm.data.bones
    ARMS[sx] = (arm.matrix_world @ bn[P + side + 'Arm'].head_local, arm.matrix_world @ bn[P + side + 'Hand'].tail_local)

# glTF splits vertices along texture seams; weld them back so smoothing can't tear the surface
import bmesh, numpy as np
bm = bmesh.new(); bm.from_mesh(mesh.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
bm.to_mesh(mesh.data); bm.free()
# how much each vertex follows an arm: the skin around the shoulder seam is part body, part arm
gi = {g.index: g.name for g in mesh.vertex_groups}
armw = np.zeros(len(mesh.data.vertices))
for v in mesh.data.vertices:
    for g in v.groups:
        if gi[g.group].endswith(('LeftArm', 'RightArm', 'LeftShoulder', 'RightShoulder')):
            armw[v.index] += g.weight
seam = np.clip(4 * armw * (1 - armw), 0, 1)
chainw = {1: np.zeros(len(mesh.data.vertices)), -1: np.zeros(len(mesh.data.vertices))}
for v in mesh.data.vertices:
    for g in v.groups:
        nm = gi[g.group]
        for side, sx in (('Left', 1), ('Right', -1)):
            if nm in (P + side + 'Arm', P + side + 'ForeArm', P + side + 'Hand'):
                chainw[sx][v.index] += g.weight

# bake the pose into the mesh and drop the skeleton
bpy.context.view_layer.objects.active = mesh
for o in bpy.context.selected_objects:
    o.select_set(False)
mesh.select_set(True)
mod = next(m for m in mesh.modifiers if m.type == 'ARMATURE')
bpy.ops.object.modifier_apply(modifier=mod.name)
mw = mesh.matrix_world.copy()
mesh.parent = None
mesh.matrix_world = mw
for o in [o for o in bpy.data.objects if o != mesh]:
    bpy.data.objects.remove(o)
mesh.vertex_groups.clear()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Raise each arm straight out sideways, turning it where it meets the body, then lay the first few
# centimetres of rope (which still lean the way the arm used to hang) onto the same straight line, so the
# arm comes straight out of his side with no dip and no elbow.
CO = np.array([v.co[:] for v in mesh.data.vertices])
bendw = np.zeros(len(CO))
B0, B1 = float(os.environ.get('BEND_FROM', -0.014)), float(os.environ.get('BEND_TO', 0.014))
for sx, (h, t) in ARMS.items():
    h, t = np.array(h), np.array(t)
    d0 = (t - h) / np.linalg.norm(t - h)
    want = np.array([sx, 0.0, 0.0])
    axis = np.cross(d0, want); axis /= np.linalg.norm(axis)
    theta = np.arccos(np.clip(d0 @ want, -1, 1))
    tt = (CO - h) @ d0
    w = np.clip((tt - B0) / (B1 - B0), 0, 1); w = w * w * (3 - 2 * w)
    follow = np.clip(chainw[sx] * 2, 0, 1)                # only what follows the arm
    w *= follow
    m = w > 0
    rel = CO[m] - h
    ang = theta * w[m]
    c, s_ = np.cos(ang)[:, None], np.sin(ang)[:, None]
    k = axis[None]
    CO[m] = h + rel * c + np.cross(k, rel) * s_ + k * (rel @ axis)[:, None] * (1 - c)
    # straighten the root: centre of each thin slice of rope onto the line out from the shoulder
    tw = (CO - h) @ want
    radv = (CO - h) - tw[:, None] * want
    rope = (chainw[sx] > 0.5) & (tw > -0.004) & (tw < 0.075)
    edges_ = np.arange(-0.004, 0.0751, 0.004)
    mids, cents = [], []
    for a_, b_ in zip(edges_[:-1], edges_[1:]):
        sl = rope & (tw >= a_) & (tw < b_)
        if sl.sum() > 6:
            mids.append((a_ + b_) / 2); cents.append(radv[sl].mean(0))
    mids, cents = np.array(mids), np.array(cents)
    corr = -np.stack([np.interp(tw, mids, cents[:, j_]) for j_ in range(3)], 1)
    ramp = np.clip((tw + 0.002) / 0.014, 0, 1); ramp = ramp * ramp * (3 - 2 * ramp)
    fade = 1 - np.clip((tw - 0.06) / 0.015, 0, 1)
    wc = ramp * fade * follow * (tw > -0.006)
    CO += corr * wc[:, None]
    # and even out its width right up to the shoulder, so the top line runs straight (no bump)
    tw = (CO - h) @ want
    radv = (CO - h) - tw[:, None] * want
    rr = np.linalg.norm(radv, axis=1)
    rope = (chainw[sx] > 0.5)
    rt = float(np.median(rr[rope & (tw > 0.03) & (tw < 0.055)]))
    cap = rt * float(os.environ.get('ROOT_CAP', 1.0))
    ramp2 = np.clip((tw + 0.004) / 0.010, 0, 1); ramp2 = ramp2 * ramp2 * (3 - 2 * ramp2)
    w2 = ramp2 * (tw < 0.06) * follow
    r_new = rr + (np.minimum(rr, cap) - rr) * w2
    CO = h + tw[:, None] * want + radv / np.maximum(rr, 1e-9)[:, None] * r_new[:, None]
    print('TPOSE arm', sx, 'raised', round(float(np.degrees(theta)), 1), 'deg; root straightened by up to',
          round(float(np.linalg.norm(cents, axis=1).max()) * 1000, 1), 'mm')
    bendw = np.maximum(bendw, np.clip(4 * w * (1 - w), 0, 1) * (w > 0))
    bendw = np.maximum(bendw, (follow > 0) * (follow < 1) * 1.0)
mesh.data.vertices.foreach_set('co', CO.ravel()); mesh.data.update()
# then relax the skin around the shoulder seam
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shapes import taubin
grow = np.maximum(seam, bendw)
E = np.array([e.vertices[:] for e in mesh.data.edges])
for _ in range(4):                                   # widen the band a little
    g2 = grow.copy(); np.maximum.at(g2, E[:, 0], grow[E[:, 1]] * 0.8); np.maximum.at(g2, E[:, 1], grow[E[:, 0]] * 0.8); grow = g2
taubin(mesh.data, int(os.environ.get('SEAM_SMOOTH', 100)), weight=np.clip(grow, 0, 1))
print('TPOSE relaxed', int((grow > 0.2).sum()), 'shoulder verts')
for ca in list(mesh.data.color_attributes):
    mesh.data.color_attributes.remove(ca)
mesh.name = mesh.data.name = 'Marty'

# feet on the ground, centred
co = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
xs = [c.x for c in co]; zs = [c.z for c in co]
shift = Vector((-(min(xs) + max(xs)) / 2, 0, -min(zs)))
mesh.data.transform(Matrix.Translation(shift))
co = [v.co for v in mesh.data.vertices]
print('TPOSE bounds x %.3f..%.3f  y %.3f..%.3f  z %.3f..%.3f' % (
    min(c.x for c in co), max(c.x for c in co), min(c.y for c in co), max(c.y for c in co),
    min(c.z for c in co), max(c.z for c in co)))

# Give the texture a real file name (the web model's has none): Mixamo only picks up an embedded texture
# whose name ends in .jpg or .png.
import tempfile
tex_dir = tempfile.mkdtemp(prefix='marty-skin-')
for img in bpy.data.images:
    if not (img.packed_file or img.has_data):
        continue
    data = img.packed_file.data if img.packed_file else None
    ext = '.jpg' if (data[:3] == b'\xff\xd8\xff' if data else img.file_format == 'JPEG') else '.png'
    path = os.path.join(tex_dir, 'marty-skin' + ext)
    if data:
        open(path, 'wb').write(data)
    else:
        img.filepath_raw = path; img.save()
    img.name = 'marty-skin'
    img.filepath = path
    print('TPOSE texture', path, img.size[:])
bpy.ops.export_scene.fbx(filepath=out, use_selection=False, object_types={'MESH'},
                         path_mode='COPY', embed_textures=True, add_leaf_bones=False,
                         apply_scale_options='FBX_SCALE_ALL', mesh_smooth_type='FACE')
print('TPOSE wrote', out, os.path.getsize(out))

if len(args) > 2:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import common
    cam = common.setup_render(900, 640)
    common.shot(cam, mesh, args[2], (0, -1, 0))
