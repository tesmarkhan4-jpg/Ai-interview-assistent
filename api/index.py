import os
import datetime
import requests
import certifi
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from pymongo import MongoClient
from dotenv import load_dotenv
import hashlib
import uuid
import traceback
# load_dotenv() - Removed for Vercel native stability

# --- DATABASE ENGINE ---
class StealthDB:
    def __init__(self):
        self.uri = os.getenv("MONGO_URI") or "mongodb+srv://admin:mannat08112025@cluster0.r7zajqb.mongodb.net/?appName=Cluster0"
        try:
            # High-compatibility connection for serverless
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
            self.db = self.client['stealthhud_pro']
            self.users = self.db['users']
            self.keys = self.db['api_keys']
            self.history = self.db["mission_history"]
            self.config = self.db['system_config']
            print("DB Engine: Link Established.")
        except Exception as e:
            print(f"DB Engine: Link Failure - {e}")
            raise e

    def get_user(self, email): return self.users.find_one({"email": email})
    def create_user(self, email, password_hash, full_name, hwid=None):
        # 7-day Trial Expiry
        expiry = datetime.datetime.utcnow() + datetime.timedelta(days=7)
        return self.users.insert_one({
            "email": email, 
            "password": password_hash, 
            "full_name": full_name, 
            "hwid": hwid,
            "tier": "TRIAL", 
            "trial_expiry": expiry,
            "joined_at": datetime.datetime.utcnow(), 
            "status": "active"
        })
    def add_key(self, provider, key_value):
        return self.keys.insert_one({"provider": provider, "key_value": key_value, "status": "healthy", "usage_count": 0, "last_used": datetime.datetime.utcnow()})
    def get_pooled_key(self, provider):
        key_doc = self.keys.find_one({"provider": provider, "status": "healthy"}, sort=[("last_used", 1)])
        if key_doc:
            self.keys.update_one({"_id": key_doc["_id"]}, {"$set": {"last_used": datetime.datetime.utcnow()}, "$inc": {"usage_count": 1}})
            return key_doc["key_value"]
        return None
    def report_key_failure(self, key_value, error): self.keys.update_one({"key_value": key_value}, {"$set": {"status": "exhausted", "error": str(error)}})
    def log_mission(self, email, prompt, response): self.history.insert_one({"email": email, "prompt": prompt, "response": response, "timestamp": datetime.datetime.utcnow()})
    def get_history(self, email): return list(self.history.find({"email": email}).sort("timestamp", -1).limit(20))
    def get_config(self): return self.config.find_one({"type": "global"}) or {"maintenance_mode": False}
    def set_maintenance(self, status): self.config.update_one({"type": "global"}, {"$set": {"maintenance_mode": status}}, upsert=True)
    def get_all_keys(self): return list(self.keys.find({}))
    def remove_key(self, key_id): 
        from bson import ObjectId
        return self.keys.delete_one({"_id": ObjectId(key_id)})
    def get_all_users(self): return list(self.users.find({}).sort("joined_at", -1).limit(50))
    def update_config(self, data):
        return self.config.update_one({"type": "global"}, {"$set": data}, upsert=True)

# --- EMAIL SYSTEM ---
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class MailService:
    @staticmethod
    def send_email(to_email, subject, html_content):
        db = StealthDB()
        cfg = db.get_config()
        smtp_host = cfg.get("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(cfg.get("SMTP_PORT", 587))
        smtp_user = cfg.get("SMTP_USER")
        smtp_pass = cfg.get("SMTP_PASS")
        
        if not smtp_user or not smtp_pass:
            print("[MAIL] SMTP Credentials missing. Email suppressed.")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = f"{cfg.get('branding', 'StealthHUD')} Support <{smtp_user}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(html_content, 'html'))

            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"[MAIL] Failed: {e}")
            return False

    @staticmethod
    def get_otp_template(otp, user_name):
        return f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 40px; background: #f8fafc; border-radius: 20px;">
            <h2 style="color: #6366f1;">Identity Verification</h2>
            <p>Hello <b>{user_name}</b>,</p>
            <p>Your one-time pass-code for StealthHUD PRO is:</p>
            <div style="font-size: 32px; font-weight: 800; letter-spacing: 5px; color: #1e293b; margin: 30px 0;">{otp}</div>
            <p style="font-size: 12px; color: #64748b;">If you did not request this, please ignore this email.</p>
        </div>
        """

    @staticmethod
    def get_maintenance_template(message):
        return f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 40px; background: #0f172a; color: white; border-radius: 20px; text-align: center;">
            <h1 style="color: #fbbf24;">⚠️ System Maintenance</h1>
            <p style="font-size: 18px;">{message or "We are currently performing a scheduled upgrade."}</p>
            <hr style="border-color: rgba(255,255,255,0.1); margin: 30px 0;">
            <p style="font-size: 14px; color: #94a3b8;">Our strategic intelligence stream is being calibrated. We will be back online shortly.</p>
        </div>
        """

