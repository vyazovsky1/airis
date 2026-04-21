import os

class Config:
    # LLM Self-Correction Loop
    MAX_SELF_CORRECTION_RETRIES = int(os.environ.get("MAX_SELF_CORRECTION_RETRIES", 5))
    TEMPERATURE = float(os.environ.get("TEMPERATURE", 0.2))
    
    # Provider Default Models
    DEFAULT_OPENAI_MODEL = os.environ.get("DEFAULT_OPENAI_MODEL", "gpt-4o")
    DEFAULT_GEMINI_MODEL = os.environ.get("DEFAULT_GEMINI_MODEL", "gemini-2.5-pro")

    # Fast-Tier Models for Discovery/Scraping
    FAST_OPENAI_MODEL = os.environ.get("FAST_OPENAI_MODEL", "gpt-4o-mini")
    FAST_GEMINI_MODEL = os.environ.get("FAST_GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
    
    # Agent Thresholds
    STORAGE_GATE_LIMIT_GI = int(os.environ.get("STORAGE_GATE_LIMIT_GI", 50))
    
    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Singleton instance
config = Config()
