"""Geometry helpers: mesh graph, geodesic distance, limb tracing."""
import heapq
from mathutils import Vector


def graph(me, co):
    adj = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        d = (co[a] - co[b]).length
        adj[a].append((b, d))
        adj[b].append((a, d))
    return adj


def dijkstra(adj, seeds, limit=float('inf')):
    dist = [float('inf')] * len(adj)
    pq = []
    for s in seeds:
        dist[s] = 0.0
        pq.append((0.0, s))
    heapq.heapify(pq)
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u] or d > limit:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def components(adj):
    comp = [-1] * len(adj)
    n = 0
    for i in range(len(adj)):
        if comp[i] >= 0:
            continue
        stack = [i]
        comp[i] = n
        while stack:
            u = stack.pop()
            for v, _ in adj[u]:
                if comp[v] < 0:
                    comp[v] = n
                    stack.append(v)
        n += 1
    return comp, n


def bands(co, dist, width, maxd):
    """Per geodesic band from the seed: (d, count, extent, centroid)."""
    out = []
    n = int(maxd / width)
    buckets = [[] for _ in range(n)]
    for i, d in enumerate(dist):
        k = int(d / width)
        if k < n:
            buckets[k].append(i)
    for k, b in enumerate(buckets):
        if not b:
            out.append((k * width, 0, 0.0, None))
            continue
        c = Vector((0, 0, 0))
        for i in b:
            c += co[i]
        c /= len(b)
        ext = 2 * max((co[i] - c).length for i in b)
        out.append((k * width, len(b), ext, c))
    return out
