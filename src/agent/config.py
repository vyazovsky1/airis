import os


class AgentConfig:
    MAX_SELF_CORRECTION_RETRIES = int(os.environ.get("MAX_SELF_CORRECTION_RETRIES", 5))
    STORAGE_GATE_LIMIT_GI = int(os.environ.get("STORAGE_GATE_LIMIT_GI", 50))


agent_config = AgentConfig()
