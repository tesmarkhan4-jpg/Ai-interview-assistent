import subprocess
import os
import shutil
import sys

def build_app():
    print("🚀 Starting Build Process for StealthHUD...")
    
    # 1. Clean previous builds
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
        
    # 2. Run PyInstaller
    print("📦 Bundling application (this may take a minute)...")
    try:
        # Using 'python -m PyInstaller' is more reliable than calling 'pyinstaller' directly
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "StealthHUD.spec"], check=True)
        print("✅ Build Successful! You can find the app in the 'dist/StealthHUD' folder.")
        
        # 3. Create .env if it doesn't exist in dist
        env_dest = os.path.join("dist", "StealthHUD", ".env")
        if not os.path.exists(env_dest):
            shutil.copy(".env.example", env_dest)
            print("📝 Created default .env in the dist folder.")

    except subprocess.CalledProcessError as e:
        print(f"❌ Build Failed: {e}")
    except FileNotFoundError:
        print("❌ Error: PyInstaller not found. Please run 'pip install pyinstaller'.")

if __name__ == "__main__":
    # Ensure pyinstaller is installed
    subprocess.run(["pip", "install", "pyinstaller"], check=True)
    build_app()
