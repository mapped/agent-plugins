---
name: mapped-graphql
description: Work with the Mapped GraphQL API. Provides three tools — a schema loader (introspects the live schema and returns its file path), a graphql-core based query validator, and a query executor that runs a query against the endpoint with auth. Use when writing, validating, exploring, or running GraphQL queries/mutations against the Mapped API.
allowed-tools: Read, Grep, Glob, Bash
---

# Mapped GraphQL

Three tools for the Mapped GraphQL API, all under `${CLAUDE_PLUGIN_ROOT}/scripts/`
and run with **uv** (which supplies the one Python dependency, `graphql-core`,
declared inline via PEP 723 — no manual `pip install`):

| Tool | Script | What it does |
| --- | --- | --- |
| **Schema loader** | `schema_loader.py` | Introspects the live endpoint, downloads the schema as SDL, and prints the **file path** on stdout. |
| **Validator** | `validate_query.py` | Validates a query/mutation against the schema (spec-complete, via graphql-core). |
| **Executor** | `execute_query.py` | Sends a query/mutation to the endpoint and prints the JSON response. |

The schema is **not bundled** — it's fetched live from
`https://api.mapped.com/graphql` so it never goes stale.

**Requirements:** `uv` (https://docs.astral.sh/uv/) on PATH; network access.
**Auth:** set `MAPPED_PAT` (a Mapped personal access token). Requests are sent
with `Authorization: token $MAPPED_PAT`. Introspection (schema loader) works
without auth; executing real queries needs it.

`${CLAUDE_PLUGIN_ROOT}` is this plugin's directory. If it isn't set, find the
scripts with `Glob: **/mapped-graphql/scripts/validate_query.py`.

## Tool 1 — Schema loader (where is the schema?)

Downloads the schema (if missing/stale or `--refresh`) and prints its path:

```bash
SCHEMA=$(uv run "${CLAUDE_PLUGIN_ROOT}/scripts/schema_loader.py")
# $SCHEMA now holds the path to the SDL file; grep it to explore:
grep -nE "^type (Query|Mutation) " "$SCHEMA"
grep -n  "^type Building " "$SCHEMA"
grep -nE "^input (Building|Floor|Thing|Point)Filter" "$SCHEMA"
grep -nE "^(enum|directive) " "$SCHEMA"
```

Status messages go to stderr; only the path is on stdout. `-o PATH` downloads
to a chosen location; `--refresh` forces a re-download; `--max-age SECONDS`
controls staleness (default 24h). Read the surrounding block with `Read` at a
matched line to see fields and their types.

## Tool 2 — Validator (is this query correct?)

Always validate a non-trivial query before executing it. The validator fetches
and caches the schema itself (24h), so no schema path is required:

```bash
V="${CLAUDE_PLUGIN_ROOT}/scripts/validate_query.py"
uv run "$V" query.graphql                       # from a file
uv run "$V" -q '{ buildings { id name } }'      # inline
echo '{ buildings { id } }' | uv run "$V" -     # stdin
uv run "$V" --refresh query.graphql             # force fresh introspection
uv run "$V" --schema some.graphqls query.graphql  # local SDL file instead
```

Exit `0` = valid, `1` = syntax/validation errors, `2` = usage/schema error.
Errors print as `source:line:col  message`. Because it uses `graphql-core`,
validation is spec-complete: unknown fields (with "did you mean"),
leaf-vs-object mistakes, unknown/missing-required/duplicate arguments,
input-value type mismatches, invalid enum literals, bad fragment conditions,
union selection without a fragment, unknown fragments, fragment cycles,
undefined/unused variables, and directive rules.

## Tool 3 — Executor (run it against the API)

Sends the query to the endpoint and prints the JSON response. **Set
`MAPPED_PAT` first** (`export MAPPED_PAT=...`) — without it the request is
unauthenticated and most fields are denied.

```bash
X="${CLAUDE_PLUGIN_ROOT}/scripts/execute_query.py"
uv run "$X" query.graphql
uv run "$X" -q '{ buildings { id name } }'
echo '{ buildings { id } }' | uv run "$X" -
uv run "$X" query.graphql --variables '{"filter": {"id": {"eq": "abc"}}}'
uv run "$X" query.graphql --var-file vars.json
uv run "$X" -q '{ buildings { id } }' -H "Authorization: token $MAPPED_PAT"  # explicit
```

Exit `0` = response had no GraphQL `errors`, `1` = response contained `errors`,
`2` = usage/transport error (e.g. HTTP 401 for a bad/absent token). The
executor only sends the request — run the validator first to catch schema
errors before a round-trip.

## Typical flow

1. (optional) `schema_loader.py` → grep the SDL to find the right fields/filters.
2. Write the query.
3. `validate_query.py` → fix any errors it reports.
4. `execute_query.py` → run it (with `MAPPED_PAT` set).

## Key entities

Core graph types: `Thing`, `Point`, `Site`, `Building`, `Floor`, `Space`,
`SubBuilding`, `Zone`, `Place`, `Person`, `Collection`.

Common `Query` root fields: `things`, `points`, `sites`, `buildings`, `floors`,
`spaces`, `connectors`, `gateways`, `collections`, `accounts`.
