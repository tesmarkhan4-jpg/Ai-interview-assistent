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
            # Use Env Var with fallback
            self.uri = os.getenv("MONGO_URI", "mongodb+srv://admin:admin%40013970@ai-a.fqixdrd.mongodb.net/?appName=Ai-A")
            
            # Add certifi for SSL compatibility on Vercel
            import certifi
            self.client = MongoClient(
                self.uri, 
                serverSelectionTimeoutMS=10000, 
                connectTimeoutMS=10000,
                tlsCAFile=certifi.where()
            )
            
            # Force a ping to verify connection
            self.client.admin.command('ping')
            
            self.db = self.client['zenith_pro']
            self.users = self.db['users']
            self.keys = self.db['api_keys']
            self.history = self.db["mission_history"]
            self.config = self.db['system_config']
            self.otps = self.db['otps']
        except Exception as e:
            print(f"CRITICAL: DB Engine Failure: {str(e)}")
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

# Global Connection Instance (Lazy Loaded)
_conn = None

def get_conn():
    global _conn
    if _conn is None:
        try:
            _conn = StealthDB()
        except Exception as e:
            # Clear error logging to console
            print(f"DB_RETRY_ERROR: {str(e)}")
            return None
    return _conn

# --- MODELS ---
class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str
    otp: str
    hwid: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    hwid: str

class UserValidate(BaseModel):
    email: str
    hwid: str

class PasswordUpdate(BaseModel):
    email: str
    password: str

# --- AUTH & OTP ---
# --- USER INTELLIGENCE ---
@app.get("/api/user/interviews")
async def get_user_interviews(email: str):
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        # Fetch missions for this user
        missions = list(conn.history.find({"user_email": email}).sort("timestamp", -1))
        for m in missions:
            m["_id"] = str(m["_id"])
            if isinstance(m.get("timestamp"), datetime.datetime):
                m["date_str"] = m["timestamp"].strftime("%b %d, %Y at %H:%M")
        return {"status": "success", "interviews": missions}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/user/interviews/delete")
async def delete_user_interview(data: dict):
    try:
        id = data.get("id")
        email = data.get("email")
        if not id or not email: return {"status": "error", "detail": "Missing ID or Email."}
        
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        conn.history.delete_one({"_id": ObjectId(id), "user_email": email})
        return {"status": "success", "msg": "Mission log purged."}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/auth/send-otp")
