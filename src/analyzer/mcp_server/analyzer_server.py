"""ARILC Analyzer MCP Server — exposes analysis artifacts as MCP tools."""

import json
import os
import sys
from typing import Optional

# Ensure src/ is on the path regardless of working directory
_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

_PROJECT_ROOT = os.path.abspath(os.path.join(_SRC, ".."))
_DEFAULT_OUTPUT_BASE = os.path.join(_PROJECT_ROOT, ".data", "analysis")

mcp = FastMCP("ARILC Analyzer")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_output_dir(application: str, output_dir: Optional[str]) -> str:
    if output_dir:
        return output_dir
    path = os.path.join(_DEFAULT_OUTPUT_BASE, application)
    os.makedirs(path, exist_ok=True)
    return path


def _safe_json(obj) -> str:
    return json.dumps(obj, indent=2, default=str)


def _no_analysis_error(application: str, artifacts_dir: str) -> str:
    return _safe_json({
        "error": f"No analysis artifacts found for application '{application}'.",
        "resolution": (
            "Run the ARILC analysis pipeline first:\n"
            f"  python src/analyzer/analyzer_main.py "
            f"--repo <repo_path> --application {application} --out {artifacts_dir}"
        ),
    })


def _artifact_catalog() -> dict:
    """Maps artifact name → (filename_or_dirname, description)."""
    return {
        "resource_dna": (
            "resource_dna.json",
            "Machine-readable resource profile: CPU/memory recommendations, application archetype, risk advisories",
        ),
        "intelligence_report": (
            "intelligence_report.md",
            "Human-readable report: archetype, resource table, signal matrix, risk advisories",
        ),
        "doc_summary": (
            "doc_summary.md",
            "LLM summary of documentation files (README, ARCHITECTURE, DESIGN, etc.)",
        ),
        "infra_summary": (
            "infra_summary.md",
            "LLM summary of infrastructure and deployment files (Dockerfile, k8s manifests, etc.)",
        ),
        "dependencies_summary": (
            "dependencies_summary.md",
            "LLM summary of dependency manifests (package.json, pom.xml, requirements.txt, etc.)",
        ),
        "module_summary": (
            "module_summary",
            "Per-module deep-dive summaries, one markdown file per analyzed source file",
        ),
    }


# ---------------------------------------------------------------------------
# Tool 1: List analyzed applications
# ---------------------------------------------------------------------------

@mcp.tool()
def list_applications(output_dir: str = "") -> str:
    """
    List all applications that have been analyzed.

    Args:
        output_dir: Directory where artifacts were written. Defaults to .data/analysis/.
    """
    base = output_dir or _DEFAULT_OUTPUT_BASE
    if not os.path.exists(base):
        return _safe_json({"applications": []})
        
    apps = []
    for item in os.listdir(base):
        if os.path.isdir(os.path.join(base, item)):
            apps.append(item)
            
    return _safe_json({
        "artifacts_dir": base,
        "applications": sorted(apps),
    })


# ---------------------------------------------------------------------------
# Tool 2: List available artifacts
# ---------------------------------------------------------------------------

@mcp.tool()
def list_artifacts(application: str, output_dir: str = "") -> str:
    """
    List all analysis artifacts for an application with their filenames and descriptions.
    Shows which artifacts already exist on disk. Call this before get_artifacts.

    Args:
        application: Semantic name for the application.
        output_dir: Directory where artifacts were written. Defaults to .data/analysis/<application>.
    """
    base = _resolve_output_dir(application, output_dir or None)
    catalog = _artifact_catalog()

    artifacts = []
    for name, (filename, description) in catalog.items():
        path = os.path.join(base, filename)
        entry = {
            "name": name,
            "file": filename,
            "description": description,
            "exists": os.path.exists(path),
        }
        if name == "module_summary" and os.path.isdir(path):
            entry["modules"] = sorted(
                f for f in os.listdir(path) if f.endswith(".md")
            )
        artifacts.append(entry)

    if not any(a["exists"] for a in artifacts):
        return _no_analysis_error(application, base)

    return _safe_json({
        "application": application,
        "artifacts_dir": base,
        "artifacts": artifacts,
    })


# ---------------------------------------------------------------------------
# Tool 3: Get artifact contents
# ---------------------------------------------------------------------------

@mcp.tool()
def get_artifacts(
    application: str,
    artifact_names: list[str],
    output_dir: str = "",
) -> str:
    """
    Return the contents of one or more analysis artifacts. Use list_artifacts first
    to see what is available and which names to pass.

    Args:
        application: Semantic name for the application.
        artifact_names: List of artifact names to retrieve, e.g. ["resource_dna", "doc_summary"].
        output_dir: Directory where artifacts were written. Defaults to .data/analysis/<application>.
    """
    base = _resolve_output_dir(application, output_dir or None)
    catalog = _artifact_catalog()

    # Check if any analysis exists at all before processing individual names
    catalog_all = _artifact_catalog()
    if not any(os.path.exists(os.path.join(base, f)) for f, _ in catalog_all.values()):
        return _no_analysis_error(application, base)

    results = {}
    errors = {}

    for name in artifact_names:
        if name not in catalog:
            errors[name] = f"Unknown artifact. Valid names: {list(catalog.keys())}"
            continue

        filename, _ = catalog[name]
        path = os.path.join(base, filename)

        if not os.path.exists(path):
            errors[name] = f"Artifact '{name}' not found at {path}."
            continue

        try:
            if name == "module_summary":
                files = {}
                for fname in sorted(os.listdir(path)):
                    if fname.endswith(".md"):
                        with open(os.path.join(path, fname), "r", encoding="utf-8") as f:
                            files[fname] = f.read()
                results[name] = files
            elif filename.endswith(".json"):
                with open(path, "r", encoding="utf-8") as f:
                    results[name] = json.load(f)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    results[name] = f.read()
        except Exception as e:
            errors[name] = str(e)

    response: dict = {"application": application, "artifacts": results}
    if errors:
        response["errors"] = errors
    return _safe_json(response)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
