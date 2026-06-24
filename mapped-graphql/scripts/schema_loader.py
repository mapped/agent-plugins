#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.8"
# dependencies = ["graphql-core>=3.2"]
# ///
"""Schema loader: download the Mapped GraphQL schema and print its file path.

This tool ensures the schema SDL is present locally — fetching it from the
endpoint via introspection when it's missing, stale (older than --max-age), or
when --refresh is given — and prints the absolute path of the schema file on
**stdout**, so the agent or another tool can read or grep it. Status messages
go to stderr.

    uv run schema_loader.py                 # -> prints the cached schema path
    uv run schema_loader.py --refresh       # re-download first
    uv run schema_loader.py -o mapped.graphqls   # download to a chosen path
    uv run schema_loader.py --endpoint https://api.mapped.com/graphql

graphql-core (used to turn introspection into SDL) is supplied by uv via the
inline metadata above. Introspection currently needs no auth, but $MAPPED_PAT —
if set — is sent as `Authorization: token <pat>`; add headers with -H.

Exit codes: 0 = schema available (path printed), 1 = download failed,
2 = usage error.
"""

import argparse
import os
import sys
import time


def _ensure_graphql():
    try:
        import graphql  # noqa: F401
        return
    except ImportError:
        pass
    if os.environ.get("_GQLVALIDATE_BOOTSTRAPPED"):
        sys.stderr.write("error: graphql-core unavailable and uv bootstrap failed.\n"
                         "Install uv (https://docs.astral.sh/uv/) and run via `uv run`.\n")
        sys.exit(2)
    env = dict(os.environ, _GQLVALIDATE_BOOTSTRAPPED="1")
    script = os.path.abspath(__file__)
    try:
        os.execvpe("uv", ["uv", "run", "--quiet", "--script", script, *sys.argv[1:]], env)
    except FileNotFoundError:
        sys.stderr.write("error: 'uv' not found on PATH and graphql-core is not installed.\n"
                         "Install uv (https://docs.astral.sh/uv/) or `pip install graphql-core`.\n")
        sys.exit(2)


_ensure_graphql()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapped_gql import DEFAULT_ENDPOINT, default_cache_path, fetch_sdl, parse_header  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Download the Mapped GraphQL schema and print its file path.")
    parser.add_argument("-o", "--output", metavar="PATH",
                        help="download to this path (default: the shared cache file)")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT,
                        help="GraphQL endpoint to introspect (default: %(default)s)")
    parser.add_argument("--refresh", action="store_true",
                        help="re-download even if a cached copy exists")
    parser.add_argument("--max-age", type=float, default=86400, metavar="SECONDS",
                        help="re-download if the existing file is older than this (default: 86400)")
    parser.add_argument("-H", "--header", action="append", default=[], metavar="'Name: value'",
                        help="extra HTTP header for introspection, e.g. auth; repeatable")
    parser.add_argument("--timeout", type=float, default=30, metavar="SECONDS")
    args = parser.parse_args(argv)

    path = os.path.abspath(args.output or default_cache_path())
    fresh = (os.path.exists(path) and not args.refresh
             and (time.time() - os.path.getmtime(path)) < args.max_age)

    if fresh:
        age_h = (time.time() - os.path.getmtime(path)) / 3600
        print("using cached schema (%.1fh old): %s" % (age_h, path), file=sys.stderr)
    else:
        try:
            headers = dict(parse_header(h) for h in args.header)
            sdl = fetch_sdl(args.endpoint, headers, args.timeout)
        except (ValueError, RuntimeError) as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 1
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(sdl)
        print("downloaded schema from %s (%d bytes): %s" % (args.endpoint, len(sdl), path),
              file=sys.stderr)

    print(path)  # stdout: the location of the downloaded schema file
    return 0


if __name__ == "__main__":
    sys.exit(main())
