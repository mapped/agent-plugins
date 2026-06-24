"""Shared helpers for talking to the Mapped GraphQL API.

Imported by `schema_loader.py`, `validate_query.py`, and `execute_query.py`.
graphql-core is imported lazily (only `fetch_sdl` needs it), so this module
itself is import-safe under a plain interpreter; everything else is stdlib.
"""

import json
import os
import urllib.error
import urllib.request

DEFAULT_ENDPOINT = "https://api.mapped.com/graphql"

# The endpoint sits behind Cloudflare, which 403s urllib's default
# "Python-urllib/x.y" User-Agent, so we send our own.
_USER_AGENT = "mapped-graphql/0.1 (+https://github.com/mapped/claude-plugins)"


def default_cache_path():
    """Canonical on-disk location for the downloaded SDL (XDG cache dir)."""
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "mapped-graphql", "schema.graphqls")


def parse_header(spec):
    """Turn 'Name: value' into ('Name', 'value')."""
    if ":" not in spec:
        raise ValueError("header must be in 'Name: value' form, got %r" % spec)
    name, value = spec.split(":", 1)
    return name.strip(), value.strip()


def auth_headers_from_env():
    """Authorization header from $MAPPED_PAT, per the Mapped convention.

    Returns {"Authorization": "token <pat>"} when MAPPED_PAT is set, else {}.
    """
    pat = os.environ.get("MAPPED_PAT")
    return {"Authorization": "token %s" % pat} if pat else {}


def post_graphql(endpoint, query, variables=None, headers=None, timeout=30):
    """POST a GraphQL request and return the parsed JSON response (a dict).

    Always sends a non-default User-Agent and, if $MAPPED_PAT is set, an
    `Authorization: token <pat>` header. Explicit `headers` override both.
    Raises RuntimeError on transport/HTTP/non-JSON failures; GraphQL-level
    errors are left in the returned payload under "errors" for the caller.
    """
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    body = json.dumps(payload).encode("utf-8")

    req_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": _USER_AGENT,
    }
    req_headers.update(auth_headers_from_env())
    if headers:
        req_headers.update(headers)

    request = urllib.request.Request(endpoint, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError("HTTP %s from %s: %s" % (exc.code, endpoint, detail))
    except urllib.error.URLError as exc:
        raise RuntimeError("could not reach %s: %s" % (endpoint, exc.reason))

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError("endpoint did not return JSON: %s" % raw[:200])


def fetch_sdl(endpoint=DEFAULT_ENDPOINT, headers=None, timeout=30):
    """Introspect `endpoint` and return its schema as SDL.

    Raises RuntimeError on failure (network, HTTP, GraphQL errors, or
    introspection disabled).
    """
    from graphql import build_client_schema, get_introspection_query, print_schema

    result = post_graphql(endpoint, get_introspection_query(descriptions=True),
                          headers=headers, timeout=timeout)
    if result.get("errors"):
        raise RuntimeError("introspection returned errors: %s" % json.dumps(result["errors"])[:500])
    data = result.get("data")
    if not data or "__schema" not in data:
        raise RuntimeError("response contained no __schema (introspection may be disabled)")
    return print_schema(build_client_schema(data))
