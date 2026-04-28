"""ARILC Analyzer MCP Server — exposes the analyzer pipeline as MCP tools."""

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

# Project root is one level above src/
_PROJECT_ROOT = os.path.abspath(os.path.join(_SRC, ".."))
_DEFAULT_OUTPUT_BASE = os.path.join(_PROJECT_ROOT, ".data", "analysis")

mcp = FastMCP("ARILC Analyzer")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_output_dir(workload_name: str, output_dir: Optional[str]) -> str:
    if output_dir:
        return output_dir
    path = os.path.join(_DEFAULT_OUTPUT_BASE, workload_name)
    os.makedirs(path, exist_ok=True)
    return path


def _safe_json(obj) -> str:
    return json.dumps(obj, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool 1: Full pipeline
# ---------------------------------------------------------------------------

@mcp.tool()
def analyze_repository(
    repo_path: str,
    workload_name: str,
    output_dir: str = "",
    provider: str = "openai",
) -> str:
    """
    Run the full ARILC pipeline (Perception → Logic Analysis → Resource DNA → Artifacts)
    on a local repository. Returns the Resource DNA profile as JSON and the path where
    all artifacts were written.

    Args:
        repo_path: Absolute path to the repository to analyze.
        workload_name: Semantic name for the workload (e.g. 'payments-api').
        output_dir: Directory to write artifacts. Defaults to .data/analysis/<workload_name>.
        provider: LLM provider — 'openai' (default) or 'gemini'.
    """
    if not os.path.isdir(repo_path):
        return json.dumps({"error": f"repo_path does not exist: {repo_path}"})

    out = _resolve_output_dir(workload_name, output_dir or None)

    from core.logger import setup_logging
    from analyzer.perception import PerceptionEngine
    from analyzer.logic_analysis import LogicAnalyzer
    from analyzer.resource_profiler import ResourceProfiler
    import core.token_stats as token_stats

    setup_logging()
    token_stats.reset()

    perception = PerceptionEngine(repo_path, workload_name)
    scanner_artifacts = perception.scan()

    logic_engine = LogicAnalyzer(repo_path, scanner_artifacts, provider_type=provider)
    logic_artifacts = logic_engine.analyze()

    profiler = ResourceProfiler(repo_path, scanner_artifacts, logic_artifacts, provider_type=provider)
    resource_dna = profiler.profile()

    try:
        from analyzer.generator.artifact_manager import ArtifactManager
        ArtifactManager(workload_name, scanner_artifacts, logic_artifacts, resource_dna, out).generate_suite()
    except Exception as e:
        resource_dna["_artifact_error"] = str(e)

    return _safe_json({
        "workload": workload_name,
        "resource_dna": resource_dna,
        "artifacts_dir": out,
        "token_usage": token_stats.get_stats(),
    })


# ---------------------------------------------------------------------------
# Tool 2: Phase 1 only — Perception scan (no LLM)
# ---------------------------------------------------------------------------

@mcp.tool()
def scan_repository(repo_path: str, workload_name: str) -> str:
    """
    Run Phase 1 (Perception) only — no LLM calls. Quickly fingerprints the repository:
    detected languages, tech stack, entry points, and a count of source files.
    Use this for a cheap, fast overview before committing to a full analysis.

    Args:
        repo_path: Absolute path to the repository to scan.
        workload_name: Semantic name for the workload.
    """
    if not os.path.isdir(repo_path):
        return json.dumps({"error": f"repo_path does not exist: {repo_path}"})

    from core.logger import setup_logging
    from analyzer.perception import PerceptionEngine

    setup_logging()

    perception = PerceptionEngine(repo_path, workload_name)
    artifacts = perception.scan()

    return _safe_json({
        "workload": workload_name,
        "languages": artifacts["languages"],
        "stack": artifacts["stack"],
        "entry_points": artifacts["entry_points"],
        "source_file_count": len(artifacts["source_manifest"]),
        "docs_found": [d["file"] for d in artifacts["docs_context"]],
        "infra_found": [i["file"] for i in artifacts["infra_context"]],
    })


# ---------------------------------------------------------------------------
# Tool 3: Phases 1+2 — Logic & complexity analysis
# ---------------------------------------------------------------------------

@mcp.tool()
def analyze_logic(
    repo_path: str,
    workload_name: str,
    provider: str = "openai",
) -> str:
    """
    Run Phases 1+2 (Perception + Logic Analysis). Returns the complexity matrix,
    hot spots, per-file logic summaries, and summaries of documentation, infrastructure,
    and dependencies. Use this when you need to understand what the application does and
    how complex it is, without generating a full resource profile.

    Args:
        repo_path: Absolute path to the repository.
        workload_name: Semantic name for the workload.
        provider: LLM provider — 'openai' (default) or 'gemini'.
    """
    if not os.path.isdir(repo_path):
        return json.dumps({"error": f"repo_path does not exist: {repo_path}"})

    from core.logger import setup_logging
    from analyzer.perception import PerceptionEngine
    from analyzer.logic_analysis import LogicAnalyzer
    import core.token_stats as token_stats

    setup_logging()
    token_stats.reset()

    perception = PerceptionEngine(repo_path, workload_name)
    scanner_artifacts = perception.scan()

    logic_engine = LogicAnalyzer(repo_path, scanner_artifacts, provider_type=provider)
    logic_artifacts = logic_engine.analyze()

    return _safe_json({
        "workload": workload_name,
        "languages": scanner_artifacts["languages"],
        "stack": scanner_artifacts["stack"],
        "entry_points": scanner_artifacts["entry_points"],
        "signal_matrix": logic_artifacts["signal_matrix"],
        "logic_summaries": logic_artifacts["logic_summaries"],
        "doc_summary": logic_artifacts.get("doc_summary", ""),
        "infra_summary": logic_artifacts.get("infra_summary", ""),
        "dependencies_summary": logic_artifacts.get("dependencies_summary", ""),
        "token_usage": token_stats.get_stats(),
    })


# ---------------------------------------------------------------------------
# Tool 4: Phase 3 only — Resource DNA from pre-computed artifacts
# ---------------------------------------------------------------------------

@mcp.tool()
def profile_resources(
    repo_path: str,
    workload_name: str,
    perception_json: str,
    logic_json: str,
    provider: str = "openai",
) -> str:
    """
    Run Phase 3 (Resource DNA Inference) only, using pre-computed perception and logic
    artifacts. Use this for re-runs or when you already have scan/analyze_logic output
    and only need the resource recommendations regenerated.

    Args:
        repo_path: Absolute path to the repository (used for context only).
        workload_name: Semantic name for the workload.
        perception_json: JSON string output from scan_repository.
        logic_json: JSON string output from analyze_logic.
        provider: LLM provider — 'openai' (default) or 'gemini'.
    """
    try:
        perception_artifacts = json.loads(perception_json)
        logic_artifacts = json.loads(logic_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON input: {e}"})

    from core.logger import setup_logging
    from analyzer.resource_profiler import ResourceProfiler
    import core.token_stats as token_stats

    setup_logging()
    token_stats.reset()

    profiler = ResourceProfiler(repo_path, perception_artifacts, logic_artifacts, provider_type=provider)
    resource_dna = profiler.profile()

    return _safe_json({
        "workload": workload_name,
        "resource_dna": resource_dna,
        "token_usage": token_stats.get_stats(),
    })


# ---------------------------------------------------------------------------
# Tool 5: Quick developer-intent summary from docs only
# ---------------------------------------------------------------------------

@mcp.tool()
def get_workload_intent(
    repo_path: str,
    workload_name: str,
    provider: str = "openai",
) -> str:
    """
    Extract a developer-intent summary by reading only documentation files (README,
    ARCHITECTURE, DESIGN, etc.) and dependency manifests from the repository — no
    source code analysis. Much faster than a full analyze_logic call. Useful as a
    pre-flight step before a K8s resource review to understand what the workload is
    meant to do.

    Args:
        repo_path: Absolute path to the repository.
        workload_name: Semantic name for the workload.
        provider: LLM provider — 'openai' (default) or 'gemini'.
    """
    if not os.path.isdir(repo_path):
        return json.dumps({"error": f"repo_path does not exist: {repo_path}"})

    from core.logger import setup_logging
    from analyzer.perception import PerceptionEngine
    from core.llm_provider import get_llm_provider
    from core.utils import load_prompt
    import core.token_stats as token_stats

    setup_logging()
    token_stats.reset()

    perception = PerceptionEngine(repo_path, workload_name)
    artifacts = perception.scan()

    llm = get_llm_provider(provider)
    summaries = {}

    docs = artifacts.get("docs_context", [])
    if docs:
        doc_data = "\n".join([f"FILE: {d['file']}\n{d['content']}" for d in docs])
        try:
            summaries["developer_intent"] = llm.generate(
                system_prompt=load_prompt("analyzer_doc_summary_system.txt"),
                user_prompt=load_prompt("analyzer_doc_summary.txt").replace("{{ doc_data }}", doc_data),
                tier="fast",
            )
        except Exception as e:
            summaries["developer_intent"] = f"[Failed: {e}]"

    manifests = artifacts.get("manifest_context", [])
    if manifests:
        deps_data = "\n".join([f"FILE: {m['file']}\n{m['content']}" for m in manifests])
        try:
            summaries["dependency_intent"] = llm.generate(
                system_prompt=load_prompt("analyzer_deps_summary_system.txt"),
                user_prompt=load_prompt("analyzer_deps_summary.txt").replace("{{ deps_data }}", deps_data),
                tier="fast",
            )
        except Exception as e:
            summaries["dependency_intent"] = f"[Failed: {e}]"

    return _safe_json({
        "workload": workload_name,
        "languages": artifacts["languages"],
        "stack": artifacts["stack"],
        "summaries": summaries,
        "token_usage": token_stats.get_stats(),
    })


# ---------------------------------------------------------------------------
# Tool 6: Read a previously generated analysis artifact
# ---------------------------------------------------------------------------

@mcp.tool()
def read_analysis_artifact(
    workload_name: str,
    artifact_type: str,
    output_dir: str = "",
) -> str:
    """
    Read a previously generated ARILC artifact for a workload. Useful for caching:
    run analyze_repository once, then read results in subsequent agent turns without
    re-running the expensive pipeline.

    Args:
        workload_name: Semantic name for the workload.
        artifact_type: One of: 'resource_dna', 'intelligence_report', 'complexity_heatmap',
                       'doc_summary', 'infra_summary', 'dependencies_summary', 'token_usage'.
        output_dir: Directory where artifacts were written. Defaults to .data/analysis/<workload_name>.
    """
    base = _resolve_output_dir(workload_name, output_dir or None)

    filename_map = {
        "resource_dna":          f"resource_dna_{workload_name}.json",
        "intelligence_report":   f"intelligence_report_{workload_name}.md",
        "complexity_heatmap":    f"complexity_heatmap_{workload_name}.csv",
        "doc_summary":           f"doc_summary_{workload_name}.md",
        "infra_summary":         f"infra_summary_{workload_name}.md",
        "dependencies_summary":  f"dependencies_summary_{workload_name}.md",
        "token_usage":           "token_usage.json",
    }

    if artifact_type not in filename_map:
        return json.dumps({
            "error": f"Unknown artifact_type '{artifact_type}'. Valid values: {list(filename_map.keys())}"
        })

    path = os.path.join(base, filename_map[artifact_type])
    if not os.path.exists(path):
        return json.dumps({"error": f"Artifact not found: {path}. Run analyze_repository first."})

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if artifact_type in ("resource_dna", "token_usage"):
        try:
            return _safe_json(json.loads(content))
        except json.JSONDecodeError:
            pass

    return content


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
