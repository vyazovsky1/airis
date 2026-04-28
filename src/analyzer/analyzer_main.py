import argparse
import sys
import os

# Add src to path if needed for standalone execution
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from core.logger import setup_logging, get_logger
from core.config import config
from analyzer.perception import PerceptionEngine
from analyzer.logic_analysis import LogicAnalyzer
from analyzer.resource_profiler import ResourceProfiler
import core.token_stats as token_stats

load_dotenv()
setup_logging()
logger = get_logger("ARILC-Analyzer")

def run_analysis(repo_path: str, workload_name: str, output_dir: str, provider: str = "openai"):
    """
    Main entry point for the Automated Resource Intelligence & Logic Comprehension (ARILC) engine.
    """
    logger.info(f"--- Starting ARILC Analysis for workload: {workload_name} ---")
    logger.info(f"Target Repository Path: {repo_path}")
    token_stats.reset()
    
    # Phase 1: Perception Layer
    logger.info("Initializing Phase 1: Perception & Scanner...")
    perception = PerceptionEngine(repo_path, workload_name)
    scanner_artifacts = perception.scan()
    
    # Phase 2: Logic & Complexity Analysis (The Sieve)
    logger.info("Initializing Phase 2: Logic & Complexity Analysis...")
    logic_engine = LogicAnalyzer(repo_path, scanner_artifacts, provider_type=provider)
    logic_artifacts = logic_engine.analyze()
    
    # Phase 3: Resource DNA Inference
    logger.info("Initializing Phase 3: Resource DNA Inference...")
    profiler = ResourceProfiler(repo_path, scanner_artifacts, logic_artifacts, provider_type=provider)
    resource_dna = profiler.profile()
    
    # Phase 4: Synthesis & Artifact Suite Generation
    logger.info("Initializing Phase 4: Artifact Generation...")
    try:
        from analyzer.generator.artifact_manager import ArtifactManager
        generator = ArtifactManager(workload_name, scanner_artifacts, logic_artifacts, resource_dna, output_dir)
        generator.generate_suite()
    except Exception as e:
        logger.error(f"Failed to generate artifact suite: {e}")

    logger.info(f"ARILC Analysis Complete. Artifacts successfully stored in: {output_dir}")
    token_stats.log_summary()

def main():
    parser = argparse.ArgumentParser(description="ARILC - Automated Resource Intelligence & Logic Comprehension")
    parser.add_argument("--repo", type=str, required=True, help="Path to the repository to analyze")
    parser.add_argument("--workload", type=str, required=True, help="Semantic name for the workload")
    parser.add_argument("--out", type=str, default=".data/analysis", help="Directory to store analysis artifacts")
    parser.add_argument("--provider", type=str, choices=["openai", "gemini"], default="openai", help="AI provider to use")
    
    args = parser.parse_args()

    if not os.path.exists(args.repo):
        logger.error(f"Repository path does not exist: {args.repo}")
        sys.exit(1)
        
    # Dynamically resolve output directory if default is used
    out_dir = args.out
    if out_dir == ".data/analysis":
        out_dir = os.path.join(out_dir, args.workload)
        
    os.makedirs(out_dir, exist_ok=True)
    
    run_analysis(args.repo, args.workload, out_dir, provider=args.provider)

if __name__ == "__main__":
    main()
