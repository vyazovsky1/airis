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
        self._generate_complexity_heatmap()
        self._generate_module_dossiers()
        self._generate_logic_graph()

    def _generate_intelligence_report(self):
        """Creates the main human-readable MD report."""
        report_path = os.path.join(self.output_dir, f"intelligence_report_{self.workload_name}.md")
        
        md_content = f"""# ARILC Intelligence Report: {self.workload_name}

## Executive Summary
**Archetype:** {self.dna.get('archetype', 'Unknown')}
**Recommended CPU:** {self.dna.get('resource_recommendations', {}).get('cpu', {}).get('request')} Request / {self.dna.get('resource_recommendations', {}).get('cpu', {}).get('limit')} Limit
**Recommended Memory:** {self.dna.get('resource_recommendations', {}).get('memory', {}).get('request')} Request / {self.dna.get('resource_recommendations', {}).get('memory', {}).get('limit')} Limit

## Logic Comprehension
The repository logic has been analyzed using a tiered reasoning approach.

### Complexity Matrix
| Component | Max Complexity | Tier Used |
| :--- | :--- | :--- |
"""
        for item in self.logic.get("complexity_matrix", []):
            tier = "Thinking" if item.get("escalate") else "Fast"
            md_content += f"| `{os.path.basename(item['file'])}` | {item['max_complexity']} | {tier} |\n"
            
        md_content += "\n## Risk Advisories\n"
        for risk in self.dna.get("risk_advisory", []):
            md_content += f"- **[{risk.get('severity')}] {risk.get('type')}**: {risk.get('reason')}\n"
            
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info(f"Intelligence Report generated: {report_path}")

    def _save_resource_dna(self):
        """Saves the machine-readable JSON DNA."""
        dna_path = os.path.join(self.output_dir, f"resource_dna_{self.workload_name}.json")
        with open(dna_path, "w", encoding="utf-8") as f:
            json.dump(self.dna, f, indent=2)
        logger.info(f"Resource DNA Profile saved: {dna_path}")

    def _generate_complexity_heatmap(self):
        """Generates a CSV heatmap of file complexities."""
        csv_path = os.path.join(self.output_dir, f"complexity_heatmap_{self.workload_name}.csv")
        try:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["file", "max_complexity", "escalated"])
                for item in self.logic.get("complexity_matrix", []):
                    writer.writerow([item["file"], item["max_complexity"], item["escalate"]])
            logger.info(f"Complexity Heatmap generated: {csv_path}")
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
