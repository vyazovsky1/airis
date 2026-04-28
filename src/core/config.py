import os


class Config:
    TEMPERATURE = float(os.environ.get("TEMPERATURE", 0.2))

    # Provider default models
    OPENAI_DEFAULT_MODEL = os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o")
    GEMINI_DEFAULT_MODEL = os.environ.get("GEMINI_DEFAULT_MODEL", "gemini-2.0-pro-exp-02-05")

    # Fast-tier models
    OPENAI_FAST_MODEL = os.environ.get("OPENAI_FAST_MODEL", "gpt-4o-mini")
    GEMINI_FAST_MODEL = os.environ.get("GEMINI_FAST_MODEL", "gemini-2.0-flash")

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


config = Config()
