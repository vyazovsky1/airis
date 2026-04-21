import os
import json
import logging
from pydantic import BaseModel, ValidationError
from openai import OpenAI
from google import genai
from tools import kubernetes_utils, github_utils, storage_cache, context_discovery
import tools.token_stats as token_stats
from config import config

logger = logging.getLogger(__name__)

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


def load_prompt(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

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
        # We would define function calling schemas here in a real production app.
        # For simplicity in this script, we'll fetch all info proactively and pass it as Context.
        # This matches the orchestration loop since data is cheap to fetch locally.
        
        logger.info(f"Step 2/3: Gathering Kubernetes cluster metrics for workload '{workload_name}'...")
        allocations = kubernetes_utils.get_allocations(workload_name)
        logger.debug(f"Gathered Allocations: {allocations}")
        
        usage = kubernetes_utils.get_resource_usage(workload_name)
        logger.debug(f"Gathered Usage Metrics: {usage}")
        
        pvc = kubernetes_utils.get_pvc(workload_name)
        logger.debug(f"Gathered PVC Configuration: {pvc}")
        
        disk = kubernetes_utils.get_disk_usage(workload_name)
        logger.debug(f"Gathered Disk Usage: {disk}")
        
        logger.info("Metrics successfully fetched. Saving state to local storage cache...")
        # Save cache
        storage_cache.save_to_cache("run_findings.csv", 
            ["timestamp", "workload", "pr_number", "status"], 
            {"workload": workload_name, "pr_number": pr_number, "status": "analyzed"}
        )

        logger.info(f"Step 3/3: Passing context to LLM ({provider.title()}) for resource optimization analysis...")

        attempt = 0
        validated_data = None
        
        while attempt < config.MAX_SELF_CORRECTION_RETRIES:
            attempt += 1
            response_text = ""
            logger.info(f"Initiating LLM generation (Attempt {attempt}/{config.MAX_SELF_CORRECTION_RETRIES})...")
            
            if provider == "openai":
                client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "mock-key"))
                
                if client.api_key == "mock-key":
                    raise Exception("Using mock key for OpenAI")

                messages = [
                    {"role": "system", "content": full_system_context},
                    {"role": "user", "content": f"Please analyze {workload_name}. \nAllocations: {json.dumps(allocations)}\nUsage: {json.dumps(usage)}\nPVC: {json.dumps(pvc)}\nDisk: {json.dumps(disk)}"}
                ]
                
                response = client.chat.completions.create(
                    model=model_name or config.OPENAI_DEFAULT_MODEL,
                    messages=messages,
                    temperature=config.TEMPERATURE
                )
                
                response_text = response.choices[0].message.content
                if response.usage:
                    in_t, out_t = response.usage.prompt_tokens, response.usage.completion_tokens
                    token_stats.record("thinking", in_t, out_t)
                    logger.info(f"LLM Reasoning attempt {attempt} complete. Tokens spent: (in: {in_t}, out: {out_t} tokens)")
                
            elif provider == "gemini":
                gemini_key = os.environ.get("GEMINI_API_KEY")
                if not gemini_key:
                    raise Exception("GEMINI_API_KEY is not set in environment or .env file")
                
                client = genai.Client(api_key=gemini_key)
                
                prompt = f"{full_system_context}\n\nPlease analyze {workload_name}. \nAllocations: {json.dumps(allocations)}\nUsage: {json.dumps(usage)}\nPVC: {json.dumps(pvc)}\nDisk: {json.dumps(disk)}"
                
                response = client.models.generate_content(
                    model=model_name or config.GEMINI_DEFAULT_MODEL,
                    contents=prompt,
                    config={'temperature': config.TEMPERATURE}
                )
                response_text = response.text
                if response.usage_metadata:
                    in_t, out_t = response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count
                    token_stats.record("thinking", in_t, out_t)
                    logger.info(f"LLM Reasoning attempt {attempt} complete. Tokens spent: (in: {in_t}, out: {out_t} tokens)")
                
            else:
                raise Exception(f"Unsupported provider: {provider}")

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
        # No simulator fallback. We log the error and stop.
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
