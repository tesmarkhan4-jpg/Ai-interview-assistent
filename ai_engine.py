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
        self.cv_context = "No CV uploaded yet."
        
        self.system_prompt = (
            "ROLE: You are the ELITE Technical Candidate described in the provided CV. You are currently in a high-stakes job interview.\n"
            "CONTEXT: Your identity, name, and background are entirely defined by this CV data: {cv_data}\n\n"
            "STYLE RULES:\n"
            "1. BE ORGANIC: Talk like a real person in a casual but professional interview. Use fillers like 'Actually...', 'Well, basically...', 'I'd say...', or 'To be honest...'.\n"
            "2. NO JARGON OVERLOAD: Avoid robotic marketing words like 'top-tier', 'powerful', 'seamless', 'optimization', or 'capabilities' unless they are essential. Talk like a senior dev chatting with a colleague.\n"
            "3. IDENTITY: You are the candidate in the CV: {cv_data}.\n"
            "4. RESPONSE LENGTH: Keep conversational answers under 25 words. Be punchy. Use contractions (I've, I'm).\n"
            "5. NO LISTS OR BULLETS: Use fluid paragraphs only.\n"
            "6. ENGLISH ONLY."
        )
        self.vision_prompt = (
            "ROLE: You are a WORLD-CLASS Technical Assessment Solver (Savant Eye).\n"
            "GOAL: Solve any MCQ, Assessment, or Code Test on screen with absolute accuracy.\n"
            "EXPLANATION RULE: For Code/Technical tests, provide a 'WHAT' (the solution) and a 'WHY' (the reasoning) so the user can explain it.\n"
            "FORMATTING:\n"
            "1. **QUESTION:** (The question found on screen)\n"
            "2. **ANSWER:** (The correct option or code snippet)\n"
            "3. **REASONING (The 'WHY'):** (2 punchy sentences explaining the logic for the candidate to say out loud).\n"
            "4. VERTICAL SPACING: Double line breaks between different items. No blocky text."
        )

    def set_cv_context(self, text: str):
        self.cv_context = text
        print(f"[AIEngine] CV Context synchronized ({len(text)} chars).")

    def get_current_system_prompt(self):
        return self.system_prompt.format(cv_data=self.cv_context)

    def get_groq_response(self, user_input: str) -> str:
        key = key_manager.get_key("GROQ")
        if not key: return "Groq API Key missing."

        client = Groq(api_key=key)
        messages = [{"role": "system", "content": self.get_current_system_prompt()}]
        # Limit history to prevent context lag
        messages.extend(self.conversation_history[-6:])
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
        prompt = self.vision_prompt if image_obj else self.get_current_system_prompt()
        
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

    def generate_interview_report(self) -> Dict:
        if not self.conversation_history:
            return {
                "summary": "Short session with no significant dialogue.",
                "needs": "N/A",
                "market": "N/A",
                "salary": "N/A"
            }
        
        # Build analysis prompt
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in self.conversation_history])
        analysis_prompt = (
            "Analyze the following interview conversation and provide a structured report in JSON format.\n"
            "Include these keys:\n"
            "1. 'summary': A 2-sentence concise summary of the interview.\n"
            "2. 'needs': What exactly does the client/interviewer want or need?\n"
            "3. 'market': What are the current market rates/salaries for this role?\n"
            "4. 'salary': A specific recommended budget or salary to ask for. It should be competitive but slightly lower than the average market rate to guarantee you win the project/job.\n\n"
            "HISTORY:\n" + history_text
        )
        
        try:
            # We use a larger model for analysis
            key = key_manager.get_key("GROQ")
            if not key: raise Exception("Groq key missing")
            
            client = Groq(api_key=key)
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": analysis_prompt}],
                response_format={"type": "json_object"}
            )
            import json
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            print(f"[AIEngine] Report generation failed: {e}")
            return {
                "summary": "Could not generate automated summary.",
                "needs": "Manual review required.",
                "market": "Standard market rates apply.",
                "salary": "Refer to market research."
            }

ai_engine = AIEngine()

