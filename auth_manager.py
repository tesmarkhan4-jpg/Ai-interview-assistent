import os
import random
import datetime
from dotenv import load_dotenv
from hwid_utils import get_hwid

class AuthManager:
    def __init__(self):
        import sys
        if getattr(sys, 'frozen', False):
            bundle_dir = sys._MEIPASS
        else:
            bundle_dir = os.path.dirname(os.path.abspath(__file__))
            
        env_path = os.path.join(bundle_dir, ".env")
        load_dotenv(env_path, override=True)
        
        self.backend_url = os.getenv("BACKEND_URL", "https://zenith-hud.vercel.app")
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
        """Loads local session data without blocking for network validation."""
        if os.path.exists(self.session_file):
            try:
                import json
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                    self.current_user = data.get("email")
                    self.current_user_name = data.get("full_name")
                    self.tier = data.get("tier", "TRIAL").upper()
                    self.trial_expiry = data.get("trial_expiry")
                    print(f"[Auth] Local Session Loaded for {self.current_user}")
            except Exception as e:
                print(f"[Auth] Local Load Failure: {e}")
                self.clear_session()

    def validate_session_async(self):
        """Checks with the server if the local session is still valid (Non-blocking)."""
        if not self.current_user: return
        
        def _check():
            try:
                import requests
                res = requests.post(
                    f"{self.backend_url}/api/auth/validate",
                    json={"email": self.current_user, "hwid": get_hwid()},
                    timeout=3
                )
                if not res.ok:
                    print("[Auth] Session invalid on server. Log out required.")
                    # We don't force logout here to avoid disrupting the user immediately,
                    # but we could trigger a signal if needed.
            except: pass
            
        import threading
        threading.Thread(target=_check, daemon=True).start()

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
            import requests
            res = requests.post(
                f"{self.backend_url}/api/auth/login",
                json={"email": email, "password": password, "hwid": get_hwid()},
                timeout=10
            )
            if res.ok:
                resp_json = res.json()
                data = resp_json.get("user", resp_json) # Fallback to top-level if "user" key is missing
                
                self.current_user = data.get("email")
                if not self.current_user:
                    return False, "Infrastructure Error: Response missing identity data."
                    
                self.current_user_name = data.get("full_name", "Authorized Agent")
                self.tier = data.get("tier", "TRIAL").upper()
                self.trial_expiry = data.get("trial_expiry")
                self.server_time = data.get("server_time")
                
                # Persist the session
                self.save_session()
                
                return True, "Identity Verified."
            else:
                detail = res.json().get("detail", "Strategic Identity Mismatch.")
                return False, detail
        except Exception as e:
            return False, f"Infrastructure Link Failure: {str(e)}"

    def register(self, email, password, full_name, otp=None):
        """Registers a new identity via the backend."""
        try:
            import requests
            res = requests.post(
                f"{self.backend_url}/api/auth/signup",
                json={"email": email, "password": password, "full_name": full_name, "hwid": get_hwid(), "otp": otp},
                timeout=10
            )
            if res.ok:
                data = res.json()
                if data.get("status") == "success":
                    return True, "Deployment Initialized. Please Sign In."
                else:
                    return False, data.get("detail", "Registration Interrupted.")
            else:
                return False, "Communication Failure."
        except Exception as e:
            return False, "Communication Failure."

    def send_verification_otp(self, email, name="User"):
        """Requests an OTP code from the backend to be sent to the user's email."""
        try:
            import requests
            from hwid_utils import get_hwid
            res = requests.post(
                f"{self.backend_url}/api/auth/send-otp",
                json={"email": email, "full_name": name, "hwid": get_hwid()},
                timeout=10
            )
            if res.ok:
                data = res.json()
                if data.get("status") == "success":
                    return True, "Verification code sent!"
                else:
                    return False, data.get("detail", "Failed to send code.")
            else:
                return False, "Communication Failure."
        except Exception as e:
            return False, "Communication Failure. Ensure you are connected to the network."
    def check_system_lock(self):
        """Checks if this HWID is already bound to another identity."""
        try:
            import requests
            res = requests.get(
                f"{self.backend_url}/api/auth/system-status",
                params={"hwid": get_hwid()},
                timeout=5
            )
            if res.ok:
                return res.json()
        except:
            pass
        return {"locked": False, "maintenance_mode": False}

    def check_maintenance(self):
        """Dedicated check for global maintenance state."""
        try:
            import requests
            res = requests.get(
                f"{self.backend_url}/api/auth/system-status",
                params={"hwid": "MAINTENANCE_POLL"},
                timeout=5
            )
            if res.ok:
                data = res.json()
                return data.get("maintenance_mode", False), data.get("maintenance_message", "Strategic calibration in progress...")
        except:
            pass
        return False, ""

    def logout(self):
        self.clear_session()
        self.current_user = None
        self.current_user_name = None

    def send_ticket_message(self, email, message, role="user"):
        """Sends a message to the support ticket system using standard JSON payload."""
        try:
            import requests
            res = requests.post(
                f"{self.backend_url}/api/auth/ticket/send",
                json={
                    "email": email,
                    "message": message,
                    "hwid": get_hwid(),
                    "role": role
                },
                timeout=10
            )
            return res.ok
        except Exception as e:
            print(f"[Auth] Ticket Send Error: {e}")
            return False

    def report_key_usage(self, provider: str, key_value: str):
        """Silently reports API key usage to the backend for real-time tracking."""
        if not key_value: return
        try:
            import requests
            # Fire and forget
            requests.post(
                f"{self.backend_url}/api/auth/keys/usage",
                json={"provider": provider, "key_value": key_value},
                timeout=2
            )
        except:
            pass

    def get_ticket_history(self, email):
        """Retrieves conversation history and metadata for a user's ticket."""
        try:
            import requests
            res = requests.get(
                f"{self.backend_url}/api/auth/ticket/history",
                params={"email": email},
                timeout=5
            )
            if res.ok:
                return res.json()
        except:
            pass
        return {"messages": [], "resolved_count": 0, "has_active": False}

# Global Instance
auth_manager = AuthManager()
