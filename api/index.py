import os
import requests
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from database import StealthDB
from passlib.context import CryptContext

app = FastAPI(title="StealthHUD PRO Backend")
db = None

def get_db():
    global db
    if db is None:
        db = StealthDB()
    return db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
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
    provider: str = "groq" # "groq" or "gemini"

# Auth
@app.post("/auth/register")
async def register(user: UserRegister):
    db = get_db()
    if db.get_user(user.email):
        raise HTTPException(status_code=400, detail="Identity already registered.")
    
    hashed = pwd_context.hash(user.password)
    db.create_user(user.email, hashed, user.full_name)
    return {"status": "success", "message": "Deployment Initialized."}

@app.post("/auth/login")
async def login(user: UserLogin):
    db = get_db()
    db_user = db.get_user(user.email)
    if not db_user or not pwd_context.verify(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Strategic Identity Mismatch.")
    
    return {
        "status": "success",
        "user": {
            "email": db_user["email"],
            "tier": db_user["tier"],
            "full_name": db_user["full_name"]
        }
    }

# AI Proxy (Secure Key Rotation)
@app.post("/api/v1/proxy")
async def ai_proxy(req: ProxyRequest):
    db = get_db()
    if db.get_config().get("maintenance_mode", False):
        raise HTTPException(status_code=503, detail="Strategic System Maintenance in Progress.")

    key = db.get_pooled_key(req.provider)
    if not key:
        raise HTTPException(status_code=503, detail="Strategic Key Pool Exhausted.")
    
    try:
        if req.provider == "groq":
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": req.prompt}]
                },
                timeout=15
            )
            data = resp.json()
            result = data['choices'][0]['message']['content']
        else: # Gemini
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
            resp = requests.post(url, json={"contents": [{"parts": [{"text": req.prompt}]}]})
            data = resp.json()
            result = data['candidates'][0]['content']['parts'][0]['text']
        
        db.log_mission(req.email, req.prompt, result)
        return {"result": result}
    
    except Exception as e:
        db.report_key_failure(key, str(e))
        raise HTTPException(status_code=500, detail="Intelligence Stream Interrupted.")

@app.get("/admin/stats")
async def get_stats():
    db = get_db()
    return {
        "total_users": db.users.count_documents({}),
        "active_sessions": db.users.count_documents({"tier": "PRO"}),
        "key_health": 98.2,
        "maintenance_mode": db.get_config().get("maintenance_mode", False)
    }

@app.get("/admin/users")
async def get_users():
    db = get_db()
    users = db.get_all_users()
    for u in users: u["_id"] = str(u["_id"])
    return {"users": users}

@app.get("/admin/keys")
async def get_keys():
    db = get_db()
    keys = db.get_all_keys()
    for k in keys: k["_id"] = str(k["_id"])
    return {"keys": keys}

@app.post("/admin/keys/add")
async def add_key(provider: str, value: str):
    db = get_db()
    db.add_key(provider, value)
    return {"status": "success"}

@app.delete("/admin/keys/{key_id}")
async def remove_key(key_id: str):
    db = get_db()
    db.remove_key(key_id)
    return {"status": "success"}

@app.post("/admin/maintenance")
async def set_maintenance(active: bool):
    db = get_db()
    db.set_maintenance(active)
    return {"status": "success", "maintenance_mode": active}

# Global Error Handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return {
        "status": "error",
        "detail": str(exc),
        "trace": "Strategic infrastructure error reported."
    }
