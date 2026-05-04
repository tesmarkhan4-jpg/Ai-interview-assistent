import os
import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv('MONGO_URI'))
db = client['stealth_hud']

gemini_keys = [k.strip() for k in os.getenv('GEMINI_API_KEYS', '').split(',') if k.strip()]
groq_keys = [k.strip() for k in os.getenv('GROQ_API_KEYS', '').split(',') if k.strip()]
deepgram_keys = [k.strip() for k in os.getenv('DEEPGRAM_API_KEYS', '').split(',') if k.strip()]

inserted = 0
updated = 0

def add_keys(provider, keys):
    global inserted, updated
    for k in keys:
        if not db.keys.find_one({'key_value': k}):
            db.keys.insert_one({'provider': provider, 'key_value': k, 'status': 'healthy', 'usage_count': 0, 'last_used': datetime.datetime.utcnow()})
            inserted += 1
        else:
            db.keys.update_one({'key_value': k}, {'$set': {'status': 'healthy', 'last_used': datetime.datetime.utcnow()}})
            updated += 1

add_keys('gemini', gemini_keys)
add_keys('groq', groq_keys)
add_keys('deepgram', deepgram_keys)

print(f'Successfully processed keys. Inserted {inserted} new keys, updated {updated} existing keys.')
