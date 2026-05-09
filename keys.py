import hashlib
import platform
import subprocess
import uuid
import os

def get_hwid():
    """Generates a unique hardware ID for the current system."""
    try:
        # Try to get Windows Machine GUID
        if platform.system() == "Windows":
            cmd = 'reg query "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography" /v MachineGuid'
            guid = subprocess.check_output(cmd, shell=True).decode().split()[-1]
            return hashlib.sha256(guid.encode()).hexdigest()
    except:
        pass

    # Fallback to UUID node (MAC address based)
    node = str(uuid.getnode())
    return hashlib.sha256(node.encode()).hexdigest()

def is_already_running():
    """Checks if another instance of the app is already running (simple lock file)."""
    lock_path = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), "StealthHUD", "app.lock")
    if os.path.exists(lock_path):
        try:
            # Try to delete it. If it fails, another process has it open.
            os.remove(lock_path)
        except OSError:
            return True
    
    # Create the lock
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with open(lock_path, 'w') as f:
        f.write(str(os.getpid()))
    return False
