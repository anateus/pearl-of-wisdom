# Pearl in Claude Desktop Chat

Install two pieces: the Pearl plugin supplies reasoning skills, and the Desktop extension supplies local MCP tools. This is the ordinary Chat workflow, not a requirement to run Claude Code or Cowork.

## Install the skills

Open Claude's plugin browser, choose the option to add a marketplace from a repository, and enter this Git URL:

```text
https://github.com/anateus/pearl-of-wisdom.git
```

Install the `pearl-of-wisdom` plugin from that marketplace and enable it for Chat. The repository must contain the published marketplace and plugin changes before this works for another user. If your organization restricts plugins or local extensions, ask its administrator to approve them.

## Install the local tools

Get `pearl-of-wisdom-0.4.0.mcpb` from the person distributing the build, or build it with the developer instructions below. In Claude Desktop, open **Settings > Extensions > Advanced settings > Install Extension…**, select the file, and review its permissions. Choose an investigation data directory when prompted. The suggested location is `${HOME}/.pearl-of-wisdom`, where `${HOME}` means your home directory. Use a location outside Claude's extension installation.

Enable the extension and start a new Chat. Ask Claude to call `pearl_status` and report the database path before starting an investigation. For a first analysis, ask it to call `pearl_example`, then `pearl_analyze` using that example. These are setup checks for you to run, not a claim that a Claude Desktop model session has already been verified.

The extension uses manifest 0.4's `uv` runtime. A supporting client can manage uv, Python, and dependency installation. First start may need network access to download Python and the locked MCP dependencies. Pearl itself comes from a wheel inside the bundle, never from a PyPI package lookup. If your Desktop version doesn't support this runtime or cannot discover uv, use the manual fallback below. The skills alone don't install or start the local tools.

Available tools are `pearl_status`, `pearl_analyze`, `pearl_example`, `pearl_create_investigation`, `pearl_list_investigations`, `pearl_show_investigation`, `pearl_record`, and `pearl_promote_investigation`. Analysis is stateless. Creating investigations, recording evidence, and promoting conclusions are explicit operations on the configured database.

## Data and privacy

Pearl performs computations on your computer and stores investigations in `pearl.sqlite3` under the directory you choose. Keeping that directory outside the extension means an extension upgrade or uninstall doesn't remove your investigations. Back it up separately. Uninstalling the extension doesn't delete that database, and choosing a new directory opens a different database rather than moving existing records.

Local storage is not a fully offline model workflow. Tool outputs, including any investigation content Claude requests, enter the conversation and reach the Claude model account you're using. Only use data that account is authorized to process. Dependencies may be downloaded at first start, but Pearl has no remote investigation storage service.

## Build the extension

From the repository root, with uv and Node.js/npm available:

```bash
uv run python scripts/build_desktop_bundle.py
```

The output is `dist/pearl-of-wisdom-0.4.0.mcpb`. To choose another output directory:

```bash
uv run python scripts/build_desktop_bundle.py --out-dir /absolute/path/to/output
```

The builder copies only the manifest, server, bundle project, lock, license, existing `pearl.png`, and the existing plugin core wheel into clean staging. It checks the lock, installs dependencies with `uv sync --locked`, validates the manifest, and packs with the official CLI. No `.venv`, repository source tree, local database, or private corpus is included.

As checked on October 13, 2026, the official CLI is published as `@anthropic-ai/mcpb`, not `@modelcontextprotocol/mcpb` (the latter returned npm E404). This build pins `npx --yes @anthropic-ai/mcpb@2.1.2`. The Desktop project declares `mcp>=2,<3`; its checked-in lock resolves stable `mcp==2.3.0`. The core runtime remains dependency-free and is pinned to `pearl-of-wisdom==0.4.0` through `wheels/pearl_of_wisdom-0.4.0-py3-none-any.whl` in `[tool.uv.sources]`.

Ordinary builds reuse `desktop/uv.lock`. After an intentional dependency or bundled wheel change, regenerate it from staging and review the diff:

```bash
uv run python scripts/build_desktop_bundle.py --refresh-lock
uv run pytest tests/test_desktop_bundle.py
```

Don't run the Desktop template directly from the source directory: its wheel path exists in staging and in the extension, not in the repository's `desktop/` directory.

## Manual developer fallback

Extract the `.mcpb` as a ZIP into a persistent directory you control. Install uv if needed, then find its executable with `command -v uv` on macOS/Linux or `where.exe uv` on Windows. Claude's GUI may not inherit your terminal's PATH. Use the literal absolute path returned by that command, not `uv`, `~`, `${HOME}`, or a shell expression, in the manual configuration.

Open **Settings > Developer > Edit Config** and add a server entry to `mcpServers`, preserving existing entries. This macOS example assumes `command -v uv` printed `/opt/homebrew/bin/uv` and the bundle was extracted to `/Users/alex/Applications/pearl-desktop`. Replace both paths and the database location with yours:

```json
{
  "mcpServers": {
    "pearl-of-wisdom": {
      "command": "/opt/homebrew/bin/uv",
      "args": ["run", "--directory", "/Users/alex/Applications/pearl-desktop", "--locked", "server.py"],
      "env": {"PEARL_DB": "/Users/alex/.pearl-of-wisdom/pearl.sqlite3"}
    }
  }
}
```

On Windows, use absolute Windows paths and escape backslashes in JSON. Restart Claude Desktop after saving. Disable the extension-managed instance if you enable this manual instance, so you don't expose duplicate tools. If startup fails, check the local MCP logs for an unavailable uv executable, blocked downloads, or a non-writable data directory.

## References

The manifest follows the official [manifest specification](https://raw.githubusercontent.com/modelcontextprotocol/mcpb/main/MANIFEST.md) and [hello-world-uv example](https://github.com/modelcontextprotocol/mcpb/tree/main/examples/hello-world-uv). Installation steps follow Claude's [plugin guide](https://support.claude.com/en/articles/13837440-use-plugins-in-claude) and [local MCP guide](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop). See the official [MCPB CLI guide](https://github.com/modelcontextprotocol/mcpb/blob/main/CLI.md) for validation, packing, and optional signing. This builder produces an unsigned bundle.
