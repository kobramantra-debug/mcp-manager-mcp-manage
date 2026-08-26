# MCP Manager

Universal MCP Server Manager — add, remove, monitor, and configure all your MCP servers from one place.

## Features

- **7 harnesses** — OpenCode, Claude Desktop, Cursor, Windsurf, Cline, Zed, Continue.dev
- **23 tools** — server management, health checks, token rotation, cross-harness sync
- **20+ server catalog** — GitHub, Supabase, Playwright, Docker, PostgreSQL, and more
- **Encrypted tokens** — Fernet AES-128-CBC with PBKDF2 key derivation
- **Cross-harness sync** — migrate servers between different AI coding tools

## Installation

### From PyPI (recommended)

```bash
pip install mcp-manager
```

### From source

```bash
git clone https://github.com/mcp-manager/mcp-manager.git
cd mcp-manager
pip install -e .
```

### Docker

```bash
docker build -t mcp-manager .
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HARNESS` | `opencode` | Active harness to manage |
| `MCP_CONFIG_PATH` | *(auto-detected)* | Override config file path |
| `MCP_MANAGER_MASTER_PASSWORD` | *(none)* | Master password for Fernet encryption |

### OpenCode

Add to `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "mcp-manager": {
      "type": "local",
      "command": ["python", "-m", "src"],
      "cwd": "/path/to/mcp-manager",
      "enabled": true
    }
  }
}
```

### Claude Desktop

Add to `%APPDATA%/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-manager": {
      "command": "python",
      "args": ["-m", "src"],
      "cwd": "/path/to/mcp-manager"
    }
  }
}
```

### Docker (STDIO)

```json
{
  "mcp": {
    "mcp-manager": {
      "type": "docker",
      "command": ["docker", "run", "-i", "--rm", "mcp-manager"],
      "enabled": true
    }
  }
}
```

## Usage

### List all harnesses

```
list_harnesses_info()
```

Returns info about all supported harnesses and which ones are installed.

### Switch harness

```
switch_harness("claude-desktop")
```

### Add a server from catalog

```
add_from_catalog("github")
```

### Add a custom server

```
add_server("my-api", server_type="remote", url="https://api.example.com/mcp")
```

### Health check

```
health_check()
```

### Sync servers between harnesses

```
sync_to_harness("cursor")
```

### Rotate a token

```
rotate_token("github", "ghp_new_token_here", expires_at="2026-12-31")
```

## Tools Reference

### Harness Management
- `list_harnesses_info` — List all harnesses and installation status
- `switch_harness` — Switch active harness
- `get_active_harness` — Get current harness info

### Server Management
- `list_servers` — List configured servers
- `add_server` — Add a new server
- `remove_server` — Remove a server
- `get_server_detail` — Get server details
- `enable_server` / `disable_server` — Toggle server

### Health & Monitoring
- `test_connection` — Test a single server
- `health_check` — Test all servers
- `get_logs` — Get health check history

### Token Management
- `rotate_token` — Update API token
- `retrieve_token` — Get decrypted token (use with caution)
- `list_all_tokens` — List stored tokens (previews only)
- `get_token_history` — Get rotation history
- `list_token_backends` — Show encryption status

### Export / Import / Sync
- `export_config` — Export config as JSON
- `import_config` — Import config from JSON
- `export_for_harness` — Export in another harness format
- `sync_to_harness` — Sync servers to another harness

### Catalog
- `search_catalog` — Search server catalog
- `add_from_catalog` — Add server from catalog

## Supported Harnesses

| Harness | Config Path | Format |
|---------|-------------|--------|
| OpenCode | `~/.config/opencode/opencode.json` | `mcp` (keyed object) |
| Claude Desktop | `%APPDATA%/Claude/claude_desktop_config.json` | `mcpServers` (keyed object) |
| Cursor | `~/.cursor/mcp.json` | `mcpServers` (keyed object) |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | `mcpServers` (keyed object) |
| Cline | `%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` | `mcpServers` (keyed object) |
| Zed | `%APPDATA%/Zed/settings.json` | `context_servers` (nested object) |
| Continue.dev | `~/.continue/config.json` | `mcpServers` (array) |

## Token Security

Tokens are stored in an encrypted SQLite database using Fernet (AES-128-CBC).

Set `MCP_MANAGER_MASTER_PASSWORD` to enable encryption:

```bash
export MCP_MANAGER_MASTER_PASSWORD="your-secure-password"
```

Without a master password, tokens are stored in plaintext (not recommended for production).

## License

MIT License — see [LICENSE](LICENSE) for details.
