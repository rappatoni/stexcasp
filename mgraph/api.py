from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator
from dataclasses import dataclass


class FlamsError(RuntimeError):
    """Raised when the FLAMS API cannot produce a usable graph."""


@dataclass(frozen=True)
class Closure:
    root: str
    nodes: frozenset[str]
    edges: frozenset[tuple[str, str]]
    rounds: int


@dataclass(frozen=True)
class DefinitionFragment:
    uri: str
    css: tuple[object, ...]
    html: str


def normalize_uri(value: str) -> str:
    """Accept a raw FTML URI or a MathHub viewer link containing ``uri=``."""
    value = value.strip().strip("<>")
    parsed = urllib.parse.urlsplit(value)
    query = urllib.parse.parse_qs(parsed.query)
    embedded = query.get("uri")
    if embedded:
        return embedded[0]
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Not an absolute URI or MathHub viewer link: {value!r}")
    return value


def default_scope_prefix(root_uri: str) -> str | None:
    """Derive an archive-family prefix by dropping the final ``a=`` segment."""
    parsed = urllib.parse.urlsplit(root_uri)
    archive = urllib.parse.parse_qs(parsed.query).get("a", [None])[0]
    if not archive or "/" not in archive:
        return None
    parent = archive.rsplit("/", 1)[0] + "/"
    return f"{parsed.scheme}://{parsed.netloc}?a={parent}"


def endpoint_for(server: str) -> str:
    server = server.rstrip("/")
    if server.endswith("/api/backend/query"):
        return server
    return server + "/api/backend/query"


def content_endpoint_for(server: str) -> str:
    server = server.rstrip("/")
    suffix = "/api/backend/query"
    if server.endswith(suffix):
        server = server[: -len(suffix)]
    return server + "/content/fragment"


def _sparql_iri(uri: str) -> str:
    forbidden = '<>"{}|^`\\'
    if any(char in uri for char in forbidden) or any(ord(char) < 0x20 for char in uri):
        raise ValueError(f"URI contains a character unsafe in a SPARQL IRI: {uri!r}")
    return f"<{uri}>"


def _chunks(values: Iterable[str], size: int) -> Iterator[list[str]]:
    chunk: list[str] = []
    for value in values:
        chunk.append(value)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def dependency_query(
    sources: Iterable[str],
    *,
    scope_prefix: str | None,
    language: str | None,
) -> str:
    values = " ".join(_sparql_iri(uri) for uri in sources)
    filters: list[str] = []
    if scope_prefix:
        filters.append(
            f"FILTER(STRSTARTS(STR(?definition), {json.dumps(scope_prefix)}))"
        )
    if language:
        filters.append(
            f"FILTER(CONTAINS(STR(?definition), {json.dumps('&l=' + language)}))"
        )
    filter_text = "\n  ".join(filters)
    return f"""SELECT DISTINCT ?from ?to WHERE {{
  VALUES ?from {{ {values} }}
  ?definition ulo:defines ?from ;
              ulo:crossrefs ?to .
  {filter_text}
}}
ORDER BY STR(?from) STR(?to)"""


def definition_query(
    symbols: Iterable[str],
    *,
    scope_prefix: str | None,
    language: str | None,
) -> str:
    values = " ".join(_sparql_iri(uri) for uri in symbols)
    filters: list[str] = []
    if scope_prefix:
        filters.append(
            f"FILTER(STRSTARTS(STR(?definition), {json.dumps(scope_prefix)}))"
        )
    if language:
        filters.append(
            f"FILTER(CONTAINS(STR(?definition), {json.dumps('&l=' + language)}))"
        )
    filter_text = "\n  ".join(filters)
    return f"""SELECT DISTINCT ?symbol ?definition WHERE {{
  VALUES ?symbol {{ {values} }}
  ?definition ulo:defines ?symbol .
  {filter_text}
}}
ORDER BY STR(?symbol) STR(?definition)"""


