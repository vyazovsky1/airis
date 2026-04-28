#!/usr/bin/env python3
"""
Analyzer MCP Server test suite — exercises all 6 tools via MCPManager.

Run from project root:
    python src/analyzer/test/test_analyzer_mcp.py
"""

import json
import os
import sys
import asyncio

# Ensure src/ is on the path
SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from dotenv import load_dotenv
load_dotenv()

from agent.mcp_manager import MCPManager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
SCAN_REPO_PATH = "/mnt/c/Dev/tmp/nodejs-demoapp"
WORKLOAD_NAME = "nodejs-demoapp"
MODEL = "gpt-4o"
PROVIDER = "openai"
TEST_OUTPUT_DIR = os.path.join(PROJECT_ROOT, ".data", "analysis", WORKLOAD_NAME)
MCP_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "analyzer_mcp_test.json")

# Pin both tiers to the requested model
os.environ["OPENAI_DEFAULT_MODEL"] = MODEL
os.environ["OPENAI_FAST_MODEL"] = MODEL
os.environ.setdefault("LOG_LEVEL", "WARNING")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _header(title: str) -> None:
    print(f"\n{'='*70}\n{title}\n{'='*70}")


def _parse(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}


def _ok(resp: dict) -> bool:
    return "error" not in resp


# ---------------------------------------------------------------------------
# Tool listing — query live from the server
# ---------------------------------------------------------------------------

async def list_tools(mcp_manager: MCPManager) -> None:
    """Print all registered tools with their descriptions and parameters."""
    _header("AVAILABLE TOOLS")

    analyzer_tools = [t for t in mcp_manager.tools if t["function"]["name"].startswith("analyzer__")]
    print(f"Total registered: {len(mcp_manager.tools)}  |  Analyzer tools: {len(analyzer_tools)}\n")

    for t in analyzer_tools:
        fn = t["function"]
        name = fn["name"]
        desc = fn.get("description", "").strip()
        params = fn.get("parameters", {})
        props = params.get("properties", {})
        required = set(params.get("required", []))

        # First non-empty line of the docstring
        first_line = next((l.strip() for l in desc.splitlines() if l.strip()), desc)

        print(f"  Tool: {name}")
        print(f"    Description : {first_line}")
        print(f"    Parameters  :")
        for pname, schema in props.items():
            ptype = schema.get("type", "any")
            pdesc = schema.get("description", "").split("\n")[0].strip()
            req = " [required]" if pname in required else " [optional]"
            print(f"      - {pname} ({ptype}){req}: {pdesc}")
        print()


# ---------------------------------------------------------------------------
# Test 1: scan_repository — Phase 1 only, no LLM
# ---------------------------------------------------------------------------

async def test_scan_repository(mcp_manager: MCPManager) -> tuple[bool, dict]:
    """
    Tool  : scan_repository
    Params: repo_path, workload_name
    """
    _header("TEST 1: scan_repository — Phase 1 Perception (no LLM)")
    print(f"  repo_path     = {SCAN_REPO_PATH}")
    print(f"  workload_name = {WORKLOAD_NAME}")

    try:
        raw = await mcp_manager.call_tool(
            "analyzer__scan_repository",
            {
                "repo_path": SCAN_REPO_PATH,
                "workload_name": WORKLOAD_NAME,
            },
        )
        resp = _parse(raw)

        if not _ok(resp):
            print(f"  ✗ Error: {resp['error']}")
            return False, {}

        print(f"  ✓ Perception scan complete")
        print(f"    languages      : {resp.get('languages', [])}")
        print(f"    stack          : {resp.get('stack', [])}")
        print(f"    entry_points   : {resp.get('entry_points', [])}")
        print(f"    source_files   : {resp.get('source_file_count', 0)}")
        print(f"    docs_found     : {len(resp.get('docs_found', []))}")
        print(f"    infra_found    : {len(resp.get('infra_found', []))}")
        return True, resp

    except Exception as e:
        print(f"  ✗ Exception: {e}")
        import traceback; traceback.print_exc()
        return False, {}


# ---------------------------------------------------------------------------
# Test 2: analyze_logic — Phases 1+2
# ---------------------------------------------------------------------------

