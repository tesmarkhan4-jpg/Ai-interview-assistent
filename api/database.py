import os
import datetime
import certifi
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

load_dotenv()

class StealthDB:
    def __init__(self):
        self.uri = os.getenv("MONGO_URI")
        try:
            self.client = MongoClient(
                self.uri, 
                server_api=ServerApi('1'),
                tlsCAFile=certifi.where()
            )
            self.db = self.client["stealthhud_pro"]
            self.users = self.db["users"]
            self.keys = self.db["api_keys"]
            self.history = self.db["mission_history"]
            self.config = self.db["system_config"]
            
            # Ensure indexes
            self.users.create_index("email", unique=True)
            print("[DB] Connected to MongoDB Atlas")
        except Exception as e:
            print(f"[DB] Connection Error: {e}")

    # User Management
    def get_user(self, email):
        return self.users.find_one({"email": email})

    def create_user(self, email, password_hash, full_name):
        user_data = {
            "email": email,
            "password": password_hash,
            "full_name": full_name,
            "tier": "TRIAL",
            "joined_at": datetime.datetime.utcnow(),
            "status": "active"
        }
        return self.users.insert_one(user_data)

    def update_subscription(self, email, tier):
        return self.users.update_one({"email": email}, {"$set": {"tier": tier}})

    # Key Pool & Rotation
    def add_key(self, provider, key_value):
        key_doc = {
            "provider": provider,
            "key_value": key_value,
            "status": "healthy",
            "usage_count": 0,
            "last_used": datetime.datetime.utcnow()
        }
        return self.keys.insert_one(key_doc)

    def get_pooled_key(self, provider):
        """Returns the healthiest key for the provider (round-robin)."""
        key_doc = self.keys.find_one(
            {"provider": provider, "status": "healthy"},
            sort=[("last_used", 1)]
        )
        if key_doc:
            self.keys.update_one(
                {"_id": key_doc["_id"]}, 
                {"$set": {"last_used": datetime.datetime.utcnow()}, "$inc": {"usage_count": 1}}
            )
            return key_doc["key_value"]
        return None

    def report_key_failure(self, key_value, error_msg):
        self.keys.update_one(
            {"key_value": key_value},
            {"$set": {"status": "exhausted", "error": error_msg}}
        )

    # Mission History
    def log_mission(self, email, prompt, response, type="text"):
        log = {
            "email": email,
            "prompt": prompt,
            "response": response,
            "type": type,
            "timestamp": datetime.datetime.utcnow()
        }
        return self.history.insert_one(log)

    def get_history(self, email, limit=20):
        return list(self.history.find({"email": email}).sort("timestamp", -1).limit(limit))

    # System Config
    def get_config(self):
        return self.config.find_one({"type": "global"}) or {"maintenance_mode": False}

    def set_maintenance(self, status):
        self.config.update_one({"type": "global"}, {"$set": {"maintenance_mode": status}}, upsert=True)

    # Admin Helpers
    def get_all_keys(self):
        return list(self.keys.find({}))

    def remove_key(self, key_id):
        from bson import ObjectId
        return self.keys.delete_one({"_id": ObjectId(key_id)})

    def get_all_users(self, limit=50):
        return list(self.users.find({}).sort("joined_at", -1).limit(limit))
