import os
import random
from typing import List, Dict

class KeyManager:
    def __init__(self):
        self.status_log = []
        self.keys: Dict[str, List[str]] = {
            "GROQ": [],
            "DEEPGRAM": [],
            "GEMINI": [],
            "TAVILY": [],
        }
        self.indices = {service: 0 for service in self.keys}
        # Initial load from local keys for immediate readiness
        for svc in self.keys:
            self.keys[svc] = self._load_keys(f"{svc}_API_KEYS")

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

    def refresh_from_dashboard(self):
        """Fetches latest keys from the live Admin Dashboard."""
        try:
            # First, load local keys as emergency fallback
            for svc in self.keys:
                local = self._load_keys(f"{svc}_API_KEYS")
                if local: self.keys[svc] = list(set(self.keys[svc] + local))

            # Fetch from Backend
            from auth_manager import auth_manager
            res = requests.get(f"{auth_manager.backend_url}/api/admin/keys", timeout=5)
            if res.ok:
                data = res.json().get("keys", [])
                backend_keys = {"GROQ": [], "DEEPGRAM": [], "GEMINI": [], "TAVILY": []}
                for item in data:
                    prov = item.get("provider", "").upper()
                    val = item.get("key_value", "").strip()
                    if prov in backend_keys and val:
                        backend_keys[prov].append(val)
                
                # Merge and update
                for prov, keys in backend_keys.items():
                    if keys:
                        # Combine with local, remove duplicates
                        self.keys[prov] = list(set(self.keys[prov] + keys))
                
                print(f"[KeyManager] Live Sync Complete. Pool size: {sum(len(v) for v in self.keys.values())} keys.")
        except Exception as e:
            print(f"[KeyManager] Dashboard Sync Failed (Using Fallback): {e}")

# Global instance
import requests # Ensure requests is available
key_manager = KeyManager()
