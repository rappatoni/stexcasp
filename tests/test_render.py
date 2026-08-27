import unittest

from mgraph.graph import PrunedGraph
from mgraph.render import render_html


class RenderTests(unittest.TestCase):
    def test_document_embeds_graph_and_d3(self) -> None:
        graph = PrunedGraph(
            root="http://example.test?a=scope/archive&m=M&s=A",
            nodes=frozenset(
                {
                    "http://example.test?a=scope/archive&m=M&s=A",
                    "http://example.test?a=scope/archive&m=M&s=B",
                }
            ),
            edges=frozenset(
                {
                    (
                        "http://example.test?a=scope/archive&m=M&s=A",
                        "http://example.test?a=scope/archive&m=M&s=B",
                    )
                }
            ),
            removed_back_edges=frozenset(),
        )
        document = render_html(
            graph,
            definitions={
                "http://example.test?a=scope/archive&m=M&s=A": [
                    "http://example.test?a=scope/archive&d=A&l=en&e=definition"
                ]
            },
        )
        self.assertIn("d3@7.9.0", document)
        self.assertIn('"label":"A"', document)
        self.assertIn('"label":"B"', document)
        self.assertIn('"links":[{"source":', document)
        self.assertIn('DATA.links.length+" edges', document)
        self.assertIn("layered by shortest-path distance from the root", document)
        self.assertIn("const layout=arrangeLayers", document)
        self.assertIn('node.y=top+layer.depth*layerGap', document)
        self.assertNotIn("forceSimulation", document)
        self.assertIn('"definitions":["http://example.test?', document)
        self.assertIn('id="definition-body"', document)
        self.assertIn('fetch("/api/definition?"', document)


if __name__ == "__main__":
    unittest.main()
