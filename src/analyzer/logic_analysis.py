import os
import re
import json
from typing import Dict, List, Any
from core.logger import get_logger
from core.llm_provider import get_llm_provider
from core.utils import load_prompt
from analyzer.config import analyzer_config

logger = get_logger(__name__)

# Patterns that indicate real resource demand at runtime
RESOURCE_SIGNALS = {
    "io":          [r"\bopen\b", r"\bread\b", r"\bwrite\b", r"\bfetch\b", r"\bdownload\b",
                    r"\bupload\b", r"\bstream\b", r"\bsocket\b", r"\bFileInputStream\b",
                    r"\bFileOutputStream\b", r"\bBufferedReader\b", r"\bPath\."],
    "compute":     [r"\bfor\b.{0,60}\brange\b", r"\bwhile\b", r"\bmap\(", r"\bfilter\(",
                    r"\breduce\(", r"\bnumpy\b", r"\bpandas\b", r"\btorch\b", r"\btensorflow\b",
                    r"\bmatmul\b", r"\bconvolve\b", r"\bFFT\b", r"\bsort\b", r"\bshuffle\b"],
    "memory":      [r"\bcache\b", r"\bbuffer\b", r"\bqueue\b", r"\bdeque\b", r"\bheap\b",
                    r"\bDataFrame\b", r"\bNDArray\b", r"\bList<", r"\bArrayList\b",
                    r"\bHashMap\b", r"\bloadAll\b", r"\bfetchAll\b"],
    "concurrency": [r"\bThread\b", r"\bExecutor\b", r"\basync\b", r"\bawait\b",
                    r"\bCoroutine\b", r"\bgoroutine\b", r"\bchannel\b", r"\bsemaphore\b",
                    r"\bLock\b", r"\bMutex\b", r"\batomic\b", r"\bparallel\b"],
}

_ALL_SIGNAL_PATTERNS = [p for patterns in RESOURCE_SIGNALS.values() for p in patterns]


def _detect_signals(code: str) -> Dict[str, List[str]]:
    """Return dict of signal category → list of matched patterns found in code."""
    found: Dict[str, List[str]] = {}
    for category, patterns in RESOURCE_SIGNALS.items():
        hits = [p for p in patterns if re.search(p, code)]
        if hits:
            found[category] = hits
    return found


