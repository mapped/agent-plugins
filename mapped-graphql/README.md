# mapped-graphql

A Claude Code plugin with **three tools for the Mapped GraphQL API**:

| Tool | Script | What it does |
| --- | --- | --- |
| **Schema loader** | `scripts/schema_loader.py` | Introspects the live endpoint, downloads the schema as SDL, prints its **file path**. |
| **Validator** | `scripts/validate_query.py` | Validates a query/mutation against the schema (spec-complete, via `graphql-core`). |
| **Executor** | `scripts/execute_query.py` | Sends a query/mutation to the endpoint and prints the JSON response. |

It's the companion to [`mapped-mcp`](../mapped-mcp): same API, exposed here as
local scripts the agent drives directly. The schema is **not committed** — it's
fetched on demand from `https://api.mapped.com/graphql` via introspection, so it
never drifts from the live API.

```
mapped-graphql/
├── scripts/schema_loader.py    # tool 1: download schema -> print path
├── scripts/validate_query.py   # tool 2: validate a query
├── scripts/execute_query.py    # tool 3: run a query against the endpoint
├── scripts/mapped_gql.py       # shared HTTP/auth/introspection helper
└── skills/mapped-graphql/      # skill documenting the three tools
```

## Install

```
/plugin marketplace add mapped/claude-plugins
/plugin install mapped-graphql@mapped
```

Requirements: [`uv`](https://docs.astral.sh/uv/) on PATH (it supplies
`graphql-core` automatically on first run), and network access to the endpoint.

## Authentication

Set a Mapped personal access token; requests are sent as
`Authorization: token $MAPPED_PAT` (the Mapped convention).

```bash
export MAPPED_PAT=your-mapped-pat
```

Introspection (the schema loader) currently needs no auth; executing real
queries does. You can also pass auth explicitly with `-H "Authorization: token …"`.

> The endpoint is behind Cloudflare, which 403s urllib's default
> `Python-urllib` User-Agent — the scripts send their own User-Agent so the
> request goes through.

## Tools

All three are run with **uv**, which installs the one dependency
(`graphql-core`, declared inline via [PEP 723](https://peps.python.org/pep-0723/))
into a cached, isolated environment — no manual `pip install`. The scripts are
also directly executable (uv-run shebang); the schema loader and validator also
self-bootstrap through uv when run with a plain `python3`.

### 1. Schema loader

```bash
# Download (if missing/stale) and print the schema file path:
SCHEMA=$(uv run scripts/schema_loader.py)
grep -n "^type Building " "$SCHEMA"

uv run scripts/schema_loader.py --refresh         # force re-download
uv run scripts/schema_loader.py -o mapped.graphqls  # download to a chosen path
```

The default download location is
`${XDG_CACHE_HOME:-~/.cache}/mapped-graphql/schema.graphqls`. Status goes to
stderr; only the path is printed to stdout.

### 2. Validator

```bash
uv run scripts/validate_query.py query.graphql        # schema fetched + cached
uv run scripts/validate_query.py -q '{ buildings { id name } }'
echo '{ buildings { id } }' | uv run scripts/validate_query.py -
uv run scripts/validate_query.py --schema mapped.graphqls query.graphql  # local SDL
```

Exit codes: `0` valid · `1` syntax/validation errors · `2` usage/schema error.
Spec-complete (graphql-core): unknown fields with "did you mean",
leaf-vs-object mistakes, unknown/missing-required/duplicate arguments,
input-value type mismatches, invalid enum literals, fragment/union/variable
rules, and more.

```
$ uv run scripts/validate_query.py -q '{ buildings(fitler: $x) { nmae } }'
✗ 3 error(s) validating <query-string>:
  <query-string>:1:13   Unknown argument 'fitler' on field 'Query.buildings'. Did you mean 'filter'?
  <query-string>:1:27   Cannot query field 'nmae' on type 'Building'. Did you mean 'name'?
  <query-string>:1:21   Variable '$x' is not defined.
```

### 3. Executor

```bash
export MAPPED_PAT=...
uv run scripts/execute_query.py query.graphql
uv run scripts/execute_query.py -q '{ buildings { id name } }'
echo '{ buildings { id } }' | uv run scripts/execute_query.py -
uv run scripts/execute_query.py query.graphql --variables '{"filter": {"id": {"eq": "abc"}}}'
uv run scripts/execute_query.py query.graphql --var-file vars.json
```

Exit codes: `0` response had no GraphQL `errors` · `1` response contained
`errors` · `2` usage/transport error (e.g. HTTP 401 for a bad/missing token).
The executor only sends the request — run the validator first to catch schema
errors before a round-trip.

## Keeping the schema current

Nothing to maintain — the schema is fetched live. Pass `--refresh` to the
loader or validator to pull the latest before the 24h cache expires.
