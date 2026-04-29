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
            "gemini-flash-latest",
            "gemini-pro-latest"
        ]
        
        self.conversation_history = []
        self.system_prompt = (
            "PERSONA: You are a warm, highly-intelligent human mentor. You want the user to sound like a RELATABLE, charming, top-tier professional.\n"
            "STYLE RULES:\n"
            "1. SIMPLE ENGLISH: Use easy, clear, and common English words. Avoid jargon. Goal: 100% understandable.\n"
            "2. CONVERSATIONAL FLEXIBILITY: If chatting, be human! Don't pivot to tech unless asked.\n"
            "3. 100% HUMAN RHYTHM: No bullet points. Short, punchy sentences.\n"
            "4. DYNAMIC SCALING: Match depth. Small talk: 5 words. Standard: 15 words. Deep: 30 words (MAX 2 SENTENCES).\n"
            "5. NATURAL FLOW: Use contractions (I'm, don't, it's). No lectures.\n"
            "6. STRATEGIC BUT HUMBLE: Drop golden nuggets naturally.\n"
            "7. FEEDBACK AWARENESS: Acknowledgements should be brief.\n"
            "8. WAIT FOR COMPLETION: Only respond to full thoughts.\n"
            "9. ENGLISH ONLY: Ignore non-English noise."
        )
        self.vision_prompt = (
            "ROLE: You are an elite AI Exam Solver. Provide answers in a CLEAN, VERTICAL format for easy reading.\n"
            "FORMATTING RULES:\n"
            "1. NEW LINES: Every question and answer MUST start on a fresh new line.\n"
            "2. BOLD HEADINGS: Use clear headings like **QUESTION 1:** and **ANSWER:**.\n"
            "3. VERTICAL SPACING: Add a double line break between different questions to separate them clearly.\n"
            "4. CONCISE EXPERTISE: Give the absolute best answer in 2-3 punchy sentences. Be the expert.\n"
            "5. NO CLUMPING: Do not write giant blocks of text. Break information into small, easy-to-read chunks."
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
        prompt = self.vision_prompt if image_obj else self.system_prompt
        
        for model_name in self.gemini_fallbacks:
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel(model_name)
                
                config = genai.types.GenerationConfig(max_output_tokens=1000, temperature=0.7)

                if image_obj:
                    # Native PIL Image support
                    response = model.generate_content([prompt, image_obj, f"USER QUERY: {user_input}"], generation_config=config)
                else:
                    response = model.generate_content([prompt, user_input], generation_config=config)
                
                return response.text
            except Exception as e:
                last_error = str(e)
                print(f"[AIEngine] Gemini Fallback {model_name} failed: {last_error}")
                continue

        return f"AI Failure: All brains exhausted. Last Error: {last_error}"

    def analyze_screen(self, image_path: str, query: str = "Identify any questions or code and solve them."):
        try:
            img = Image.open(image_path)
            img.load() 
            return self.get_gemini_response(query, image_obj=img)
        except Exception as e:
            return f"Vision Error: {e}"

ai_engine = AIEngine()
