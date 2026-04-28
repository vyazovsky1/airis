#!/usr/bin/env bash
set -e

echo "=========================================="
echo "  AIRIS MCP Server Installer"
echo "=========================================="
echo ""

# ── Kubernetes MCP server (via npx / Node.js) ─────────────────────────────
echo "Installing Kubernetes MCP server..."
echo "  Source: https://github.com/containers/kubernetes-mcp-server"

if ! command -v node &>/dev/null; then
    echo "  ERROR: Node.js is not installed. Install Node.js 18+ from https://nodejs.org"
    exit 1
fi
echo "  Using Node.js $(node --version)"
npm install -g kubernetes-mcp-server@latest
echo "  OK: kubernetes-mcp-server installed"
echo ""

# ── GitHub MCP server (via Docker) ────────────────────────────────────────
echo "Setting up GitHub MCP server..."
echo "  Source: https://github.com/github/github-mcp-server"

if command -v docker &>/dev/null; then
    docker pull ghcr.io/github/github-mcp-server
    echo "  OK: github/github-mcp-server Docker image pulled"
else
    echo "  WARNING: Docker is not installed."
    echo "  Option 1: Install Docker from https://docs.docker.com/get-docker/"
    echo "  Option 2: Download the pre-built binary from:"
    echo "    https://github.com/github/github-mcp-server/releases"
    echo "  Place it in PATH and update mcp_servers.json:"
    echo '    "command": "github-mcp-server", "args": ["stdio"]'
fi
echo ""

echo "=========================================="
echo "  Next steps:"
echo "  1. Add to .env:  GITHUB_PERSONAL_ACCESS_TOKEN=ghp_..."
echo "  2. Verify kubectl works:  kubectl cluster-info"
echo "  3. Test:  python src/main.py --action dry-run"
echo "=========================================="
