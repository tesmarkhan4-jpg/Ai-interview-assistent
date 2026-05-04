import requests
url = "https://stealth-hud-pro.vercel.app/api/ping"
try:
    res = requests.get(url, timeout=10)
    print(f"Status: {res.status_code}")
    print(f"Body: {res.text}")
except Exception as e:
    print(f"Error: {e}")
