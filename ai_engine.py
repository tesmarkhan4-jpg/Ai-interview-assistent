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
            "ROLE: You are the candidate described in the provided CV. You are in a live online interview right now.\n"
            "CONTEXT: Your identity, name, and background are entirely defined by this CV data: {cv_data}\n\n"
            "CRITICAL CONVERSATION RULES:\n"
            "1. HYPER-NATURAL SPEECH: Write exactly as a normal, confident person speaks in real life. Do not sound like a written essay or a formal cover letter.\n"
            "2. ADAPTIVE LENGTH (SMART SIZING): Adapt your length to the prompt. If it's a simple greeting ('How are you?'), give a short 1-sentence reply ('Doing great, thanks!'). If it's 'Tell me about yourself', give a casual, punchy 3-sentence overview and stop. NEVER generate long paragraphs.\n"
            "3. READABILITY: Every single response MUST be incredibly easy to read out loud on the fly. Use short, breath-sized sentences. No complex corporate jargon.\n"
            "4. HUMAN REACTIONS: If you make a mistake, brush it off casually ('Ah, my bad!'). Do not over-apologize or sound subservient.\n"
            "5. DYNAMIC TONE: Vary your sentence structures. Sometimes start with 'Yeah,', 'Sure,', or just dive straight into the answer. Do not follow a predictable pattern. Speak like an equal to the interviewer."
        )
        self.vision_prompt = (
            "ROLE: You are a WORLD-CLASS Technical Assessment Solver and Senior Software Engineer (Savant Eye).\n"
            "GOAL: Instantly analyze the provided image, determine the type of test (MCQ, Coding Challenge, or General Assessment), and solve it with absolute accuracy.\n\n"
            "INSTRUCTIONS BASED ON TEST TYPE:\n"
            "--- IF IT IS A MULTIPLE CHOICE QUESTION (MCQ) ---\n"
            "1. Provide the CORRECT OPTION(S) clearly.\n"
            "2. Provide a 1-sentence plain-English explanation of WHY it is correct.\n\n"
            "--- IF IT IS A CODING CHALLENGE ---\n"
            "1. IDENTIFY the language required (e.g., Python, JavaScript, C++).\n"
            "2. WRITE THE COMPLETE, ERROR-FREE CODE exactly as needed to pass the test cases. Do not omit anything. Keep the code clean, optimal, and readable.\n"
            "3. EXPLAIN the logic in 2-3 extremely simple, non-technical sentences so the user can easily talk about it out loud.\n\n"
            "FORMATTING RULES:\n"
            "- Use bolding for headers like **ANSWER** or **CODE**.\n"
            "- Be concise but thoroughly accurate."
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
        last_error = ""
        prompt = self.vision_prompt if image_obj else self.get_current_system_prompt()
        
        # Try up to 15 times to account for multiple exhausted keys
        for attempt in range(15):
            key = key_manager.get_key("GEMINI")
            if not key: return "Gemini API Key missing."

            for model_name in self.gemini_fallbacks:
                try:
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel(model_name)
                    
                    config = genai.types.GenerationConfig(max_output_tokens=2000, temperature=0.7)

                    if image_obj:
                        # Native PIL Image support
                        response = model.generate_content([prompt, image_obj, f"USER QUERY: {user_input}"], generation_config=config)
                    else:
                        response = model.generate_content([prompt, user_input], generation_config=config)
                    
                    return response.text
                except Exception as e:
                    last_error = str(e)
                    safe_key = f"...{key[-4:]}" if len(key) > 4 else "UNKNOWN"
                    print(f"[AIEngine] Gemini {model_name} failed with key {safe_key}: {last_error}")
                    
                    # If it's a rate limit, quota, or exhaustion error, report failure to remove key from rotation temporarily
                    if "429" in last_error or "quota" in last_error.lower() or "exhausted" in last_error.lower() or "ResourceExhausted" in last_error:
                        key_manager.report_failure("GEMINI", key)
                        break  # Break out of model loop to get a NEW key immediately
                    
                    continue # Try the next fallback model with the same key
                    
        return f"AI Failure: All brains exhausted across all keys. Last Error: {last_error}"

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

