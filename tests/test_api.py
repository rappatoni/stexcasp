import unittest
from unittest.mock import patch

from mgraph.api import (
    FlamsClient,
    content_endpoint_for,
    default_scope_prefix,
    definition_query,
    dependency_query,
    normalize_uri,
)


ROOT = "http://mathhub.info?a=JLogic/smglol/Commercial-Law&p=mod&m=Kaufmann&s=Kaufmann"


class UriTests(unittest.TestCase):
    def test_raw_uri(self) -> None:
        self.assertEqual(normalize_uri(ROOT), ROOT)

    def test_viewer_link(self) -> None:
        link = (
            "https://mathhub.info/?uri="
            "http%3A%2F%2Fmathhub.info%3Fa%3DJLogic%2Fsmglol%2FCommercial-Law"
            "%26p%3Dmod%26m%3DKaufmann%26s%3DKaufmann"
        )
        self.assertEqual(normalize_uri(link), ROOT)

    def test_default_scope(self) -> None:
        self.assertEqual(
            default_scope_prefix(ROOT),
            "http://mathhub.info?a=JLogic/smglol/",
        )

    def test_query_has_scope_and_language(self) -> None:
        query = dependency_query(
            [ROOT],
            scope_prefix="http://mathhub.info?a=JLogic/smglol/",
            language="de",
        )
        self.assertIn("ulo:defines", query)
        self.assertIn("ulo:crossrefs", query)
        self.assertIn("JLogic/smglol/", query)
        self.assertIn("&l=de", query)

    def test_definition_query_returns_exact_paragraph_uri(self) -> None:
        query = definition_query(
            [ROOT],
            scope_prefix="http://mathhub.info?a=JLogic/smglol/",
            language="de",
        )
        self.assertIn("SELECT DISTINCT ?symbol ?definition", query)
        self.assertIn("?definition ulo:defines ?symbol", query)
        self.assertIn("&l=de", query)

    def test_content_endpoint_from_query_endpoint(self) -> None:
        self.assertEqual(
            content_endpoint_for("http://localhost:3000/api/backend/query"),
            "http://localhost:3000/content/fragment",
        )


class FakeClient(FlamsClient):
    def __init__(self, adjacency: dict[str, set[str]]) -> None:
        self.adjacency = adjacency

    def direct_dependencies(self, sources, **kwargs):
        return {
            (source, target)
            for source in sources
            for target in self.adjacency.get(source, set())
        }


class DefinitionClient(FlamsClient):
    def __init__(self) -> None:
        super().__init__("http://example.test")

    def query(self, sparql):
        return [
            {
                "symbol": {"value": "A"},
                "definition": {"value": "definition-2"},
            },
            {
                "symbol": {"value": "A"},
                "definition": {"value": "definition-1"},
            },
        ]


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'["definition-1", [{"Link": "style.css"}], "<p>Definition</p>"]'


class ClosureTests(unittest.TestCase):
    def test_closure_keeps_diamond_edges(self) -> None:
        client = FakeClient(
            {"A": {"B", "C"}, "B": {"D"}, "C": {"D"}, "D": {"A"}}
        )
        closure = client.closure(
            "A", scope_prefix=None, language=None, batch_size=10
        )
        self.assertEqual(closure.nodes, frozenset({"A", "B", "C", "D"}))
        self.assertIn(("B", "D"), closure.edges)
        self.assertIn(("C", "D"), closure.edges)
        self.assertIn(("D", "A"), closure.edges)

    def test_max_depth_stops_before_expanding_boundary(self) -> None:
        client = FakeClient(
            {
                "A": {"B", "C"},
                "B": {"D"},
                "C": {"D"},
                "D": {"A", "E"},
            }
        )
        closure = client.closure(
            "A",
            scope_prefix=None,
            language=None,
            batch_size=10,
            max_depth=2,
        )
        self.assertEqual(closure.nodes, frozenset({"A", "B", "C", "D"}))
        self.assertEqual(
            closure.edges,
            frozenset({("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")}),
        )
        self.assertEqual(closure.rounds, 2)

    def test_max_depth_zero_returns_only_root(self) -> None:
        client = FakeClient({"A": {"B"}})
        closure = client.closure(
            "A", scope_prefix=None, language=None, max_depth=0
        )
        self.assertEqual(closure.nodes, frozenset({"A"}))
        self.assertEqual(closure.edges, frozenset())
        self.assertEqual(closure.rounds, 0)

    def test_negative_max_depth_is_rejected(self) -> None:
        client = FakeClient({})
        with self.assertRaisesRegex(ValueError, "max_depth must be non-negative"):
            client.closure(
                "A", scope_prefix=None, language=None, max_depth=-1
            )


class DefinitionTests(unittest.TestCase):
    def test_definition_uris_are_grouped_and_sorted(self) -> None:
        definitions = DefinitionClient().definition_uris(
            ["A"], scope_prefix=None, language=None
        )
        self.assertEqual(
            definitions, {"A": ("definition-1", "definition-2")}
        )

    @patch("urllib.request.urlopen", return_value=FakeResponse())
    def test_definition_fragment(self, urlopen) -> None:
        fragment = DefinitionClient().definition_fragment("definition-1")
        self.assertEqual(fragment.uri, "definition-1")
        self.assertEqual(fragment.css, ({"Link": "style.css"},))
        self.assertEqual(fragment.html, "<p>Definition</p>")
        self.assertIn("uri=definition-1", urlopen.call_args.args[0].full_url)


if __name__ == "__main__":
    unittest.main()
