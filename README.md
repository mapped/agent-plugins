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
(`graphql_gen`, `graphql_gen_with_results`) over HTTP. The plugin connects to
Mapped's hosted instance at `https://mcp.mapped.com/mcp`, so all you need is a
credential. (Self-hosting? Edit `url` in `mapped-mcp/.claude-plugin/plugin.json`.)

1. **Provide your credential.** Each tool call relays an `Authorization` header;
   the plugin sends `token ${MAPPED_PAT}`, which Claude Code expands from your
   environment at connect time (the server exchanges the PAT for a JWT via the
   vault micro). **Never put the token in the plugin manifest** — it's committed
   to this marketplace. Supply it through your own config instead; pick one:

   - **Recommended — project-local settings.** `.claude/settings.local.json` in
     the repo you launch Claude Code from (Claude Code keeps this file out of
     git):

     ```json
     {
       "env": {
         "MAPPED_PAT": "your-mapped-pat"
       }
     }
     ```

   - **All your projects** — the same `env` block in `~/.claude/settings.json`.

   - **Quick / one-off** — export it before launching Claude Code:

     ```bash
     export MAPPED_PAT=<your-mapped-pat> && claude
     ```

   Do **not** put the PAT in a git-committed `.claude/settings.json`. `${VAR}`
   expansion is supported in MCP `headers`, so the manifest stays secret-free and
   each user supplies their own value.

   To avoid storing the PAT on disk at all, replace the static header in
   `mapped-mcp/.claude-plugin/plugin.json` with a `headersHelper` that fetches it
   from a secret manager at connect time (its stdout JSON becomes the headers):

   ```json
   "mapped": {
     "type": "http",
     "url": "https://mcp.mapped.com/mcp",
     "headersHelper": "echo \"{\\\"Authorization\\\": \\\"token $(op read op://vault/mapped/pat)\\\"}\""
   }
   ```

2. **Install and enable it:**

   ```
   /plugin marketplace add mapped/claude-plugins
   /plugin install mapped-mcp@mapped
   ```

   The `graphql_gen` and `graphql_gen_with_results` tools then appear under the
   `mapped` server.

#### On Claude on the web (claude.ai/code)

Web sessions run in an Anthropic-managed cloud VM. The plugin's
`https://mcp.mapped.com/mcp` endpoint is publicly reachable, so it works from web
sessions — two things differ from desktop:

- **Config must be committed to the repo.** User-scoped `/plugin install` and
  `~/.claude/settings.json` don't carry into web sessions — only repo config is
  cloned in. Declare the marketplace and enable the plugin in the repo's
  `.claude/settings.json`:

  ```json
  {
    "extraKnownMarketplaces": {
      "mapped": { "source": { "source": "github", "repo": "mapped/claude-plugins" } }
    },
    "enabledPlugins": ["mapped-mcp@mapped"]
  }
  ```

- **Supply the PAT as an environment variable** in the session's environment
  config (the web UI's *Environment variables*, `.env` format, no quotes):
  `MAPPED_PAT=...`. `${VAR}` expansion runs the same as on desktop. Note: there's
  no dedicated secrets store yet — the value is visible to anyone who can edit
  that environment.
