import os
import json
from openai import OpenAI
from google import genai
from core.config import config
from core.logger import get_logger
import tools.token_stats as token_stats

logger = get_logger(__name__)

class LLMProvider:
    """
    Centralized provider for LLM interactions.
    Shared by both the Analyzer and the Orchestrator.
    """
    
    def __init__(self, provider_type: str = "openai"):
        self.provider_type = provider_type.lower()
        self.client = self._initialize_client()

    def _initialize_client(self):
        if self.provider_type == "openai":
            api_key = os.environ.get("OPENAI_API_KEY", "mock-key")
            return OpenAI(api_key=api_key)
        elif self.provider_type == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY is not set in environment.")
            return genai.Client(api_key=api_key)
        else:
            raise ValueError(f"Unsupported provider: {self.provider_type}")

    def generate(self, system_prompt: str, user_prompt: str, model: str = None, temperature: float = None, tier: str = "thinking"):
        """Generates content using the configured provider and model."""
        temp = temperature if temperature is not None else config.TEMPERATURE
        
        if self.provider_type == "openai":
            model_name = model or (config.OPENAI_DEFAULT_MODEL if tier == "thinking" else config.OPENAI_FAST_MODEL)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temp
            )
            response_text = response.choices[0].message.content
            if response.usage:
                token_stats.record(tier, response.usage.prompt_tokens, response.usage.completion_tokens)
            return response_text

        elif self.provider_type == "gemini":
            model_name = model or (config.GEMINI_DEFAULT_MODEL if tier == "thinking" else config.GEMINI_FAST_MODEL)
            # Combine system and user prompt for Gemini if needed, or use specific config if supported by client
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = self.client.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config={'temperature': temp}
            )
            if response.usage_metadata:
                token_stats.record(tier, response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count)
            return response.text

        return ""

def get_llm_provider(provider_type: str = "openai"):
    return LLMProvider(provider_type)
