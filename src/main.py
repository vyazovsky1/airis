import argparse
import sys
from core.logger import setup_logging, get_logger
from core.config import config
from orchestrator import orchestrator_engine
from dotenv import load_dotenv

load_dotenv()
setup_logging()
logger = get_logger(__name__)

def main():
    parser = argparse.ArgumentParser(description="AIRIS - AI Engine for Resource Intelligence")
    parser.add_argument("--demo", action="store_true", help="Run the dummy PR scenario")
    parser.add_argument("--workload", type=str, default="payments-db", help="Name of the workload to analyze")
    parser.add_argument("--pr", type=int, default=101, help="Pull Request number to review")
    parser.add_argument("--provider", type=str, choices=["openai", "gemini"], default="openai", help="AI provider to use")
    parser.add_argument("--model", type=str, default=None, help="Specific model name to use overriding provider default")
    parser.add_argument("--action", type=str, choices=["pr", "dry-run"], default="pr", help="Action route to execute after analysis")
    parser.add_argument("--root", type=str, default=None, help="Explicit path to the workload's source code/config directory")
    parser.add_argument("--skip-cache", action="store_true", help="Force re-discovery of app context by skipping the local cache")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=config.LOG_LEVEL, help="Logging verbosity level")
    
    args = parser.parse_args()

    # Update log level if explicitly provided
    if args.log_level:
        import logging
        logging.getLogger().setLevel(args.log_level)
    
    logger.info(f"Running AIRIS Engine in {args.action} mode.")
    orchestrator_engine.run_airis_cycle(
        pr_number=args.pr, 
        workload_name=args.workload, 
        provider=args.provider, 
        model_name=args.model, 
        action=args.action, 
        workload_root=args.root, 
        skip_cache=args.skip_cache
    )

if __name__ == "__main__":
    main()
