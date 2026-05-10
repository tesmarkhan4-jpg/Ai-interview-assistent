import pymongo
from urllib.parse import quote_plus

# Connection String
USER = "admin"
PASS = "admin@013970"
HOST = "ai-a.fqixdrd.mongodb.net"

MONGO_URI = f"mongodb+srv://{USER}:{quote_plus(PASS)}@{HOST}/?appName=Ai-A"

def fetch_smtp():
    client = pymongo.MongoClient(MONGO_URI)
    db = client.zenith_pro
    config = db.system_config.find_one({})
    
    if config:
        print("--- SMTP CONFIG FOUND ---")
        for key in ['SMTP_USER', 'SMTP_PASS', 'SMTP_HOST', 'SMTP_PORT']:
            val = config.get(key, 'NOT SET')
            print(f"{key}: {val}")
    else:
        print("No configuration found in zenith_pro.system_config.")

if __name__ == "__main__":
    fetch_smtp()
