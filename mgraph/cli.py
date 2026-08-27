from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .api import FlamsClient, FlamsError, default_scope_prefix, normalize_uri
from .graph import eliminate_dfs_back_edges
from .render import render_html
from .server import serve_html


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="mgraph",
        description=(
            "Query FLAMS definition cross-references, remove DFS back edges, "
            "and serve an interactive dependency DAG."
        ),
    )
    result.add_argument("uri", help="Raw FTML URI or MathHub viewer link")
    result.add_argument(
        "--server",
        default="https://mathhub.info",
        help="FLAMS server base URL or full query endpoint",
    )
    result.add_argument(
        "--scope-prefix",
        help="Only use definitions whose RDF URI starts with this prefix",
    )
    result.add_argument(
        "--no-auto-scope",
        action="store_true",
        help="Do not derive a scope prefix from the root archive",
    )
    result.add_argument(
        "--language",
        default="de",
        help="Definition URI language code; pass an empty string for any language",
    )
    result.add_argument("--timeout", type=float, default=30.0)
    result.add_argument("--batch-size", type=int, default=100)
    result.add_argument("--max-nodes", type=int, default=5_000)
    result.add_argument("--max-edges", type=int, default=25_000)
    result.add_argument(
        "--max-depth",
        type=int,
        help=(
            "Maximum dependency distance from the root (root is depth 0); "
            "nodes at the limit are shown but not expanded"
        ),
    )
    result.add_argument("--host", default="127.0.0.1")
    result.add_argument("--port", type=int, default=0, help="0 chooses a free port")
    result.add_argument("--no-open", action="store_true")
    result.add_argument("--save-html", type=Path)
    return result


def run(arguments: argparse.Namespace) -> int:
    root = normalize_uri(arguments.uri)
    scope = arguments.scope_prefix
    if scope is None and not arguments.no_auto_scope:
        scope = default_scope_prefix(root)
    language = arguments.language or None

    print(f"Root: {root}")
    print(f"Server: {arguments.server}")
    print(f"Scope: {scope or '(unrestricted)'}")
    print(f"Language: {language or '(any)'}")
    print(
        "Max depth: "
        + (str(arguments.max_depth) if arguments.max_depth is not None else "(unlimited)")
    )
    client = FlamsClient(arguments.server, timeout=arguments.timeout)
    closure = client.closure(
        root,
        scope_prefix=scope,
        language=language,
        batch_size=arguments.batch_size,
        max_nodes=arguments.max_nodes,
        max_edges=arguments.max_edges,
        max_depth=arguments.max_depth,
    )
    graph = eliminate_dfs_back_edges(root, closure.nodes, closure.edges)
    print(
        f"Retrieved {len(closure.nodes)} nodes and {len(closure.edges)} edges "
        f"in {closure.rounds} rounds"
    )
    print(
        f"DAG has {len(graph.edges)} edges; removed "
        f"{len(graph.removed_back_edges)} DFS back edges/self-loops"
    )
    definitions = client.definition_uris(
        graph.nodes,
        scope_prefix=scope,
        language=language,
        batch_size=arguments.batch_size,
    )
    definition_count = sum(len(uris) for uris in definitions.values())
    print(
        f"Resolved {definition_count} definition paragraphs for "
        f"{len(definitions)} nodes"
    )
    document = render_html(graph, definitions=definitions)
    if arguments.save_html:
        arguments.save_html.write_text(document, encoding="utf-8")
        print(f"Saved {arguments.save_html.resolve()}")
    serve_html(
        document,
        host=arguments.host,
        port=arguments.port,
        open_browser=not arguments.no_open,
        definition_loader=client.definition_fragment,
        allowed_definition_uris={
            uri for uris in definitions.values() for uri in uris
        },
    )
    return 0


def main(argv: list[str] | None = None) -> None:
    arguments = parser().parse_args(argv)
    try:
        raise SystemExit(run(arguments))
    except (FlamsError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
