import os

def load_prompt(filename: str, component: str = None) -> str:
    """Loads a prompt from the specific component's prompts/ directory."""
    current = os.path.dirname(__file__)
    
    # If component is provided, try looking in src/<component>/prompts
    if component:
        src_dir = os.path.abspath(os.path.join(current, ".."))
        path = os.path.join(src_dir, component, "prompts", filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

    while current:
        if component:
            path = os.path.join(current, component, "prompts", filename)
        else:
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
            
    raise FileNotFoundError(f"Could not find prompt file: {filename} for component: {component}")
