import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AIRIS-Github")

MOCKS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "mocks")

def get_pull_request_diff(pr_number: int, workload_name: str = "") -> str:
    """
    Simulates fetching a PR diff from a local mock file.
    Expects files to be named 'pr{number}.diff' in the examples/mocks directory.
    """
    diff_filename = f"pr{pr_number}.diff"
    diff_path = os.path.join(MOCKS_DIR, diff_filename)
    
    try:
        if os.path.exists(diff_path):
            with open(diff_path, "r", encoding="utf-8") as f:
                return f.read()
        logger.warning(f"Mock diff file not found at {diff_path}. Ensure it exists in examples/mocks/")
    except Exception as e:
        logger.error(f"Error reading mock diff file {diff_path}: {e}")
            
    return "No significant changes."

def create_pull_request_review(pr_number: int, comment_markdown: str):
    """Simulates posting the final AIRIS decision block to standard output."""
    logger.info(f"--- POSTING TO GITHUB PR #{pr_number} ---")
    print("\n" + "="*50)
    print(comment_markdown)
    print("="*50 + "\n")
