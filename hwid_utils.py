import hashlib
import platform
import subprocess
import uuid
import os
import random
from typing import List, Dict
import sys
from dotenv import load_dotenv

def get_hwid():
    """Generates a unique hardware ID for the current system."""
    try:
        if platform.system() == "Windows":
            cmd = 'reg query "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography" /v MachineGuid'
            guid = subprocess.check_output(cmd, shell=True).decode().split()[-1]
            return hashlib.sha256(guid.encode()).hexdigest()
    except:
        pass

    node = str(uuid.getnode())
    return hashlib.sha256(node.encode()).hexdigest()

def is_already_running():
    """Checks if another instance of the app is already running (simple lock file)."""
    lock_path = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), "StealthHUD", "app.lock")
    if os.path.exists(lock_path):
        try:
            os.remove(lock_path)
        except OSError:
            return True
    
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with open(lock_path, 'w') as f:
        f.write(str(os.getpid()))
    return False

class KeyManager:
    def __init__(self):
        # Ensure .env is loaded from the correct location (bundle or current dir)
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        env_path = os.path.join(base_path, ".env")
        load_dotenv(env_path, override=True)

        self.status_log = []
        self.keys: Dict[str, List[str]] = {
            "GROQ": self._load_keys("GROQ_API_KEYS"),
            "DEEPGRAM": self._load_keys("DEEPGRAM_API_KEYS"),
            "GEMINI": self._load_keys("GEMINI_API_KEYS"),
            "TAVILY": self._load_keys("TAVILY_API_KEYS"),
        }
        self.indices = {service: 0 for service in self.keys}

    def _load_keys(self, env_var: str) -> List[str]:
        keys_raw = os.getenv(env_var, "")
        placeholders = ["key1", "key2", "key3"]
        keys = [k.strip().replace("\\r", "").replace("\\n", "").replace(" ", "") for k in keys_raw.split(",") if k.strip()]
        keys = [k for k in keys if k.lower() not in placeholders]
        
        single_var = env_var.replace("_KEYS", "")
        single_key = os.getenv(single_var, "")
        if single_key:
            clean_single = single_key.strip().replace("\\r", "").replace("\\n", "").replace(" ", "")
            if clean_single and clean_single not in keys:
                keys.append(clean_single)
        
        if keys:
            self.status_log.append(f"Loaded {len(keys)} {env_var} keys.")
            print(f"[KeyManager] Successfully loaded {len(keys)} keys for {env_var}")
        else:
            self.status_log.append(f"ERROR: No keys found for {env_var}")
        return keys

    def get_key(self, service: str) -> str:
        service = service.upper()
        if not self.keys.get(service):
            return ""
        
        key = self.keys[service][self.indices[service]]
        self.indices[service] = (self.indices[service] + 1) % len(self.keys[service])
        return key

    def report_failure(self, service: str, key: str):
        service = service.upper()
        if key in self.keys.get(service, []):
            print(f"[KeyManager] Key for {service} reported failure. Removing from rotation.")
            self.keys[service].remove(key)
            if self.indices[service] >= len(self.keys[service]):
                self.indices[service] = 0

key_manager = KeyManager()