class LogicAnalyzer:
    """
    PHASE 2: Logic & Resource Signal Analysis
    Scans source files for runtime resource demand signals, then performs
    tiered LLM analysis: entry points individually, everything else in batches.
    """

    def __init__(self, repo_path: str, perception_artifacts: Dict[str, Any], provider_type: str = "openai"):
        self.repo_path = repo_path
        self.perception = perception_artifacts
        self.provider_type = provider_type
        self.llm = get_llm_provider(provider_type)
        self.analysis_results: Dict[str, Any] = {
            "signal_matrix": [],
            "logic_summaries": {},
            "doc_summary": "",
            "infra_summary": "",
            "dependencies_summary": "",
        }

    def analyze(self) -> Dict[str, Any]:
        """Performs tiered logical analysis."""
        logger.info("Starting Phase 2: Logic & Resource Signal Analysis...")

        self._summarize_environmental_context()
        self._scan_source_files()
        self._perform_tiered_reasoning()

        return self.analysis_results

    # ── Environmental context ────────────────────────────────────────────────

    def _summarize_environmental_context(self):
        """Summarizes documentation and infrastructure manifests using fast tier."""
        logger.info("Summarizing Environmental Context (Docs & Infra)...")

        docs = self.perception.get("docs_context", [])
        if docs:
            doc_data = "\n".join([f"FILE: {d['file']}\n{d['content']}" for d in docs])
            try:
                self.analysis_results["doc_summary"] = self.llm.generate(
                    system_prompt=load_prompt("analyzer_doc_summary_system.txt"),
                    user_prompt=load_prompt("analyzer_doc_summary.txt").replace("{{ doc_data }}", doc_data),
                    tier="fast",
                )
            except Exception as e:
                logger.warning(f"Doc summary failed: {e}")

        infra = self.perception.get("infra_context", [])
        if infra:
            infra_data = "\n".join([f"FILE: {i['file']}\n{i['content']}" for i in infra])
            try:
                self.analysis_results["infra_summary"] = self.llm.generate(
                    system_prompt=load_prompt("analyzer_infra_summary_system.txt"),
                    user_prompt=load_prompt("analyzer_infra_summary.txt").replace("{{ infra_data }}", infra_data),
                    tier="fast",
                )
            except Exception as e:
                logger.warning(f"Infra summary failed: {e}")

        dependencies = self.perception.get("manifest_context", [])
        if dependencies:
            deps_data = "\n".join([f"FILE: {i['file']}\n{i['content']}" for i in dependencies])
            try:
                self.analysis_results["dependencies_summary"] = self.llm.generate(
                    system_prompt=load_prompt("analyzer_deps_summary_system.txt"),
                    user_prompt=load_prompt("analyzer_deps_summary.txt").replace("{{ deps_data }}", deps_data),
                    tier="fast",
                )
            except Exception as e:
                logger.warning(f"Dependency summary failed: {e}")

    # ── Resource signal scan ─────────────────────────────────────────────────

    def _scan_source_files(self):
        """Scans all source files for resource demand signals."""
        source_files = self.perception.get("source_manifest", [])
        logger.info(f"Scanning {len(source_files)} source files for resource signals...")

        for rel_path in source_files:
            if any(skip in rel_path.lower() for skip in [
                "/test/", "/mock/", "/maven-wrapper/", "/.mvn/", "/lang/", "/resources/", "/assets/",
            ]):
                continue

            abs_path = os.path.join(self.repo_path, rel_path)
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    code = f.read()

                signals = _detect_signals(code)
                line_count = len(code.splitlines())

                record = {
                    "file": rel_path,
                    "has_signals": bool(signals),
                    "resource_signals": list(signals.keys()),
                    "line_count": line_count,
                }
                self.analysis_results["signal_matrix"].append(record)

                if signals:
                    logger.info(
                        "Resource signals in %s: %s",
                        rel_path, ", ".join(signals.keys()),
                    )
            except Exception as e:
                logger.warning(f"Failed to scan {rel_path}: {e}")

    # ── Tiered LLM reasoning ─────────────────────────────────────────────────

    def _perform_tiered_reasoning(self):
        """Entry points are analyzed individually; all other files are batched by directory."""
        records = self.analysis_results["signal_matrix"]
        entry_paths = set(self.perception.get("entry_points", []))

        entry_records = [r for r in records if r["file"] in entry_paths]
        other_records = [r for r in records if r["file"] not in entry_paths]

        for r in entry_records:
            self._analyze_file(r["file"])

        # Group remaining files by directory
        batches: Dict[str, List[Dict]] = {}
        for r in other_records:
            dirname = os.path.dirname(r["file"])
            batches.setdefault(dirname, []).append(r)

        for dirname, batch_records in batches.items():
            logger.info(f"Batch analysis: {len(batch_records)} files in {dirname}")
            self._analyze_batch(dirname, batch_records)

    def _analyze_file(self, rel_path: str):
        """Analyze a single entry-point file with the fast tier."""
        logger.info(f"Analyzing entry point: {rel_path}")
        abs_path = os.path.join(self.repo_path, rel_path)
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # Use signal limit if file has signals, otherwise default batch limit
            record = next(
                (r for r in self.analysis_results["signal_matrix"] if r["file"] == rel_path),
                None,
            )
            limit = (
                analyzer_config.BATCH_SIGNAL_LINES
                if record and record["has_signals"]
                else analyzer_config.BATCH_LINES
            )
            code_snippet = "".join(lines[:limit])
            summary = self.llm.generate(
                system_prompt=load_prompt("analyzer_file_system.txt"),
                user_prompt=load_prompt("analyzer_logic.txt").replace("{{ code_snippet }}", code_snippet),
                tier="fast",
            )
            self.analysis_results["logic_summaries"][rel_path] = summary
        except Exception as e:
            logger.error(f"LLM analysis failed for {rel_path}: {e}")

    def _analyze_batch(self, dirname: str, records: List[Dict]):
        """Batch-analyze files in a single directory."""
        batch_context = f"Directory: {dirname}\nFiles:\n"
        for r in records:
            sigs = ", ".join(r["resource_signals"]) if r["resource_signals"] else "none"
            batch_context += f"- {os.path.basename(r['file'])}  [signals: {sigs}]\n"

        for r in records[:10]:
            rel_path = r["file"]
            line_limit = (
                analyzer_config.BATCH_SIGNAL_LINES
                if r["has_signals"]
                else analyzer_config.BATCH_LINES
            )
            abs_path = os.path.join(self.repo_path, rel_path)
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                snippet = "".join(lines[:line_limit])
                batch_context += f"\nFILE: {os.path.basename(rel_path)}\n```\n{snippet}\n```\n"
            except Exception:
                continue

        try:
            summary = self.llm.generate(
                system_prompt=load_prompt("analyzer_batch_system.txt"),
                user_prompt=load_prompt("analyzer_batch.txt").replace("{{ batch_context }}", batch_context),
                tier="fast",
            )
            self.analysis_results["logic_summaries"][f"BATCH: {dirname}"] = summary
        except Exception as e:
            logger.error(f"Batch analysis failed for {dirname}: {e}")
