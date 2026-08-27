import unittest

from mgraph.graph import eliminate_dfs_back_edges


class BackEdgeTests(unittest.TestCase):
    def test_removes_back_edge_but_preserves_diamond(self) -> None:
        edges = {
            ("A", "B"),
            ("A", "C"),
            ("B", "D"),
            ("C", "D"),
            ("D", "A"),
        }
        graph = eliminate_dfs_back_edges("A", {"A", "B", "C", "D"}, edges)
        self.assertEqual(graph.removed_back_edges, frozenset({("D", "A")}))
        self.assertIn(("B", "D"), graph.edges)
        self.assertIn(("C", "D"), graph.edges)

    def test_removes_self_loop(self) -> None:
        graph = eliminate_dfs_back_edges("A", {"A"}, {("A", "A")})
        self.assertEqual(graph.edges, frozenset())
        self.assertEqual(graph.removed_back_edges, frozenset({("A", "A")}))

    def test_output_is_acyclic(self) -> None:
        edges = {
            ("A", "B"),
            ("B", "C"),
            ("C", "A"),
            ("A", "D"),
            ("D", "C"),
        }
        graph = eliminate_dfs_back_edges("A", {"A", "B", "C", "D"}, edges)
        adjacency = {node: [] for node in graph.nodes}
        indegree = {node: 0 for node in graph.nodes}
        for source, target in graph.edges:
            adjacency[source].append(target)
            indegree[target] += 1
        queue = [node for node, degree in indegree.items() if degree == 0]
        visited = 0
        while queue:
            source = queue.pop()
            visited += 1
            for target in adjacency[source]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        self.assertEqual(visited, len(graph.nodes))


if __name__ == "__main__":
    unittest.main()