async def test_analyze_logic(mcp_manager: MCPManager) -> tuple[bool, dict]:
    """
    Tool  : analyze_logic
    Params: repo_path, workload_name, provider
    """
    _header("TEST 2: analyze_logic — Phases 1+2 (Perception + Logic Analysis)")
    print(f"  repo_path     = {SCAN_REPO_PATH}")
    print(f"  workload_name = {WORKLOAD_NAME}")
    print(f"  provider      = {PROVIDER}  (model: {MODEL})")

    try:
        raw = await mcp_manager.call_tool(
            "analyzer__analyze_logic",
            {
                "repo_path": SCAN_REPO_PATH,
                "workload_name": WORKLOAD_NAME,
                "provider": PROVIDER,
            },
        )
        resp = _parse(raw)

        if not _ok(resp):
            print(f"  ✗ Error: {resp['error']}")
            return False, {}

        print(f"  ✓ Logic analysis complete")
        print(f"    languages          : {resp.get('languages', [])}")
        print(f"    stack              : {resp.get('stack', [])}")
        print(f"    signal_matrix      : {len(resp.get('signal_matrix', []))} entries")
        print(f"    logic_summaries    : {len(resp.get('logic_summaries', {}))} files")
        print(f"    doc_summary        : {len(resp.get('doc_summary', ''))} chars")
        print(f"    infra_summary      : {len(resp.get('infra_summary', ''))} chars")
        print(f"    dependencies_summary: {len(resp.get('dependencies_summary', ''))} chars")
        usage = resp.get("token_usage", {})
        if usage:
            print(f"    token_usage        : {json.dumps(usage)}")
        return True, resp

    except Exception as e:
        print(f"  ✗ Exception: {e}")
        import traceback; traceback.print_exc()
        return False, {}


# ---------------------------------------------------------------------------
# Test 3: get_workload_intent — docs-only, fast
# ---------------------------------------------------------------------------

