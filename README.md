# Claude Plugins

Mapped's [Claude Code plugins](https://code.claude.com/docs/en/plugins). This
repo is also a plugin **marketplace** (`.claude-plugin/marketplace.json`), so it
can be added and installed directly.

```
/plugin marketplace add mapped/claude-plugins   # or a local path: /plugin marketplace add .
/plugin install <plugin-name>@mapped
```

## Plugins

### `mapped-mcp`

Wraps the [mapped-mcp](https://github.com/mapped/mapped-mcp) server's tools
(`graphql_gen`, `graphql_gen_with_results`, and the ontology lookups) over HTTP.
The plugin connects to Mapped's hosted instance at `https://mcp.mapped.com/mcp`.
(Self-hosting? Edit `url` in `mapped-mcp/mcp.json`; both clients read it.)

**Auth is OAuth only — no PAT, no headers.** The manifests carry no credential.
The server answers unauthenticated requests with OAuth discovery metadata
(`/.well-known/oauth-protected-resource`), and you sign in with Mapped SSO
(`https://sso.mapped.com`: Client ID Metadata Document + PKCE, so there is no
client registration and no secret). The client stores and refreshes the token;
nothing is written to this repo.

1. **Install and enable it:**

   ```
   /plugin marketplace add mapped/agent-plugins
   /plugin install mapped-mcp@mapped
   ```

2. **Sign in:** run `/mcp`, select the `mapped` server, choose **Authenticate**,
   and complete the browser login. The `graphql_gen` and
   `graphql_gen_with_results` tools then appear under the `mapped` server. Use
   **Clear authentication** in the same menu to sign out.

#### On Claude on the web (claude.ai/code)

Web sessions run in an Anthropic-managed cloud VM with no local browser for the
OAuth sign-in. The simplest route there is to add Mapped as a custom connector on
claude.ai (Settings → Connectors → Add custom connector, URL
`https://mcp.mapped.com/mcp`); it uses the same OAuth sign-in.

#### On ChatGPT / Codex

The same directory is also a portable
[Agent Plugin](https://developers.openai.com/plugins/build/plugins) for ChatGPT
and Codex: `mapped-mcp/plugin.json` is the manifest and `mapped-mcp/mcp.json`
declares the `mapped` server (`streamable-http`, same endpoint, same OAuth
sign-in declared as `client.mode: "cimd"`). The Claude manifest
(`.claude-plugin/plugin.json`) points its `mcpServers` at that same `mcp.json`,
so the server is defined once; Claude Code ignores the OpenAI `extensions`
block and reads nothing else from `plugin.json`.

- **Repo / CLI:** `.agents/plugins/marketplace.json` lists the plugin, so
  `codex plugin marketplace add mapped/agent-plugins` (or `add .` from a
  checkout) makes it installable; enable it per repo with
  `[plugins."mapped-mcp@mapped"] enabled = true` in your Codex config.
- **Workspace / public directory:** upload the `mapped-mcp/` directory on the
  [ChatGPT Plugins](https://chatgpt.com/plugins) page and follow the
  [submission guide](https://developers.openai.com/plugins/deploy/submission).

### `mapped-graphql`

Three local tools for the Mapped GraphQL API — no MCP server required, just
[`uv`](https://docs.astral.sh/uv/) on PATH:

- **Schema loader** (`scripts/schema_loader.py`) — introspects the live API and
  prints the path to the downloaded schema (SDL).
- **Validator** (`scripts/validate_query.py`) — checks a query/mutation against
  the schema with `graphql-core` (spec-complete, with "did you mean" hints).
- **Executor** (`scripts/execute_query.py`) — runs a query against the endpoint
  and prints the JSON response.

The schema is **fetched live** via introspection (not embedded), so it never
goes stale. The scripts run via `uv`, which installs their one dependency
(`graphql-core`) on first use — nothing is added to global site-packages.

1. **Install and enable it:**

   ```
   /plugin marketplace add mapped/claude-plugins
   /plugin install mapped-graphql@mapped
   ```

2. **Provide your credential** for the executor (the schema loader and validator
   need none). Requests send `Authorization: token ${MAPPED_PAT}`, so export your
   PAT before launching Claude Code:

   ```bash
   export MAPPED_PAT=<your-mapped-pat>
   ```

See [`mapped-graphql/README.md`](./mapped-graphql/README.md) for the full tool
reference, flags, and examples.
