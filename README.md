# AIRIS — AI Engine for Resource Intelligence and Sizing

AIRIS is an AI agent that analyzes Kubernetes workload resource allocations — CPU requests/limits, memory requests/limits, and storage claims — and produces actionable right-sizing recommendations. It understands the *intent* of an application by reading its source code, design documents, and workload context, then compares that against real observed cluster usage.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Clone the Repository](#clone-the-repository)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Running the Agent](#running-the-agent)
7. [CLI Reference](#cli-reference)
8. [Project Structure](#project-structure)

---

## Quick Start

```bash
# Clone (SSH)
git clone git@github.com:vyazovsky1/airis.git
cd airis

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your API keys (see Configuration section)

# Run a demo analysis
python src/main.py --demo --provider gemini
```

---

## Clone the Repository

### SSH (recommended)

```bash
git clone git@github.com:vyazovsky1/airis.git
cd airis
```

### HTTPS (if SSH keys are not configured)

```bash
git clone https://github.com/vyazovsky1/airis.git
cd airis
```

### Push an existing local repo

```bash
cd existing_repo
git remote add origin git@github.com:vyazovsky1/airis.git
git branch -M main
git push -uf origin main
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

---

## Configuration

`.env.example` is a committed template with placeholder values and full comments — it contains **no real secrets**.  
Copy it to `.env` (gitignored) and fill in your actual keys:

```bash
cp .env.example .env
# then edit .env with your real API keys
```

**`.env.example` variable reference:**

```env
# General Agent settings
LOG_LEVEL=INFO                        # DEBUG | INFO | WARNING | ERROR
MAX_SELF_CORRECTION_RETRIES=5         # Max LLM self-correction loops
TEMPERATURE=0.2                       # LLM temperature (lower = more deterministic)

# OpenAI
OPENAI_API_KEY=<your-openai-key>
DEFAULT_OPENAI_MODEL=gpt-4o           # Primary reasoning model
FAST_OPENAI_MODEL=gpt-4o-mini         # Fast model for discovery tasks

# Google Gemini
GEMINI_API_KEY=<your-gemini-key>
DEFAULT_GEMINI_MODEL=gemini-2.5-pro   # Primary reasoning model
FAST_GEMINI_MODEL=gemini-3.1-flash-lite-preview  # Fast model for discovery tasks

# Agent thresholds
STORAGE_GATE_LIMIT_GI=50              # PVC size (GiB) that triggers the storage gate
```

> **Note:** `.env` is listed in `.gitignore` — only `.env.example` (the template) is committed. Never put real API keys in `.env.example`.

---

## Running the Agent

The agent entrypoint is `src/main.py`. Always run from the **project root**:

```bash
python src/main.py [OPTIONS]
```

### Common examples

**Demo run — analyze the `payments-db` workload on PR #101 using Gemini:**
```bash
python src/main.py --demo --workload payments-db --pr 101 --provider gemini
```

**Analyze a specific PR using GPT-4o:**
```bash
python src/main.py --pr 42 --workload payments-api --provider openai
```

**Use a specific model, overriding the provider default:**
```bash
python src/main.py --pr 42 --workload payments-api --provider openai --model gpt-4o-mini
```

**Dry-run — analyze without posting a PR review comment:**
```bash
python src/main.py --pr 42 --workload payments-api --provider gemini --action dry-run
```

**Provide an explicit path to the workload source code:**
```bash
python src/main.py --pr 42 --workload payments-api --provider gemini --root ./apps/payments
```

---

## CLI Reference

| Argument | Type | Default | Description |
|---|---|---|---|
| `--demo` | flag | `false` | Run in demo mode with the pre-configured dummy PR scenario |
| `--workload` | string | `payments-db` | Name of the Kubernetes workload to analyze |
| `--pr` | int | `101` | Pull Request number to review |
| `--provider` | `openai` \| `gemini` | `gemini` | AI provider to use for reasoning |
| `--model` | string | *(provider default)* | Override the model name (e.g. `gpt-4o-mini`, `gemini-2.5-flash`) |
| `--action` | `pr` \| `dry-run` | `pr` | `pr` posts a review comment; `dry-run` prints the recommendation only |
| `--root` | string | `None` | Explicit path to the workload's source code / config directory |

---

## Project Structure

```
airis/
├── src/
│   ├── main.py              # CLI entrypoint & argument parser
│   ├── config.py            # Environment-backed configuration singleton
│   ├── orchestrator/        # Agent loop: perceive → reason → act → check
│   └── tools/               # MCP tool wrappers (Kubernetes, GitHub)
├── prompts/                 # Versioned LLM prompt templates (.txt / .jinja2)
├── examples/                # Example manifests and fixture data for testing
├── data/                    # Local metrics cache (CSV, gitignored)
├── requirements.txt
├── .env                     # Local configuration (do not commit)
├── solution_design.md       # Full solution design document
└── ToDo.md                  # Deferred implementation items
```
