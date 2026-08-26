"""Health checker for MCP servers.

Sends MCP initialize requests to servers via STDIO, Docker, or HTTP
and reports their status (healthy, unhealthy, timeout, unknown).
"""

import asyncio
import json
import os
import subprocess
import time
from datetime import datetime
from typing import Any, Optional


class HealthStatus:
    """Result of a health check for an MCP server."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"

    def __init__(self, status: str, message: str = "", latency_ms: float = 0):
        self.status = status
        self.message = message
        self.latency_ms = latency_ms
        self.checked_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """Serialize the health status to a dictionary."""
        return {
            "status": self.status,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "checked_at": self.checked_at,
        }


class HealthChecker:
    """Checks the health of MCP servers by sending initialize requests."""

    def __init__(self, timeout_seconds: int = 5):
        self.timeout = timeout_seconds
        self._history: dict[str, list[dict]] = {}

    def check_stdio(self, command: list[str], env: Optional[dict[str, str]] = None) -> HealthStatus:
        """Test a STDIO-based MCP server by sending an initialize request."""
        init_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "mcp-manager-health-check", "version": "1.0"},
            },
        })

        try:
            start = time.time()
            process_env = os.environ.copy()
            if env:
                process_env.update(env)

            result = subprocess.run(
                command,
                input=init_request + "\n",
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=process_env,
            )
            latency = (time.time() - start) * 1000

            if result.returncode == 0 and result.stdout.strip():
                # Try to parse the JSON-RPC response
                for line in result.stdout.strip().split("\n"):
                    try:
                        response = json.loads(line)
                        if "result" in response:
                            server_info = response["result"].get("serverInfo", {})
                            return HealthStatus(
                                HealthStatus.HEALTHY,
                                f"Server: {server_info.get('name', 'unknown')}",
                                latency,
                            )
                    except json.JSONDecodeError:
                        continue

                return HealthStatus(HealthStatus.HEALTHY, "Responded (non-JSON)", latency)
            else:
                return HealthStatus(HealthStatus.UNHEALTHY, f"No response (exit {result.returncode})", latency)

        except subprocess.TimeoutExpired:
            return HealthStatus(HealthStatus.TIMEOUT, f"Timeout after {self.timeout}s")
        except FileNotFoundError:
            return HealthStatus(HealthStatus.UNHEALTHY, f"Command not found: {command[0]}")
        except Exception as e:
            return HealthStatus(HealthStatus.UNHEALTHY, str(e))

    def check_docker(self, image: str, env: Optional[dict[str, str]] = None) -> HealthStatus:
        """Test a Docker-based MCP server."""
        command = ["docker", "run", "-i", "--rm", "--entrypoint", ""]

        if env:
            for k, v in env.items():
                if not v.startswith("{env:"):
                    command.extend(["-e", f"{k}={v}"])

        command.append(image)
        command.extend(["echo", "ok"])

        try:
            start = time.time()
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout + 10,  # Docker has extra overhead
            )
            latency = (time.time() - start) * 1000

            if result.returncode == 0:
                return HealthStatus(HealthStatus.HEALTHY, "Docker container accessible", latency)
            else:
                return HealthStatus(HealthStatus.UNHEALTHY, f"Docker error: {result.stderr[:200]}", latency)

        except subprocess.TimeoutExpired:
            return HealthStatus(HealthStatus.TIMEOUT, f"Docker timeout after {self.timeout + 10}s")
        except Exception as e:
            return HealthStatus(HealthStatus.UNHEALTHY, str(e))

    def check_http(self, url: str, headers: Optional[dict[str, str]] = None) -> HealthStatus:
        """Test an HTTP/remote MCP server."""
        import urllib.request
        import urllib.error

        start = time.time()
        try:
            req = urllib.request.Request(url, method="GET")
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)

            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                latency = (time.time() - start) * 1000
                if resp.status < 400:
                    return HealthStatus(HealthStatus.HEALTHY, f"HTTP {resp.status}", latency)
                else:
                    return HealthStatus(HealthStatus.UNHEALTHY, f"HTTP {resp.status}", latency)

        except urllib.error.HTTPError as e:
            latency = (time.time() - start) * 1000
            if e.code == 404:
                return HealthStatus(HealthStatus.HEALTHY, "Endpoint exists (404 is normal for MCP)", latency)
            return HealthStatus(HealthStatus.UNHEALTHY, f"HTTP {e.code}", latency)
        except Exception as e:
            return HealthStatus(HealthStatus.UNHEALTHY, str(e))

    def check_server(self, name: str, config: dict[str, Any]) -> HealthStatus:
        """Check a server based on its configuration type (local/docker/remote)."""
        server_type = config.get("type", "local")
        env = config.get("environment", {})

        # Resolve {env:VAR} placeholders
        resolved_env = {}
        for k, v in env.items():
            if isinstance(v, str) and v.startswith("{env:") and v.endswith("}"):
                env_var = v[5:-1]
                resolved_env[k] = os.environ.get(env_var, v)
            else:
                resolved_env[k] = v

        if server_type == "local" or server_type == "npx":
            command = config.get("command", [])
            if not command:
                return HealthStatus(HealthStatus.UNKNOWN, "No command configured")
            status = self.check_stdio(command, resolved_env or None)
        elif server_type == "docker":
            command = config.get("command", [])
            if command:
                status = self.check_stdio(command, resolved_env or None)
            else:
                image = config.get("image", "")
                status = self.check_docker(image, resolved_env or None)
        elif server_type == "remote":
            url = config.get("url", "")
            headers = config.get("headers", {})
            status = self.check_http(url, headers or None)
        else:
            status = HealthStatus(HealthStatus.UNKNOWN, f"Unknown type: {server_type}")

        # Store in history (keep last 100 entries per server)
        self._history.setdefault(name, []).append(status.to_dict())
        if len(self._history[name]) > 100:
            self._history[name] = self._history[name][-100:]

        return status

    def check_all(self, servers: dict[str, dict[str, Any]]) -> dict[str, dict]:
        """Check all servers and return a summary."""
        results = {}
        for name, config in servers.items():
            status = self.check_server(name, config)
            results[name] = status.to_dict()
        return results

    def get_history(self, server_name: str, limit: int = 10) -> list[dict]:
        """Get recent health check history for a server."""
        return self._history.get(server_name, [])[-limit:]
