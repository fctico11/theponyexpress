"""Small geometry helpers: ellipsoids, smooth paths, tubes and three-strand rope, smoothing."""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix


def ellipsoid(bm, c, r, rot=None, segs=(40, 24)):
    m = Matrix.Translation(c) @ (rot.to_matrix().to_4x4() if rot is not None else Matrix.Identity(4)) @ \
        Matrix.Diagonal((*r, 1))
    bmesh.ops.create_uvsphere(bm, u_segments=segs[0], v_segments=segs[1], radius=1.0, matrix=m)


def catmull(pts, n):
    pts = [pts[0] * 2 - pts[1]] + list(pts) + [pts[-1] * 2 - pts[-2]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1:i + 3]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-2])
    return out


def resample(path, step):
    d = [0.0]
    for a, b in zip(path, path[1:]):
        d.append(d[-1] + (b - a).length)
    n = max(2, int(d[-1] / step) + 1)
    out, j = [], 0
    for k in range(n):
        s = d[-1] * k / (n - 1)
        while j < len(d) - 2 and d[j + 1] < s:
            j += 1
        t = (s - d[j]) / max(1e-9, d[j + 1] - d[j])
        out.append(path[j].lerp(path[j + 1], t))
    return out


def frames(path):
    T = [(path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized() for i in range(len(path))]
    up = Vector((1, 0, 0)) if abs(T[0].x) < 0.9 else Vector((0, -1, 0))
    N = [(up - T[0] * up.dot(T[0])).normalized()]
    for i in range(1, len(path)):
        N.append((N[-1] - T[i] * N[-1].dot(T[i])).normalized())
    return T, N


def tube(bm, pts, radius, ring=8, taper=None):
    T, N = frames(pts)
    rings = []
    for i, (p, t, n) in enumerate(zip(pts, T, N)):
        b = t.cross(n)
        r = radius * (taper(i / (len(pts) - 1)) if taper else 1)
        rings.append([bm.verts.new(p + (n * math.cos(a) + b * math.sin(a)) * r)
                      for a in (2 * math.pi * k / ring for k in range(ring))])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(ring):
            bm.faces.new((r0[k], r0[(k + 1) % ring], r1[(k + 1) % ring], r1[k]))
    for r, flip in ((rings[0], True), (rings[-1], False)):
        c = bm.verts.new(sum((v.co for v in r), Vector()) / ring)
        for k in range(ring):
            bm.faces.new((r[k], r[(k + 1) % ring], c) if not flip else (r[(k + 1) % ring], r[k], c))


def rope(bm, ctrl, rope_r, strand_r, pitch, phase=0.0):
    path = resample(catmull(ctrl, 12), 0.0015)
    T, N = frames(path)
    off = rope_r - strand_r * 0.85
    for s in range(3):
        pts, acc = [], 0.0
        for i, (p, t, n) in enumerate(zip(path, T, N)):
            if i:
                acc += (p - path[i - 1]).length
            a = phase + 2 * math.pi * (s / 3 + acc / pitch)
            pts.append(p + (n * math.cos(a) + t.cross(n) * math.sin(a)) * off)
        tube(bm, pts, strand_r)


def obj_from(bm, name, attrs):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    for k, v in attrs.items():
        a = me.attributes.get(k) or me.attributes.new(k, 'FLOAT', 'POINT')
        a.data.foreach_set('value', [float(v)] * len(me.vertices))
    return o


def taubin(me, iters, lam=0.5, mu=-0.53, weight=None):
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    E = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get('vertices', E)
    E = E.reshape(-1, 2)
    deg = np.maximum(np.bincount(E.ravel(), minlength=len(co)).astype(float), 1)[:, None]
    w = np.ones((len(co), 1)) if weight is None else weight[:, None]
    for _ in range(iters):
        for f in (lam, mu):
            s = np.zeros_like(co)
            np.add.at(s, E[:, 0], co[E[:, 1]])
            np.add.at(s, E[:, 1], co[E[:, 0]])
            co += f * w * (s / deg - co)
    me.vertices.foreach_set('co', co.ravel())
    me.update()


def select_only(o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def sstep(a, b, v):
    t = np.clip((v - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def to_srgb(c):
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0), 1 / 2.4) - 0.055)
