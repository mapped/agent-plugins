#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
"""Execute a GraphQL query/mutation against the Mapped endpoint and print JSON.

Sends the request to https://api.mapped.com/graphql (override with --endpoint)
and prints the raw JSON response.

Authentication uses the Mapped convention: set $MAPPED_PAT and the request is
sent with `Authorization: token $MAPPED_PAT`. Without it (and without an
explicit -H Authorization header) the request is unauthenticated and the API
will deny most fields. Add or override headers with -H "Name: value".

    export MAPPED_PAT=...                    # your Mapped personal access token
    uv run execute_query.py query.graphql
    uv run execute_query.py -q '{ buildings { id name } }'
    echo '{ buildings { id } }' | uv run execute_query.py -
    uv run execute_query.py query.graphql --variables '{"filter": {"id": {"eq": "x"}}}'
    uv run execute_query.py query.graphql --var-file vars.json

This tool only sends the request (pure standard library, no dependencies); use
validate_query.py first if you want to catch schema errors before executing.

Exit codes: 0 = response with no GraphQL "errors", 1 = response contained
"errors", 2 = usage or transport error.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapped_gql import DEFAULT_ENDPOINT, parse_header, post_graphql  # noqa: E402


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Execute a GraphQL query/mutation against the Mapped endpoint.")
    parser.add_argument("query", nargs="?", default="-",
                        help="path to a .graphql file, or '-' for stdin (default)")
    parser.add_argument("-q", "--query-string", metavar="TEXT",
                        help="inline query text instead of a file/stdin")
    parser.add_argument("--variables", metavar="JSON",
                        help="query variables as a JSON object")
    parser.add_argument("--var-file", metavar="PATH",
                        help="read query variables (JSON object) from a file")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT,
                        help="GraphQL endpoint (default: %(default)s)")
    parser.add_argument("-H", "--header", action="append", default=[], metavar="'Name: value'",
                        help="extra HTTP header, e.g. auth; repeatable, overrides $MAPPED_PAT")
    parser.add_argument("--timeout", type=float, default=30, metavar="SECONDS")
    parser.add_argument("--compact", action="store_true", help="print compact (not indented) JSON")
    args = parser.parse_args(argv)

    if args.query_string is not None:
        query = args.query_string
    elif args.query == "-":
        query = sys.stdin.read()
    else:
        try:
            query = _read(args.query)
        except OSError as exc:
            print("error: cannot read query: %s" % exc, file=sys.stderr)
            return 2

    variables = None
    raw_vars = None
    if args.var_file is not None:
        try:
            raw_vars = _read(args.var_file)
        except OSError as exc:
            print("error: cannot read --var-file: %s" % exc, file=sys.stderr)
            return 2
    elif args.variables is not None:
        raw_vars = args.variables
    if raw_vars is not None:
        try:
            variables = json.loads(raw_vars)
        except json.JSONDecodeError as exc:
            print("error: variables are not valid JSON: %s" % exc, file=sys.stderr)
            return 2

    try:
        headers = dict(parse_header(h) for h in args.header)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    has_auth_header = any(name.lower() == "authorization" for name in headers)
    if "MAPPED_PAT" not in os.environ and not has_auth_header:
        print("warning: MAPPED_PAT is not set and no Authorization header given; "
              "request is unauthenticated and most fields will be denied.", file=sys.stderr)

    try:
        result = post_graphql(args.endpoint, query, variables, headers, args.timeout)
    except RuntimeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if args.compact:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 1 if result.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())
