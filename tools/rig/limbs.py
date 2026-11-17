"""Lay a kinked rope limb out straight, keeping its woven surface (numpy only, so it runs outside Blender).

straighten(pts, a, e, wr) -> new_pts, info
  pts: (n, 3) the limb's vertices; a, e, wr: rough attach, elbow and wrist points.
Every vertex keeps its offset from the rope's centre line, carried along as the centre line is pulled
straight from the attach point; the rope's width is evened out along it, and stray bits sticking out
(the scan's ragged cut ends) are pulled back in.
"""
import numpy as np


def sstep(a, b, v):
    t = np.clip((v - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def project(P, C, S):
    best_d = np.full(len(P), 1e9)
    best_s = np.zeros(len(P))
    for k in range(len(C) - 1):
        ab = C[k + 1] - C[k]
        L = max(float(ab @ ab), 1e-12)
        t = np.clip((P - C[k]) @ ab / L, 0, 1)
        d = np.linalg.norm(C[k] + t[:, None] * ab - P, axis=1)
        m = d < best_d
        best_d[m] = d[m]
        best_s[m] = S[k] + t[m] * (S[k + 1] - S[k])
    return best_s


def rot_between(u, v):
    """Rotation matrices taking unit vectors u[i] onto v (Rodrigues)."""
    v = np.broadcast_to(v, u.shape)
    ax = np.cross(u, v)
    s = np.linalg.norm(ax, axis=1)
    c = np.clip((u * v).sum(1), -1, 1)
    k = ax / np.maximum(s, 1e-12)[:, None]
    K = np.zeros((len(u), 3, 3))
    K[:, 0, 1], K[:, 0, 2], K[:, 1, 2] = -k[:, 2], k[:, 1], -k[:, 0]
    K[:, 1, 0], K[:, 2, 0], K[:, 2, 1] = k[:, 2], -k[:, 1], k[:, 0]
    I = np.eye(3)[None]
    return I + s[:, None, None] * K + (1 - c)[:, None, None] * (K @ K)


def straighten(pts, a, e, wr, nb=14, attach=0.012, lo=0.8, hi=1.15):
    a, e, wr = (np.asarray(x, float) for x in (a, e, wr))
    poly = np.array([a, e, wr])
    cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(poly, axis=0), axis=1))])
    s = project(pts, poly, cum)
    edges = np.linspace(0, s.max() + 1e-9, nb + 1)
    C = [a]
    for k in range(nb):
        m = (s >= edges[k]) & (s < edges[k + 1])
        C.append(pts[m].mean(0) if m.sum() > 8 else C[-1])
    C[1] = (C[0] + C[2]) / 2
    C = np.array(C)
    for _ in range(2):
        C[1:-1] = C[1:-1] * 0.5 + (C[:-2] + C[2:]) * 0.25
    S = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    s = project(pts, C, S)
    L = S[-1]
    cs = np.stack([np.interp(s, S, C[:, j]) for j in range(3)], 1)
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    tang = np.stack([np.interp(s, S, T[:, j]) for j in range(3)], 1)
    tang /= np.linalg.norm(tang, axis=1)[:, None]
    # the straight line: a best fit through the rope's centre (so it stays where it was on average),
    # starting level with the attach point
    Cm = C[1:].mean(0)
    D = np.linalg.svd(C[1:] - Cm)[2][0]
    if D @ (C[-1] - C[0]) < 0:
        D = -D
    a0 = Cm + D * ((a - Cm) @ D)
    off = pts - cs
    o = np.einsum('nij,nj->ni', rot_between(tang, D), off)     # offsets in the straight frame
    along = o @ D
    rad_v = o - along[:, None] * D
    rad = np.linalg.norm(rad_v, axis=1)
    mids = (S[:-1] + S[1:]) / 2
    rb = np.array([np.median(rad[(s >= S[k]) & (s <= S[k + 1])]) if ((s >= S[k]) & (s <= S[k + 1])).sum() > 8
                   else np.nan for k in range(len(S) - 1)])
    rb = np.where(np.isnan(rb), np.nanmedian(rb), rb)
    rt = float(np.median(rb[2:-1]))
    r_new = rad * (rt / np.interp(s, mids, rb))
    r_new = np.clip(r_new, lo * rt, hi * rt)                  # pull in stray fins, fill in dents
    along = np.clip(along, -0.4 * rt, 0.4 * rt)
    end = sstep(L - 0.006, L - 0.002, s)                     # a neat round cut end (the hand covers it)
    r_new = r_new + (0.9 * rt - r_new) * end
    along = along * (1 - end)
    sn = np.minimum(s, L)
    new = a0 + D * sn[:, None] + along[:, None] * D + rad_v / np.maximum(rad, 1e-9)[:, None] * r_new[:, None]
    blend = sstep(0.0, attach, s)
    out = pts + (new - pts) * blend[:, None]
    return out, dict(D=D, L=L, a0=a0, end_old=C[-1], end_new=a0 + D * L, rt=rt, s=s)
