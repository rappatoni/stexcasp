# stexcasp

`stexcasp` turns semantic definition dependencies from a FLAMS ontology into
executable s(CASP)/Prolog scaffolding. The repository also provides `mgraph`,
an interactive viewer for inspecting the same dependency graph and its
definition paragraphs.

Both commands compute the dependency closure and remove only depth-first-search
back edges and self-loops. The viewer arranges the resulting DAG in horizontal
levels by shortest distance from the root. Selecting a node loads its rendered
definition paragraph from FLAMS into a side panel.

Tree, forward, and cross edges are retained. In particular, diamond structures
remain intact.

## Requirements

- Python 3.11 or newer
- Network access to the selected FLAMS server
- Network access to jsDelivr when viewing the graph (for D3.js)

The Python program itself has no third-party runtime dependencies.

## Definitions

After retrieving the closure, the graph viewer resolves the exact semantic
paragraph URIs connected to every included symbol by `ulo:defines`. Definition bodies
are fetched lazily from FLAMS through `/content/fragment` when a node is
selected. The returned semantic HTML and its CSS are rendered in an isolated
side panel, so initial graph loading does not require one HTTP request per
node.

If several matching definition paragraphs exist, the panel provides a
selector. Missing or temporarily unavailable fragments do not prevent the
graph from loading. Because fragments are served through the viewer's localhost
proxy, definition loading is available while the local server is running; a
saved HTML file opened directly still contains the graph and definition URIs,
but cannot fetch the bodies by itself.

## Run the interactive graph viewer

From the repository root:

```sh
python3 -m mgraph 'https://mathhub.info/?uri=http%3A%2F%2Fmathhub.info%3Fa%3DJLogic%2Fsmglol%2FCommercial-Law%26p%3Dmod%26m%3DKaufmann%26s%3DKaufmann'
```

`mgraph` chooses a free localhost port and opens the graph in the default
browser. Stop the server with `Ctrl-C`.

Raw FTML URIs are accepted as well:

```sh
python3 -m mgraph 'http://mathhub.info?a=JLogic/smglol/Commercial-Law&p=mod&m=Kaufmann&s=Kaufmann'
```

## Install the commands

```sh
git clone https://github.com/rappatoni/stexcasp.git
cd stexcasp
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/stexcasp '<URI-or-MathHub-link>' --output program.pl
```

The installation also provides `.venv/bin/mgraph` for the interactive viewer.

## Query a local FLAMS server

```sh
python3 -m mgraph '<URI-or-link>' --server http://127.0.0.1:3000
```

`--server` may also be the complete endpoint URL, for example
`http://127.0.0.1:3000/api/backend/query`.

## Limit the depth

Use `--max-depth` to limit the graph by shortest dependency distance from the
root. The root has depth 0. Nodes exactly at the limit are included, but their
dependencies are not queried:

```sh
python3 -m mgraph '<URI-or-link>' --max-depth 3
```

Thus `--max-depth 0` renders only the root, while omitting the option retrieves
the complete scoped closure.

## Scoping

By default both commands:

1. derives an archive-family prefix by removing the last component of the
   root's `a=` value; and
2. uses German definition paragraphs (`--language de`).

For the Kaufmann URI, the derived prefix is:

```text
http://mathhub.info?a=JLogic/smglol/
```

Override it explicitly:

```sh
python3 -m mgraph '<URI>' --scope-prefix 'http://mathhub.info?a=JLogic/smglol/'
```

Or query definitions without those restrictions:

```sh
python3 -m mgraph '<URI>' --no-auto-scope --language ''
```

Unrestricted closures can become very large. `--max-nodes` and `--max-edges`
provide safety limits.

## Useful options

```text
--server URL          FLAMS server or query endpoint
--scope-prefix TEXT   accepted definition-URI prefix
--no-auto-scope       disable automatic archive-family scope
--language CODE       definition language; empty means any
--max-depth N         greatest dependency distance to include (root is 0)
--save-html PATH      also save the generated standalone HTML
--host HOST           local viewer host (default 127.0.0.1)
--port PORT           local viewer port; 0 chooses a free port
--no-open             do not open a browser automatically
```

## Cycle elimination

The complete scoped graph is retrieved before pruning. A deterministic DFS,
with outgoing URIs ordered lexicographically, classifies nodes as:

- white: not visited;
- gray: on the active recursion stack;
- black: fully processed.

An edge is removed only if it is a self-loop or points to a gray node. Edges to
black nodes are retained, which preserves cross edges and diamonds.

## Hierarchical layout

A node is placed on level `d` when the shortest directed path from the root to
that node contains `d` edges. This makes the dependency hierarchy tree-like
without discarding cross edges or diamond structures. Because the level is
based on the shortest path, a retained cross edge can skip levels, stay within
a level, or point toward an earlier level.

## Generate an s(CASP) program

`stexcasp` retrieves and prunes the same dependency graph, then writes an
executable `.pl` program. Each concept becomes a unary predicate. Its direct
dependencies form the clause body. Every predicate also carries an explicit
`not_implemented/3` proof obligation, including non-leaves:

```prolog
kaufmann(X) :-
    firma(X),
    handelsgewerbe(X),
    handelsregister(X),
    person(X),
    not_implemented(kaufmann, 1, X).

firma(X) :- not_implemented(firma, 1, X).

not_implemented(kaufmann, 1, _).
not_implemented(firma, 1, _).
% ...one axiom for every generated predicate...

?- kaufmann(X), not_implemented(Node, Arity, X).
```

The combined query requests a model for the root and also binds `Node` and
`Arity` to an open implementation obligation. Because these markers are part
of the object program rather than host-language exceptions, s(CASP) retains
them in its model and justification instead of collapsing the result to “no
models”.

Run it as follows:

```sh
stexcasp '<URI-or-link>' --max-depth 3 --output kaufmann.pl
```

If `--output` is omitted, the root predicate name is used, such as
`kaufmann.pl`. Symbol names are converted to lower-case Prolog atoms, with
non-alphanumeric runs replaced by underscores. Name collisions receive stable
numeric suffixes.

Add semantic definition paragraphs as s(CASP) natural-language predicate
patterns with `--verbalizations`:

```sh
stexcasp '<URI-or-link>' --verbalizations --output kaufmann.pl
```

This produces directives of the form:

```prolog
#pred kaufmann(X) :: 'A @(X) is a person who operates a commercial business.'.
```

The FTML definiendum is replaced by `@(X)`, matching the argument of the unary
predicate. When several matching paragraphs exist, the first URI in
lexicographic order is used. Fragment failures are reported as warnings and do
not prevent generation of the remaining program.

## Tests

```sh
python3 -m unittest discover -s tests -v
```
