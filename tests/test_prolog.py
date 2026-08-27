import unittest

from mgraph.api import DefinitionFragment
from mgraph.graph import PrunedGraph
from mgraph.prolog import (
    definition_verbalization,
    predicate_names,
    prologify,
    render_scasp,
)


class NamingTests(unittest.TestCase):
    def test_prologify(self) -> None:
        self.assertEqual(prologify("Association of Persons"), "association_of_persons")
        self.assertEqual(prologify("Öffentliches Register"), "offentliches_register")
        self.assertEqual(prologify("27 States"), "node_27_states")

    def test_colliding_names_get_deterministic_suffix(self) -> None:
        first = "http://example.test?m=A&s=Foo-Bar"
        second = "http://example.test?m=B&s=Foo Bar"
        names = predicate_names(frozenset({second, first}))
        self.assertEqual(names[first], "foo_bar")
        self.assertEqual(names[second], "foo_bar_2")


class RenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.a = "http://example.test?m=M&s=Root Node"
        self.b = "http://example.test?m=M&s=Child One"
        self.c = "http://example.test?m=M&s=Child Two"
        self.graph = PrunedGraph(
            root=self.a,
            nodes=frozenset({self.a, self.b, self.c}),
            edges=frozenset({(self.a, self.b), (self.a, self.c)}),
            removed_back_edges=frozenset(),
        )

    def test_renders_clauses_leaves_and_root_query(self) -> None:
        program = render_scasp(self.graph)
        self.assertIn(
            "root_node(X) :-\n"
            "    child_one(X),\n"
            "    child_two(X),\n"
            "    not_implemented(root_node, 1, X).",
            program,
        )
        self.assertIn(
            "child_one(X) :- not_implemented(child_one, 1, X).",
            program,
        )
        self.assertIn("not_implemented(root_node, 1, _).", program)
        self.assertIn("not_implemented(child_one, 1, _).", program)
        self.assertIn(
            "?- root_node(X), not_implemented(Node, Arity, X).", program
        )
        self.assertNotIn("throw(", program)

    def test_verbalization_replaces_definiendum_with_argument(self) -> None:
        fragment = DefinitionFragment(
            "definition",
            (),
            (
                '<div>A <span data-ftml-definiendum="'
                + self.a
                + '">root node</span> uses children.</div>'
            ),
        )
        program = render_scasp(self.graph, definitions={self.a: fragment})
        self.assertIn(
            "#pred root_node(X) :: 'A @(X) uses children.'.", program
        )

    def test_definiendum_matching_ignores_http_scheme(self) -> None:
        secure_uri = self.a.replace("http://", "https://")
        wording = definition_verbalization(
            f'<span data-ftml-definiendum="{secure_uri}">root</span> applies.',
            self.a,
        )
        self.assertEqual(wording, "@(X) applies.")

    def test_plain_definition_gets_argument_marker(self) -> None:
        self.assertEqual(
            definition_verbalization("<p>A definition.</p>", self.a),
            "@(X): A definition.",
        )


if __name__ == "__main__":
    unittest.main()