# --- API CORE ---
app = FastAPI(title="StealthHUD PRO Backend")
db = None

def get_db():
    try:
        return StealthDB()
    except Exception as e:
        # Pass the error through for diagnostics
        raise e

def hash_password(password: str):
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ":" + salt

def verify_password(hashed_password, user_password):
    try:
        password, salt = hashed_password.split(':')
        return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()
    except:
        return False

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    hwid: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    hwid: str

class ProxyRequest(BaseModel):
    email: str
    prompt: str
    provider: str = "groq"

@app.get("/api/ping")
async def ping():
    return {"status": "online", "message": "Strategic systems operational."}

# --- AUTH ---
@app.post("/api/auth/register")
async def register(user: UserRegister):
    try:
        conn = StealthDB()
        # Check if HWID is already linked to another trial account
        existing_hwid = conn.users.find_one({"hwid": user.hwid})
        if existing_hwid:
            raise HTTPException(status_code=403, detail="System already registered. Please login with original identity.")
            
        if conn.get_user(user.email): raise HTTPException(status_code=400, detail="Identity already registered.")
        hashed = hash_password(user.password)
        conn.create_user(user.email, hashed, user.full_name, hwid=user.hwid)
        return {"status": "success"}
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

@app.post("/api/auth/login")
async def login(user: UserLogin):
    try:
        conn = StealthDB()
        db_user = conn.get_user(user.email)
        if not db_user or not verify_password(db_user["password"], user.password):
            raise HTTPException(status_code=401, detail="Strategic Identity Mismatch.")
            
        # Verify HWID binding
        if db_user.get("hwid") and db_user["hwid"] != user.hwid:
            if db_user.get("tier") == "TRIAL":
                raise HTTPException(status_code=403, detail="Identity locked to another system. Multiple trials prohibited.")
        
        return {
            "status": "success", 
            "user": {
                "email": db_user["email"], 
                "tier": db_user.get("tier", "TRIAL"), 
                "full_name": db_user["full_name"],
                "trial_expiry": db_user.get("trial_expiry", datetime.datetime.utcnow()).isoformat(),
                "server_time": datetime.datetime.utcnow().isoformat()
            }
        }
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

