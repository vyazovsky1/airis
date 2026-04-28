# AIRIS MCP Server Installer — Windows PowerShell

# Refresh PATH from registry so recently-installed tools (Node.js, Docker) are visible
# regardless of which terminal session launched this script
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("PATH", "User")

Write-Host "=========================================="
Write-Host "  AIRIS MCP Server Installer"
Write-Host "=========================================="
Write-Host ""

# ── Kubernetes MCP server (via npx / Node.js) ─────────────────────────────
Write-Host "Installing Kubernetes MCP server..."
Write-Host "  Source: https://github.com/containers/kubernetes-mcp-server"

$nodeCheck = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCheck) {
    Write-Host "  ERROR: Node.js is not found in PATH even after refresh."
    Write-Host "  Install Node.js 18+ from https://nodejs.org, then re-run this script."
    exit 1
}
$nodeVersion = & node --version
Write-Host "  Using Node.js $nodeVersion"
npm install -g kubernetes-mcp-server@latest
Write-Host "  OK: kubernetes-mcp-server installed"
Write-Host ""

# ── GitHub MCP server (via Docker) ────────────────────────────────────────
Write-Host "Setting up GitHub MCP server..."
Write-Host "  Source: https://github.com/github/github-mcp-server"

$dockerCheck = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCheck) {
    Write-Host "  WARNING: Docker is not installed."
    Write-Host "  Option 1: Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
    Write-Host "  Option 2: Download the pre-built Windows binary from:"
    Write-Host "    https://github.com/github/github-mcp-server/releases"
    Write-Host "  Then update mcp_servers.json:"
    Write-Host '    "command": "github-mcp-server", "args": ["stdio"]'
} else {
    docker pull ghcr.io/github/github-mcp-server
    Write-Host "  OK: github/github-mcp-server Docker image pulled"
}
Write-Host ""

Write-Host "=========================================="
Write-Host "  Next steps:"
Write-Host "  1. Add to .env:  GITHUB_PERSONAL_ACCESS_TOKEN=ghp_..."
Write-Host "  2. Verify kubectl works:  kubectl cluster-info"
Write-Host "  3. Test:  python src/main.py --action dry-run"
Write-Host "=========================================="
