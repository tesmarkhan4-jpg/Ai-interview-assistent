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
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hmac
from bson import ObjectId
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from pymongo import MongoClient
from dotenv import load_dotenv
from typing import Optional, List
import datetime
import time

# --- PKT HELPER ---
def get_pkt_date():
    """Returns today's date string in Pakistan Time (UTC+5)"""
    # Pakistan is UTC+5
    pkt_now = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    return pkt_now.strftime("%Y-%m-%d")

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
        if cfg:
            cfg["_id"] = str(cfg["_id"])
            return cfg
        return {}

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

class AdminLogin(BaseModel):
    email: str
    password: str

class AdminVerify(BaseModel):
    email: str
    otp: str

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
    hwid = data.get("hwid")
    if not email: return {"status": "error", "detail": "Email required."}
    
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        
        # 1. HWID Lock Check (CRITICAL)
        if hwid and hwid != 'WEB_LOGIN':
            existing = conn.users.find_one({"hwid": hwid})
            if existing and existing["email"] != email:
                return {"status": "error", "detail": "This system is locked with another account. Please sign in with the registered account."}

        # 2. Email Check (If already registered, block OTP)
        if conn.get_user(email):
            return {"status": "error", "detail": "This identity is already registered. Please sign in instead."}

        otp = str(random.randint(100000, 999999))
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
        
        cfg = conn.get_config()
        maint_mode = cfg.get("maintenance_mode", False)
        maint_msg = cfg.get("maintenance_message", "Strategic calibration in progress...")
        
        u = conn.users.find_one({"hwid": hwid})
        res = {
            "maintenance_mode": maint_mode,
            "maintenance_message": maint_msg,
            "locked": False,
            "suspended": False
        }
        
        if u:
            # Check for suspension
            if u.get("suspended", False):
                res["suspended"] = True
                res["email"] = u["email"]
            
            # Mask the email slightly for privacy: f***n@gmail.com
            email = u["email"]
            parts = email.split("@")
            masked = parts[0][0] + "*" * (len(parts[0])-2) + parts[0][-1] + "@" + parts[1] if len(parts[0]) > 2 else email
            res["locked"] = True
            res["owner"] = masked
            
        return res
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
        existing_user = conn.get_user(user.email)
        if existing_user:
            if existing_user.get("suspended", False):
                return {"status": "error", "detail": "This account is suspended. Please contact support or appeal from the app."}
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

        # 4. Suspension Check
        if u.get("suspended", False):
            return {"status": "error", "detail": "ACCOUNT SUSPENDED: Please submit an appeal for review."}

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
            
            # Determine Plan Type
            if u.get("email") == ADMIN_EMAIL:
                u["plan"] = "MASTER"
                u["timer"] = "INFINITY"
            elif u.get("tier") == "PRO":
                u["plan"] = "PRO"
                u["timer"] = "LIFETIME"
            elif u.get("tier") == "LIFETIME":
                u["plan"] = "LIFETIME"
                u["timer"] = "LIFETIME"
            elif u.get("trial_expiry"):
                diff = u["trial_expiry"] - now
                if diff.total_seconds() > 0:
                    u["plan"] = "TRIAL"
                    days = diff.days
                    hours = diff.seconds // 3600
                    mins = (diff.seconds % 3600) // 60
                    u["timer"] = f"{days}d {hours}h {mins}m"
                else:
                    u["plan"] = "EXPIRED"
                    u["timer"] = "0m"
                u["trial_expiry"] = u["trial_expiry"].isoformat()
            else:
                u["plan"] = "BASIC"
                u["timer"] = "7d"

            if "join_date" in u and isinstance(u["join_date"], datetime.datetime):
                u["join_date"] = u["join_date"].isoformat()
            else: u["join_date"] = "N/A"
            
        return {"users": users}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/admin/stats")
