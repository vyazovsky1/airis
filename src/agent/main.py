#!/usr/bin/env python3
"""Entry point - AIRIS agent CLI."""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Ensure src/ is on the path when run as a script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

from core.logger import setup_logging, get_logger
from core.config import config
from agent.mcp_manager import MCPManager
from agent.airis_agent import AirisAgent, AirisDecision

setup_logging()
logger = get_logger(__name__)


def _configure_log_levels() -> None:
    """Suppress noisy third-party and MCP protocol loggers to WARNING."""
    for name in ("asyncio", "httpx", "httpcore", "openai", "googleapiclient", "google", "mcp", "mcp.client", "mcp.client.stdio"):
        logging.getLogger(name).setLevel(logging.WARNING)


def load_servers_config() -> dict:
    config_path = Path(__file__).parent.parent.parent / "mcp_servers.json"
    if not config_path.exists():
        return {"mcpServers": {}}
    with open(config_path) as fh:
        return json.load(fh)


def print_banner(mcp: MCPManager) -> None:
    print("=" * 60)
    print("  AIRIS - AI Resource Intelligence & Sizing Agent")
    print("=" * 60)
    if mcp.tools:
        names = [t["function"]["name"] for t in mcp.tools]
        print(f"  Tools ({len(names)}): {', '.join(names)}")
    else:
        print("  Warning: no MCP tools loaded - check mcp_servers.json")
    print("=" * 60)
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIRIS - AI Engine for Resource Intelligence & Sizing")
    parser.add_argument("--namespace", type=str, default="default",
                        help="Kubernetes namespace to analyze")
    parser.add_argument("--pr",        type=int, help="Pull Request number to review")
    parser.add_argument("--provider",  type=str, choices=["openai", "gemini"], default="openai",
                        help="AI provider to use")
    parser.add_argument("--model",     type=str, help="Model override (default: provider's thinking-tier model)")
    parser.add_argument("--action",    type=str,
                        choices=["analyze", "review", "dry-run"],
                        default="dry-run",
                        help=(
                            "analyze  - inspect current K8s metrics, suggest fixes (no PR needed); "
                            "review   - review PR diff, post result to GitHub, block merge on REQUEST_CHANGES; "
                            "dry-run  - review PR diff, print result only"
                        ))
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default=config.LOG_LEVEL, help="Logging verbosity")
    return parser.parse_args()


def _format_pr_comment(result: AirisDecision) -> str:
    decision_icons = {"APPROVE": "✅", "COMMENT": "💬", "REQUEST_CHANGES": "❌"}
    deployment_lines = []
    for d in result.deployments:
        icon = decision_icons.get(d.decision, "❓")
        resources_json = d.target_resources.model_dump_json(indent=2)
        deployment_lines.append(
            f"#### {icon} `{d.deployment_name}` — {d.decision}\n"
            f"{d.reasoning}\n"
            f"<details><summary>Target resources</summary>\n\n```json\n{resources_json}\n```\n</details>"
        )

    overall_icon = "✅ All good" if all(d.decision != "REQUEST_CHANGES" for d in result.deployments) else "❌ Changes required"
    return (
        f"### AIRIS Resource Review — {overall_icon}\n\n"
        f"{result.reasoning}\n\n"
        + "\n\n---\n\n".join(deployment_lines)
    )


async def main() -> None:
    args = parse_args()

    if args.log_level:
        logging.getLogger().setLevel(args.log_level)

    _configure_log_levels()

    logger.info("Running AIRIS in '%s' mode - namespace: %s, PR: #%s",
                args.action, args.namespace, args.pr)

    servers_cfg = load_servers_config()

    result = None
    error = None

    async with MCPManager(servers_cfg) as mcp:
        print_banner(mcp)
        agent = AirisAgent(mcp, model_name=args.model)
        try:
            if args.action == "analyze":
                result = await agent.run_k8s_analysis(namespace=args.namespace)
            else:  # review or dry-run
                if not args.pr:
                    logger.error("--pr <number> is required for 'review' or 'dry-run' actions.")
                    sys.exit(1)

                from agent import github_utils
                pr_diff = github_utils.get_pull_request_diff(args.pr)
                result = await agent.run_pr_review(pr_diff=pr_diff, namespace=args.namespace)
        except Exception as exc:
            error = exc

    if error:
        logger.error("Agent error: %s", error)
        sys.exit(1)

    if not result:
        print("Agent failed to produce a decision.")
        sys.exit(1)

    print("\n--- AIRIS Decision ---")
    print(result.model_dump_json(indent=2))

    if args.action == "review":
        from agent import github_utils
        github_utils.create_pull_request_review(args.pr, _format_pr_comment(result))

    # Exit 1 to block merge if any deployment requires changes
    if args.action in ("review", "dry-run"):
        if any(d.decision == "REQUEST_CHANGES" for d in result.deployments):
            logger.warning("AIRIS: blocking merge — REQUEST_CHANGES detected in one or more deployments.")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
