import os
import json
from typing import Dict, List, Any
from radon.complexity import cc_visit
from core.logger import get_logger
from core.config import config
from core.llm_provider import get_llm_provider

logger = get_logger(__name__)

class LogicAnalyzer:
    """
    PHASE 2: Logic & Complexity Analysis (The Sieve)
    Identifies high-complexity modules and performs tiered LLM analysis.
    """
    
    def __init__(self, perception_artifacts: Dict[str, Any], provider_type: str = "openai"):
        self.perception = perception_artifacts
        self.provider_type = provider_type
        self.llm = get_llm_provider(provider_type)
        self.analysis_results = {
            "complexity_matrix": [],
            "hot_spots": [],
            "logic_summaries": {}
        }
        # Threshold for escalating to Thinking Model
        self.cc_threshold = 15 

    def analyze(self) -> Dict[str, Any]:
        """Performs tiered logical analysis."""
        logger.info("Starting Phase 2: Logic & Complexity Analysis...")
        
        # 1. Compute complexity for all discovered entry points and relevant files
        self._batch_complexity_scan()
        
        # 2. Perform Tiered LLM Analysis
        self._perform_tiered_reasoning()
        
        return self.analysis_results

    def _batch_complexity_scan(self):
        """Scans relevant files for Cyclomatic Complexity."""
        repo_path = self.perception.get("repo_path") # Wait, I need to make sure repo_path is in perception results
        # For now, we'll use the entry points identified in Phase 1
        files_to_scan = self.perception.get("entry_points", [])
        
        for file_path in files_to_scan:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    code = f.read()
                    blocks = cc_visit(code)
                    
                    max_cc = 0
                    if blocks:
                        max_cc = max([b.complexity for b in blocks])
                    
                    record = {
                        "file": file_path,
                        "max_complexity": max_cc,
                        "escalate": max_cc >= self.cc_threshold
                    }
                    
                    self.analysis_results["complexity_matrix"].append(record)
                    if record["escalate"]:
                        self.analysis_results["hot_spots"].append(file_path)
                        logger.info(f"HOT SPOT Detected: {file_path} (CC: {max_cc}) - Escalating to Thinking Tier.")
            except Exception as e:
                logger.warning(f"Failed to scan complexity for {file_path}: {e}")

    def _perform_tiered_reasoning(self):
        """Processes files using either Fast or Thinking LLM tiers."""
        for record in self.analysis_results["complexity_matrix"]:
            file_path = record["file"]
            tier = "thinking" if record["escalate"] else "fast"
            
            logger.info(f"Analyzing {file_path} using {tier} tier...")
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    # Read code (limited for context window)
                    code_snippet = f.read()[:5000]
                    
                    system_prompt = "You are a senior Software Architect. Analyze the provided code for logic and resource implications."
                    from core.utils import load_prompt
                    raw_prompt = load_prompt("analyzer_logic.txt")
                    user_prompt = raw_prompt.replace("{{ code_snippet }}", code_snippet)
                    
                    summary = self.llm.generate(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        tier=tier
                    )
                    
                    self.analysis_results["logic_summaries"][file_path] = summary
            except Exception as e:
                logger.error(f"LLM Analysis failed for {file_path}: {e}")
                self.analysis_results["logic_summaries"][file_path] = f"Error during analysis: {e}"