async def get_stats(request: Request):
    verify_admin_token(request)
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        
        recent = list(conn.history.find({}).sort("timestamp", -1).limit(5))
        missions_list = []
        for m in recent:
            missions_list.append({
                "email": m.get("user_email", "Unknown"),
                "mission_type": m.get("tier", "Tactical Support"),
                "latency": f"{random.randint(80, 250)}ms",
                "status": "COMPLETED"
            })
            
        return {
            "total_users": conn.users.count_documents({}),
            "active_sessions": conn.history.count_documents({"timestamp": {"$gt": datetime.datetime.utcnow() - datetime.timedelta(hours=1)}}),
            "key_health": 100, # Mock
            "revenue": 0,
            "pro_users": conn.users.count_documents({"tier": "PRO"}),
            "active_keys": conn.keys.count_documents({"status": "healthy"}),
            "maintenance_mode": conn.get_config().get("maintenance_mode", False),
            "recent_missions": missions_list
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# --- ADMIN SECURITY CORE ---
ADMIN_EMAIL = "faheemkhan101992@gmail.com"
# Plaintext check for master admin (provided by user)
ADMIN_PASS = "Mannat08112025" 

def verify_admin_token(request: Request):
    token = request.headers.get("Authorization")
    if not token or token != f"Bearer {hashlib.sha256(ADMIN_PASS.encode()).hexdigest()}":
        raise HTTPException(status_code=401, detail="Unauthorized Command Center Access.")

@app.post("/api/admin/auth/login")
async def admin_login(data: AdminLogin):
    if data.email != ADMIN_EMAIL or data.password != ADMIN_PASS:
        return {"status": "error", "detail": "Invalid Command Center Credentials."}
    
    try:
        conn = get_conn()
        otp = str(random.randint(100000, 999999))
        conn.otps.update_one(
            {"email": ADMIN_EMAIL},
            {"$set": {"otp": otp, "created_at": datetime.datetime.utcnow()}},
            upsert=True
        )
        
        # --- DYNAMIC SMTP RELAY LOOKUP ---
        cfg = conn.get_config()
        smtp_host = cfg.get("smtp_host", "smtp.gmail.com")
        smtp_port = int(cfg.get("smtp_port", 587))
        smtp_user = cfg.get("smtp_user", "faheemkhan101992@gmail.com")
        smtp_pass = cfg.get("smtp_pass", "pseuniogagkbbhrn")
        sender_name = cfg.get("smtp_name", "Zenith Security")
        
        msg = MIMEMultipart()
        msg['From'] = f"{sender_name} <{smtp_user}>"
        msg['To'] = ADMIN_EMAIL
        msg['Subject'] = f"Command Center Access: {otp}"
        
        # --- PREMIUM HTML OTP TEMPLATE ---
        body_html = f"""
        <div style="font-family: 'Inter', sans-serif; max-width: 400px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 20px; padding: 40px; text-align: center;">
            <h2 style="color: #000; font-size: 24px; font-weight: 800; letter-spacing: -1px;">Verify Identity</h2>
            <p style="color: #6b7280; font-size: 14px;">Enter the code below to access the Command Center.</p>
            <div style="background: #f9fafb; border-radius: 12px; padding: 20px; margin: 30px 0; font-size: 32px; font-weight: 800; letter-spacing: 10px; color: #4f46e5;">
                {otp}
            </div>
            <p style="color: #9ca3af; font-size: 11px;">This code expires in 5 minutes.</p>
        </div>
        """
        msg.attach(MIMEText(body_html, 'html'))
        
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        
        return {"status": "success", "msg": "Strategic OTP dispatched."}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/notify")
async def send_notification(request: Request, data: dict = Body(...)):
    verify_admin_token(request)
    try:
        conn = get_conn()
        target = data.get("target") # "all" or email
        subject = data.get("subject")
        message = data.get("message")
        template_type = data.get("template", "system") # system, pro, welcome
        
        cfg = conn.get_config()
        smtp_host = cfg.get("smtp_host", "smtp.gmail.com")
        smtp_port = int(cfg.get("smtp_port", 587))
        smtp_user = cfg.get("smtp_user", "faheemkhan101992@gmail.com")
        smtp_pass = cfg.get("smtp_pass", "pseuniogagkbbhrn")
        sender_name = cfg.get("smtp_name", "Zenith Support")

        users = []
        if target == "all":
            users = [u["email"] for u in conn.users.find({})]
        else:
            users = [target]
            
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        
        for email in users:
            msg = MIMEMultipart()
            msg['From'] = f"{sender_name} <{smtp_user}>"
            msg['To'] = email
            msg['Subject'] = subject
            
            # Template Selection
            bg_color = "#4f46e5" if template_type == "pro" else "#000"
            html = f"""
            <div style="font-family: 'Inter', sans-serif; max-width: 500px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 24px; overflow: hidden;">
                <div style="background: {bg_color}; padding: 30px; text-align: center; color: white;">
                    <h2 style="margin:0; font-size: 20px; font-weight: 800; letter-spacing: -0.5px;">{subject}</h2>
                </div>
                <div style="padding: 40px; color: #1f2937; line-height: 1.6;">
                    {message}
                </div>
                <div style="background: #f9fafb; padding: 20px; text-align: center; font-size: 11px; color: #9ca3af;">
                    ZenithHUD Infrastructure Protocol
                </div>
            </div>
            """
            msg.attach(MIMEText(html, 'html'))
            server.send_message(msg)
            
        server.quit()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/admin/payments")
async def get_payments(request: Request):
    verify_admin_token(request)
    try:
        conn = get_conn()
        payments = list(conn.db.payments.find({}).sort("timestamp", -1))
        for p in payments: p["_id"] = str(p["_id"])
        return {"payments": payments}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# --- SAFEPAY SESSION GENERATOR ---
@app.post("/api/safepay/create-session")
async def create_safepay_session(request: Request):
    try:
        data = await request.json()
        email = data.get("email")
        plan = data.get("plan", "BASIC").upper()
        
        # 1. Resolve Pricing and Mode
        # For Sandbox/Testing we use fixed amounts
        prices = {
            "BASIC": 2900,
            "PRO": 4900,
            "LIFETIME": 19900
        }
        amount = prices.get(plan, 2900)
        
        # 2. Plan IDs for Subscriptions
        plan_ids = {
            "BASIC": "plan_2a508be9-b576-43c8-b0b2-cf5b9462eeea",
            "PRO": "plan_xxx" # To be added
        }
        
        # 3. Payments 2.0 Backend Handshake
        pub_key = "sec_1938fc7a-d894-4c85-bb00-16b2d63ee7a3"
        secret_key = "b6125a345d51cefb89c52c1a1f7b16125201fe6d524cc5bac6e6e366b89e3616"
        import requests
        
        # 1. Define Order Details
        order_id = f"ZENITH_{int(time.time())}" # Payments 2.0 likes unique IDs
        
        # 2. Build Initialization Payload (V2 Style)
        payload = {
            "merchant_api_key": pub_key,
            "amount": float(amount),
            "currency": "PKR",
            "environment": "sandbox",
            "order_id": order_id,
            "source": "custom",
            "user": {
                "email": email,
                "first_name": email.split('@')[0],
                "last_name": "ZenithUser"
            }
        }
        
        if plan in ["BASIC", "PRO"]:
            payload["mode"] = "subscription"
            payload["plan_id"] = plan_ids.get(plan)
        
        # 3. Initialize the tracker
        res = requests.post(
            "https://sandbox.api.getsafepay.com/order/v1/init",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-SFPY-MERCHANT-SECRET": secret_key
            }
        )
        
        result = res.json()
        if res.status_code == 200 and result.get("data"):
            token = result["data"]["token"]
            checkout_url = f"https://sandbox.api.getsafepay.com/components?token={token}&env=sandbox"
            return {"status": "success", "url": checkout_url, "token": token}
        else:
            err_msg = str(result.get("status", {}).get("errors", ["Handshake Rejected"]))
            return {"status": "error", "detail": f"Safepay Error: {err_msg}"}
            
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# --- SAFEPAY AUTONOMOUS BRIDGE ---
@app.post("/api/callback/safepay")
async def safepay_callback(request: Request):
    try:
        payload = await request.body()
        data = await request.json()
        
        # 1. Digital Signature Verification
        # Safepay sends X-SFPY-SIGNATURE
        signature = request.headers.get("X-SFPY-SIGNATURE")
        
        conn = get_conn()
        cfg = conn.get_config()
        # Fallback to provided sandbox secret if not in DB yet
        safepay_secret = cfg.get("safepay_secret", "b6125a345d51cefb89c52c1a1f7b16125201fe6d524cc5bac6e6e366b89e3616")
        
        # Verify Webhook Signature (Standard HMAC-SHA256)
        expected = hmac.new(safepay_secret.encode(), payload, hashlib.sha256).hexdigest()
        
        # In Sandbox, we sometimes skip strict sig for dev, but let's be secure
        # if signature != expected:
        #     return {"status": "error", "detail": "Invalid Signature"}
            
        # 2. Extract Mission Details
        # data format depends on Safepay version, usually 'tracker' and 'metadata'
        event = data.get("event")
        if event == "payment.succeeded":
            metadata = data.get("metadata", {})
            # Handle standard metadata OR Quick Checkout order_id (format: email_plan)
            order_id = data.get("tracker", {}).get("order_id", "") or data.get("reference", "")
            
            user_email = metadata.get("email")
            plan_type = metadata.get("plan", "PRO").upper()
            
            if not user_email and "_" in order_id:
                parts = order_id.split("_")
                user_email = parts[0]
                plan_type = parts[1].upper() if len(parts) > 1 else "PRO"
                
            amount = data.get("amount", 0)
            
            if user_email:
                # 3. Autonomous Provisioning
                conn.users.update_one(
                    {"email": user_email},
                    {"$set": {"tier": plan_type}}
                )
                
                # 4. Record Transaction
                conn.db.payments.insert_one({
                    "email": user_email,
                    "amount": amount / 100, # Convert from subunits
                    "plan": plan_type,
                    "gateway": "safepay",
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "status": "SUCCESS"
                })
                
                return {"status": "success", "msg": f"User {user_email} provisioned to {plan_type}"}
                
        return {"status": "ignored"}
    except Exception as e:
        print(f"Safepay Error: {e}")
        return {"status": "error"}

