import os
import re
from typing import Dict, List, Any
from core.logger import get_logger

logger = get_logger(__name__)

class PerceptionEngine:
    """
    PHASE 1: Perception Layer
    Responsible for repository-wide reconnaissance to identify tech stack,
    entry points, and resource-heavy signatures.
    """
    
    def __init__(self, repo_path: str, workload_name: str):
        self.repo_path = repo_path
        self.workload_name = workload_name
        self.results = {
            "workload": workload_name,
            "languages": {},
            "stack": [],
            "entry_points": [],
            "source_manifest": [],
            "docs_context": [],
            "infra_context": [],
            "manifest_context": []
        }

    def scan(self) -> Dict[str, Any]:
        """Performs the full spectrum perception scan."""
        logger.info(f"Scanning repository for Full-Spectrum Perception: {self.repo_path}")
        
        self._detect_languages()
        self._detect_stack_metadata()
        self._harvest_documentation()
        self._harvest_infrastructure()
        self._map_entry_points()
        
        return self.results

    def _detect_languages(self):
        """Identifies programming languages based on file extensions."""
        extensions = {
            ".py": "Python",
            ".go": "Go",
            ".js": "JavaScript", ".mjs": "Module JavaScript (NodeJS)", ".ejs": "Embedded JavaScript (NodeJS)",
            ".ts": "TypeScript",
            ".php": "PHP",
            ".java": "Java",
            ".yaml": "Infrastructure (YAML)",
            ".yml": "Infrastructure (YAML)",
            ".dockerfile": "Container",
            "Dockerfile": "Container"
        }
        
        counts = {}
        for root, _, files in os.walk(self.repo_path):
            for file in files:
                path = os.path.join(root, file)
                ext = os.path.splitext(file)[1] or file
                if ext in extensions:
                    lang = extensions[ext]
                    counts[lang] = counts.get(lang, 0) + 1
                    
                    # Track source code files in manifest for full logic depth (RELPATH)
                    if lang not in ["Infrastructure (YAML)", "Container"]:
                        rel_path = os.path.relpath(path, self.repo_path)
                        self.results["source_manifest"].append(rel_path)
        
        self.results["languages"] = counts
        logger.info(f"Detected languages: {counts}")

    def _detect_stack_metadata(self):
        """Scans for manifest files to identify frameworks and libraries."""
        manifests = {
            "requirements.txt": "Python (pip)",
            "package.json": "Node.js (npm)",
            "go.mod": "Go (modules)",
            "pom.xml": "Java (Maven)",
            "build.gradle": "Java (Gradle)"
        }
        
        for root, _, files in os.walk(self.repo_path):
            for file in files:
                if file in manifests:
                    manifest_path = os.path.join(root, file)
                    self.results["stack"].append(manifests[file])
                    # Harvest raw manifest for context
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            self.results["manifest_context"].append({
                                "file": os.path.relpath(manifest_path, self.repo_path),
                                "content": f.read()[:2000] # Cap manifest context
                            })
                    except Exception: pass
                    
    def _harvest_documentation(self):
        """Recursively scans for and ingests documentation for logical intent."""
        logger.info("Harvesting Documentation Context...")
        doc_exts = [".md", ".txt", ".adoc"]
        doc_files = ["README", "ARCHITECTURE", "INSTALL", "DESIGN", "CONTRIBUTING"]
        
        for root, _, files in os.walk(self.repo_path):
            # Only look in root or 'docs' folders
            rel_path = os.path.relpath(root, self.repo_path)
            if rel_path != "." and not rel_path.lower().startswith("docs"):
                continue

            for file in files:
                name, ext = os.path.splitext(file)
                if ext.lower() in doc_exts or any(dn in name.upper() for dn in doc_files):
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            self.results["docs_context"].append({
                                "file": os.path.relpath(path, self.repo_path),
                                "content": f.read()[:3000] # Cap doc context
                            })
                    except Exception: pass

    def _harvest_infrastructure(self):
        """Ingests Infrastructure-as-Code files for environment baselines."""
        logger.info("Harvesting Infrastructure Context...")
        infra_files = ["Dockerfile", ".yaml", ".yml", "docker-compose"]
        
        for root, _, files in os.walk(self.repo_path):
            for file in files:
                if any(inf in file for inf in infra_files):
                    # Skip common non-infra YAMLs
                    if any(skip in file.lower() for skip in ["label", "dependabot", "workflow"]):
                        continue
                        
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                            # Specifically look for resource-heavy keywords in YAML/Dockerfile
                            if any(kw in content for kw in ["memory", "cpu", "limit", "request", "EXPOSE", "VOLUME"]):
                                self.results["infra_context"].append({
                                    "file": os.path.relpath(path, self.repo_path),
                                    "content": content[:2000]
                                })
                    except Exception: pass

    def _map_entry_points(self):
        """Identifies logical entry points (Controllers, Listeners, Mains)."""
        logger.info("Mapping Logical Entry Points...")
        patterns = {
            "Python": [r"if\s+__name__\s*==\s*['\"]__main__['\"]", r"@app\.(route|get|post)"],
            "Go": [r"func\s+main\s*\(\)"],
            "Node.js": [r"app\.listen", r"server\.listen", r"exports\.handler"],
            "Java": [r"public\s+static\s+void\s+main", r"@RestController", r"@Component", r"@Service"]
        }
        
        for root, _, files in os.walk(self.repo_path):
            for file in files:
                ext = os.path.splitext(file)[1]
                path = os.path.join(root, file)
                
                for lang, lang_patterns in patterns.items():
                    # Basic extension match
                    valid_ext = False
                    if lang == "Python" and ext == ".py": valid_ext = True
                    elif lang == "Go" and ext == ".go": valid_ext = True
                    elif lang == "Node.js" and ext in [".js", ".ts"]: valid_ext = True
                    elif lang == "Java" and ext == ".java": valid_ext = True
                    
                    if valid_ext:
                        try:
                            with open(path, "r", encoding="utf-8") as f:
                                # Read more lines for Java controllers/services
                                head = "".join([f.readline() for _ in range(2000)])
                                for pattern in lang_patterns:
                                    if re.search(pattern, head):
                                        self.results["entry_points"].append(os.path.relpath(path, self.repo_path))
                                        break
                        except Exception: continue
