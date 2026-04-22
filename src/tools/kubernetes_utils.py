import json
import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)

MOCKS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "mocks", "k8s_data.json")

def load_mocks() -> Dict[str, Any]:
    """Loads all K8s mock data from the JSON store."""
    try:
        if os.path.exists(MOCKS_PATH):
            with open(MOCKS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        logger.warning(f"Mock data not found at {MOCKS_PATH}. Tool will return empty data.")
    except Exception as e:
        logger.error(f"Error loading K8s mocks: {e}")
    return {}

def thin_json(data: Dict[str, Any], allowed_keys: list) -> Dict[str, Any]:
    """Projection Layer logic: thin down massive JSON payloads to only valid keys."""
    if not isinstance(data, dict):
        return data
    
    thinned = {}
    for k, v in data.items():
        if k in allowed_keys:
            thinned[k] = v
        elif isinstance(v, dict):
            # Recursively thin, but keep structure
            sub_thinned = thin_json(v, allowed_keys)
            if sub_thinned:
                thinned[k] = sub_thinned
        elif isinstance(v, list):
            thinned[k] = [thin_json(i, allowed_keys) if isinstance(i, dict) else i for i in v]
    return thinned

def get_allocations(workload_name: str) -> Dict[str, Any]:
    """Retrieves stripped down workload manifests showing limits and requests."""
    mocks = load_mocks()
    raw = mocks.get(workload_name, {}).get("allocations", {})
    # Projection Layer: Strip out everything except basic info and resources
    allowed = ["kind", "metadata", "name", "namespace", "spec", "template", "containers", "resources", "requests", "limits"]
    thinned = thin_json(raw, allowed)
    return thinned

def get_resource_usage(workload_name: str) -> list:
    """Retrieves PodMetrics for the workload to establish real usage trends."""
    # Projection Layer: Return just the raw values, no overhead
    mocks = load_mocks()
    return mocks.get(workload_name, {}).get("usage_metrics", [])

def get_pvc(workload_name: str) -> Dict[str, Any]:
    """Retrieves PVC configuration to check against the Storage Gate threshold."""
    mocks = load_mocks()
    raw = mocks.get(workload_name, {}).get("pvc", {})
    allowed = ["kind", "spec", "resources", "requests", "storage"]
    return thin_json(raw, allowed)

def get_disk_usage(workload_name: str) -> Dict[str, str]:
    """Simulates execing into a pod to run `df -h` to find real storage usage."""
    mocks = load_mocks()
    return mocks.get(workload_name, {}).get("disk_usage", {})
