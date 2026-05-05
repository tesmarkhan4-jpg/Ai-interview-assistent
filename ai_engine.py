import os
from groq import Groq
import google.generativeai as genai
from keys import key_manager
import base64
from typing import List, Dict
from PIL import Image
import io

import os
import requests
import base64
from PIL import Image
import io
from auth_manager import auth_manager

class AIEngine:
    def __init__(self):
        self.conversation_history = []
        self.cv_context = "No CV uploaded yet."
        self.jd_context = "No Job Description provided."
        self.company_link = "No company link provided."
        
        self.groq_keys = []
        # --- LIVE API KEY POOL ---
        from keys import key_manager
        self.groq_client = Groq(api_key=key_manager.get_key("GROQ")) if key_manager.get_key("GROQ") else None
        if not self.groq_client:
            # Fallback to .env
            self.groq_keys = [k.strip() for k in os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", "")).split(",") if k.strip()]
            if self.groq_keys:
                self.groq_client = Groq(api_key=self.groq_keys[0])
        
        # --- INTELLIGENCE MODES ---
        self.mode = "interview" # interview, code, mcq
        self.intelligence_tier = "turbo" # turbo (8b), savant (70b)
        
        self.prompts = {
            "interview": (
                "ROLE: You are an elite candidate. Speak as 'I'. Use SIMPLE, EASY ENGLISH that is easy to understand.\n"
                "HUMAN VOICE: Sound like a real person, not a robot. Use simple words. Be humble and helpful.\n"
                "DYNAMIC LENGTH: Match the length of the question. Short question = 1 short sentence. Deep question = 2-3 simple sentences.\n"
                "CONTEXT:\n- EXPERIENCE: {cv_data}\n- ROLE: {jd_data}\n\n"
                "STRICT RULES:\n"
                "1. NO markdown (*, #), NO structural symbols, NO lists.\n"
                "2. MAX 3 sentences. Usually 1 or 2 is enough.\n"
                "3. Avoid 'big' words. Use 'I built' instead of 'I implemented'. Use 'I lead' instead of 'I spearheaded'.\n"
                "4. Be natural. If they say 'How are you?', just say 'I am doing great, thank you for asking!'"
            ),
            "code": (
                "ROLE: Senior Software Architect.\n"
                "TASK: Solve the challenge with elite efficiency.\n"
                "FORMAT: Code first. Max 1 sentence explanation. Clean, copy-paste ready. NO markdown symbols except code blocks."
            ),
            "mcq": (
                "ROLE: Subject Matter Expert.\n"
                "TASK: Letter only + 5-word professional rationale. Speed is priority."
            )
        }

    def set_cv_context(self, text: str):
        self.cv_context = text

    def set_job_context(self, jd: str, link: str):
        self.jd_context = jd
        self.company_link = link

    def set_mode(self, mode: str):
        if mode in self.prompts:
            self.mode = mode

    def set_tier(self, tier: str):
        self.intelligence_tier = tier

    def get_current_system_prompt(self):
        base_prompt = self.prompts.get(self.mode, self.prompts["interview"])
        return base_prompt.format(
            cv_data=self.cv_context, 
            jd_data=self.jd_context, 
            company_link=self.company_link
        )

    def _get_next_client(self):
        """Rotates to the next available API key from the live pool."""
        from keys import key_manager
        key = key_manager.get_key("GROQ")
        if not key: return None
        return Groq(api_key=key)

    def get_ai_response(self, user_input: str, provider: str = "groq") -> str:
        """Gets AI response with silent retry and key rotation logic."""
        if not user_input or len(user_input.strip()) < 2: return "..."
        if not auth_manager.current_user: return "Auth Error: Please sign in."
        
        full_prompt = f"{self.get_current_system_prompt()}\n\nUSER: {user_input}"
        
        # Self-Healing Retry Loop
        for attempt in range(len(self.groq_keys) if self.groq_keys else 2):
            try:
                if provider == "groq" and self.groq_client:
                    model = "llama-3.3-70b-specdec" if self.intelligence_tier == "savant" else "llama-3.1-8b-instant"
                    chat_completion = self.groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": full_prompt}],
                        model=model,
                    )
                    return chat_completion.choices[0].message.content.replace("*", "")
            except Exception as e:
                # Rotate key and try again silently
                self.groq_client = self._get_next_client()
                continue
        
        return "System is stabilizing. Please wait..."

    def get_ai_response_stream(self, user_input: str, provider: str = "groq"):
        """Yields chunks of the AI response with real-time rotation failsafes."""
        if not user_input or len(user_input.strip()) < 2: return
        
        full_prompt = f"{self.get_current_system_prompt()}\n\nUSER: {user_input}"
        
        for attempt in range(2):
            try:
                if provider == "groq" and self.groq_client:
                    model = "llama-3.3-70b-specdec" if self.intelligence_tier == "savant" else "llama-3.1-8b-instant"
                    stream = self.groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": full_prompt}],
                        model=model,
                        stream=True,
                    )
                    for chunk in stream:
                        if chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content.replace("*", "")
                    return
            except Exception as e:
                self.groq_client = self._get_next_client()
                continue
        
        yield self.get_ai_response(user_input, provider)

    def analyze_screen(self, image_path: str, query: str = "Identify any questions or code and solve them."):
        """Sends screen capture for elite vision analysis via Gemini."""
        try:
            from keys import key_manager
            api_key = key_manager.get_key("GEMINI")
            if not api_key:
                api_key = os.getenv("GEMINI_API_KEY")
            
            if not api_key:
                return "Vision Error: No Gemini Key. Please check dashboard."

            from google import genai
            client = genai.Client(api_key=api_key)
            
            img = Image.open(image_path)
            
            # Integrated Savant Eye Vision Prompt
            vision_prompt = (
                "ROLE: You are an elite candidate taking an assessment or interview. Speak as 'I'. Use SIMPLE, EASY ENGLISH.\n"
                "TASK: Look at the screen. Identify the main technical question, code test, or MCQ. Solve it instantly.\n"
                "STRICT RULES:\n"
                "1. MAX 3 sentences TOTAL for your entire response. Be extremely brief.\n"
                "2. NO markdown (*, #), NO lists, NO long paragraphs.\n"
                "3. If there are multiple questions on screen, only answer the first or most prominent one.\n"
                "4. Sound like a real human in an interview, not a textbook."
            )
            
            # Use a robust fallback loop to handle High Demand (503) or Not Found (404) errors
            models_to_try = ['gemini-2.5-flash', 'gemini-1.5-flash-8b', 'gemini-1.5-flash', 'gemini-1.5-pro']
            
            for model_name in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[vision_prompt, query, img]
                    )
                    return response.text.replace("*", "").strip()
                except Exception as e:
                    error_msg = str(e)
                    if "503" in error_msg or "404" in error_msg or "429" in error_msg:
                        continue # Try the next model
                    else:
                        raise e # If it's an auth error or something else, throw it
            
            return "Vision System Busy: High demand across all servers. Please try again in a few seconds."
            
        except Exception as e:
            print(f"[Vision] Critical Failure: {e}")
            return f"Vision Link Error: {str(e)}"

ai_engine = AIEngine()

