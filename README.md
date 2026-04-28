# AIRIS — AI Engine for Resource Intelligence and Sizing

AIRIS is an AI agent that analyzes Kubernetes workload resource allocations — CPU requests/limits, memory requests/limits, and storage claims — and produces actionable right-sizing recommendations. It understands the *intent* of an application by reading its source code, design documents, and workload context, then compares that against real observed cluster usage.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [MCP Tool Setup](#mcp-tool-setup)
5. [Configuration](#configuration)
6. [Running the Agent](#running-the-agent)
7. [Running the Analyzer](#running-the-analyzer)
8. [CLI Reference](#cli-reference)
9. [Project Structure](#project-structure)

---

## Quick Start

```bash
# Clone
git clone git@github.com:vyazovsky1/airis.git
cd airis

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your API keys (see Configuration section)

# Dry-run PR review (prints recommendation, no GitHub post)
python src/agent/main.py --action dry-run --pr 42 --namespace default
```

---

## Prerequisites

- **Python 3.10+**
- Access to at least one supported AI provider:
  - [OpenAI API key](https://platform.openai.com/api-keys) (for GPT-4o)
  - [Google AI Studio API key](https://aistudio.google.com/app/apikey) (for Gemini)
- A configured `kubeconfig` with access to the target Kubernetes cluster
- `kubectl` access to the cluster (used by the MCP Kubernetes server)

---

## Installation

```bash
pip install -r requirements.txt
```

**Dependencies:**

| Package | Purpose |
|---|---|
| `openai >= 1.0.0` | OpenAI GPT-4o provider |
| `google-genai` | Google Gemini provider |
| `pydantic >= 2.0` | Structured data validation |
| `python-dotenv` | Environment variable loading |
| `mcp >= 1.0.0` | MCP client + server (Kubernetes, GitHub, Analyzer tools) |

---

## MCP Tool Setup

AIRIS connects to three MCP servers at startup. Tools are discovered automatically — nothing is hardcoded.

| Server | Transport | Purpose |
|---|---|---|
| `analyzer` | Python subprocess (stdio) | ARILC static analysis pipeline — scan repos, infer Resource DNA |
| `kubernetes` | `npx` (stdio) | Live cluster metrics, PVC inspection, pod exec |
| `github` | Docker (stdio) | PR diffs, file contents, review comments |

### Requirements

- **Node.js 18+** — for the Kubernetes MCP server (`npx`)
- **Docker** — for the GitHub MCP server (or a pre-built binary)
- **GitHub Personal Access Token** — classic token with `repo` scope

### Install External MCP Servers

**Linux / macOS / WSL:**

```bash
chmod +x tools/install_mcp.sh && ./tools/install_mcp.sh
```

**Windows (PowerShell):**

```powershell
.\tools\install_mcp.ps1
```

The scripts install `kubernetes-mcp-server` via `npm install -g` and pull the `ghcr.io/github/github-mcp-server` Docker image. The Analyzer MCP server is built-in and requires no installation.

### GitHub Binary Alternative

If Docker is unavailable, download the pre-built `github-mcp-server` binary from the [GitHub releases page](https://github.com/github/github-mcp-server/releases), add it to your PATH, then update `mcp_servers.json`:

```json
"github": {
  "command": "github-mcp-server",
  "args": ["stdio"],
  "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}" }
}
```

### Configure

Add to `.env`:

```env
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
```

Kubernetes MCP uses your local kubeconfig (`~/.kube/config`) automatically.

### Verify

```bash
python src/agent/main.py --action dry-run
```

The startup banner lists all discovered tools. If the tools list is empty, check that the MCP servers are installed and your `.env` is configured correctly.

---

## Configuration

`.env.example` is a committed template with placeholder values — it contains **no real secrets**.  
Copy it to `.env` (gitignored) and fill in your actual keys:

```bash
cp .env.example .env
```

**`.env.example` variable reference:**

```env
# General Agent settings
LOG_LEVEL=INFO                        # DEBUG | INFO | WARNING | ERROR
MAX_SELF_CORRECTION_RETRIES=5         # Max LLM self-correction loops
TEMPERATURE=0.2                       # LLM temperature (lower = more deterministic)

# OpenAI
OPENAI_API_KEY=<your-openai-key>
OPENAI_DEFAULT_MODEL=gpt-4o           # Primary reasoning model
OPENAI_FAST_MODEL=gpt-4o-mini         # Fast model for discovery tasks

# Google Gemini
GEMINI_API_KEY=<your-gemini-key>
GEMINI_DEFAULT_MODEL=gemini-2.5-pro   # Primary reasoning model
GEMINI_FAST_MODEL=gemini-3.1-flash-lite-preview  # Fast model for discovery tasks

# Agent thresholds
STORAGE_GATE_LIMIT_GI=50              # PVC size (GiB) that triggers the storage gate
```

> **Note:** `.env` is listed in `.gitignore` — only `.env.example` is committed. Never put real API keys in `.env.example`.

---

## Running the Agent

The agent entrypoint is `src/agent/main.py`. Always run from the **project root**:

```bash
python src/agent/main.py [OPTIONS]
```

### Common examples

**Analyze current K8s resource utilization in a namespace:**
```bash
python src/agent/main.py --action analyze --namespace payments
```

**Review a PR for resource impact, print result only:**
```bash
python src/agent/main.py --action dry-run --pr 42 --namespace payments --provider gemini
```

**Review a PR and post the result as a GitHub comment:**
```bash
python src/agent/main.py --action review --pr 42 --namespace payments --provider openai
```

**Use a specific model, overriding the provider default:**
```bash
python src/agent/main.py --action dry-run --pr 42 --provider openai --model gpt-4o-mini
```

---

## Running the Analyzer

The ARILC Analyzer can be run standalone to produce a full static-analysis report for any repository. Always run from the **project root**:

```bash
python src/analyzer/analyzer_main.py --repo <path> --workload <name> [OPTIONS]
```

### Examples

**Analyze a local repository with OpenAI:**
```bash
python src/analyzer/analyzer_main.py --repo ./apps/payments-api --workload payments-api
```

**Analyze with Gemini and a custom output directory:**
```bash
python src/analyzer/analyzer_main.py \
  --repo ./apps/payments-api \
  --workload payments-api \
  --out .data/reports/payments \
  --provider gemini
```

### Analyzer CLI Reference

| Argument | Default | Description |
|---|---|---|
| `--repo` | *(required)* | Path to the repository to analyze |
| `--workload` | *(required)* | Semantic name for the workload |
| `--out` | `.data/analysis/<workload>` | Output directory for artifacts |
| `--provider` | `openai` | LLM provider: `openai` or `gemini` |

### Analyzer Output Artifacts

All artifacts are written to `--out`:

| File | Description |
|---|---|
| `resource_dna_<workload>.json` | Machine-readable Resource DNA: CPU/memory/storage recommendations |
| `intelligence_report_<workload>.md` | Human-readable full-spectrum analysis report |
| `complexity_heatmap_<workload>.csv` | Per-file cyclomatic complexity scores |
| `doc_summary_<workload>.md` | LLM summary of documentation & developer intent |
| `infra_summary_<workload>.md` | LLM summary of infrastructure manifests |
| `dependencies_summary_<workload>.md` | LLM summary of dependency manifests |
| `module_dossiers/` | Per-file deep-dive logic analysis documents |
| `token_usage.json` | Token consumption breakdown by model tier |

---

## CLI Reference

### Agent (`src/agent/main.py`)

| Argument | Type | Default | Description |
|---|---|---|---|
| `--action` | `analyze` \| `review` \| `dry-run` | `dry-run` | `analyze` — K8s metrics review; `review` — PR review + post to GitHub; `dry-run` — PR review, print only |
| `--namespace` | string | `default` | Kubernetes namespace to inspect |
| `--pr` | int | — | Pull Request number (required for `review`/`dry-run`) |
| `--provider` | `openai` \| `gemini` | `openai` | AI provider |
| `--model` | string | *(provider default)* | Override the model name |
| `--log-level` | `DEBUG`…`ERROR` | `INFO` | Logging verbosity |

---

## Project Structure

```
airis/
├── src/
│   ├── agent/                   # AIRIS agent — agentic loop, CLI entrypoint
│   │   ├── main.py              # CLI entrypoint
│   │   ├── airis_agent.py       # AirisAgent: tool-call loop + decision parsing
│   │   ├── mcp_manager.py       # MCP server connection manager
│   │   └── github_utils.py      # GitHub API helpers (PR diff, post review)
│   ├── analyzer/                # ARILC static analysis pipeline
│   │   ├── analyzer_main.py     # Standalone CLI for the analyzer
│   │   ├── perception.py        # Phase 1: repo scan (languages, stack, entry points)
│   │   ├── logic_analysis.py    # Phase 2: complexity + tiered LLM analysis
│   │   ├── resource_profiler.py # Phase 3: Resource DNA inference
│   │   ├── generator/           # Phase 4: artifact generation
│   │   └── mcp_server/          # Analyzer exposed as MCP tools
│   │       └── analyzer_server.py
│   ├── core/                    # Shared: config, logger, LLM provider, token stats
│   │   └── token_stats.py       # Global token usage counters
│   └── scripts/                 # Dev utilities (not part of the runtime)
│       ├── llm_utils.py         # Model listing helpers
│       └── list_models.py       # Print available models for configured providers
├── prompts/                     # Versioned LLM prompt templates
├── mcp_servers.json             # MCP server config (Analyzer + Kubernetes + GitHub)
├── tools/                       # install_mcp.sh / install_mcp.ps1
├── examples/                    # Mock data for local development
├── .data/                       # Local state: analysis artifacts, CSV findings
├── requirements.txt
├── .env                         # Local configuration (do not commit)
├── solution_design.md           # Full solution design document
└── ToDo.md                      # Deferred implementation items
```