class FlamsClient:
    def __init__(self, server: str, *, timeout: float = 30.0) -> None:
        self.endpoint = endpoint_for(server)
        self.content_endpoint = content_endpoint_for(server)
        self.timeout = timeout

    def query(self, sparql: str) -> list[dict[str, dict[str, object]]]:
        body = urllib.parse.urlencode(
            {"query": sparql, "decode_uris": "false"}
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except (OSError, ValueError, urllib.error.URLError) as error:
            raise FlamsError(f"FLAMS request failed: {error}") from error
        try:
            return payload["results"]["bindings"]
        except (KeyError, TypeError) as error:
            raise FlamsError(f"Unexpected FLAMS response: {payload!r}") from error

    def direct_dependencies(
        self,
        sources: Iterable[str],
        *,
        scope_prefix: str | None,
        language: str | None,
    ) -> set[tuple[str, str]]:
        bindings = self.query(
            dependency_query(
                sources, scope_prefix=scope_prefix, language=language
            )
        )
        edges: set[tuple[str, str]] = set()
        for binding in bindings:
            try:
                source = str(binding["from"]["value"])
                target = str(binding["to"]["value"])
            except (KeyError, TypeError) as error:
                raise FlamsError(f"Malformed result binding: {binding!r}") from error
            edges.add((source, target))
        return edges

    def definition_uris(
        self,
        symbols: Iterable[str],
        *,
        scope_prefix: str | None,
        language: str | None,
        batch_size: int = 100,
    ) -> dict[str, tuple[str, ...]]:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        found: dict[str, set[str]] = {}
        for batch in _chunks(sorted(set(symbols)), batch_size):
            for binding in self.query(
                definition_query(
                    batch, scope_prefix=scope_prefix, language=language
                )
            ):
                try:
                    symbol = str(binding["symbol"]["value"])
                    definition = str(binding["definition"]["value"])
                except (KeyError, TypeError) as error:
                    raise FlamsError(
                        f"Malformed definition binding: {binding!r}"
                    ) from error
                found.setdefault(symbol, set()).add(definition)
        return {
            symbol: tuple(sorted(definitions))
            for symbol, definitions in found.items()
        }

    def definition_fragment(self, definition_uri: str) -> DefinitionFragment:
        url = self.content_endpoint + "?" + urllib.parse.urlencode(
            {"uri": definition_uri}
        )
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except (OSError, ValueError, urllib.error.URLError) as error:
            raise FlamsError(f"FLAMS definition request failed: {error}") from error
        try:
            returned_uri, css, fragment_html = payload
            if not isinstance(returned_uri, str):
                raise TypeError("definition URI is not a string")
            if not isinstance(css, list):
                raise TypeError("definition CSS is not a list")
            if not isinstance(fragment_html, str):
                raise TypeError("definition HTML is not a string")
        except (TypeError, ValueError) as error:
            raise FlamsError(
                f"Unexpected FLAMS definition response: {payload!r}"
            ) from error
        return DefinitionFragment(returned_uri, tuple(css), fragment_html)

    def closure(
        self,
        root: str,
        *,
        scope_prefix: str | None,
        language: str | None,
        batch_size: int = 100,
        max_nodes: int = 5_000,
        max_edges: int = 25_000,
        max_depth: int | None = None,
    ) -> Closure:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_depth is not None and max_depth < 0:
            raise ValueError("max_depth must be non-negative")
        expanded: set[str] = set()
        nodes = {root}
        edges: set[tuple[str, str]] = set()
        frontier = {root}
        depths = {root: 0}
        rounds = 0

        while frontier:
            current = sorted(
                node
                for node in frontier - expanded
                if max_depth is None or depths[node] < max_depth
            )
            if not current:
                break
            rounds += 1
            expanded.update(current)
            round_edges: set[tuple[str, str]] = set()
            for batch in _chunks(current, batch_size):
                round_edges.update(
                    self.direct_dependencies(
                        batch,
                        scope_prefix=scope_prefix,
                        language=language,
                    )
                )
            edges.update(round_edges)
            targets = {target for _, target in round_edges}
            for source, target in round_edges:
                candidate_depth = depths[source] + 1
                if target not in depths or candidate_depth < depths[target]:
                    depths[target] = candidate_depth
            nodes.update(targets)
            if len(nodes) > max_nodes:
                raise FlamsError(
                    f"Closure exceeded --max-nodes={max_nodes}; narrow the scope"
                )
            if len(edges) > max_edges:
                raise FlamsError(
                    f"Closure exceeded --max-edges={max_edges}; narrow the scope"
                )
            frontier = targets - expanded

        return Closure(root, frozenset(nodes), frozenset(edges), rounds)
