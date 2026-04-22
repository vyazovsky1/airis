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
            "heavy_libs": []
        }

    def scan(self) -> Dict[str, Any]:
        """Performs the full perception scan."""
        logger.info(f"Scanning repository for workload perception: {self.repo_path}")
        
        self._detect_languages()
        self._detect_stack_metadata()
        self._map_entry_points()
        self._identify_resource_signatures()
        
        return self.results

    def _detect_languages(self):
        """Identifies programming languages based on file extensions."""
        extensions = {
            ".py": "Python",
            ".go": "Go",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".java": "Java",
            ".yaml": "Infrastructure (YAML)",
            ".yml": "Infrastructure (YAML)",
            ".dockerfile": "Container",
            "Dockerfile": "Container"
        }
        
        counts = {}
        for root, _, files in os.walk(self.repo_path):
            for file in files:
                ext = os.path.splitext(file)[1] or file
                if ext in extensions:
                    lang = extensions[ext]
                    counts[lang] = counts.get(lang, 0) + 1
        
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
                    self.results["stack"].append(manifests[file])
                    
                    # Deep scan for heavy libraries in requirements.txt
                    if file == "requirements.txt":
                        self._scan_python_deps(os.path.join(root, file))

    def _scan_python_deps(self, path: str):
        """Scans requirements.txt for 'Heavy' libraries."""
        heavy_patterns = ["pandas", "numpy", "tensorflow", "torch", "scipy", "grpcio", "celery", "django", "flask"]
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().lower()
                for lib in heavy_patterns:
                    if lib in content:
                        self.results["heavy_libs"].append(f"Python-{lib}")
        except Exception as e:
            logger.warning(f"Failed to read requirements.txt: {e}")

    def _map_entry_points(self):
        """Identifies entry points (main functions, API controllers)."""
        patterns = {
            "Python": [r"if\s+__name__\s*==\s*['\"]__main__['\"]", r"@app\.(route|get|post)"],
            "Go": [r"func\s+main\s*\(\)"],
            "Node.js": [r"app\.listen", r"server\.listen"],
            "Java": [r"public\s+static\s+void\s+main"]
        }
        
        for root, _, files in os.walk(self.repo_path):
            for file in files:
                ext = os.path.splitext(file)[1]
                path = os.path.join(root, file)
                
                # Check based on language
                for lang, lang_patterns in patterns.items():
                    if (lang == "Python" and ext == ".py") or \
                       (lang == "Go" and ext == ".go") or \
                       (lang == "Node.js" and (ext == ".js" or ext == ".ts")) or \
                       (lang == "Java" and ext == ".java"):
                        
                        try:
                            with open(path, "r", encoding="utf-8") as f:
                                # Read first 1000 lines for efficiency
                                head = "".join([f.readline() for _ in range(1000)])
                                for pattern in lang_patterns:
                                    if re.search(pattern, head):
                                        self.results["entry_points"].append(path)
                                        break
                        except Exception:
                            continue

    def _identify_resource_signatures(self):
        """Searches for concurrency and storage management patterns."""
        signatures = {
            "Concurrency": [r"Threading", r"multiprocessing", r"asyncio", r"ThreadPool", r"go\s+", r"goroutine"],
            "Cache/In-Memory": [r"Redis", r"cache", r"buffer", r"LRU", r"LocalStorage"],
            "Disk/State": [r"persistence", r"storage", r"volume", r"pvc", r"sqlite"]
        }
        
        # This is a high-level scan of the whole repo
        # Limit to critical paths later in Phase 2
        pass
