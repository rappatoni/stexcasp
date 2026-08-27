from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .api import (
    DefinitionFragment,
    FlamsClient,
    FlamsError,
    default_scope_prefix,
    normalize_uri,
)
from .graph import eliminate_dfs_back_edges
from .prolog import predicate_names, render_scasp


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="stexcasp",
        description=(
            "Generate an executable s(CASP)/Prolog program from a "
            "cycle-pruned FLAMS dependency graph."
        ),
    )
    result.add_argument("uri", help="Raw FTML URI or MathHub viewer link")
    result.add_argument("-o", "--output", type=Path)
    result.add_argument(
        "--definitions",
        "--verbalizations",
        dest="definitions",
        action="store_true",
        help=(
            "Append definition text to the default symbol-URI #pred "
            "verbalizations (--verbalizations is a deprecated alias)"
        ),
    )
    result.add_argument(
        "--server",
        default="https://mathhub.info",
        help="FLAMS server base URL or full query endpoint",
    )
    result.add_argument("--scope-prefix")
    result.add_argument("--no-auto-scope", action="store_true")
    result.add_argument(
        "--language",
        default="de",
        help="Definition URI language code; pass an empty string for any language",
    )
    result.add_argument("--timeout", type=float, default=30.0)
    result.add_argument("--batch-size", type=int, default=100)
    result.add_argument("--max-nodes", type=int, default=5_000)
    result.add_argument("--max-edges", type=int, default=25_000)
    result.add_argument("--max-depth", type=int)
    return result


def _fetch_definitions(
    client: FlamsClient,
    nodes: frozenset[str],
    *,
    scope_prefix: str | None,
    language: str | None,
    batch_size: int,
) -> tuple[dict[str, DefinitionFragment], list[str]]:
    definition_uris = client.definition_uris(
        nodes,
        scope_prefix=scope_prefix,
        language=language,
        batch_size=batch_size,
    )
    chosen = {
        symbol: uris[0] for symbol, uris in definition_uris.items() if uris
    }
    fragments: dict[str, DefinitionFragment] = {}
    warnings: list[str] = []
    if not chosen:
        return fragments, warnings

    def fetch(symbol: str, definition_uri: str) -> DefinitionFragment:
        try:
            return client.definition_fragment(definition_uri)
        except FlamsError as exact_error:
            try:
                return client.definition_fragment(symbol)
            except FlamsError as symbol_error:
                raise FlamsError(
                    f"exact paragraph failed ({exact_error}); "
                    f"symbol fallback failed ({symbol_error})"
                ) from symbol_error

    with ThreadPoolExecutor(max_workers=min(8, len(chosen))) as executor:
        futures = {
            executor.submit(fetch, symbol, uri): (symbol, uri)
            for symbol, uri in chosen.items()
        }
        for future in as_completed(futures):
            symbol, uri = futures[future]
            try:
                fragments[symbol] = future.result()
            except FlamsError as error:
                warnings.append(f"{uri}: {error}")
    return fragments, sorted(set(warnings))


def run(arguments: argparse.Namespace) -> int:
    root = normalize_uri(arguments.uri)
    scope = arguments.scope_prefix
    if scope is None and not arguments.no_auto_scope:
        scope = default_scope_prefix(root)
    language = arguments.language or None
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
    definitions: dict[str, DefinitionFragment] = {}
    if arguments.definitions:
        definitions, warnings = _fetch_definitions(
            client,
            graph.nodes,
            scope_prefix=scope,
            language=language,
            batch_size=arguments.batch_size,
        )
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)

    output = arguments.output
    if output is None:
        output = Path(predicate_names(graph.nodes)[root] + ".pl")
    output.write_text(render_scasp(graph, definitions=definitions), encoding="utf-8")
    print(
        f"Wrote {output.resolve()} ({len(graph.nodes)} predicates, "
        f"{len(graph.edges)} dependencies, {len(graph.nodes)} URI "
        f"verbalizations, {len(definitions)} with definitions)"
    )
    return 0


def main(argv: list[str] | None = None) -> None:
    arguments = parser().parse_args(argv)
    try:
        raise SystemExit(run(arguments))
    except (FlamsError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
