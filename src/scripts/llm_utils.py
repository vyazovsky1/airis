import os
import logging
from datetime import datetime
from openai import OpenAI
from google import genai

logger = logging.getLogger(__name__)

def get_gemini_models() -> list:
    """Fetches a list of available Gemini models for the current API key including attributes."""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    current_models = []
    if not gemini_key:
        logger.warning("GEMINI_API_KEY not set. Cannot fetch models.")
        return current_models
        
    client = genai.Client(api_key=gemini_key)
    
    try:
        models = client.models.list()
        for m in models:
            if getattr(m, 'supported_actions', None) and 'generateContent' in m.supported_actions:
                model_info = {
                    "id": m.name,
                    "display_name": getattr(m, "display_name", "N/A"),
                    "version": getattr(m, "version", "N/A"),
                    "description": getattr(m, "description", "N/A"),
                    "input_token_limit": getattr(m, "input_token_limit", "Unknown"),
                    "output_token_limit": getattr(m, "output_token_limit", "Unknown"),
                    "temperature": getattr(m, "temperature", "Unknown"),
                    "top_p": getattr(m, "top_p", "Unknown"),
                    "top_k": getattr(m, "top_k", "Unknown")
                }
                # Note: Pricing is not exposed in the Gemini API model endpoints.
                current_models.append(model_info)
    except Exception as e:
        logger.error(f"Error fetching Gemini models: {e}")
        
    return current_models

def get_openai_models() -> list:
    """Fetches a list of available OpenAI models along with basic attributes."""
    openai_key = os.environ.get("OPENAI_API_KEY")
    current_models = []
    
    if not openai_key or openai_key == "mock-key":
        logger.warning("OPENAI_API_KEY not set or is mock-key. Cannot fetch models.")
        return current_models

    try:
        client = OpenAI(api_key=openai_key)
        models = client.models.list()
        
        for m in models.data:
            # Exclude non-chat endpoint models to avoid 404 errors during orchestrator cycles
            exclude_keywords = ["codex", "audio", "realtime", "embedding", "tts", "whisper", "search", "babbage", "davinci"]
            if any(k in m.id for k in exclude_keywords):
                continue
                
            # Note: Features like context length and pricing are NOT provided via the OpenAI API.
            created_date = datetime.fromtimestamp(m.created).strftime("%Y-%m-%d") if getattr(m, "created", None) else "N/A"
            model_info = {
                "id": m.id,
                "owned_by": m.owned_by,
                "created": created_date
            }
            current_models.append(model_info)
    except Exception as e:
        logger.error(f"Error fetching OpenAI models: {e}")
        
    return current_models