async def send_otp(data: dict):
    email = data.get("email")
    if not email: return {"status": "error", "detail": "Email required."}
    
    otp = str(random.randint(100000, 999999))
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        conn.otps.update_one(
            {"email": email},
            {"$set": {"otp": otp, "created_at": datetime.datetime.utcnow()}},
            upsert=True
        )
        
        # SMTP CONFIG
        smtp_user = "faheemkhan101992@gmail.com"
        smtp_pass = "pseuniogagkbbhrn" 
        
        # HTML TEMPLATE
        html_content = f"""
        <html>
            <body style="font-family: 'Inter', Helvetica, Arial, sans-serif; background-color: #f8fafc; padding: 40px; margin: 0;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 24px; overflow: hidden; box-shadow: 0 10px 40px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;">
                    <div style="background: linear-gradient(135deg, #4f46e5, #0ea5e9); padding: 40px; text-align: center;">
                        <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 900; letter-spacing: -1px;">Zenith<span style="opacity: 0.8;">HUD</span> PRO</h1>
                        <p style="color: rgba(255,255,255,0.9); margin-top: 8px; font-size: 16px;">Strategic Verification System</p>
                    </div>
                    <div style="padding: 40px; text-align: center;">
                        <h2 style="color: #1e293b; margin-bottom: 8px; font-weight: 800; letter-spacing: -1px; font-size: 24px;">Confirm Your Identity</h2>
                        <p style="color: #64748b; font-size: 16px; line-height: 1.6; margin-bottom: 32px;">Please use the code below to complete your account deployment. This code is valid for 10 minutes.</p>
                        
                        <div style="background: #f1f5f9; border-radius: 16px; padding: 24px; display: inline-block; min-width: 200px;">
                            <span style="font-family: 'Courier New', monospace; font-size: 40px; font-weight: 900; color: #4f46e5; letter-spacing: 8px;">{otp}</span>
                        </div>
                        
                        <p style="color: #94a3b8; font-size: 14px; margin-top: 40px;">If you did not request this verification, you can safely ignore this email.</p>
                    </div>
                    <div style="padding: 24px; background: #f8fafc; text-align: center; border-top: 1px solid #f1f5f9;">
                        <p style="color: #cbd5e1; font-size: 12px; margin: 0;">&copy; 2026 ZenithHUD PRO &bull; All Rights Reserved</p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        msg = MIMEMultipart("alternative")
        msg['Subject'] = f"{otp} is your ZenithHUD Verification Code"
        msg['From'] = f"ZenithHUD PRO <{smtp_user}>"
        msg['To'] = email
        
        msg.attach(MIMEText(f"Your ZenithHUD PRO code is: {otp}", "plain"))
        msg.attach(MIMEText(html_content, "html"))
        
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            
        return {"status": "success", "msg": "Code sent."}
    except Exception as e:
        return {"status": "error", "detail": f"System Failure: {str(e)}"}

@app.get("/api/auth/system-status")
async def get_system_status(hwid: str):
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        u = conn.users.find_one({"hwid": hwid})
        if u:
            # Mask the email slightly for privacy: f***n@gmail.com
            email = u["email"]
            parts = email.split("@")
            masked = parts[0][0] + "*" * (len(parts[0])-2) + parts[0][-1] + "@" + parts[1] if len(parts[0]) > 2 else email
            return {"locked": True, "owner": masked}
        return {"locked": False}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/auth/signup")
async def signup(user: UserRegister):
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        
        # 1. HWID Lock: Check if this system is already linked to another account (CRITICAL)
        if user.hwid and user.hwid != 'WEB_LOGIN':
            existing_hwid_user = conn.users.find_one({"hwid": user.hwid})
            if existing_hwid_user:
                return {"status": "error", "detail": "This system is locked with another account. Please sign in with the registered account."}

        # 2. OTP Verification
        otp_doc = conn.otps.find_one({"email": user.email})
        if not otp_doc or otp_doc["otp"] != user.otp:
            return {"status": "error", "detail": "Invalid or expired verification code."}
            
        # 3. Email Check
        if conn.get_user(user.email): 
            return {"status": "error", "detail": "Identity already registered."}
            
        # Basic hashing for demo (in prod use bcrypt)
        hashed = hashlib.sha256(user.password.encode()).hexdigest()
        conn.create_user(user.email, hashed, user.full_name, hwid=user.hwid)
        
        conn.otps.delete_one({"email": user.email})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/auth/login")
async def login(user: UserLogin):
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        u = conn.get_user(user.email)
        if not u: return {"status": "error", "detail": "Identity not found in database."}
        
        # 1. HWID Lock (Only for App, skip for WEB_LOGIN)
        if user.hwid != 'WEB_LOGIN':
            if u.get("hwid") and u["hwid"] != 'WEB_LOGIN':
                if u["hwid"] != user.hwid:
                    return {"status": "error", "detail": "This system is locked with another account. Please sign in with the registered account."}
            else:
                # User doesn't have an HWID yet, but is this system already taken?
                existing_owner = conn.users.find_one({"hwid": user.hwid})
                if existing_owner and existing_owner["email"] != user.email:
                    return {"status": "error", "detail": "This system is locked with another account. Please sign in with the registered account."}

        # 2. Match hash
        hashed = hashlib.sha256(user.password.encode()).hexdigest()
        if u["password"] != hashed:
            return {"status": "error", "detail": "Invalid credentials provided."}
            
        # Success - generate response
        # Link this system to the user if not already linked
        if not u.get("hwid") or u["hwid"] == 'WEB_LOGIN':
            conn.users.update_one({"email": user.email}, {"$set": {"hwid": user.hwid}})
        
        # Prepare response
        user_data = {
            "email": u["email"],
            "full_name": u["full_name"],
            "tier": u["tier"],
            "role": u.get("role", "user"),
            "hwid": u.get("hwid", user.hwid),
            "trial_expiry": u.get("trial_expiry").isoformat() if u.get("trial_expiry") else None
        }
        return {"status": "success", "user": user_data}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/auth/validate")
async def validate_session(data: UserValidate):
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        u = conn.get_user(data.email)
        if not u: return {"status": "error", "detail": "User not found."}
        
        # Strictly enforce system lock
        if u.get("hwid") and u["hwid"] != data.hwid:
            return {"status": "error", "detail": "This system is locked with another account. Please sign in with the registered account."}
            
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
        
# --- ADMIN ROUTES ---
@app.get("/api/admin/users")
async def get_admin_users():
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
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
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        return {
            "total_users": conn.users.count_documents({}),
            "active_sessions": conn.history.count_documents({"timestamp": {"$gt": datetime.datetime.utcnow() - datetime.timedelta(hours=1)}}),
            "key_health": 100, # Mock
            "revenue": 0,
            "pro_users": conn.users.count_documents({"tier": "PRO"}),
            "active_keys": conn.keys.count_documents({"status": "healthy"}),
            "maintenance_mode": conn.get_config().get("maintenance_mode", False)
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/admin/keys")
async def get_keys():
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        keys = list(conn.keys.find({}))
        for k in keys:
            k["_id"] = str(k["_id"])
            if isinstance(k.get("last_used"), datetime.datetime):
                k["last_used"] = k["last_used"].isoformat()
        return {"keys": keys}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/keys")
async def add_key(provider: str, key_value: str):
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        conn.keys.insert_one({
            "provider": provider,
            "key_value": key_value,
            "status": "healthy",
            "usage_count_total": 0,
            "usage_count_today": 0,
            "last_used": None
        })
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.delete("/api/admin/keys/{key_id}")
async def delete_key(key_id: str):
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        conn.keys.delete_one({"_id": ObjectId(key_id)})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/users/upgrade")
async def upgrade_user(email: str):
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        conn.users.update_one({"email": email}, {"$set": {"tier": "PRO"}})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/users/password")
async def update_user_password(data: PasswordUpdate):
    try:
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        hashed = hashlib.sha256(data.password.encode()).hexdigest()
        conn.users.update_one({"email": data.email}, {"$set": {"password": hashed}})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/users/reset-hwid")
async def reset_hwid(email: str):
    try:
        conn = StealthDB()
        conn.users.update_one({"email": email}, {"$set": {"hwid": None}})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.delete("/api/admin/users/{email}")
async def delete_user(email: str):
    try:
        conn = StealthDB()
        conn.users.delete_one({"email": email})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/admin/config")
async def get_config():
    try:
        conn = StealthDB()
        return conn.get_config()
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/config")
async def update_config(config: dict = Body(...)):
    try:
        conn = StealthDB()
        conn.config.update_one({}, {"$set": config}, upsert=True)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/maintenance")
async def toggle_maintenance(active: bool):
    try:
        conn = StealthDB()
        conn.config.update_one({}, {"$set": {"maintenance_mode": active}}, upsert=True)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
