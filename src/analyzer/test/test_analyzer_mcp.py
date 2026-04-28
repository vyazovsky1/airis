#!/usr/bin/env python3
"""
Analyzer MCP Server test suite — exercises the 2 artifact tools via MCPManager.

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
WORKLOAD_NAME = "nodejs-demoapp"
TEST_OUTPUT_DIR = os.path.join(PROJECT_ROOT, ".data", "analysis", WORKLOAD_NAME)
MCP_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "analyzer_mcp_test.json")

os.environ.setdefault("LOG_LEVEL", "WARNING")

ALL_ARTIFACT_NAMES = [
    "resource_dna",
    "intelligence_report",
    "doc_summary",
    "infra_summary",
    "dependencies_summary",
    "module_summary",
]


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

async def show_registered_tools(mcp_manager: MCPManager) -> None:
    _header("REGISTERED TOOLS")
    analyzer_tools = [t for t in mcp_manager.tools if t["function"]["name"].startswith("analyzer__")]
    print(f"Total registered: {len(mcp_manager.tools)}  |  Analyzer tools: {len(analyzer_tools)}\n")

    for t in analyzer_tools:
        fn = t["function"]
        params = fn.get("parameters", {})
        props = params.get("properties", {})
        required = set(params.get("required", []))
        first_line = next((l.strip() for l in fn.get("description", "").splitlines() if l.strip()), "")

        print(f"  Tool: {fn['name']}")
        print(f"    Description : {first_line}")
        print(f"    Parameters  :")
        for pname, schema in props.items():
            ptype = schema.get("type", "any")
            req = " [required]" if pname in required else " [optional]"
            print(f"      - {pname} ({ptype}){req}")
        print()


# ---------------------------------------------------------------------------
# Test 1: list_artifacts — catalog with exists flags
# ---------------------------------------------------------------------------

async def test_list_artifacts(mcp_manager: MCPManager) -> bool:
    """
    Tool  : list_artifacts
    Params: workload_name, output_dir
    """
    _header("TEST 1: list_artifacts — Catalog of Analysis Artifacts")
    print(f"  workload_name = {WORKLOAD_NAME}")
    print(f"  output_dir    = {TEST_OUTPUT_DIR}")

    try:
        raw = await mcp_manager.call_tool(
            "analyzer__list_artifacts",
            {"workload_name": WORKLOAD_NAME, "output_dir": TEST_OUTPUT_DIR},
        )
        resp = _parse(raw)

        if not _ok(resp):
            # No artifacts yet — verify the error carries a resolution hint
            print(f"  ✓ No artifacts found — error returned as expected")
            print(f"    error      : {resp.get('error', '')}")
            print(f"    resolution : {resp.get('resolution', '')}")
            return "resolution" in resp

        print(f"  ✓ Artifact catalog returned")
        print(f"    artifacts_dir : {resp.get('artifacts_dir', '')}\n")
        for a in resp.get("artifacts", []):
            mark = "✓" if a["exists"] else "✗"
            print(f"    {mark} {a['name']}")
            print(f"         file    : {a['file']}")
            print(f"         purpose : {a.get('description', '')}")
            if "modules" in a:
                for m in a["modules"]:
                    print(f"           • {m}")
        return True

    except Exception as e:
        print(f"  ✗ Exception: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Test 2: get_artifacts — invalid name returns error
# ---------------------------------------------------------------------------

async def test_get_artifacts_invalid_name(mcp_manager: MCPManager) -> bool:
    """
    Tool  : get_artifacts
    Params: workload_name, artifact_names=[<invalid>], output_dir

    Verifies that an unknown artifact name produces a clear error.
    """
    _header("TEST 2: get_artifacts — Unknown Artifact Name")
    print(f"  artifact_names = ['does_not_exist']")

    try:
        raw = await mcp_manager.call_tool(
            "analyzer__get_artifacts",
            {
                "workload_name": WORKLOAD_NAME,
                "artifact_names": ["does_not_exist"],
                "output_dir": TEST_OUTPUT_DIR,
            },
        )
        resp = _parse(raw)

        # Either a top-level "no analysis" error or a per-artifact error in "errors"
        if not _ok(resp):
            print(f"  ✓ Top-level error returned (no analysis exists): {resp.get('error', '')[:80]}")
            return True

        errors = resp.get("errors", {})
        if "does_not_exist" in errors:
            print(f"  ✓ Per-artifact error returned: {errors['does_not_exist']}")
            return True

        print(f"  ✗ Expected an error but got: {raw[:200]}")
        return False

    except Exception as e:
        print(f"  ✗ Exception: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Test 3: get_artifacts — fetch all known artifact names
# ---------------------------------------------------------------------------

async def test_get_artifacts_all(mcp_manager: MCPManager) -> bool:
    """
    Tool  : get_artifacts
    Params: workload_name, artifact_names=ALL_ARTIFACT_NAMES, output_dir

    Requests all known artifacts. If analysis has been run, each is returned;
    if not, the top-level "no analysis" error is returned and we verify it
    contains the resolution hint.
    """
    _header("TEST 3: get_artifacts — Fetch All Artifacts")
    print(f"  workload_name  = {WORKLOAD_NAME}")
    print(f"  artifact_names = {ALL_ARTIFACT_NAMES}")
    print(f"  output_dir     = {TEST_OUTPUT_DIR}")

    try:
        raw = await mcp_manager.call_tool(
            "analyzer__get_artifacts",
            {
                "workload_name": WORKLOAD_NAME,
                "artifact_names": ALL_ARTIFACT_NAMES,
                "output_dir": TEST_OUTPUT_DIR,
            },
        )
        resp = _parse(raw)

        if not _ok(resp):
            print(f"  ✓ No artifacts found — error returned as expected")
            print(f"    error      : {resp.get('error', '')}")
            print(f"    resolution : {resp.get('resolution', '')}")
            return "resolution" in resp

        artifacts = resp.get("artifacts", {})
        errors = resp.get("errors", {})

        print(f"  ✓ Response received")
        for name in ALL_ARTIFACT_NAMES:
            if name in artifacts:
                value = artifacts[name]
                if name == "module_summary" and isinstance(value, dict):
                    print(f"    ✓ {name:<25} {len(value)} module(s)")
                    for fname, content in value.items():
                        print(f"        • {fname:<30} {len(content)} chars")
                elif isinstance(value, dict):
                    print(f"    ✓ {name:<25} {len(value)} keys: {list(value.keys())[:5]}")
                else:
                    print(f"    ✓ {name:<25} {len(str(value))} chars")
            elif name in errors:
                print(f"    ✗ {name:<25} {errors[name]}")

        return len(artifacts) > 0

    except Exception as e:
        print(f"  ✗ Exception: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> int:
    print("\n╔" + "="*68 + "╗")
    print("║" + " "*16 + "ANALYZER MCP SERVER — ARTIFACT TOOL TEST SUITE" + " "*6 + "║")
    print("╚" + "="*68 + "╝")
    print(f"\n  workload   : {WORKLOAD_NAME}")
    print(f"  output_dir : {TEST_OUTPUT_DIR}")
    print(f"  mcp_config : {MCP_CONFIG_PATH}")

    results: dict[str, bool] = {}

    try:
        with open(MCP_CONFIG_PATH, "r") as f:
            servers_config = json.load(f)

        mcp_manager = MCPManager(servers_config)

        async with mcp_manager:
            print(f"\n  ✓ MCP connected — {len(mcp_manager.tools)} tool(s) registered")

            await show_registered_tools(mcp_manager)

            results["list_artifacts"] = await test_list_artifacts(mcp_manager)
            results["get_artifacts_invalid_name"] = await test_get_artifacts_invalid_name(mcp_manager)
            results["get_artifacts_all"] = await test_get_artifacts_all(mcp_manager)

    except FileNotFoundError:
        print(f"\n  ✗ MCP config not found: {MCP_CONFIG_PATH}")
        return 1
    except Exception as e:
        print(f"\n  ✗ Fatal: {e}")
        import traceback; traceback.print_exc()
        return 1

    _header("TEST SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        print(f"  {'✓ PASS' if ok else '✗ FAIL'}  {name}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
