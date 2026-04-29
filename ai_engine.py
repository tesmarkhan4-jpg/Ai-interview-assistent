import os
from groq import Groq
import google.generativeai as genai
from keys import key_manager
import base64
from typing import List, Dict
from PIL import Image
import io

class AIEngine:
    def __init__(self):
        self.groq_fallbacks = [
            "llama-3.1-8b-instant",
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "mixtral-8x7b-32768"
        ]
        self.gemini_fallbacks = [
            "gemini-2.5-flash"
        ]
        
        self.conversation_history = []
        self.system_prompt = (
            "PERSONA: You are a warm, highly-intelligent human mentor. You want the user to sound like a RELATABLE, charming, top-tier professional.\n"
            "STYLE RULES:\n"
            "1. SIMPLE ENGLISH: Use easy, clear, and common English words. Avoid complex jargon or 'big' words that are hard to speak. Your goal is for the user to be 100% understandable.\n"
            "2. CONVERSATIONAL FLEXIBILITY: You are not a robot. If the interviewer is just chatting or making small talk, just be a nice human! Do not pivot to technical topics unless a technical question is asked.\n"
            "3. 100% HUMAN RHYTHM: Speak like a real person. No bullet points. Use short, punchy sentences that are easy to read out loud.\n"
            "4. DYNAMIC SCALING: Match the 'depth' of the question. For small talk or interviewer agreement, keep your response under 5 words (e.g., 'Exactly, I totally agree.'). For standard questions, use 10-15 words. For deep stories, MAXIMUM 30 WORDS and MAXIMUM 2 SENTENCES.\n"
            "5. NATURAL FLOW: Use contractions (I'm, don't, it's) to sound human. Never give a long lecture. Be punchy and relatable.\n"
            "6. STRATEGIC BUT HUMBLE: Drop your 'golden nuggets' naturally. Don't brag—just share what works in a simple way.\n"
            "7. FEEDBACK AWARENESS: If they give feedback, just say 'Thank you' or 'I totally agree.'\n"
            "8. WAIT FOR COMPLETION: Only respond once a full thought or question is done.\n"
            "9. ENGLISH ONLY: Ignore non-English noise."
        )

    def get_groq_response(self, user_input: str) -> str:
        key = key_manager.get_key("GROQ")
        if not key: return "Groq API Key missing."

        client = Groq(api_key=key)
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.conversation_history[-10:])
        messages.append({"role": "user", "content": user_input})

        last_error = ""
        for model_name in self.groq_fallbacks:
            try:
                completion = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.8,
                    max_tokens=250,
                )
                response = completion.choices[0].message.content
                self.conversation_history.append({"role": "user", "content": user_input})
                self.conversation_history.append({"role": "assistant", "content": response})
                return response
            except Exception as e:
                last_error = str(e)
                print(f"[AIEngine] Groq Fallback {model_name} failed: {last_error}")
                continue
        
        return self.get_gemini_response(user_input)

    def get_gemini_response(self, user_input: str, image_obj=None) -> str:
        key = key_manager.get_key("GEMINI")
        if not key: return "Gemini API Key missing."

        last_error = ""
        for model_name in self.gemini_fallbacks:
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel(model_name)
                
                config = genai.types.GenerationConfig(max_output_tokens=250, temperature=0.8)

                if image_obj:
                    # Native PIL Image support
                    response = model.generate_content([self.system_prompt, image_obj, f"USER QUESTION: {user_input}"], generation_config=config)
                else:
                    response = model.generate_content([self.system_prompt, user_input], generation_config=config)
                
                return response.text
            except Exception as e:
                last_error = str(e)
                print(f"[AIEngine] Gemini Fallback {model_name} failed: {last_error}")
                continue

        return f"AI Failure: All brains exhausted. Last Error: {last_error}"

    def analyze_screen(self, image_path: str, query: str = "Analyze and solve."):
        try:
            img = Image.open(image_path)
            img.load() # Force load into memory to avoid file lock issues
            return self.get_gemini_response(query, image_obj=img)
        except Exception as e:
            return f"Vision Error: {e}"

ai_engine = AIEngine()
