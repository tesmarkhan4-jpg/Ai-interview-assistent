import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load from .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEYS")

if not api_key:
    print("No GEMINI_API_KEYS found in .env")
else:
    try:
        genai.configure(api_key=api_key)
        print("Available models:")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)
    except Exception as e:
        print(f"Error listing models: {e}")
