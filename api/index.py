import os
import datetime
import requests
import certifi
import bcrypt
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

load_dotenv()

# --- DATABASE ENGINE (Inlined for reliability) ---
class StealthDB:
    def __init__(self):
        self.uri = os.getenv("MONGO_URI")
        if not self.uri:
            raise Exception("MONGO_URI missing from environment.")
        self.client = MongoClient(self.uri, server_api=ServerApi('1'), tlsCAFile=certifi.where())
        self.db = self.client["stealthhud_pro"]
        self.users = self.db["users"]
        self.keys = self.db["api_keys"]
        self.history = self.db["mission_history"]
        self.config = self.db["system_config"]

    def get_user(self, email): return self.users.find_one({"email": email})
    def create_user(self, email, password_hash, full_name):
        return self.users.insert_one({"email": email, "password": password_hash, "full_name": full_name, "tier": "TRIAL", "joined_at": datetime.datetime.utcnow(), "status": "active"})
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

# --- API CORE ---
app = FastAPI(title="StealthHUD PRO Backend")
db = None

def get_db():
    global db
    if db is None: db = StealthDB()
    return db

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ProxyRequest(BaseModel):
    email: str
    prompt: str
    provider: str = "groq"

# --- AUTH ---
@app.post("/auth/register")
async def register(user: UserRegister):
    conn = get_db()
    if conn.get_user(user.email): raise HTTPException(status_code=400, detail="Identity already registered.")
    hashed = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
    conn.create_user(user.email, hashed, user.full_name)
    return {"status": "success"}

@app.post("/auth/login")
async def login(user: UserLogin):
    conn = get_db()
    db_user = conn.get_user(user.email)
    if not db_user or not bcrypt.checkpw(user.password.encode('utf-8'), db_user["password"]):
        raise HTTPException(status_code=401, detail="Strategic Identity Mismatch.")
    return {"status": "success", "user": {"email": db_user["email"], "tier": db_user["tier"], "full_name": db_user["full_name"]}}

# --- PROXY ---
@app.post("/api/v1/proxy")
async def ai_proxy(req: ProxyRequest):
    conn = get_db()
    if conn.get_config().get("maintenance_mode", False): raise HTTPException(status_code=503, detail="Strategic System Maintenance.")
    key = conn.get_pooled_key(req.provider)
    if not key: raise HTTPException(status_code=503, detail="Strategic Key Pool Exhausted.")
    try:
        if req.provider == "groq":
            resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": req.prompt}]}, timeout=15)
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
@app.get("/admin/stats")
async def get_stats():
    conn = get_db()
    return {"total_users": conn.users.count_documents({}), "active_sessions": conn.users.count_documents({"tier": "PRO"}), "key_health": 98.2, "maintenance_mode": conn.get_config().get("maintenance_mode", False)}

@app.get("/admin/users")
async def get_users():
    conn = get_db()
    users = conn.get_all_users()
    for u in users: u["_id"] = str(u["_id"])
    return {"users": users}

@app.get("/admin/keys")
async def get_keys():
    conn = get_db()
    keys = conn.get_all_keys()
    for k in keys: k["_id"] = str(k["_id"])
    return {"keys": keys}

@app.delete("/admin/keys/{key_id}")
async def remove_key(key_id: str):
    conn = get_db()
    conn.remove_key(key_id)
    return {"status": "success"}

@app.post("/admin/maintenance")
async def set_maintenance(active: bool):
    conn = get_db()
    conn.set_maintenance(active)
    return {"status": "success", "maintenance_mode": active}

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return {"status": "error", "detail": str(exc)}
