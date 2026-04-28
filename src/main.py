#!/usr/bin/env python3
"""Entry point - AIRIS agent CLI."""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from core.logger import setup_logging, get_logger
from core.config import config
from tools.mcp_manager import MCPManager
from agent.airis_agent import AirisAgent

setup_logging()
logger = get_logger(__name__)


def _configure_log_levels() -> None:
    """Suppress noisy third-party and MCP protocol loggers to WARNING."""
    for name in ("asyncio", "httpx", "httpcore", "openai", "googleapiclient", "google", "mcp", "mcp.client", "mcp.client.stdio"):
        logging.getLogger(name).setLevel(logging.WARNING)


def load_servers_config() -> dict:
    config_path = Path(__file__).parent.parent / "mcp_servers.json"
    if not config_path.exists():
        return {"mcpServers": {}}
    with open(config_path) as fh:
        return json.load(fh)


def print_banner(mcp: MCPManager) -> None:
    print("=" * 60)
    print("  AIRIS - AI Resource Intelligence & Sizing Agent")
    print("=" * 60)
    if mcp.openai_tools:
        names = [t["function"]["name"] for t in mcp.openai_tools]
        print(f"  Tools ({len(names)}): {', '.join(names)}")
    else:
        print("  Warning: no MCP tools loaded - check mcp_servers.json")
    print("  Commands: --action pr | dry-run")
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
                            "review   - review PR impact on resources, post result to GitHub; "
                            "dry-run  - review PR impact on resources, print result only"
                        ))
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default=config.LOG_LEVEL, help="Logging verbosity")
    return parser.parse_args()


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
                result = await agent.run_pr_review(pr_number=args.pr, namespace=args.namespace)
        except Exception as exc:
            error = exc

    # Handle errors after MCP cleanup completes cleanly
    if error:
        logger.error("Agent error: %s", error)
        sys.exit(1)

    if not result:
        print("Agent failed to produce a decision.")
        sys.exit(1)

    if args.action in ("dry-run", "analyze"):
        print("\n--- AIRIS Decision ---")
        print(result.model_dump_json(indent=2))
    elif args.action == "review":
        from tools import github_utils
        md_comment = (
            f"### AIRIS Resource Review\n"
            f"**Decision:** {result.decision}\n\n"
            f"**Reasoning:**\n{result.reasoning}\n\n"
            f"**Target Resources:**\n```json\n"
            f"{result.target_resources.model_dump_json(indent=2)}\n```"
        )
        github_utils.create_pull_request_review(args.pr, md_comment)


if __name__ == "__main__":
    asyncio.run(main())