async def test_get_workload_intent(mcp_manager: MCPManager) -> bool:
    """
    Tool  : get_workload_intent
    Params: repo_path, workload_name, provider
    """
    _header("TEST 3: get_workload_intent — Docs-only Intent Summary (fast)")
    print(f"  repo_path     = {SCAN_REPO_PATH}")
    print(f"  workload_name = {WORKLOAD_NAME}")
    print(f"  provider      = {PROVIDER}  (model: {MODEL})")

    try:
        raw = await mcp_manager.call_tool(
            "analyzer__get_workload_intent",
            {
                "repo_path": SCAN_REPO_PATH,
                "workload_name": WORKLOAD_NAME,
                "provider": PROVIDER,
            },
        )
        resp = _parse(raw)

        if not _ok(resp):
            print(f"  ✗ Error: {resp['error']}")
            return False

        print(f"  ✓ Workload intent extracted")
        print(f"    languages : {resp.get('languages', [])}")
        print(f"    stack     : {resp.get('stack', [])}")
        for k, v in resp.get("summaries", {}).items():
            print(f"    {k} : {len(str(v))} chars")
        usage = resp.get("token_usage", {})
        if usage:
            print(f"    token_usage : {json.dumps(usage)}")
        return True

    except Exception as e:
        print(f"  ✗ Exception: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Test 4: profile_resources — Phase 3 only, from cached JSON
# ---------------------------------------------------------------------------

async def test_profile_resources(
    mcp_manager: MCPManager,
    scan_json: str,
    logic_json: str,
) -> tuple[bool, dict]:
    """
    Tool  : profile_resources
    Params: repo_path, workload_name, perception_json, logic_json, provider

    Feeds the JSON outputs from test_scan_repository and test_analyze_logic
    back into the profiler so Phase 3 can be re-run without re-scanning.
    """
    _header("TEST 4: profile_resources — Phase 3 Resource DNA (from cached artifacts)")
    print(f"  repo_path       = {SCAN_REPO_PATH}")
    print(f"  workload_name   = {WORKLOAD_NAME}")
    print(f"  provider        = {PROVIDER}  (model: {MODEL})")
    print(f"  perception_json = {len(scan_json)} chars")
    print(f"  logic_json      = {len(logic_json)} chars")

    try:
        raw = await mcp_manager.call_tool(
            "analyzer__profile_resources",
            {
                "repo_path": SCAN_REPO_PATH,
                "workload_name": WORKLOAD_NAME,
                "perception_json": scan_json,
                "logic_json": logic_json,
                "provider": PROVIDER,
            },
        )
        resp = _parse(raw)

        if not _ok(resp):
            print(f"  ✗ Error: {resp['error']}")
            return False, {}

        print(f"  ✓ Resource DNA inferred")
        dna = resp.get("resource_dna", {})
        print(f"    resource_dna keys : {list(dna.keys())[:8]}")
        usage = resp.get("token_usage", {})
        if usage:
            print(f"    token_usage       : {json.dumps(usage)}")
        return True, resp

    except Exception as e:
        print(f"  ✗ Exception: {e}")
        import traceback; traceback.print_exc()
        return False, {}


# ---------------------------------------------------------------------------
# Test 5: analyze_repository — full pipeline
# ---------------------------------------------------------------------------

async def test_analyze_repository(mcp_manager: MCPManager) -> tuple[bool, dict]:
    """
    Tool  : analyze_repository
    Params: repo_path, workload_name, output_dir, provider
    """
    _header("TEST 5: analyze_repository — Full Pipeline (Phases 1→2→3 + Artifacts)")
    print(f"  repo_path     = {SCAN_REPO_PATH}")
    print(f"  workload_name = {WORKLOAD_NAME}")
    print(f"  output_dir    = {TEST_OUTPUT_DIR}")
    print(f"  provider      = {PROVIDER}  (model: {MODEL})")

    try:
        raw = await mcp_manager.call_tool(
            "analyzer__analyze_repository",
            {
                "repo_path": SCAN_REPO_PATH,
                "workload_name": WORKLOAD_NAME,
                "output_dir": TEST_OUTPUT_DIR,
                "provider": PROVIDER,
            },
        )
        resp = _parse(raw)

        if not _ok(resp):
            print(f"  ✗ Error: {resp['error']}")
            return False, {}

        print(f"  ✓ Full pipeline complete")
        dna = resp.get("resource_dna", {})
        print(f"    resource_dna keys : {list(dna.keys())[:8]}")
        print(f"    artifacts_dir     : {resp.get('artifacts_dir', '')}")
        usage = resp.get("token_usage", {})
        if usage:
            print(f"    token_usage       : {json.dumps(usage)}")
        return True, resp

    except Exception as e:
        print(f"  ✗ Exception: {e}")
        import traceback; traceback.print_exc()
        return False, {}


# ---------------------------------------------------------------------------
# Test 6: read_analysis_artifact — read each artifact type
# ---------------------------------------------------------------------------

async def test_read_analysis_artifact(mcp_manager: MCPManager) -> bool:
    """
    Tool  : read_analysis_artifact
    Params: workload_name, artifact_type, output_dir

    Reads every artifact type that analyze_repository writes.
    Expects test 5 (analyze_repository) to have run first.
    """
    _header("TEST 6: read_analysis_artifact — Read Cached Artifacts")
    print(f"  workload_name = {WORKLOAD_NAME}")
    print(f"  output_dir    = {TEST_OUTPUT_DIR}\n")

    artifact_types = [
        "resource_dna",
        "intelligence_report",
        "complexity_heatmap",
        "doc_summary",
        "infra_summary",
        "dependencies_summary",
        "token_usage",
    ]

    any_ok = False
    for atype in artifact_types:
        try:
            raw = await mcp_manager.call_tool(
                "analyzer__read_analysis_artifact",
                {
                    "workload_name": WORKLOAD_NAME,
                    "artifact_type": atype,
                    "output_dir": TEST_OUTPUT_DIR,
                },
            )
            resp = _parse(raw)
            if "error" in resp:
                print(f"  ✗ {atype:<25} {resp['error']}")
            else:
                print(f"  ✓ {atype:<25} {len(raw)} chars")
                any_ok = True
        except Exception as e:
            print(f"  ✗ {atype:<25} Exception: {e}")

    return any_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> int:
    print("\n╔" + "="*68 + "╗")
    print("║" + " "*14 + "ANALYZER MCP SERVER — FULL TOOL TEST SUITE" + " "*12 + "║")
    print("╚" + "="*68 + "╝")
    print(f"\n  repo       : {SCAN_REPO_PATH}")
    print(f"  workload   : {WORKLOAD_NAME}")
    print(f"  model      : {MODEL}  (provider: {PROVIDER})")
    print(f"  output_dir : {TEST_OUTPUT_DIR}")
    print(f"  mcp_config : {MCP_CONFIG_PATH}")

    results: dict[str, bool] = {}

    try:
        with open(MCP_CONFIG_PATH, "r") as f:
            servers_config = json.load(f)

        mcp_manager = MCPManager(servers_config)

        async with mcp_manager:
            print(f"\n  ✓ MCP connected — {len(mcp_manager.tools)} tool(s) registered")

            # List all tools with descriptions and parameters
            await list_tools(mcp_manager)

            # Test 1: scan_repository (no LLM — fast)
            ok1, scan_resp = await test_scan_repository(mcp_manager)
            results["scan_repository"] = ok1
            scan_json = json.dumps(scan_resp)

            # Test 2: analyze_logic (Phases 1+2)
            ok2, logic_resp = await test_analyze_logic(mcp_manager)
            results["analyze_logic"] = ok2
            logic_json = json.dumps(logic_resp)

            # Test 3: get_workload_intent (docs-only, fast)
            results["get_workload_intent"] = await test_get_workload_intent(mcp_manager)

            # Test 4: profile_resources (Phase 3, feeds outputs from tests 1+2)
            ok4, _ = await test_profile_resources(mcp_manager, scan_json, logic_json)
            results["profile_resources"] = ok4

            # Test 5: analyze_repository (full pipeline — slowest, writes artifacts)
            ok5, _ = await test_analyze_repository(mcp_manager)
            results["analyze_repository"] = ok5

            # Test 6: read_analysis_artifact (reads artifacts written by test 5)
            results["read_analysis_artifact"] = await test_read_analysis_artifact(mcp_manager)

    except FileNotFoundError:
        print(f"\n  ✗ MCP config not found: {MCP_CONFIG_PATH}")
        return 1
    except Exception as e:
        print(f"\n  ✗ Fatal: {e}")
        import traceback; traceback.print_exc()
        return 1

    # Summary
    _header("TEST SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        marker = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {marker}  {name}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
