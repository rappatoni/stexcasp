from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class PrunedGraph:
    root: str
    nodes: frozenset[str]
    edges: frozenset[tuple[str, str]]
    removed_back_edges: frozenset[tuple[str, str]]


def eliminate_dfs_back_edges(
    root: str,
    nodes: set[str] | frozenset[str],
    edges: set[tuple[str, str]] | frozenset[tuple[str, str]],
) -> PrunedGraph:
    """Remove only DFS back edges and self-loops, preserving diamonds.

    Outgoing neighbors and disconnected roots are visited in URI order, making
    the chosen DAG reproducible.
    """
    all_nodes = set(nodes)
    all_nodes.add(root)
    adjacency: dict[str, list[str]] = defaultdict(list)
    for source, target in sorted(set(edges)):
        all_nodes.add(source)
        all_nodes.add(target)
        adjacency[source].append(target)

    white, gray, black = 0, 1, 2
    color = {node: white for node in all_nodes}
    kept: set[tuple[str, str]] = set()
    removed: set[tuple[str, str]] = set()

    def visit(start: str) -> None:
        color[start] = gray
        stack: list[tuple[str, Iterator[str]]] = [
            (start, iter(adjacency.get(start, ())))
        ]
        while stack:
            source, neighbors = stack[-1]
            try:
                target = next(neighbors)
            except StopIteration:
                color[source] = black
                stack.pop()
                continue

            edge = (source, target)
            if source == target or color[target] == gray:
                removed.add(edge)
                continue

            kept.add(edge)
            if color[target] == white:
                color[target] = gray
                stack.append((target, iter(adjacency.get(target, ()))))

    roots = [root, *(node for node in sorted(all_nodes) if node != root)]
    for candidate in roots:
        if color[candidate] == white:
            visit(candidate)

    return PrunedGraph(
        root=root,
        nodes=frozenset(all_nodes),
        edges=frozenset(kept),
        removed_back_edges=frozenset(removed),
    )


def shortest_depths(
    root: str, edges: set[tuple[str, str]] | frozenset[tuple[str, str]]
) -> dict[str, int]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for source, target in edges:
        adjacency[source].append(target)
    depths = {root: 0}
    queue = deque([root])
    while queue:
        source = queue.popleft()
        for target in adjacency.get(source, ()):
            if target not in depths:
                depths[target] = depths[source] + 1
                queue.append(target)
    return depths
