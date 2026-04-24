import os
import re
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
    
    def __init__(self, repo_path: str, perception_artifacts: Dict[str, Any], provider_type: str = "openai"):
        self.repo_path = repo_path
        self.perception = perception_artifacts
        self.provider_type = provider_type
        self.llm = get_llm_provider(provider_type)
        self.analysis_results = {
            "complexity_matrix": [],
            "hot_spots": [],
            "logic_summaries": {},
            "doc_summary": "",      # Synthesized developer intent
            "infra_summary": ""     # Synthesized infrastructure intent
        }
        # Threshold for escalating to Fast LLM
        self.cc_threshold = 15 

    def analyze(self) -> Dict[str, Any]:
        """Performs tiered logical analysis."""
        logger.info("Starting Phase 2: Logic & Complexity Analysis...")
        
        # 1. Summarize Environmental Context (Docs/Infra) using Fast tier first
        self._summarize_environmental_context()

        # 2. Compute complexity for all discovered entry points and relevant files
        self._batch_complexity_scan()
        
        # 3. Perform Tiered LLM Analysis for source code
        self._perform_tiered_reasoning()
        
        return self.analysis_results

    def _summarize_environmental_context(self):
        """Summarizes documentation and infrastructure manifests using Fast tier."""
        logger.info("Summarizing Environmental Context (Docs & Infra)...")
        
        # 1. Summarize Documentation
        docs = self.perception.get("docs_context", [])
        if docs:
            doc_data = "\n".join([f"FILE: {d['file']}\n{d['content']}" for d in docs])
            prompt = f"Summarize the following developer documentation to extract logical intent and resource requirements:\n\n{doc_data}"
            try:
                self.analysis_results["doc_summary"] = self.llm.generate(
                    system_prompt="You are a senior technical architect. Condense documentation into technical logic and scaling intent.",
                    user_prompt=prompt,
                    tier="fast"
                )
            except Exception as e: logger.warning(f"Doc summary failed: {e}")

        # 2. Summarize Infrastructure
        infra = self.perception.get("infra_context", [])
        if infra:
            infra_data = "\n".join([f"FILE: {i['file']}\n{i['content']}" for i in infra])
            prompt = f"Summarize the following infrastructure manifests to extract scaling baselines and environment constraints:\n\n{infra_data}"
            try:
                self.analysis_results["infra_summary"] = self.llm.generate(
                    system_prompt="You are a DevOps architect. Condense infrastructure code into resource baselines and architectural constraints.",
                    user_prompt=prompt,
                    tier="fast"
                )
            except Exception as e: logger.warning(f"Infra summary failed: {e}")

        # 3. Summarize Dependencies
        dependencies = self.perception.get("manifest_context", [])
        if dependencies:
            dependencies_data = "\n".join([f"FILE: {i['file']}\n{i['content']}" for i in dependencies])
            prompt = f"Summarize the following dependencies manifests to identify resource demanding ones and environment constraints:\n\n{dependencies_data}"
            try:
                self.analysis_results["dependencies_summary"] = self.llm.generate(
                    system_prompt="You are a senior technical architect. Condense dependency information into technical logic and scaling intent.",
                    user_prompt=prompt,
                    tier="fast"
                )
            except Exception as e: logger.warning(f"Dependency summary failed: {e}")


    def _batch_complexity_scan(self):
        """Scans all identified source files for complexity and relevance."""
        source_files = self.perception.get("source_manifest", [])
        entry_points = self.perception.get("entry_points", [])
        
        logger.info(f"Scanning {len(source_files)} source files for complexity...")
        
        for rel_path in source_files:
            abs_path = os.path.join(self.repo_path, rel_path)
            # Skip common non-logic boilerplate to focus intelligence
            if any(skip in rel_path.lower() for skip in ["/test/", "/mock/", "/maven-wrapper/", "/.mvn/", "/lang/", "/resources/", "/assets/"]):
                continue

            try:
                ext = os.path.splitext(rel_path)[1].lower()
                complexity_score = 0
                
                with open(abs_path, "r", encoding="utf-8") as f:
                    code = f.read()
                    if ext == ".py":
                        blocks = cc_visit(code)
                        complexity_score = max([b.complexity for b in blocks]) if blocks else 0
                    else:
                        complexity_score = self._heuristic_complexity(code)
                
                is_entry = rel_path in entry_points
                record = {
                    "file": rel_path, # Keep relative
                    "max_complexity": complexity_score,
                    "escalate": complexity_score >= self.cc_threshold,
                    "is_entry": is_entry,
                    "method": "static-cc" if ext == ".py" else "heuristic"
                }
                
                self.analysis_results["complexity_matrix"].append(record)
                if record["escalate"]:
                    self.analysis_results["hot_spots"].append(rel_path)
                    logger.info(f"HOT SPOT Detected ({record['method']}): {rel_path} (score: {complexity_score}) - Escalating.")
            except Exception as e:
                logger.warning(f"Failed to scan complexity for {rel_path}: {e}")

    def _heuristic_complexity(self, code: str) -> int:
        """Calculates a language-agnostic complexity score based on control flow keywords."""
        keywords = [
            r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bswitch\b", r"\bcase\b", 
            r"\bcatch\b", r"\btry\b", r"\b&&" , r"\|\|"
        ]
        score = 1
        for pattern in keywords:
            score += len(re.findall(pattern, code))
        loc = len(code.splitlines())
        score += (loc // 50)
        return score

    def _perform_tiered_reasoning(self):
        """Processes files using a three-tier strategy: Deep, Entry, and Batch."""
        records = self.analysis_results["complexity_matrix"]
        
        # 1. Thinking Tier (Hot Spots)
        hot_spots = [r for r in records if r["escalate"]]
        for r in hot_spots:
            self._analyze_file(r["file"], tier="fast")
            
        # 2. Fast Tier (Entry Points that aren't hot spots)
        entries = [r for r in records if r["is_entry"] and not r["escalate"]]
        for r in entries:
            self._analyze_file(r["file"], tier="fast")
            
        # 3. Batch Tier (The 'Long Tail' of remaining logic)
        remaining = [r for r in records if not r["is_entry"] and not r["escalate"]]
        # Group by directory to maintain package context
        batches = {}
        for r in remaining:
            dirname = os.path.dirname(r["file"])
            if dirname not in batches: batches[dirname] = []
            batches[dirname].append(r["file"])
            
        for dirname, file_list in batches.items():
            if len(file_list) > 0:
                logger.info(f"Performing Batch Analysis on {len(file_list)} files in {dirname}...")
                self._analyze_batch(dirname, file_list)

    def _analyze_file(self, rel_path: str, tier: str):
        """Single file analysis."""
        logger.info(f"Analyzing {rel_path} using {tier} tier...")
        abs_path = os.path.join(self.repo_path, rel_path)
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                code_snippet = f.read()[:5000]
                system_prompt = "You are a senior Software Architect. Analyze the provided code for logic and resource implications."
                from core.utils import load_prompt
                raw_prompt = load_prompt("analyzer_logic.txt")
                user_prompt = raw_prompt.replace("{{ code_snippet }}", code_snippet)
                
                summary = self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt, tier=tier)
                self.analysis_results["logic_summaries"][rel_path] = summary
        except Exception as e:
            logger.error(f"LLM Analysis failed for {rel_path}: {e}")

    def _analyze_batch(self, dirname: str, file_list: List[str]):
        """Batch analysis of multiple files in a single directory."""
        batch_context = f"Directory: {dirname}\nFiles:\n"
        for f in file_list: # file_list contains relative paths
            batch_context += f"- {os.path.basename(f)}\n"
            
        # Read small snippets from each file to give the LLM a 'taste'
        for rel_f in file_list[:10]: # Limit to 10 files per batch to stay within context
            try:
                abs_f = os.path.join(self.repo_path, rel_f)
                with open(abs_f, "r", encoding="utf-8") as file_obj:
                    content = file_obj.read()[:500] 
                    batch_context += f"\nFILE: {os.path.basename(rel_f)}\n```\n{content}\n```\n"
            except Exception: continue

        system_prompt = "You are a senior Software Architect. Summarize the logical theme and resource implications of this file cluster."
        user_prompt = f"Please summarize these background files:\n{batch_context}"
        
        try:
            summary = self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt, tier="fast")
            # Assign the batch summary to the directory record
            self.analysis_results["logic_summaries"][f"BATCH: {dirname}"] = summary
        except Exception as e:
            logger.error(f"Batch Analysis failed for {dirname}: {e}")
