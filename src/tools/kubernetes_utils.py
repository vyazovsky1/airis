import json
from typing import Dict, Any

# Mock Data Storage for Pilot/Hackathon
MOCK_K8S_DATA = {
    "payments-db": {
        "allocations": {
            "kind": "StatefulSet",
            "metadata": {
                "name": "payments-db",
                "namespace": "production"
            },
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "postgres",
                            "resources": {
                                "requests": {"cpu": "2", "memory": "4Gi"},
                                "limits": {"cpu": "4", "memory": "8Gi"}
                            }
                        }]
                    }
                }
            }
        },
        "usage_metrics": [
            {"cpu": "0.5", "memory": "3.5Gi"},
            {"cpu": "0.6", "memory": "3.6Gi"},
            {"cpu": "0.4", "memory": "3.4Gi"}
        ],
        "pvc": {
            "kind": "PersistentVolumeClaim",
            "metadata": {"name": "data-payments-db"},
            "spec": {
                "resources": {
                    "requests": {"storage": "200Gi"}
                }
            }
        },
        "disk_usage": {
            "used": "12Gi",
            "capacity": "200Gi",
            "percentage_used": "6%"
        }
    }
}

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
    raw = MOCK_K8S_DATA.get(workload_name, {}).get("allocations", {})
    # Projection Layer: Strip out everything except basic info and resources
    allowed = ["kind", "metadata", "name", "namespace", "spec", "template", "containers", "resources", "requests", "limits"]
    thinned = thin_json(raw, allowed)
    return thinned

def get_resource_usage(workload_name: str) -> list:
    """Retrieves PodMetrics for the workload to establish real usage trends."""
    # Projection Layer: Return just the raw values, no overhead
    return MOCK_K8S_DATA.get(workload_name, {}).get("usage_metrics", [])

def get_pvc(workload_name: str) -> Dict[str, Any]:
    """Retrieves PVC configuration to check against the Storage Gate threshold."""
    raw = MOCK_K8S_DATA.get(workload_name, {}).get("pvc", {})
    allowed = ["kind", "spec", "resources", "requests", "storage"]
    return thin_json(raw, allowed)

def get_disk_usage(workload_name: str) -> Dict[str, str]:
    """Simulates execing into a pod to run `df -h` to find real storage usage."""
    return MOCK_K8S_DATA.get(workload_name, {}).get("disk_usage", {})
