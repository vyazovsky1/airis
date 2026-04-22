import os
import json
from pydantic import BaseModel, ValidationError
from core.logger import get_logger
from core.config import config
from core.llm_provider import get_llm_provider
from tools import kubernetes_utils, github_utils, storage_cache, context_discovery
import tools.token_stats as token_stats

logger = get_logger(__name__)

class CpuMemoryLimits(BaseModel):
    requests: str
    limits: str

class TargetResources(BaseModel):
    cpu: CpuMemoryLimits
    memory: CpuMemoryLimits
    storage: str

class AirisDecision(BaseModel):
    decision: str
    reasoning: str
    target_resources: TargetResources


from core.utils import load_prompt

def run_airis_cycle(pr_number: int, workload_name: str, provider: str = "gemini", model_name: str = None, action: str = "pr", workload_root: str = None, skip_cache: bool = False):
    logger.info(f"Starting AIRIS Cycle for PR #{pr_number}, Workload: {workload_name}, Provider: {provider}, Action: {action}")
    token_stats.reset()
    
    # 1. Perceive Background info
    logger.info(f"Step 1/3: Fetching Pull Request diff for PR #{pr_number} from GitHub...")
    pr_diff = github_utils.get_pull_request_diff(pr_number, workload_name)
    
    logger.debug("Loading system prompts and guidelines...")
    
    syst_prompt = load_prompt("system.txt")
    analyse_prompt = load_prompt("analyse_resources.txt")
    storage_prompt = load_prompt("storage_gate.txt")
    conf_prompt = load_prompt("confidence_calibration.txt")
    format_prompt = load_prompt("resource_validation.txt")

    # Step 0: Context Discovery (Fast-Scraper Tier)
    app_intent_summary = "No explicit intent discovered."
    if workload_root:
        app_intent_summary = context_discovery.discover_app_context(workload_name, workload_root, provider, skip_cache)
    else:
        logger.warning(f"No workload_root provided for '{workload_name}'. Skipping Intent Discovery.")

    full_system_context = f"""
{syst_prompt}

Application Intent & Context Summary:
{app_intent_summary}

Guidelines:
{analyse_prompt}
{storage_prompt}
{conf_prompt}
{format_prompt}

Context:
PR Diff:
{pr_diff}
"""

    try:
        logger.info(f"Step 2/3: Gathering Kubernetes cluster metrics for workload '{workload_name}'...")
        allocations = kubernetes_utils.get_allocations(workload_name)
        usage = kubernetes_utils.get_resource_usage(workload_name)
        pvc = kubernetes_utils.get_pvc(workload_name)
        disk = kubernetes_utils.get_disk_usage(workload_name)
        
        logger.info("Metrics successfully fetched. Saving state to local storage cache...")
        storage_cache.save_to_cache("run_findings.csv", 
            ["timestamp", "workload", "pr_number", "status"], 
            {"workload": workload_name, "pr_number": pr_number, "status": "analyzed"}
        )

        logger.info(f"Step 3/3: Passing context to LLM ({provider.title()}) for resource optimization analysis...")

        llm = get_llm_provider(provider)
        attempt = 0
        validated_data = None
        
        user_prompt = f"Please analyze {workload_name}. \nAllocations: {json.dumps(allocations)}\nUsage: {json.dumps(usage)}\nPVC: {json.dumps(pvc)}\nDisk: {json.dumps(disk)}"

        while attempt < config.MAX_SELF_CORRECTION_RETRIES:
            attempt += 1
            logger.info(f"Initiating LLM generation (Attempt {attempt}/{config.MAX_SELF_CORRECTION_RETRIES})...")
            
            response_text = llm.generate(
                system_prompt=full_system_context,
                user_prompt=user_prompt,
                model=model_name,
                tier="thinking"
            )

            # Parse and Validate output
            logger.info("LLM generation complete. Parsing response against Pydantic schema constraints...")
            try:
                # Clean formatting blocks if LLM hallucinated them
                raw_json = response_text.replace('```json', '').replace('```', '').strip()
                validated_data = AirisDecision.model_validate_json(raw_json)
                logger.debug("JSON successfully validated against the schema! AI analysis complete.")
                break # Break if successful validation
            except ValidationError as e:
                logger.warning(f"JSON Validation failed on attempt {attempt}: {e}")
                if attempt >= config.MAX_SELF_CORRECTION_RETRIES:
                    raise Exception(f"Failed to parse valid JSON from LLM after {config.MAX_SELF_CORRECTION_RETRIES} attempts. Last error: {e}")
                
                # Append correction prompt
                error_instruction = f"\n\n[SYSTEM WARNING]: Your previous output failed JSON schema validation with error: {e}. Please correct it and output ONLY raw JSON."
                full_system_context += error_instruction

    except Exception as e:
        logger.error(f"AIRIS Cycle Failed: {str(e)}")
        return

    # -------------------------
    # ACTION ROUTER
    # -------------------------
    if not validated_data:
         logger.error("No valid payload was generated. Aborting.")
         return

    if action == "pr":
        md_comment = f"### 🤖 AIRIS Resource Review\n**Decision:** {validated_data.decision}\n\n**Reasoning:**\n{validated_data.reasoning}\n\n**Target Resources JSON:**\n```json\n{validated_data.target_resources.model_dump_json(indent=2)}\n```"
        github_utils.create_pull_request_review(pr_number, md_comment)
    elif action == "dry-run":
        logger.info(f"DRY-RUN action selected. Final structured payload:\n{validated_data.model_dump_json(indent=2)}")
    else:
        logger.warning(f"Action '{action}' is not implemented.")

    token_stats.log_summary()