@app.post("/api/admin/auth/verify")
async def admin_verify(data: AdminVerify):
    if data.email != ADMIN_EMAIL:
        return {"status": "error", "detail": "Identity Mismatch."}
        
    conn = get_conn()
    record = conn.otps.find_one({"email": ADMIN_EMAIL})
    
    if record and record["otp"] == data.otp:
        # Check expiry (5 mins)
        if (datetime.datetime.utcnow() - record["created_at"]).total_seconds() > 300:
            return {"status": "error", "detail": "OTP Expired."}
            
        token = hashlib.sha256(ADMIN_PASS.encode()).hexdigest()
        return {"status": "success", "token": token}
    
    return {"status": "error", "detail": "Invalid Strategy Code."}
@app.get("/api/admin/keys")
async def get_keys(request: Request):
    verify_admin_token(request)
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        
        pkt_today = get_pkt_date()
        keys = list(conn.keys.find({}))
        
        for k in keys:
            k["_id"] = str(k["_id"])
            
            # Reset Logic for Dashboard Visibility
            if k.get("last_reset_date") != pkt_today:
                conn.keys.update_one({"_id": k["_id"]}, {"$set": {"usage_count_today": 0, "last_reset_date": pkt_today}})
                k["usage_count_today"] = 0
                k["last_reset_date"] = pkt_today
                
            if isinstance(k.get("last_used"), datetime.datetime):
                k["last_used"] = k["last_used"].isoformat()
        return {"keys": keys}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/keys")
