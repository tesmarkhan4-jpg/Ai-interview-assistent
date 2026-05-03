import os
from database import StealthDB
from dotenv import load_dotenv

load_dotenv()

def migrate():
    db = StealthDB()
    
    # Get keys from .env
    gemini = os.getenv("GEMINI_API_KEYS", "").split(",")
    groq = os.getenv("GROQ_API_KEYS", "").split(",")
    deepgram = os.getenv("DEEPGRAM_API_KEYS", "").split(",")
    
    # Push to DB
    counts = {"gemini": 0, "groq": 0, "deepgram": 0}
    
    for key in gemini:
        if key.strip():
            db.add_key("gemini", key.strip())
            counts["gemini"] += 1
            
    for key in groq:
        if key.strip():
            db.add_key("groq", key.strip())
            counts["groq"] += 1
            
    for key in deepgram:
        if key.strip():
            db.add_key("deepgram", key.strip())
            counts["deepgram"] += 1
            
    print(f"Migration Complete: {counts}")

if __name__ == "__main__":
    migrate()
