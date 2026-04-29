import os
import random
from typing import List, Dict

class KeyManager:
    def __init__(self):
        self.status_log = []
        self.keys: Dict[str, List[str]] = {
            "GROQ": self._load_keys("GROQ_API_KEYS"),
            "DEEPGRAM": self._load_keys("DEEPGRAM_API_KEYS"),
            "GEMINI": self._load_keys("GEMINI_API_KEYS"),
            "TAVILY": self._load_keys("TAVILY_API_KEYS"),
        }
        self.indices = {service: 0 for service in self.keys}

    def _load_keys(self, env_var: str) -> List[str]:
        """Loads keys from a comma-separated string in environment variables with aggressive cleaning."""
        keys_raw = os.getenv(env_var, "")
        # Remove ALL types of whitespace and hidden chars, and IGNORE placeholders like 'key1', 'key2'
        placeholders = ["key1", "key2", "key3"]
        keys = [k.strip().replace("\r", "").replace("\n", "").replace(" ", "") for k in keys_raw.split(",") if k.strip()]
        keys = [k for k in keys if k.lower() not in placeholders]
        
        # Fallback to single key if exists (e.g., GROQ_API_KEY)
        single_var = env_var.replace("_KEYS", "")
        single_key = os.getenv(single_var, "")
        if single_key:
            clean_single = single_key.strip().replace("\r", "").replace("\n", "").replace(" ", "")
            if clean_single and clean_single not in keys:
                keys.append(clean_single)
        
        if keys:
            self.status_log.append(f"Loaded {len(keys)} {env_var} keys.")
            print(f"[KeyManager] Successfully loaded {len(keys)} keys for {env_var}")
        else:
            self.status_log.append(f"ERROR: No keys found for {env_var}")
        return keys

    def get_key(self, service: str) -> str:
        """Returns the next available key for a service in a round-robin fashion."""
        service = service.upper()
        if not self.keys.get(service):
            return ""
        
        key = self.keys[service][self.indices[service]]
        # Move to next index for next time
        self.indices[service] = (self.indices[service] + 1) % len(self.keys[service])
        return key

    def report_failure(self, service: str, key: str):
        """Removes a failed/rate-limited key from the rotation temporarily."""
        service = service.upper()
        if key in self.keys.get(service, []):
            print(f"[KeyManager] Key for {service} reported failure. Removing from rotation.")
            self.keys[service].remove(key)
            # Adjust index
            if self.indices[service] >= len(self.keys[service]):
                self.indices[service] = 0

# Global instance
key_manager = KeyManager()