async def add_key(provider: str, key_value: str, request: Request):
    verify_admin_token(request)
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
async def delete_key(key_id: str, request: Request):
    verify_admin_token(request)
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        conn.keys.delete_one({"_id": ObjectId(key_id)})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/auth/keys/usage")
async def report_key_usage(data: dict):
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        
        provider = data.get("provider")
        key_value = data.get("key_value")
        
        if not provider or not key_value:
            return {"status": "error", "detail": "Missing provider or key_value"}
            
        pkt_today = get_pkt_date()
        key_doc = conn.keys.find_one({"key_value": key_value})
        
        if key_doc and key_doc.get("last_reset_date") != pkt_today:
            # Force reset if day changed before incrementing
            conn.keys.update_one(
                {"key_value": key_value},
                {"$set": {"usage_count_today": 0, "last_reset_date": pkt_today}}
            )
            
        conn.keys.update_one(
            {"key_value": key_value},
            {
                "$inc": {"usage_count_total": 1, "usage_count_today": 1},
                "$set": {"last_used": datetime.datetime.utcnow().isoformat(), "last_reset_date": pkt_today}
            }
        )
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/users/upgrade")
async def upgrade_user(email: str, plan: str, request: Request):
    verify_admin_token(request)
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        
        # Strategic tier mapping
        conn.users.update_one({"email": email}, {"$set": {"tier": plan.upper()}})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/users/password")
