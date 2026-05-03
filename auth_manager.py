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

class AuthManager:
    def __init__(self):
        # Fix for PyInstaller path handling
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

    def login(self, email, password):
        """Securely logs in via the centralized backend API."""
        try:
            res = requests.post(
                f"{self.backend_url}/api/auth/login",
                json={"email": email, "password": password},
                timeout=10
            )
            if res.ok:
                data = res.json()["user"]
                self.current_user = data["email"]
                self.current_user_name = data.get("full_name", "Authorized Agent")
                self.tier = data.get("tier", "TRIAL")
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
                json={"email": email, "password": password, "full_name": full_name},
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

# Global Instance
auth_manager = AuthManager()


# Global Instance
auth_manager = AuthManager()
