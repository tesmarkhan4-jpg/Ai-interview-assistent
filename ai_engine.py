import os
from groq import Groq
import base64
from typing import List, Dict
from PIL import Image
import io
from memory_manager import memory_manager
from knowledge_base import kb
from linkedin_scraper import enrich_brain_with_linkedin

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
        self.linkedin_url = "No LinkedIn URL provided."
        
        self.groq_keys = []
        # --- LIVE API KEY POOL ---
        from hwid_utils import key_manager
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
                "### CANDIDATE IDENTITY ###\n"
                "{cv_data}\n"
                "\n"
                "### OPERATIONAL RULES ###\n"
                "1. ORGANIC EXPERT: You are the candidate. Speak with a natural, human-like professional friendly tone. Use contractions (I'm, don't, I've). Use natural fillers (Honestly, actually, I'd say...). Avoid formal academic structures.\n"
                "2. NO REPETITION: Never repeat your name, location, or background if you have already mentioned it in the conversation history. Treat this like a continuous natural chat.\n"
                "3. DYNAMIC LENGTH: Match your response to the question's weight. Simple questions = 1 punchy sentence. Complex technical deep-dives = 2-3 concise paragraphs (max 60 words total).\n"
                "4. FIRST-PERSON FLOW: Explain HOW you do things using 'I'. Instead of 'A custom post type is...', say 'In my experience, I usually set up custom post types by...'.\n"
                "5. ZERO ROBOTICS: No bolding, no lists, no AI-isms. Avoid academic transitions like 'For instance' or 'In conclusion'. Use 'So...' or 'Actually...' instead."
            ),
            "code_challenge": (
                "SYSTEM (HIDDEN): Output ONLY the solution.\n"
                "**BOLD SOLUTION AT TOP.** Clean Code."
            ),
            "mcq": (
                "SYSTEM (HIDDEN): Output ONLY the option.\n"
                "**BOLD OPTION.** 3-word logic."
            )
        }

    def set_cv_context(self, text: str):
        """Ingests the FULL RAW TEXT of the CV for Photographic Memory."""
        if not text or len(text.strip()) < 50:
            return

        print("[AIEngine] Neural Core: Ingesting FULL CV Text for Total Recall...")
        self.cv_context = text # Store the full raw text
        
        # Mapping facts into SQLite for backup
        kb.init_db()
        kb.clear_brain()
        
        architect_prompt = (
            "TASK: Extract basic identity from this CV into JSON.\n"
            "FORMAT: { \"name\": \"\", \"email\": \"\", \"whatsapp\": \"\", \"location\": \"\", \"current_role\": \"\", \"current_company\": \"\" }\n"
            "CV: " + text[:3000]
        )
        
        try:
            import json
            chat_completion = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": architect_prompt}],
                model="llama-3.3-70b-specdec",
                response_format={"type": "json_object"}
            )
            data = json.loads(chat_completion.choices[0].message.content)
            
            kb.add_identity("name", data.get("name", "Faheem Khan"))
            kb.add_identity("email", data.get("email", ""))
            kb.add_identity("whatsapp", data.get("whatsapp", ""))
            kb.add_identity("location", data.get("location", "Islamabad, Pakistan"))
            
            # Save raw text into a specialized 'Deep Memory' key
            kb.add_identity("deep_memory_cv", text)
            
            print(f"[AIEngine] Photographic Memory Locked for {data.get('name')}.")
        except Exception as e:
            print(f"[AIEngine] Memory Mapping Error: {e}")

    def set_job_context(self, jd: str, link: str, linkedin: str = ""):
        self.jd_context = jd
        self.company_link = link
        self.linkedin_url = linkedin
        
        # Optionally enrich brain with LinkedIn data in background
        if linkedin and len(linkedin.strip()) > 5:
            try:
                enrich_brain_with_linkedin(linkedin.strip(), self.groq_client, kb)
            except Exception as e:
                print(f"[AIEngine] LinkedIn enrichment skipped: {e}")

    def set_mode(self, mode: str):
        if mode in self.prompts:
            self.mode = mode

    def set_tier(self, tier: str):
        self.intelligence_tier = tier

    def get_current_system_prompt(self, user_query: str = ""):
        base_prompt = self.prompts.get(self.mode, self.prompts["interview"])
        
        # DYNAMIC EXTRACTION (ABSOLUTE TRUTH)
        identity = {r['key']: r['value'] for r in kb.query_identity()}
        raw_cv = identity.get('deep_memory_cv', self.cv_context)
        all_exp = kb.query_brain("all")
        
        # Identity Logic
        name = identity.get('name', 'FAHEEM KHAN')
        location = identity.get('location', 'Islāmābād, Pakistan')
        
        # TEMPORAL LOGIC: Find CURRENT role
        current_role = "AI Automation Specialist"
        current_company = "Try Soft AI"
        for exp in all_exp:
            if "present" in exp.get('duration', '').lower():
                current_role = exp['role']
                current_company = exp['company']
                break

        # AGENTIC SEARCH (DEEP RECALL)
        query_lower = user_query.lower()
        recalled_facts = []
        for exp in all_exp:
            if any(k in exp['company'].lower() for k in query_lower.split() if len(k) > 3):
                recalled_facts.append(f"VERIFIED RECORD: {exp['role']} at {exp['company']} ({exp['duration']})")

        # Construct the High-Fidelity Context
        brain_context = f"## ACTIVE PERSONA ##\n"
        brain_context += f"NAME: {name}\n"
        brain_context += f"LOCATION: {location}\n"
        brain_context += f"CURRENT STATUS: Working as {current_role} at {current_company} (May 2025 - Present)\n"
        brain_context += f"HEADLINE: {identity.get('linkedin_headline', 'AI Automation Specialist')}\n\n"
        
        if recalled_facts:
            brain_context += "### HISTORICAL RECALL ###\n"
            brain_context += "\n".join(recalled_facts) + "\n\n"
            
        brain_context += "### SOURCE CV TEXT (FULL RECALL) ###\n"
        brain_context += f"{raw_cv[:5000]}\n"

        # --- CONTEXT PERSISTENCE (Fix for lost memory) ---
        chat_history_str = ""
        if self.conversation_history:
            chat_history_str = "### RECENT CONVERSATION HISTORY ###\n"
            # Include last 10 messages for deep context
            for msg in self.conversation_history[-10:]:
                role = "INTERVIEWER" if msg["role"] == "user" else "AI"
                chat_history_str += f"{role}: {msg['content']}\n"
            chat_history_str += "\n"
            
        return base_prompt.format(
            cv_data=brain_context + chat_history_str, 
            jd_data=self.jd_context, 
            company_link=self.company_link,
            linkedin_url=self.linkedin_url
        )

    def _get_next_client(self):
        """Rotates to the next available API key from the live pool."""
        from hwid_utils import key_manager
        key = key_manager.get_key("GROQ")
        if not key: return None
        return Groq(api_key=key)

    def get_ai_response(self, user_input: str, provider: str = "groq") -> str:
        """Gets AI response with silent retry and proactive key rotation."""
        if not user_input or len(user_input.strip()) < 2: return "..."
        if not auth_manager.current_user: return "Auth Error: Please sign in."
        
        # --- PLAN LIMIT ENFORCEMENT ---
        if auth_manager.tier == "BASIC":
            from history_manager import history_manager
            import datetime
            history = history_manager.get_user_history(auth_manager.current_user)
            if history:
                try:
                    last_mission_time = datetime.datetime.strptime(history[0]["id"], "%Y%m%d%H%M%S")
                    if (datetime.datetime.now() - last_mission_time).days < 7:
                        return "TACTICAL LIMIT REACHED: Basic Tier is restricted to 1 mission per week. Upgrade to PRO for Unlimited Dominance."
                except Exception as e:
                    print(f"Time parse error: {e}")
                    
        # Proactively rotate key before starting the request
        if provider == "groq":
            self.groq_client = self._get_next_client() or self.groq_client
            
        # Record user input
        self.conversation_history.append({"role": "user", "content": user_input})

        # --- PROPER MESSAGE STRUCTURE ---
        system_content = self.get_current_system_prompt(user_input)
        
        messages = [{"role": "system", "content": system_content}]
        # Include last 10 messages for deep context
        for msg in self.conversation_history[-10:]:
            messages.append(msg)
            
        # Self-Healing Retry Loop
        for attempt in range(len(self.groq_keys) if self.groq_keys else 2):
            try:
                if provider == "groq" and self.groq_client:
                    model = "llama-3.3-70b-versatile" if self.intelligence_tier == "savant" else "llama-3.1-8b-instant"
                    chat_completion = self.groq_client.chat.completions.create(
                        messages=messages,
                        model=model,
                    )
                    response = chat_completion.choices[0].message.content.replace("*", "")
                    # Record AI response
                    self.conversation_history.append({"role": "assistant", "content": response})
                    auth_manager.report_key_usage("Groq", self.groq_client.api_key)
                    return response
            except Exception as e:
                # Rotate key and try again silently
                self.groq_client = self._get_next_client()
                continue
        
        return "System is stabilizing. Please wait..."

    def get_ai_response_stream(self, user_input: str, provider: str = "groq"):
        """Yields chunks of the AI response with proactive rotation failsafes."""
        if not user_input or len(user_input.strip()) < 2: return
        
        # --- PLAN LIMIT ENFORCEMENT ---
        if auth_manager.tier == "BASIC":
            from history_manager import history_manager
            import datetime
            history = history_manager.get_user_history(auth_manager.current_user)
            if history:
                try:
                    last_mission_time = datetime.datetime.strptime(history[0]["id"], "%Y%m%d%H%M%S")
                    if (datetime.datetime.now() - last_mission_time).days < 7:
                        yield "TACTICAL LIMIT REACHED: Basic Tier is restricted to 1 mission per week. Upgrade to PRO for Unlimited Dominance."
                        return
                except Exception as e:
                    print(f"Time parse error: {e}")

        # Proactively rotate key before starting the request
        if provider == "groq":
            self.groq_client = self._get_next_client() or self.groq_client
            
        # Record user input
        self.conversation_history.append({"role": "user", "content": user_input})

        # --- PROPER MESSAGE STRUCTURE ---
        system_content = self.get_current_system_prompt(user_input)
        
        messages = [{"role": "system", "content": system_content}]
        for msg in self.conversation_history[-10:]:
            messages.append(msg)
            
        for attempt in range(2):
            try:
                if provider == "groq" and self.groq_client:
                    model = "llama-3.3-70b-versatile" if self.intelligence_tier == "savant" else "llama-3.1-8b-instant"
                    stream = self.groq_client.chat.completions.create(
                        messages=messages,
                        model=model,
                        stream=True,
                    )
                    
                    full_response = ""
                    for chunk in stream:
                        if chunk.choices[0].delta.content:
                            text = chunk.choices[0].delta.content.replace("*", "")
                            full_response += text
                            yield text
                    
                    # Record AI response
                    self.conversation_history.append({"role": "assistant", "content": full_response})
                    auth_manager.report_key_usage("Groq", self.groq_client.api_key)
                    return
            except Exception as e:
                self.groq_client = self._get_next_client()
                continue
        
        yield self.get_ai_response(user_input, provider)

    def analyze_screen(self, image_path: str, query: str = "Identify any questions or code and solve them."):
        """Sends screen capture for elite vision analysis via Gemini."""
        try:
            from hwid_utils import key_manager
            api_key = key_manager.get_key("GEMINI")
            if not api_key:
                api_keys = os.getenv("GEMINI_API_KEYS")
                if api_keys:
                    api_key = api_keys.split(",")[0].strip()
                else:
                    api_key = os.getenv("GEMINI_API_KEY")
            
            if not api_key:
                return "Vision Error: No Gemini Key. Please check .env"

            import google.generativeai as genai
            genai.configure(api_key=api_key)
            
            img = Image.open(image_path)
            
            # Integrated Savant Eye Vision Prompt
            vision_prompt = (
                "ROLE: You are an elite candidate taking an interview. Speak as 'I'. Use SIMPLE, NATURAL, EVERYDAY ENGLISH.\n"
                "TASK: Look at the screen. Identify all questions and provide short, organic answers.\n"
                "STRICT RULES:\n"
                "1. ADAPT LENGTH: Match your answer length to the question. Do not over-explain. Max 3 sentences.\n"
                "2. ONLY ANSWER WHAT IS ASKED: Stop after answering. Do not ask questions back.\n"
                "3. FRIENDLY TONE: Be polite and human. Do not sound like a robot or textbook.\n"
                "4. FORMAT: Write 'Q: [Question]' then a new line with 'A: [Answer]'.\n"
                "5. PURE SPEECH: No markdown (*, #), no lists, no AI preambles."
            )
            
            # Use a robust fallback loop to handle High Demand (503) or Not Found (404) errors
            # Optimized models for faster vision analysis (Legacy format)
            models_to_try = [
                'models/gemini-1.5-flash', 
                'models/gemini-2.0-flash-exp', 
                'models/gemini-flash-latest',
                'models/gemini-1.5-pro'
            ]
            
            for model_name in models_to_try:
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content([vision_prompt, query, img])
                    auth_manager.report_key_usage("Gemini", api_key)
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

    def generate_interview_report(self):
        """Analyzes the complete interview history and generates a professional report."""
        if not self.conversation_history:
            return {"summary": "No conversation data to analyze."}

        history_text = ""
        for msg in self.conversation_history:
            role = "USER" if msg["role"] == "user" else "AI"
            history_text += f"{role}: {msg['content']}\n\n"

        # Truncate if extremely long to avoid API limits (keep last 6000 words)
        words = history_text.split()
        if len(words) > 6000:
            history_text = "[...Transcript Truncated for Length...]\n" + " ".join(words[-6000:])


        report_prompt = (
            "TASK: Analyze the following interview transcript and generate a detailed project/job report.\n"
            "CONTEXT: This is for a technical developer or hiring manager.\n\n"
            "TRANSCRIPT:\n" + history_text + "\n\n"
            "OUTPUT FORMAT (JSON ONLY):\n"
            "{\n"
            "  \"summary\": \"Brief overview of what happened\",\n"
            "  \"client_needs\": \"What exactly does the client/hiring manager want?\",\n"
            "  \"project_scope\": \"Detailed understanding of the project or full-time role tasks\",\n"
            "  \"technical_breakdown\": \"Step-by-step instructions for a developer to follow to complete this task\",\n"
            "  \"job_requirements\": \"If full-time, what skills and commitments do they need?\",\n"
            "  \"salary\": \"Strategic recommendation for selection\",\n"
            "  \"market\": \"Quick market context\",\n"
            "  \"full_transcript\": \"The stored conversation\"\n"
            "}\n"
        )

        try:
            import json
            model = "llama-3.3-70b-versatile"
            chat_completion = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": report_prompt}],
                model=model,
                response_format={"type": "json_object"}
            )
            report = json.loads(chat_completion.choices[0].message.content)
            report["full_transcript"] = history_text # Ensure we keep the raw log
            return report
        except Exception as e:
            print(f"[AIEngine] Report Gen Failure: {e}")
            return {"summary": f"Failed to generate report: {str(e)}", "full_transcript": history_text}

ai_engine = AIEngine()