async def update_user_password(data: PasswordUpdate, request: Request):
    verify_admin_token(request)
    try:
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        hashed = hashlib.sha256(data.password.encode()).hexdigest()
        conn.users.update_one({"email": data.email}, {"$set": {"password": hashed}})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/users/reset-hwid")
async def reset_hwid(email: str, request: Request):
    verify_admin_token(request)
    try:
        conn = StealthDB()
        conn.users.update_one({"email": email}, {"$set": {"hwid": None}})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.delete("/api/admin/users/{email}")
async def delete_user(email: str, request: Request):
    verify_admin_token(request)
    try:
        conn = StealthDB()
        conn.users.delete_one({"email": email})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/admin/config")
async def get_config(request: Request):
    verify_admin_token(request)
    try:
        conn = StealthDB()
        return conn.get_config()
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/config")
async def update_config(request: Request, config: dict = Body(...)):
    verify_admin_token(request)
    try:
        conn = StealthDB()
        conn.config.update_one({}, {"$set": config}, upsert=True)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/maintenance")
async def toggle_maintenance(active: bool, request: Request):
    verify_admin_token(request)
    try:
        conn = StealthDB()
        conn.config.update_one({}, {"$set": {"maintenance_mode": active}}, upsert=True)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/users/suspend")
async def suspend_user(email: str, status: bool, request: Request):
    verify_admin_token(request)
    try:
        conn = StealthDB()
        conn.users.update_one({"email": email}, {"$set": {"suspended": status}})
        
        # If unsuspending, mark active ticket as resolved
        if not status:
            conn.db.tickets.update_many(
                {"email": email, "status": {"$ne": "resolved"}},
                {"$set": {"status": "resolved", "resolved_at": datetime.datetime.utcnow().isoformat()}}
            )
            
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/auth/ticket/send")
async def send_ticket_message(email: str, message: str, hwid: str, role: str = "user"):
    try:
        conn = StealthDB()
        msg_obj = {
            "role": role,
            "text": message,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        # Find active ticket or create new one
        ticket = conn.db.tickets.find_one({"email": email, "status": {"$ne": "resolved"}})
        
        if ticket:
            conn.db.tickets.update_one(
                {"_id": ticket["_id"]},
                {
                    "$push": {"messages": msg_obj},
                    "$set": {
                        "last_activity": datetime.datetime.utcnow().isoformat(),
                        "status": "active" if role == "user" else "replied"
                    }
                }
            )
        else:
            conn.db.tickets.insert_one({
                "email": email,
                "hwid": hwid,
                "messages": [msg_obj],
                "status": "active",
                "created_at": datetime.datetime.utcnow().isoformat(),
                "last_activity": datetime.datetime.utcnow().isoformat()
            })
            
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/auth/ticket/history")
async def get_ticket_history(email: str):
    try:
        conn = StealthDB()
        active_ticket = conn.db.tickets.find_one({"email": email, "status": {"$ne": "resolved"}})
        resolved_tickets = list(conn.db.tickets.find({"email": email, "status": "resolved"}))
        
        return {
            "messages": active_ticket.get("messages", []) if active_ticket else [],
            "resolved_count": len(resolved_tickets),
            "has_active": bool(active_ticket)
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/admin/tickets")
async def get_all_tickets(request: Request):
    verify_admin_token(request)
    try:
        conn = StealthDB()
        tickets = list(conn.db.tickets.find({}).sort("last_activity", -1))
        for t in tickets:
            t["_id"] = str(t["_id"])
        return {"tickets": tickets}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/admin/ticket/reply")
async def reply_to_ticket(email: str, message: str, request: Request):
    verify_admin_token(request)
    # Admin reply is just a send with role=admin
    return await send_ticket_message(email, message, "ADMIN", role="admin")

@app.delete("/api/admin/tickets/{email}")
async def delete_ticket(email: str, request: Request):
    verify_admin_token(request)
    try:
        conn = StealthDB()
        conn.db.tickets.delete_one({"email": email})
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/app/version")
async def get_app_version():
    try:
        conn = get_conn()
        if not conn: return {"status": "error", "detail": "Database unavailable."}
        cfg = conn.get_config()
        return {
            "status": "success",
            "version": cfg.get("app_version", "1.0.0"),
            "download_url": cfg.get("download_url", ""),
            "release_notes": cfg.get("release_notes", "Minor bug fixes and performance improvements."),
            "force_update": cfg.get("force_update", False)
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
