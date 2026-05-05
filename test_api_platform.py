import requests
url = "https://stealth-hud-platform.vercel.app/api/auth/login"
data = {"email": "tesmarkhan4@gmail.com", "password": "password123"}
try:
    res = requests.post(url, json=data, timeout=10)
    print(f"Status: {res.status_code}")
    print(f"Body: {res.text}")
except Exception as e:
    print(f"Error: {e}")
