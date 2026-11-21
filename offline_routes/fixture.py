"""Built-in fixture graph (id fixture-v1)."""

GRAPH_ID = "fixture-v1"
WIDTH = 400
HEIGHT = 260

# (id, name, x, y)
NODES = (
    ("depot", "Depot", 60, 190),
    ("library", "Library", 190, 80),
    ("observatory", "Observatory", 340, 190),
    ("island", "Island", 330, 40),
)

# (from, to, meters); undirected
EDGES = (
    ("depot", "library", 70),
    ("library", "observatory", 50),
    ("depot", "observatory", 165),
)

NODE_NAMES = {n[0]: n[1] for n in NODES}


def graph_payload() -> dict:
    """Return the JSON-serialisable graph exactly as served by GET /api/v1/graph."""
    return {
        "id": GRAPH_ID,
        "width": WIDTH,
        "height": HEIGHT,
        "nodes": [{"id": i, "name": n, "x": x, "y": y} for i, n, x, y in NODES],
        "edges": [
            {"id": f"{a}-{b}", "from": a, "to": b, "meters": m} for a, b, m in EDGES
        ],
    }
