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
    
    def __init__(self, perception_results: Dict[str, Any], logic_results: Dict[str, Any], provider_type: str = "openai"):
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
        """Performs final resource DNA synthesis using LLM reasoning."""
        logger.info("Starting Phase 3: Resource DNA Inference Synthesis...")
        
        # We use a reasoning model (Thinking) for the final synthesis
        # because it needs to 'connect the dots' across files and tiers.
        
        # Prepare context for the synthesis
        context = {
            "languages": self.perception.get("languages"),
            "heavy_libs": self.perception.get("heavy_libs"),
            "complexity_matrix": self.logic.get("complexity_matrix"),
            "logic_summaries": self.logic.get("logic_summaries")
        }
        
        from core.utils import load_prompt
        raw_prompt = load_prompt("analyzer_resource_dna.txt")
        user_prompt = raw_prompt.replace("{{ context_json }}", json.dumps(context, indent=2))
        system_prompt = "You are a Cloud Infrastructure Architect. Synthesize code analysis into Kubernetes resource recommendations."
        
        try:
            response_text = self.llm.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tier="thinking"
            )
            
            # Clean and parse JSON
            raw_json = response_text.replace('```json', '').replace('```', '').strip()
            self.resource_dna = json.loads(raw_json)
            
            logger.info("Resource DNA synthesis complete.")
        except Exception as e:
            logger.error(f"Resource DNA Synthesis failed: {e}")
            
        return self.resource_dna
