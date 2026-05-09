import os
import bcrypt
import random
import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
from email_service import email_service

import os
import requests
from dotenv import load_dotenv
from keys import get_hwid

class AuthManager:
    def __init__(self):
        import sys
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
            
        env_path = os.path.join(application_path, ".env")
        load_dotenv(env_path, override=True)
        
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        self.current_user = None
        self.current_user_name = None
        self.tier = "TRIAL"
        self.trial_expiry = None
        self.server_time = None

        # Use APPDATA for user-writable files
        self.data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), "StealthHUD")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.session_file = os.path.join(self.data_dir, "session.json")
        self.load_session()

    def load_session(self):
        """Loads and validates a saved session."""
        if os.path.exists(self.session_file):
            try:
                import json
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                    email = data.get("email")
                
                if email:
                    # VALIDATE with Backend
                    res = requests.post(
                        f"{self.backend_url}/api/auth/validate",
                        json={"email": email, "hwid": get_hwid()},
                        timeout=5
                    )
                    if res.ok:
                        val_data = res.json()
                        self.current_user = email
                        self.current_user_name = val_data.get("full_name")
                        self.tier = val_data.get("tier", "TRIAL")
                        self.trial_expiry = val_data.get("trial_expiry")
                        print(f"[Auth] Strategic Session Validated for {self.current_user}")
                    else:
                        print("[Auth] Identity Expired or Mismatch. Clearing.")
                        self.clear_session()
            except Exception as e:
                print(f"[Auth] Validation Failure: {e}")
                self.clear_session()

    def save_session(self):
        """Saves current session to local file."""
        if self.current_user:
            try:
                import json
                with open(self.session_file, 'w') as f:
                    json.dump({
                        "email": self.current_user,
                        "full_name": self.current_user_name,
                        "tier": self.tier,
                        "trial_expiry": self.trial_expiry,
                        "server_time": self.server_time
                    }, f)
            except:
                pass

    def clear_session(self):
        """Clears the saved session."""
        if os.path.exists(self.session_file):
            os.remove(self.session_file)
        self.current_user = None
        self.current_user_name = None

    def login(self, email, password):
        """Securely logs in via the centralized backend API."""
        try:
            res = requests.post(
                f"{self.backend_url}/api/auth/login",
                json={"email": email, "password": password, "hwid": get_hwid()},
                timeout=10
            )
            if res.ok:
                data = res.json()["user"]
                self.current_user = data["email"]
                self.current_user_name = data.get("full_name", "Authorized Agent")
                self.tier = data.get("tier", "TRIAL")
                self.trial_expiry = data.get("trial_expiry")
                self.server_time = data.get("server_time")
                
                # Persist the session
                self.save_session()
                
                # --- AUTO-SYNC KEYS FROM DASHBOARD ---
                from keys import key_manager
                key_manager.refresh_from_dashboard()
                
                return True, "Identity Verified."
            else:
                detail = res.json().get("detail", "Strategic Identity Mismatch.")
                return False, detail
        except Exception as e:
            return False, f"Infrastructure Link Failure: {str(e)}"

    def register(self, email, password, full_name, otp=None):
        """Registers a new identity via the backend."""
        try:
            res = requests.post(
                f"{self.backend_url}/api/auth/register",
                json={"email": email, "password": password, "full_name": full_name, "hwid": get_hwid()},
                timeout=10
            )
            if res.ok:
                return True, "Deployment Initialized. Please Sign In."
            else:
                detail = res.json().get("detail", "Registration Interrupted.")
                return False, detail
        except Exception as e:
            return False, "Communication Failure."

    def send_verification_otp(self, email, name="User"):
        # The new backend handles OTP or simplified registration
        return True, "Endpoint Ready"
    def logout(self):
        self.clear_session()
        self.current_user = None
        self.current_user_name = None

# Global Instance
auth_manager = AuthManager()
