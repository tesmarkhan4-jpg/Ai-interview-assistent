import os
import datetime
import requests
import certifi
import hashlib
import uuid
import traceback
import smtplib
import random
import pymongo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bson import ObjectId
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from pymongo import MongoClient
from dotenv import load_dotenv
from typing import Optional, List

# --- API CORE ---
app = FastAPI(title="ZenithHUD PRO Backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- DATABASE ENGINE ---
class StealthDB:
    def __init__(self):
        try:
            # Simplified for high compatibility (Ai-A Cluster)
            self.uri = "mongodb+srv://admin:admin%40013970@ai-a.fqixdrd.mongodb.net/?appName=Ai-A"
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
            self.db = self.client['zenith_pro']
            self.users = self.db['users']
            self.keys = self.db['api_keys']
            self.history = self.db["mission_history"]
            self.config = self.db['system_config']
            self.otps = self.db['otps']
        except Exception as e:
            print(f"DB Engine Failure: {e}")
            raise e

    def get_user(self, email): return self.users.find_one({"email": email})
    
    def create_user(self, email, password_hash, full_name, hwid=None, tier="TRIAL", join_date=None):
        expiry = datetime.datetime.utcnow() + datetime.timedelta(days=7)
        return self.users.insert_one({
            "email": email, 
            "password": password_hash, 
            "full_name": full_name, 
            "hwid": hwid,
            "tier": tier, 
            "trial_expiry": expiry,
            "join_date": join_date or datetime.datetime.utcnow(), 
            "status": "active"
        })

    def get_all_users(self): return list(self.users.find({}))
    
    def get_config(self):
        cfg = self.config.find_one({})
        return cfg if cfg else {}

# --- MODELS ---
class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str
    otp: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    hwid: str

# --- AUTH & OTP ---
@app.get("/api/health")
async def health():
    return {"status": "online", "timestamp": datetime.datetime.utcnow().isoformat()}

@app.post("/api/auth/send-otp")
async def send_otp(data: dict):
    email = data.get("email")
    if not email: return {"status": "error", "detail": "Email required."}
    
    otp = str(random.randint(100000, 999999))
    try:
        conn = StealthDB()
        conn.otps.update_one(
            {"email": email},
            {"$set": {"otp": otp, "created_at": datetime.datetime.utcnow()}},
            upsert=True
        )
        
        # SMTP CONFIG (Verified Credentials)
        smtp_user = "faheemkhan101992@gmail.com"
        smtp_pass = "pseuniogagkbbhrn" 
        
        msg = MIMEText(f"Your ZenithHUD PRO verification code is: {otp}\n\nValid for 10 minutes.")
        msg['Subject'] = f"{otp} is your ZenithHUD Code"
        msg['From'] = f"ZenithHUD PRO <{smtp_user}>"
        msg['To'] = email
        
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            
        return {"status": "success", "msg": "Verification code sent."}
    except Exception as e:
        return {"status": "error", "detail": f"System Failure: {str(e)}"}

@app.post("/api/auth/signup")
async def signup(user: UserRegister):
    try:
        conn = StealthDB()
        otp_doc = conn.otps.find_one({"email": user.email})
        if not otp_doc or otp_doc["otp"] != user.otp:
            return {"status": "error", "detail": "Invalid or expired verification code."}
            
        if conn.get_user(user.email): 
            return {"status": "error", "detail": "Identity already registered."}
            
        # Basic hashing for demo (in prod use bcrypt)
        hashed = hashlib.sha256(user.password.encode()).hexdigest()
        conn.create_user(user.email, hashed, user.full_name)
        
        conn.otps.delete_one({"email": user.email})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/auth/login")
async def login(user: UserLogin):
    try:
        conn = StealthDB()
        u = conn.get_user(user.email)
        if not u: return {"status": "error", "detail": "Identity not found."}
        
        # Match hash
        hashed = hashlib.sha256(user.password.encode()).hexdigest()
        if u["password"] != hashed:
            return {"status": "error", "detail": "Invalid credentials."}
            
        # HWID Lock (Only for App, skip for WEB_LOGIN)
        if user.hwid != 'WEB_LOGIN':
            if u.get("hwid") and u["hwid"] != user.hwid:
                return {"status": "error", "detail": "Hardware mismatch. Please contact support."}
            if not u.get("hwid"):
                conn.users.update_one({"email": user.email}, {"$set": {"hwid": user.hwid}})
        
        # Prepare response
        user_data = {
            "email": u["email"],
            "full_name": u["full_name"],
            "tier": u["tier"],
            "hwid": u.get("hwid", user.hwid),
            "trial_expiry": u.get("trial_expiry").isoformat() if u.get("trial_expiry") else None
        }
        return {"status": "success", "user": user_data}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# --- ADMIN ROUTES ---
@app.get("/api/admin/users")
async def get_admin_users():
    try:
        conn = StealthDB()
        users = conn.get_all_users()
        now = datetime.datetime.utcnow()
        for u in users:
            u["_id"] = str(u["_id"])
            if u.get("tier") == "PRO":
                u["status_label"] = "PRO"
                u["timer"] = "UNLIMITED"
            elif u.get("trial_expiry"):
                diff = u["trial_expiry"] - now
                if diff.total_seconds() > 0:
                    u["status_label"] = "TRIAL"
                    u["timer"] = f"{diff.days}d {diff.seconds // 3600}h"
                else:
                    u["status_label"] = "EXPIRED"
                    u["timer"] = "0h"
                u["trial_expiry"] = u["trial_expiry"].isoformat()
            else:
                u["status_label"] = "TRIAL"
                u["timer"] = "7d"

            if "join_date" in u and isinstance(u["join_date"], datetime.datetime):
                u["join_date"] = u["join_date"].isoformat()
            else: u["join_date"] = "N/A"
            
        return {"users": users}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/admin/stats")
async def get_stats():
    try:
        conn = StealthDB()
        return {
            "total_users": conn.users.count_documents({}),
            "pro_users": conn.users.count_documents({"tier": "PRO"}),
            "active_keys": conn.keys.count_documents({"status": "healthy"})
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
