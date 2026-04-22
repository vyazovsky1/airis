import os

def load_prompt(filename: str) -> str:
    """Loads a prompt from the prompts/ directory."""
    # This works from both src/ and src/subfolders
    # We go up until we find prompts or reach root
    current = os.path.dirname(__file__)
    while current:
        path = os.path.join(current, "prompts", filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
        
    # Final fallback to direct relative path
    path = os.path.join("prompts", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
            
    raise FileNotFoundError(f"Could not find prompt file: {filename}")
