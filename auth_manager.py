import os
import bcrypt
import random
import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
from email_service import email_service

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
        
        self.mongo_uri = os.getenv("MONGO_URI")
        self.client = None
        self.db = None
        self.users = None
        self.otps = None
        self.is_connected = False
        self.current_user = None
        self.current_user_name = None
        
        if self.mongo_uri:
            try:
                self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
                # Check connection
                self.client.server_info()
                self.db = self.client["StealthHUD"]
                self.users = self.db["users"]
                self.otps = self.db["otps"]
                
                # Ensure OTP index for auto-deletion
                self.otps.create_index("created_at", expireAfterSeconds=600)
                
                self.is_connected = True
                print("[Auth] Connected to MongoDB.")
            except Exception as e:
                print(f"[Auth] Connection Error: {e}")
        else:
            print("[Auth] MONGO_URI not found in .env")

    def send_verification_otp(self, email, name="User"):
        if not self.is_connected: return False, "DB Error"
        
        otp = str(random.randint(100000, 999999))
        self.otps.update_one(
            {"email": email},
            {"$set": {"otp": otp, "created_at": datetime.datetime.utcnow()}},
            upsert=True
        )
        
        if email_service.send_otp(email, otp, name):
            return True, "OTP Sent"
        return False, "Failed to send email"

    def verify_otp(self, email, otp):
        if not self.is_connected: return False
        record = self.otps.find_one({"email": email, "otp": otp})
        return record is not None

    def register(self, email, password, full_name, otp):
        """Registers a new user with hashed password after OTP check."""
        if not self.is_connected:
            return False, "Database connection failed."
            
        if not self.verify_otp(email, otp):
            return False, "Invalid or expired OTP."

        if self.users.find_one({"username": email}):
            return False, "Email already registered."
            
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        self.users.insert_one({
            "username": email,
            "password": hashed,
            "full_name": full_name,
            "created_at": datetime.datetime.utcnow()
        })
        self.otps.delete_one({"email": email})
        return True, "Registration successful."

    def reset_password(self, email, new_password, otp):
        if not self.verify_otp(email, otp):
            return False, "Invalid or expired OTP."
            
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        res = self.users.update_one({"username": email}, {"$set": {"password": hashed}})
        if res.modified_count > 0:
            self.otps.delete_one({"email": email})
            return True, "Password reset successful."
        return False, "User not found."

    def login(self, username, password):
        """Verifies user credentials."""
        if not self.is_connected:
            return False, "Database connection failed."
            
        user = self.users.find_one({"username": username})
        if user and bcrypt.checkpw(password.encode('utf-8'), user["password"]):
            self.current_user = username
            self.current_user_name = user.get("full_name", username)
            return True, "Login successful."
            
        return False, "Invalid username or password."

# Global Instance
auth_manager = AuthManager()
