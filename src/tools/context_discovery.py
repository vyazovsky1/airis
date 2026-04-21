import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from google import genai
from config import config

logger = logging.getLogger(__name__)

CACHE_DIR = ".data"

def get_intent_cache_path(workload_name: str) -> str:
    return os.path.join(CACHE_DIR, f"{workload_name}_intent_cache.json")

def scan_directory_structure(root_path: str) -> str:
    """Recursive scan of the directory structure to give the LLM a 'view' of the project."""
    structure = []
    for root, dirs, files in os.walk(root_path):
        level = root.replace(root_path, '').count(os.sep)
        indent = ' ' * 4 * level
        structure.append(f"{indent}{os.path.basename(root)}/")
        sub_indent = ' ' * 4 * (level + 1)
        for f in files:
            structure.append(f"{sub_indent}{f}")
    return "\n".join(structure)

def sample_key_files(root_path: str) -> Dict[str, str]:
    """Reads high-signal files like READMEs and configuration manifests."""
    samples = {}
    
    # Priority 1: README
    readme_paths = [os.path.join(root_path, f) for f in ["readme.md", "README.md", "README.txt"]]
    for rp in readme_paths:
        if os.path.exists(rp):
            with open(rp, "r", encoding="utf-8") as f:
                samples["README"] = f.read()[:2000] # Cap to 2k chars
                break
    
    # Priority 2: Technical manifests
    tech_files = ["package.json", "requirements.txt", "pom.xml", "go.mod", "Dockerfile", "main.py", "index.js"]
    for tf in tech_files:
        p = os.path.join(root_path, tf)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                samples[tf] = f.read()[:1000] # Sample first 1k chars
    
    return samples

def discover_app_context(workload_name: str, workload_root: str, provider: str = "openai") -> str:
    """
    Main entry point for discovery. 
    1. Checks cache.
    2. Scans files.
    3. Uses Fast-tier LLM to summarize intent.
    """
    cache_path = get_intent_cache_path(workload_name)
    if os.path.exists(cache_path):
        logger.info(f"Loading cached intent summary for '{workload_name}'...")
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f).get("intent_summary", "No summary found in cache.")

    if not os.path.exists(workload_root):
        logger.warning(f"Explicit root '{workload_root}' not found. Cannot perform context discovery.")
        return "No application context available (root not found)."

    logger.info(f"Performing Case Study/Discovery on '{workload_root}' using {provider} fast-tier model...")
    
    structure = scan_directory_structure(workload_root)
    samples = sample_key_files(workload_root)
    
    prompt = f"""
Analyze the following source code repository context and provide a concise 'Technical Intent Summary'.
This summary will be used by another AI to calibrate Kubernetes resource requests (CPU/Memory/Storage).

### Directory Structure:
{structure}

### Key File Samples:
{json.dumps(samples, indent=2)}

### Output Requirements:
Provide a 1-2 paragraph summary including:
1. **Application Purpose:** What does this service do?
2. **Tech Stack:** What language/framework is used (e.g., Python FastAPI, JVM Spring)?
3. **Resource Characteristics:** Is it CPU-heavy, Memory-heavy, or IO-heavy based on the code/manifests?
4. **Usage Patterns:** Any mention of peak hours, user concurrency, or scaling needs.

BE CONCISE. FOCUS ON TECHNICAL TRUTH.
"""

    summary = ""
    try:
        if provider == "openai":
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model=config.FAST_OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            summary = response.choices[0].message.content
        elif provider == "gemini":
            client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
            response = client.models.generate_content(
                model=config.FAST_GEMINI_MODEL,
                contents=prompt
            )
            summary = response.text
        
        # Cache the result
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"workload": workload_name, "intent_summary": summary}, f, indent=2)
            
        return summary
    except Exception as e:
        logger.error(f"Context Discovery Failed: {e}")
        return f"Discovery Layer Error: {e}"
