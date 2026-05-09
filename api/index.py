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
        self.uri = os.getenv("MONGO_URI")
        if not self.uri:
            raise Exception("MONGO_URI missing from environment.")
        try:
            # High-compatibility connection for serverless
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
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

# --- AUTOMATED PAYMENTS (STRIPE WEBHOOK) ---
@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    conn = get_db()
    config = conn.get_config()
    webhook_secret = config.get("STRIPE_WEBHOOK_SECRET")
    
    if not webhook_secret:
        # Fallback for dev/manual mode
        data = await request.json()
        if data.get("type") == "checkout.session.completed":
            session = data.get("data", {}).get("object", {})
            email = session.get("customer_details", {}).get("email")
            if email:
                conn.users.update_one({"email": email}, {"$set": {"tier": "PRO"}})
                return {"status": "success", "message": f"Auto-Upgraded {email}"}
        return {"status": "ignored"}

    import stripe
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session["customer_details"]["email"]
        conn.users.update_one({"email": email}, {"$set": {"tier": "PRO"}})
        
    return {"status": "success"}

# --- PROXY ---
@app.post("/v1/ai")
async def get_ai_response(req: ProxyRequest):
    conn = get_db()
    if conn.get_config().get("maintenance_mode", False): raise HTTPException(status_code=503, detail="Strategic System Maintenance.")
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
@app.get("/v1/history")
async def get_history(email: str):
    conn = get_db()
    history = conn.get_history(email)
    for h in history: h["_id"] = str(h["_id"])
    return {"history": history}

@app.get("/admin/stats")
async def get_stats():
    try:
        conn = StealthDB()
        total = conn.users.count_documents({})
        pro = conn.users.count_documents({"tier": "PRO"})
        trial = conn.users.count_documents({"tier": "TRIAL"})
        return {
            "total_users": total, 
            "pro_users": pro, 
            "trial_users": trial,
            "key_health": 98.2, 
            "maintenance_mode": conn.get_config().get("maintenance_mode", False)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/users")
async def get_users():
    try:
        conn = StealthDB()
        users = conn.get_all_users()
        for u in users: 
            u["_id"] = str(u["_id"])
            if "trial_expiry" in u and isinstance(u["trial_expiry"], datetime.datetime):
                u["trial_expiry"] = u["trial_expiry"].isoformat()
            if "joined_at" in u and isinstance(u["joined_at"], datetime.datetime):
                u["joined_at"] = u["joined_at"].isoformat()
        return {"users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/keys")
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

@app.post("/admin/keys")
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

@app.post("/admin/config")
async def update_global_config(request: Request):
    data = await request.json()
    conn = get_db()
    conn.update_config(data)
    return {"status": "success"}

@app.get("/admin/config")
async def get_global_config():
    conn = get_db()
    return conn.get_config()

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
