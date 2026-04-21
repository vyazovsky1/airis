import os

class Config:
    # LLM Self-Correction Loop
    MAX_SELF_CORRECTION_RETRIES = int(os.environ.get("MAX_SELF_CORRECTION_RETRIES", 5))
    TEMPERATURE = float(os.environ.get("TEMPERATURE", 0.2))
    
    # Provider Default Models
    OPENAI_DEFAULT_MODEL = os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o")
    GEMINI_DEFAULT_MODEL = os.environ.get("GEMINI_DEFAULT_MODEL", "gemini-2.5-pro")

    # Fast-Tier Models for Discovery/Scraping
    OPENAI_FAST_MODEL = os.environ.get("OPENAI_FAST_MODEL", "gpt-4o-mini")
    GEMINI_FAST_MODEL = os.environ.get("GEMINI_FAST_MODEL", "gemini-3.1-flash-lite-preview")
    
    # Agent Thresholds
    STORAGE_GATE_LIMIT_GI = int(os.environ.get("STORAGE_GATE_LIMIT_GI", 50))
    
    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Singleton instance
config = Config()
