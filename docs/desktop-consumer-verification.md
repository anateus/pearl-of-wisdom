# Desktop consumer compatibility verification

Pearl's local integration is verified below, but a live Claude Desktop install and Chat session still need the user's approval and account. The end-user rollout isn't complete. These runtime checks did not change Desktop preferences or access conversations, credentials, or customer data. The repository and marketplace have since been published publicly; that does not establish live Chat acceptance.

## Installed application checks

On October 13, 2026 local time, the installed macOS/aarch64 application reported Claude Desktop `2.37337.1`. Only immutable files from its application bundle were inspected. Extracted program files were checked against their ASAR header SHA-256 values; application user data and credentials weren't read.

The app's bundled worker contains a manifest 0.4 schema that supports the `uv` server type. That exact schema was executed in an empty-environment Node process with filesystem access limited to the static-source scratch directory. It accepted the actual Pearl manifest without changing `server` or `user_config`. Three controls failed: manifest version 0.5, an unknown runtime, and a non-string command. This validates the bundled schema, not the complete live installer or account policy.

The actual main-process code selects its `dynamic-uv` launcher for an extension with `server.type="uv"`. It resolves a managed uv binary, preserves the configured arguments, launches from the installed extension directory, and forwards the configured environment. Its installer runs `uv sync --quiet` before launching the server. These dispatch statements were inspected, not invoked against real Desktop settings.

## Exact managed runtime

This Desktop build pins uv `0.9.7`, not the developer machine's uv `0.13.0`. The official macOS/aarch64 release archive was downloaded into scratch and matched the checksum embedded in the application:

```text
35572b9619fc14d67fc1cd72582c3cfc5c9c66d97f310192e04f26fb3fe96005
```

That binary successfully installed the actual bundle's locked dependencies, including its reviewed revision-5 lock. The exact installer command, `uv sync --quiet`, subsequently left the lock bytes unchanged. Its manifest-driven server discovered all eight tools, ran all five engine examples, and retained a synthetic investigation across process restart. An independent SQLite query confirmed the saved ID and durable status.

Python 3.12.13 was already available. An initial offline attempt lacked an ABI-specific dependency wheel; normal locked retrieval populated a disposable cache, after which installer and runtime checks ran offline. This doesn't prove cold Python provisioning, another operating system, or every organization policy.

## Reproduce the packaged runtime check

The normal test builds an actual extension, extracts it outside the checkout, runs the installer's `sync --quiet` step, asserts lock stability, then tests the manifest launch, calculation, and persistence. By default it uses uv from PATH. To check the exact binary managed by a Desktop release, first verify that binary's official checksum and populate a disposable dependency cache, then run:

```bash
PEARL_DESKTOP_UV_EXECUTABLE=/absolute/path/to/verified/uv \
PEARL_DESKTOP_UV_CACHE_DIR=/absolute/path/to/disposable/cache \
uv run --locked pytest -q tests/test_desktop_packaged_mcp.py
```

These overrides affect tests only. They don't change the shipped extension's command or the user's Desktop configuration. The test uses the Python interpreter running pytest and disables dependency-network access after the build's cache preparation.

## Remaining rollout gates

The user still needs to install the `.plugin` and `.mcpb`, approve their account's permissions, choose a fresh synthetic data directory, start a new Chat, and verify actual model tool routing and readback.

The public marketplace can be added from its Git URL without a repository access grant. Organization policies may still restrict plugin or local-extension installation. These checks establish local schema and runtime compatibility. They don't establish that a user's Desktop account can install the files and route model requests to them.
