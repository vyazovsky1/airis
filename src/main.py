import argparse
import sys
import logging
from orchestrator import orchestrator_engine
from dotenv import load_dotenv
from config import config

load_dotenv()

logging.basicConfig(level=config.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

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
        logging.getLogger().setLevel(args.log_level)
    
    if args.demo:
        logger.info("======== AIRIS DEMO MODE ========")
        orchestrator_engine.run_airis_cycle(args.pr, args.workload, args.provider, args.model, args.action, args.root, args.skip_cache)
    else:
        logger.info("Running in standard mode.")
        orchestrator_engine.run_airis_cycle(args.pr, args.workload, args.provider, args.model, args.action, args.root, args.skip_cache)

if __name__ == "__main__":
    main()
