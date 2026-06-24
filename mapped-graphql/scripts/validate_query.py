#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.8"
# dependencies = ["graphql-core>=3.2"]
# ///
"""Validate a GraphQL query/mutation against the Mapped schema using graphql-core.

The schema is **fetched live** from the GraphQL endpoint via introspection
(see `schema_loader.py`) rather than embedded in the repo, then cached locally
for 24h so repeated validations don't re-introspect. Pass `--schema PATH` to
validate against a local SDL file instead, `--refresh` to force a re-fetch, or
`--endpoint URL` to point elsewhere.

Dependencies are managed by **uv**. The inline script metadata above (PEP 723)
declares graphql-core; running this file with `uv run` makes uv install it into
a cached, isolated environment automatically — no manual `pip install`, and
nothing is added to the user's global site-packages. If invoked under a plain
interpreter that lacks graphql-core, the script re-execs itself through
`uv run` so it works regardless of how it was launched.

Inputs:
    uv run validate_query.py query.graphql         # schema from endpoint (cached)
    uv run validate_query.py -                     # query from stdin
    uv run validate_query.py -q '{ things { id } }'
    uv run validate_query.py --schema S query.graphql   # local SDL file

Exit codes: 0 = valid, 1 = syntax/validation errors, 2 = usage or schema error.
"""

import argparse
import os
import sys
import time


def _ensure_graphql():
    """Make `graphql` importable, installing it via uv if necessary.

    Under `uv run` the dependency is already present, so the import just
    succeeds. Under a plain interpreter it won't be, so we re-exec ourselves
    through `uv run`, which reads the PEP 723 metadata above and installs
    graphql-core. A sentinel env var prevents an infinite re-exec loop.
    """
    try:
        import graphql  # noqa: F401
        return
    except ImportError:
        pass

    if os.environ.get("_GQLVALIDATE_BOOTSTRAPPED"):
        sys.stderr.write(
            "error: graphql-core is unavailable and bootstrapping via uv did not "
            "provide it.\n"
            "Install uv (https://docs.astral.sh/uv/) and run:\n"
            "  uv run %s --schema <schema> <query>\n" % os.path.basename(__file__)
        )
        sys.exit(2)

    env = dict(os.environ, _GQLVALIDATE_BOOTSTRAPPED="1")
    script = os.path.abspath(__file__)
    try:
        os.execvpe("uv", ["uv", "run", "--quiet", "--script", script, *sys.argv[1:]], env)
    except FileNotFoundError:
        sys.stderr.write(
            "error: 'uv' was not found on PATH and graphql-core is not installed.\n"
            "Install uv (https://docs.astral.sh/uv/), or `pip install graphql-core` "
            "and re-run with a plain interpreter.\n"
        )
        sys.exit(2)


_ensure_graphql()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapped_gql import DEFAULT_ENDPOINT, default_cache_path, fetch_sdl, parse_header  # noqa: E402

from graphql import build_schema, parse, validate  # noqa: E402
from graphql.error import GraphQLError, GraphQLSyntaxError  # noqa: E402


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _resolve_schema_sdl(args):
    """Return (sdl_text, source_label) from a file, the cache, or a live fetch."""
    if args.schema:
        return _read(args.schema), args.schema

    cache = default_cache_path()
    fresh = (os.path.exists(cache) and not args.refresh
             and (time.time() - os.path.getmtime(cache)) < args.max_age)
    if fresh:
        return _read(cache), cache

    headers = dict(parse_header(h) for h in args.header)
    sdl = fetch_sdl(args.endpoint, headers, args.timeout)  # may raise RuntimeError
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w", encoding="utf-8") as handle:
        handle.write(sdl)
    return sdl, "%s (fetched from %s)" % (cache, args.endpoint)


def _print_errors(errors, source_name):
    print("✗ %d error(s) validating %s:" % (len(errors), source_name))
    for err in errors:
        loc = err.locations[0] if err.locations else None
        where = "%s:%d:%d" % (source_name, loc.line, loc.column) if loc else source_name
        # graphql-core messages can span lines; keep each finding on one line.
        message = " ".join(err.message.split())
        print("  %-28s %s" % (where, message))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate a GraphQL query/mutation against the Mapped schema "
                    "(fetched live via introspection; graphql-core via uv).")
    parser.add_argument("query", nargs="?", default="-",
                        help="path to a .graphql file, or '-' for stdin (default)")
    parser.add_argument("-q", "--query-string", metavar="TEXT",
                        help="inline query text instead of a file/stdin")
    parser.add_argument("--schema", metavar="PATH",
                        help="validate against this local SDL file instead of the live endpoint")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT,
                        help="GraphQL endpoint to introspect (default: %(default)s)")
    parser.add_argument("--refresh", action="store_true",
                        help="ignore the cache and re-introspect the endpoint")
    parser.add_argument("--max-age", type=float, default=86400, metavar="SECONDS",
                        help="re-fetch if the cached schema is older than this (default: 86400)")
    parser.add_argument("-H", "--header", action="append", default=[], metavar="'Name: value'",
                        help="extra HTTP header for introspection, e.g. auth; repeatable")
    parser.add_argument("--timeout", type=float, default=30, metavar="SECONDS")
    args = parser.parse_args(argv)

    try:
        schema_src, schema_source = _resolve_schema_sdl(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print("error: could not load schema: %s" % exc, file=sys.stderr)
        return 2
    try:
        # The schema is a trusted, generated artifact, so we skip re-validating
        # the SDL itself and only validate queries against it.
        schema = build_schema(schema_src, assume_valid_sdl=True)
    except GraphQLError as exc:
        print("error: schema failed to build from %s: %s"
              % (schema_source, " ".join(exc.message.split())), file=sys.stderr)
        return 2

    if args.query_string is not None:
        query_src = args.query_string
        source_name = "<query-string>"
    elif args.query == "-":
        query_src = sys.stdin.read()
        source_name = "<stdin>"
    else:
        try:
            query_src = _read(args.query)
        except OSError as exc:
            print("error: cannot read query: %s" % exc, file=sys.stderr)
            return 2
        source_name = args.query

    try:
        document = parse(query_src)
    except GraphQLSyntaxError as exc:
        loc = exc.locations[0] if exc.locations else None
        where = "%s:%d:%d" % (source_name, loc.line, loc.column) if loc else source_name
        print("✗ syntax error at %s: %s" % (where, " ".join(exc.message.split())))
        return 1

    errors = validate(schema, document)
    if errors:
        _print_errors(errors, source_name)
        return 1

    print("✓ %s is valid against the schema." % source_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
