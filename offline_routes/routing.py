"""Dijkstra shortest path over the fixture graph, exact integer meters."""

import heapq

from . import fixture


class UnknownLandmark(Exception):
    def __init__(self, landmark_id):
        super().__init__(landmark_id)
        self.landmark_id = landmark_id


def _adjacency(edges):
    adj = {}
    for a, b, m in edges:
        adj.setdefault(a, {})
        adj.setdefault(b, {})
        for u, v in ((a, b), (b, a)):
            if v not in adj[u] or m < adj[u][v]:
                adj[u][v] = m
    return adj


def shortest_path(from_id, to_id, nodes=fixture.NODES, edges=fixture.EDGES):
    """Return (distance_m, [node ids]) or None when unreachable.

    Raises UnknownLandmark for ids not in `nodes`. Ties are broken
    deterministically by (distance, node id), including predecessors.
    """
    ids = {n[0] for n in nodes}
    for i in (from_id, to_id):
        if not isinstance(i, str) or i not in ids:
            raise UnknownLandmark(i)
    adj = _adjacency(edges)
    dist = {from_id: 0}
    prev = {}
    settled = set()
    heap = [(0, from_id)]
    while heap:
        d, u = heapq.heappop(heap)
        if u in settled:
            continue
        settled.add(u)
        if u == to_id:
            break
        for v, w in adj.get(u, {}).items():
            if v in settled:
                continue
            nd = d + w
            if v not in dist or nd < dist[v] or (nd == dist[v] and u < prev[v]):
                better = v not in dist or nd < dist[v]
                dist[v] = nd
                prev[v] = u
                if better:
                    heapq.heappush(heap, (nd, v))
    if to_id not in settled:
        return None
    path = [to_id]
    while path[-1] != from_id:
        path.append(prev[path[-1]])
    path.reverse()
    return dist[to_id], path


def _edge_meters(a, b):
    return _adjacency(fixture.EDGES)[a][b]


def compute_route(from_id, to_id):
    """Compute the route response body (see contract POST /api/v1/route)."""
    names = fixture.NODE_NAMES
    found = shortest_path(from_id, to_id)
    if found is None:
        return {
            "reachable": False,
            "from": from_id,
            "to": to_id,
            "distance_m": None,
            "path": [],
            "steps": [],
            "message": f"No route from {names[from_id]} to {names[to_id]}",
        }
    total, path = found
    if len(path) == 1:
        steps = [f"Already at {names[from_id]}"]
    else:
        steps = [f"Start at {names[path[0]]}"]
        for a, b in zip(path, path[1:]):
            steps.append(
                f"Go from {names[a]} to {names[b]} ({_edge_meters(a, b)} m)"
            )
        steps.append(f"Arrive at {names[to_id]}: {total} m total")
    return {
        "reachable": True,
        "from": from_id,
        "to": to_id,
        "distance_m": total,
        "path": path,
        "steps": steps,
    }
