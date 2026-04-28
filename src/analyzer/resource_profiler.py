import json
from typing import Dict, List, Any
from core.logger import get_logger
from core.llm_provider import get_llm_provider

logger = get_logger(__name__)

class ResourceProfiler:
    """
    PHASE 3: Resource DNA Inference
    Synthesizes logical comprehension into concrete resource requirement predictions.
    """
    
    def __init__(self, repo_path: str, perception_results: Dict[str, Any], logic_results: Dict[str, Any], provider_type: str = "openai"):
        self.repo_path = repo_path
        self.perception = perception_results
        self.logic = logic_results
        self.llm = get_llm_provider(provider_type)
        self.resource_dna = {
            "archetype": "Unknown",
            "resource_recommendations": {
                "cpu": {"request": "Unknown", "limit": "Unknown"},
                "memory": {"request": "Unknown", "limit": "Unknown"},
                "storage": {"request": "Unknown", "reversibility": "Unknown"}
            },
            "risk_advisory": []
        }

    def profile(self) -> Dict[str, Any]:
        """Performs final resource DNA synthesis using Full-Spectrum Context Fusion."""
        logger.info("Starting Phase 3: Resource DNA Inference Synthesis...")
        
        # Prepare the Fusion Context (Using Summaries for Docs/Infra)
        context = {
            "developer_intent": self.logic.get("doc_summary", "No documentation summary available."),
            "infrastructure_baseline": self.logic.get("infra_summary", "No infrastructure summary available."),
            "dependencies_summary": self.logic.get("dependencies_summary", []),
            "emergent_logic_clusters": self.logic.get("logic_summaries", {}),
            "complexity_data": self.logic.get("complexity_matrix", [])
        }
        
        from core.utils import load_prompt
        # We use a dedicated 2.0 prompt that understands context fusion
        raw_prompt = load_prompt("analyzer_resource_dna.txt")
        user_prompt = raw_prompt.replace("{{ context_json }}", json.dumps(context, indent=2))
        
        system_prompt = (
            "You are a Principal Cloud Architect. Your goal is to synthesize 'Full-Spectrum' repository intelligence "
            "into a Kubernetes Resource DNA profile. You must weigh 'Developer Intent' (Docs), 'Deployment Baselines' (Infra), "
            "and 'Emergent Logic' (Code) to produce a reasoned, highly accurate recommendation."
        )
        
        try:
            response_text = self.llm.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tier="thinking"
            )
            
            # Clean and parse JSON
            raw_json = response_text.replace('```json', '').replace('```', '').strip()
            self.resource_dna = json.loads(raw_json)
            
            # Ensure mandatory reasoning fields exist (schema safety)
            for res in ["cpu", "memory"]:
                if res in self.resource_dna.get("resource_recommendations", {}):
                    if "reason" not in self.resource_dna["resource_recommendations"][res]:
                        self.resource_dna["resource_recommendations"][res]["reason"] = "Inferred from holistic logic analysis."
            
            logger.info("Resource DNA synthesis complete.")
        except Exception as e:
            logger.error(f"Resource DNA Synthesis failed: {e}")
            
        return self.resource_dna
