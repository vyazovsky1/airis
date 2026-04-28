import json
import logging
import os

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AIRIS-Github")

MOCKS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "mocks")


def _github_headers(accept: str = "application/vnd.github+json") -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def get_pull_request_diff(pr_number: int, workload_name: str = "") -> str:
    """
    Fetches PR diff from the real GitHub API when GITHUB_TOKEN + GITHUB_REPOSITORY
    are present (CI mode). Falls back to a local mock file for local development.
    """
    repo = os.environ.get("GITHUB_REPOSITORY")  # "owner/repo" set automatically in Actions
    token = os.environ.get("GITHUB_TOKEN")

    if token and repo:
        try:
            url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
            response = requests.get(
                url,
                headers=_github_headers(accept="application/vnd.github.v3.diff"),
                timeout=30,
            )
            if response.ok:
                logger.info(f"Fetched real diff for PR #{pr_number} from {repo}")
                return response.text
            logger.warning(
                f"GitHub API returned {response.status_code} for PR #{pr_number}: "
                f"{response.text[:200]}"
            )
        except Exception as e:
            logger.error(f"GitHub API request failed: {e}")

    # ── Local development fallback ──────────────────────────────────────────
    diff_path = os.path.join(MOCKS_DIR, f"pr{pr_number}.diff")
    try:
        if os.path.exists(diff_path):
            logger.info(f"Using mock diff: {diff_path}")
            with open(diff_path, "r", encoding="utf-8") as f:
                return f.read()
        logger.warning(f"Mock diff not found at {diff_path}")
    except Exception as e:
        logger.error(f"Error reading mock diff: {e}")

    return "No significant changes."


def create_pull_request_review(pr_number: int, comment_markdown: str):
    """
    Posts the AIRIS decision as a PR comment via the GitHub Issues API.
    Falls back to stdout when GITHUB_TOKEN is not available (dry-run / local dev).
    """
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")

    if token and repo:
        try:
            # Issues comments endpoint works for both issues and PRs
            url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
            response = requests.post(
                url,
                headers=_github_headers(),
                json={"body": comment_markdown},
                timeout=30,
            )
            if response.ok:
                html_url = response.json().get("html_url", "")
                logger.info(f"Posted review comment to PR #{pr_number}: {html_url}")
                return
            logger.error(
                f"Failed to post PR comment ({response.status_code}): "
                f"{response.text[:200]}"
            )
        except Exception as e:
            logger.error(f"GitHub API request failed: {e}")

    # ── Stdout fallback ─────────────────────────────────────────────────────
    logger.info(f"[DRY-RUN] AIRIS review for PR #{pr_number}:")
    print("\n" + "=" * 60)
    print(comment_markdown)
    print("=" * 60 + "\n")
