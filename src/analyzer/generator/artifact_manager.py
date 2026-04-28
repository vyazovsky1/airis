import os
import json
import csv
from typing import Dict, List, Any
from core.logger import get_logger

logger = get_logger(__name__)

class ArtifactManager:
    """
    PHASE 4: Synthesis & Artifact Suite Generation
    Produces human-readable and machine-consumable analysis results.
    """
    
    def __init__(self, workload_name: str, perception: Dict[str, Any], logic: Dict[str, Any], resource_dna: Dict[str, Any], output_dir: str):
        self.workload_name = workload_name
        self.perception = perception
        self.logic = logic
        self.dna = resource_dna
        self.output_dir = output_dir
        
        # Ensure output structure exists
        os.makedirs(output_dir, exist_ok=True)
        self.dossier_dir = os.path.join(output_dir, "module_dossiers")
        os.makedirs(self.dossier_dir, exist_ok=True)

    def generate_suite(self):
        """Generates the full suite of ARILC artifacts."""
        logger.info("Generating ARILC Artifact Suite...")
        
        self._generate_intelligence_report()
        self._save_resource_dna()
        self._generate_signal_heatmap()
        self._generate_module_dossiers()
        self._generate_summaries()
        #self._generate_logic_graph()
        self._save_token_usage()

    def _generate_intelligence_report(self):
        """Creates the main human-readable MD report with Full-Spectrum context."""
        report_path = os.path.join(self.output_dir, f"intelligence_report_{self.workload_name}.md")
        
        cpu_rec = self.dna.get('resource_recommendations', {}).get('cpu', {})
        mem_rec = self.dna.get('resource_recommendations', {}).get('memory', {})

        md_content = f"""# ARILC Intelligence Report: {self.workload_name}

## Executive Summary
**Archetype:** {self.dna.get('archetype', 'Unknown')}

### Resource Recommendations
| Resource | Request | Limit | Reason |
| :--- | :--- | :--- | :--- |
| **CPU** | {cpu_rec.get('request')} | {cpu_rec.get('limit')} | {cpu_rec.get('reason')} |
| **Memory** | {mem_rec.get('request')} | {mem_rec.get('limit')} | {mem_rec.get('reason')} |

## Full-Spectrum Context
The analysis synthesized intelligence from the following repository pillars:

### 📄 Documentation & Intent
"""
        docs = self.perception.get("docs_context", [])
        if docs:
            for doc in docs:
                md_content += f"- `{doc['file']}`\n"
        else:
            md_content += "- *No significant documentation discovered.*\n"

        md_content += "\n### 🏗️ Infrastructure & Deployment\n"
        infra = self.perception.get("infra_context", [])
        if infra:
            for inf in infra:
                md_content += f"- `{inf['file']}`\n"
        else:
            md_content += "- *No infrastructure-as-code artifacts discovered.*\n"

        md_content += "\n## Logic Comprehension\n"
        md_content += "The repository logic has been analyzed using entry-point (individual) and directory batch reasoning.\n\n"
        md_content += "### Resource Signal Matrix\n"
        md_content += "| File | Signals | Lines |\n| :--- | :--- | :--- |\n"

        for item in self.logic.get("signal_matrix", []):
            sigs = ", ".join(item.get("resource_signals", [])) or "—"
            md_content += f"| `{os.path.basename(item['file'])}` | {sigs} | {item.get('line_count', '?')} |\n"
            
        md_content += "\n## Risk Advisories\n"
        risk_list = self.dna.get("risk_advisory", [])
        if risk_list:
            for risk in risk_list:
                md_content += f"- **[{risk.get('severity')}] {risk.get('type')}**: {risk.get('reason')}\n"
        else:
            md_content += "- *No critical resource risks identified.*\n"

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info(f"Intelligence Report generated: {report_path}")

    def _save_resource_dna(self):
        """Saves the machine-readable JSON DNA."""
        dna_path = os.path.join(self.output_dir, f"resource_dna_{self.workload_name}.json")
        with open(dna_path, "w", encoding="utf-8") as f:
            json.dump(self.dna, f, indent=2)
        logger.info(f"Resource DNA Profile saved: {dna_path}")

    def _generate_signal_heatmap(self):
        """Generates a CSV heatmap of resource signals per file."""
        csv_path = os.path.join(self.output_dir, f"complexity_heatmap_{self.workload_name}.csv")
        try:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["file", "resource_signals", "has_signals", "line_count"])
                for item in self.logic.get("signal_matrix", []):
                    writer.writerow([
                        item["file"],
                        "|".join(item.get("resource_signals", [])),
                        item.get("has_signals", False),
                        item.get("line_count", 0),
                    ])
            logger.info(f"Signal heatmap generated: {csv_path}")
        except Exception as e:
            logger.error(f"Failed to generate CSV heatmap: {e}")

    def _generate_module_dossiers(self):
        """Creates detailed deep-dive docs for each analyzed file."""
        for file_path, summary in self.logic.get("logic_summaries", {}).items():
            file_name = os.path.basename(file_path)
            dossier_path = os.path.join(self.dossier_dir, f"{file_name}.md")
            
            content = f"# Module Dossier: {file_name}\n\n"
            content += f"**Source Path:** `{file_path}`\n\n"
            content += "## Logical Analysis\n"
            content += summary
            
            with open(dossier_path, "w", encoding="utf-8") as f:
                f.write(content)
        logger.info(f"Module Dossiers generated in {self.dossier_dir}")

    def _generate_summaries(self):
        """Dump of Documentation, Infrastructure, Dependency summaries."""

        doc_summary_path = os.path.join(self.output_dir, f"doc_summary_{self.workload_name}.md")
        with open(doc_summary_path, "w", encoding="utf-8") as f:
            f.write(self.logic.get("doc_summary", "No documentation summary available."))

        infra_summary_path = os.path.join(self.output_dir, f"infra_summary_{self.workload_name}.md")
        with open(infra_summary_path, "w", encoding="utf-8") as f:
            f.write(self.logic.get("infra_summary", "No infrastructure summary available."))

        dependencies_summary_path = os.path.join(self.output_dir, f"dependencies_summary_{self.workload_name}.md")
        with open(dependencies_summary_path, "w", encoding="utf-8") as f:
            f.write(self.logic.get("dependencies_summary", "No dependencies summary available."))

        logger.info(f"Documentation, Infrastructure, Dependency summaries generated in {self.output_dir}")

    def _generate_logic_graph(self):
        """Generates a basic Mermaid graph of logic flow."""
        graph_path = os.path.join(self.output_dir, f"logic_flow_{self.workload_name}.mermaid")
        
        # Simple placeholder logic for now
        content = "graph TD\n"
        content += "  Start --> Perception\n"
        content += "  Perception --> LogicAnalysis\n"
        content += "  LogicAnalysis --> ResourceInference\n"
        content += "  ResourceInference --> Result\n"
        
        with open(graph_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Logic Flow graph generated: {graph_path}")

    def _save_token_usage(self):
        """Saves token usage summary for cost tracking."""
        import core.token_stats as token_stats
        usage_path = os.path.join(self.output_dir, "token_usage.json")
        stats = token_stats.get_stats()
        
        # Add a simple 'total' rollup for convenience
        stats["total_combined"] = {
            "input": stats["thinking"]["input"] + stats["fast"]["input"],
            "output": stats["thinking"]["output"] + stats["fast"]["output"],
            "calls": stats["thinking"]["calls"] + stats["fast"]["calls"]
        }
        
        with open(usage_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
        logger.info(f"Token usage summary saved: {usage_path}")
