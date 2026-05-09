import json
import os
import re

class MemoryManager:
    def __init__(self):
        self.memory_path = "user_memory.json"
        self.brain_map = {
            "identity": {"name": "Faheem Khan", "location": "Islamabad, Pakistan"},
            "current_role": "AI Automation Architect",
            "timeline": [],
            "raw_cv": ""
        }
        self.load_memory()

    def purge_and_remap(self, cv_text: str):
        """Wipes old data and structures the new CV into a high-precision Brain Map."""
        print("[MemoryManager] Purging old context and re-mapping neural core...")
        
        # Reset Map
        self.brain_map = {
            "identity": {"name": "Faheem Khan", "location": "Islamabad, Pakistan"},
            "current_role": "Unknown",
            "timeline": [],
            "raw_cv": cv_text
        }

        # High-Precision Extraction Logic
        try:
            # Extract Current Role (Looking for 'Present' or 'Current')
            lines = cv_text.split('\n')
            for i, line in enumerate(lines):
                if "Present" in line or "Current" in line:
                    # The line above or the start of this line usually contains the role
                    potential_role = lines[i-1].strip() if i > 0 else line
                    self.brain_map["current_role"] = potential_role
                    break
            
            # Simple list of all roles for context
            roles = re.findall(r"([A-Z][a-zA-Z\s&]{5,})\n", cv_text)
            self.brain_map["timeline"] = [r.strip() for r in roles if len(r.strip()) > 10][:10]
            
        except Exception as e:
            print(f"[MemoryManager] Mapping Warning: {e}")

        self.save_memory()
        print(f"[MemoryManager] Successfully mapped: {self.brain_map['current_role']}")

    def get_context_snapshot(self):
        """Returns a structured snapshot for the AI to use as ground truth."""
        return (
            f"IDENTIFIED PERSONA: {self.brain_map['identity']['name']}\n"
            f"CURRENT EMPLOYMENT: {self.brain_map['current_role']}\n"
            f"PROFESSIONAL HISTORY: {', '.join(self.brain_map['timeline'])}\n"
            f"FULL SOURCE DATA: {self.brain_map['raw_cv'][:2000]}"
        )

    def save_memory(self):
        try:
            with open(self.memory_path, "w") as f:
                json.dump(self.brain_map, f, indent=4)
        except:
            pass

    def load_memory(self):
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r") as f:
                    self.brain_map = json.load(f)
            except:
                pass

memory_manager = MemoryManager()