# --- AUTOMATED PAYMENTS (LEMONSQUEEZY & STRIPE) ---
@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    # (Existing stripe logic)
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    conn = get_db()
    config = conn.get_config()
    webhook_secret = config.get("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        data = await request.json()
        if data.get("type") == "checkout.session.completed":
            email = data.get("data", {}).get("object", {}).get("customer_details", {}).get("email")
            if email: conn.users.update_one({"email": email}, {"$set": {"tier": "PRO"}})
        return {"status": "success"}
    return {"status": "success"}

@app.post("/api/webhook/lemonsqueezy")
async def lemonsqueezy_webhook(request: Request):
    payload = await request.body()
    # Simplified validation for manual/dev config
    import json
    data = json.loads(payload)
    event_name = data.get("meta", {}).get("event_name")
    
    if event_name == "order_created":
        email = data.get("data", {}).get("attributes", {}).get("user_email")
        if email:
            conn = get_db()
            conn.users.update_one({"email": email}, {"$set": {"tier": "PRO"}})
            return {"status": "success", "message": "LemonSqueezy Upgrade Complete"}
    
    return {"status": "ignored"}

# --- PROXY ---
@app.post("/api/v1/ai")
async def get_ai_response(req: ProxyRequest):
    conn = get_db()
    cfg = conn.get_config()
    if cfg.get("maintenance_mode", False):
        msg = cfg.get("maintenance_message", "Strategic System Maintenance in Progress. Please try again later.")
        raise HTTPException(status_code=503, detail=msg)
    
    key = conn.get_pooled_key(req.provider)
    if not key: raise HTTPException(status_code=503, detail="Strategic Key Pool Exhausted.")
    try:
        if req.provider == "groq":
            resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": req.prompt}]}, timeout=10)
            result = resp.json()['choices'][0]['message']['content']
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
            resp = requests.post(url, json={"contents": [{"parts": [{"text": req.prompt}]}]})
            result = resp.json()['candidates'][0]['content']['parts'][0]['text']
        conn.log_mission(req.email, req.prompt, result)
        return {"result": result}
    except Exception as e:
        conn.report_key_failure(key, str(e))
        raise HTTPException(status_code=500, detail="Intelligence Stream Interrupted.")

# --- ADMIN ---
@app.get("/api/v1/history")
async def get_history(email: str):
    conn = get_db()
    history = conn.get_history(email)
    for h in history: h["_id"] = str(h["_id"])
    return {"history": history}

@app.get("/api/admin/stats")
async def get_stats():
    try:
        conn = StealthDB()
        total = conn.users.count_documents({})
        pro = conn.users.count_documents({"tier": "PRO"})
        trial = conn.users.count_documents({"tier": "TRIAL"})
        return {
            "total_users": total or 0, 
            "pro_users": pro or 0, 
            "trial_users": trial or 0,
            "active_sessions": conn.history.count_documents({"timestamp": {"$gt": datetime.datetime.utcnow() - datetime.timedelta(hours=1)}}),
            "revenue": pro * 49, # Simplified MRR calculation
            "key_health": 100, 
            "maintenance_mode": conn.get_config().get("maintenance_mode", False)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/users")
async def get_users():
    try:
        conn = StealthDB()
        users = conn.get_all_users()
        now = datetime.datetime.utcnow()
        for u in users: 
            u["_id"] = str(u["_id"])
            # Calculate Timers
            if u.get("trial_expiry"):
                diff = u["trial_expiry"] - now
                u["trial_timer"] = f"{max(0, diff.days)}d {max(0, diff.seconds // 3600)}h"
                u["trial_expiry"] = u["trial_expiry"].isoformat()
            else:
                u["trial_timer"] = "EXPIRED"

            if u.get("tier") == "PRO" and u.get("sub_expiry"):
                diff = u["sub_expiry"] - now
                u["sub_timer"] = f"{max(0, diff.days)}d {max(0, diff.seconds // 3600)}h"
            else:
                u["sub_timer"] = "N/A"

            if "joined_at" in u and isinstance(u["joined_at"], datetime.datetime):
                u["joined_at"] = u["joined_at"].isoformat()
        return {"users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/users")
async def admin_create_user(req: UserRegister):
    conn = get_db()
    if conn.get_user(req.email):
        raise HTTPException(status_code=400, detail="User already exists")
    conn.create_user(req.email, hash_password(req.password), req.full_name, req.hwid)
    return {"status": "success"}

@app.post("/api/admin/users/upgrade")
async def upgrade_user(email: str, tier: str = "PRO"):
    conn = get_db()
    expiry = datetime.datetime.utcnow() + datetime.timedelta(days=30)
    conn.users.update_one({"email": email}, {"$set": {"tier": tier, "sub_expiry": expiry}})
    return {"status": "success"}

@app.delete("/api/admin/users/{email}")
async def delete_user(email: str):
    conn = get_db()
    conn.users.delete_one({"email": email})
    return {"status": "success"}

@app.get("/api/admin/keys")
async def get_keys():
    conn = get_db()
    keys = conn.get_all_keys()
    for k in keys: k["_id"] = str(k["_id"])
    return {"keys": keys}

@app.delete("/api/admin/keys/{key_id}")
async def remove_key(key_id: str):
    conn = get_db()
    conn.remove_key(key_id)
    return {"status": "success"}

@app.post("/api/admin/keys")
async def add_key(provider: str, key_value: str):
    try:
        conn = StealthDB()
        conn.add_key(provider, key_value)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/users/{email}")
async def delete_user(email: str):
    try:
        conn = StealthDB()
        conn.users.delete_one({"email": email})
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/maintenance")
async def set_maintenance(active: bool):
    conn = get_db()
    conn.set_maintenance(active)
    return {"status": "success", "maintenance_mode": active}

@app.post("/api/auth/upgrade")
async def upgrade_user(email: str):
    try:
        conn = StealthDB()
        conn.users.update_one({"email": email}, {"$set": {"tier": "PRO"}})
        return {"status": "success", "message": "Identity Upgraded to PRO tier."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/config")
async def update_global_config(request: Request):
    data = await request.json()
    conn = get_db()
    conn.update_config(data)
    return {"status": "success"}

@app.get("/api/admin/config")
async def get_global_config():
    conn = get_db()
    cfg = conn.get_config()
    if "_id" in cfg: cfg["_id"] = str(cfg["_id"])
    return cfg

@app.get("/{full_path:path}")
async def catch_all(request: Request, full_path: str):
    return {
        "status": "diagnostic",
        "path_param": full_path,
        "scope_path": request.scope.get('path'),
        "message": "Strategic routing captured."
    }

# Global Error Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_trace = traceback.format_exc()
    print(f"CRITICAL ERROR: {str(exc)}\n{error_trace}")
    return {
        "status": "error",
        "detail": str(exc),
        "trace": error_trace
    }
