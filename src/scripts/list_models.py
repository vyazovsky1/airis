import os
import sys

# Ensure the parent 'src' directory is in the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from scripts import llm_utils

def main():
    print("="*100)
    print("Fetching Supported Google Gemini Models...")
    print("="*100)
    try:
        gemini_models = llm_utils.get_gemini_models()
        if not gemini_models:
            print("No Gemini models found or API key missing.")
        else:
            # Table header
            print(f"{'ID':<40} | {'VERSION':<8} | {'IN TOKENS':<10} | {'OUT TOKENS':<10} | {'DESCRIPTION'}")
            print("-" * 100)
            for m in gemini_models:
                desc = m.get('description', '')
                if desc and len(desc) > 30:
                    desc = desc[:27] + "..."
                print(f"{m.get('id', 'N/A'):<40} | {m.get('version', 'N/A'):<8} | {str(m.get('input_token_limit', 'N/A')):<10} | {str(m.get('output_token_limit', 'N/A')):<10} | {desc}")
    except Exception as e:
        print(f"Error fetching Gemini: {e}")

    print("\n" + "="*80)
    print("Fetching Supported OpenAI Models...")
    print("="*80)
    try:
        openai_models = llm_utils.get_openai_models()
        if not openai_models:
            print("No OpenAI models found or API key missing.")
        else:
            # Table header
            print(f"{'ID':<45} | {'OWNER':<20} | {'CREATED TIMESTAMP'}")
            print("-" * 80)
            for m in openai_models:
                print(f"{m.get('id', 'N/A'):<45} | {m.get('owned_by', 'N/A'):<20} | {m.get('created', 'N/A')}")
    except Exception as e:
        print(f"Error fetching OpenAI: {e}")
        
    print("="*80)

if __name__ == "__main__":
    main()
