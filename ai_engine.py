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
        
        self.system_prompt = (
            "ROLE: You are the candidate. LIVE INTERVIEW MODE.\n"
            "CONTEXT:\n"
            "- BACKGROUND: {cv_data}\n"
            "- JOB: {jd_data}\n\n"
            "STRICT RULES:\n"
            "1. CONCISE: Max 2 sentences. Be punchy. No long paragraphs.\n"
            "2. NATURAL: Use spoken English ('So...', 'I'd say...', 'Actually...').\n"
            "3. PURE SPEECH: No bolding, no lists, no markdown. Just plain text.\n"
            "4. SPEED: Get straight to the point. Answer the question immediately."
        )

    def set_cv_context(self, text: str):
        self.cv_context = text

    def set_job_context(self, jd: str, link: str):
        self.jd_context = jd
        self.company_link = link

    def get_current_system_prompt(self):
        return self.system_prompt.format(
            cv_data=self.cv_context, 
            jd_data=self.jd_context, 
            company_link=self.company_link
        )

    def get_ai_response(self, user_input: str, provider: str = "groq") -> str:
        """Securely fetches AI response from the centralized backend proxy."""
        if not auth_manager.current_user:
            return "Auth Error: Please sign in to activate tactical stream."

        full_prompt = f"{self.get_current_system_prompt()}\n\nUSER: {user_input}"
        
        try:
            res = requests.post(
                f"{auth_manager.backend_url}/api/v1/ai",
                json={
                    "email": auth_manager.current_user,
                    "prompt": full_prompt,
                    "provider": provider
                },
                timeout=20
            )
            if res.ok:
                result = res.json().get("result", "Thinking...")
                # Update local history for persistence in current session
                self.conversation_history.append({"role": "user", "content": user_input})
                self.conversation_history.append({"role": "assistant", "content": result})
                return result
            else:
                return f"Backend Error: {res.json().get('detail', 'Unknown Failure')}"
        except Exception as e:
            return f"Strategic Link Failure: {str(e)}"

    def analyze_screen(self, image_path: str, query: str = "Identify any questions or code and solve them."):
        """Sends screen capture for vision analysis via backend."""
        try:
            img = Image.open(image_path)
            # Encode image to base64 for transmission
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            # The backend proxy handles vision too
            return self.get_ai_response(f"[VISION ANALYSIS] {query}\nIMAGE_DATA: {img_str[:100]}...", provider="gemini")
        except Exception as e:
            return f"Vision Link Error: {str(e)}"

ai_engine = AIEngine()


ai_engine = AIEngine()

