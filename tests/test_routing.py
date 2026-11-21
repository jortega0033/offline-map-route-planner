import unittest

from offline_routes import fixture, routing


class RoutingTests(unittest.TestCase):
    def test_depot_to_observatory(self):
        r = routing.compute_route("depot", "observatory")
        self.assertEqual(
            r,
            {
                "reachable": True,
                "from": "depot",
                "to": "observatory",
                "distance_m": 120,
                "path": ["depot", "library", "observatory"],
                "steps": [
                    "Start at Depot",
                    "Go from Depot to Library (70 m)",
                    "Go from Library to Observatory (50 m)",
                    "Arrive at Observatory: 120 m total",
                ],
            },
        )

    def test_reverse_is_symmetric(self):
        r = routing.compute_route("observatory", "depot")
        self.assertEqual(r["distance_m"], 120)
        self.assertEqual(r["path"], ["observatory", "library", "depot"])

    def test_unreachable_island(self):
        for src in ("depot", "library", "observatory"):
            r = routing.compute_route(src, "island")
            self.assertFalse(r["reachable"])
            self.assertIsNone(r["distance_m"])
            self.assertEqual(r["path"], [])
            self.assertEqual(r["steps"], [])
        self.assertEqual(
            routing.compute_route("depot", "island")["message"],
            "No route from Depot to Island",
        )
        self.assertFalse(routing.compute_route("island", "depot")["reachable"])

    def test_same_node(self):
        r = routing.compute_route("library", "library")
        self.assertTrue(r["reachable"])
        self.assertEqual(r["distance_m"], 0)
        self.assertEqual(r["path"], ["library"])
        self.assertEqual(r["steps"], ["Already at Library"])
        island = routing.compute_route("island", "island")
        self.assertTrue(island["reachable"])
        self.assertEqual(island["distance_m"], 0)

    def test_unknown_landmark(self):
        with self.assertRaises(routing.UnknownLandmark):
            routing.compute_route("depot", "nowhere")
        with self.assertRaises(routing.UnknownLandmark):
            routing.compute_route("nowhere", "depot")

    def test_direct_edge_not_shorter(self):
        self.assertEqual(routing.shortest_path("depot", "observatory"), (120, ["depot", "library", "observatory"]))
        self.assertEqual(routing.shortest_path("depot", "library"), (70, ["depot", "library"]))

    def test_tie_break_is_deterministic(self):
        nodes = (("a", "A", 0, 0), ("b", "B", 0, 0), ("c", "C", 0, 0), ("d", "D", 0, 0))
        edges = (("a", "c", 1), ("c", "d", 1), ("a", "b", 1), ("b", "d", 1))
        for _ in range(3):
            self.assertEqual(routing.shortest_path("a", "d", nodes, edges), (2, ["a", "b", "d"]))

    def test_parallel_edges_use_minimum(self):
        nodes = (("a", "A", 0, 0), ("b", "B", 0, 0))
        edges = (("a", "b", 9), ("b", "a", 4))
        self.assertEqual(routing.shortest_path("a", "b", nodes, edges), (4, ["a", "b"]))

    def test_graph_payload(self):
        g = fixture.graph_payload()
        self.assertEqual(g["id"], "fixture-v1")
        self.assertEqual((g["width"], g["height"]), (400, 260))
        self.assertEqual([n["id"] for n in g["nodes"]], ["depot", "library", "observatory", "island"])
        self.assertEqual(
            g["edges"][0], {"id": "depot-library", "from": "depot", "to": "library", "meters": 70}
        )
        self.assertEqual(len(g["edges"]), 3)


if __name__ == "__main__":
    unittest.main()
