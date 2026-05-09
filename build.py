import subprocess
import os
import shutil
import sys

def build_app():
    print(" Starting Build Process for StealthHUD...")
    
    # 1. Clean previous builds
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
        
    # 2. Run PyInstaller
    print(" Bundling application (this may take a minute)...")
    try:
        # Using 'python -m PyInstaller' is more reliable than calling 'pyinstaller' directly
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "StealthHUD.spec"], check=True)
        print(" Build Successful! You can find the app in the 'dist/StealthHUD' folder.")
        
        # 3. Copy actual .env to dist folder
        if os.path.exists(".env"):
            shutil.copy(".env", "dist/SystemHost/.env")
            print(" Synced production .env to the dist/SystemHost folder.")
        else:
            shutil.copy(".env.example", "dist/SystemHost/.env")
            print(" Created default .env in the dist/SystemHost folder.")

    except subprocess.CalledProcessError as e:
        print(f" Build Failed: {e}")
    except FileNotFoundError:
        print(" Error: PyInstaller not found. Please run 'pip install pyinstaller'.")

if __name__ == "__main__":
    # Ensure all requirements are installed
    print(" Installing dependencies...")
    deps = [
        "pyinstaller", "PyQt6", "groq", "google-generativeai", "google-genai", "mss", 
        "win32mica", "keyboard", "soundcard", "deepgram-sdk", "python-dotenv", 
        "requests", "bcrypt", "pymongo", "dnspython", "numpy", "pillow"
    ]
    subprocess.run(["pip", "install"] + deps, check=True)
    build_app()
