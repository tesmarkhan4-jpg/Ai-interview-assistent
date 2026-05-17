import sys
import os

# Fix for PyInstaller path handling
def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

import time
start_time = time.time()
def log_time(label):
    print(f"[BOOT] {label}: {time.time() - start_time:.3f}s")

log_time("Core Imports")
import dotenv
log_time("Dotenv Imported")
env_path = get_resource_path(".env")
dotenv.load_dotenv(env_path, override=True)
log_time("Env Loaded")

from PyQt6.QtCore import QObject, QThread
from PyQt6.QtWidgets import QApplication
import requests

class HeartbeatThread(QThread):
    def __init__(self, email):
        super().__init__()
        self.email = email
        self._is_stopped = False

    def stop(self):
        self._is_stopped = True

    def run(self):
        from auth_manager import auth_manager
        
        while not self._is_stopped:
            try:
                requests.post(
                    f"{auth_manager.backend_url}/api/user/heartbeat",
                    json={"email": self.email, "status": "Active"},
                    timeout=5
                )
            except Exception as e:
                print(f"[Heartbeat] Active ping anomaly: {e}")
            
            # Cooperative sleep for 25 seconds
            for _ in range(25):
                if self._is_stopped:
                    break
                self.sleep(1)

class StealthController(QObject):
    def __init__(self):
        super().__init__()
        log_time("Controller Start")
        self.login_win = None
        self.dash_win = None
        self.hud_win = None
        self.heartbeat_worker = None
        
        # Check if already signed in
        log_time("Importing Auth")
        from auth_manager import auth_manager
        log_time("Auth Manager Imported")
        if auth_manager.current_user:
            print(f"[Launcher] Session detected: {auth_manager.current_user}. Skipping Login.")
            auth_manager.validate_session_async() # Verify in background
            self.start_heartbeat(auth_manager.current_user)
            self.transition_to_cv()
        else:
            self.show_login()

    def start_heartbeat(self, email):
        self.stop_heartbeat()
        if email:
            print(f"[Launcher] Engaging live heartbeat monitor for: {email}")
            self.heartbeat_worker = HeartbeatThread(email)
            self.heartbeat_worker.start()

    def stop_heartbeat(self):
        if self.heartbeat_worker:
            self.heartbeat_worker.stop()
            self.heartbeat_worker.wait()
            self.heartbeat_worker = None

    def show_login(self):
        from login_window import LoginWindow
        self.login_win = LoginWindow()
        self.login_win.login_success.connect(self.handle_login_success)
        self.login_win.show()

    def handle_login_success(self):
        from auth_manager import auth_manager
        if auth_manager.current_user:
            self.start_heartbeat(auth_manager.current_user)
        self.transition_to_cv()

    def transition_to_cv(self):
        from cv_panel import UserDashboard
        pos = self.login_win.pos() if self.login_win else None
        self.dash_win = UserDashboard()
        if pos: self.dash_win.move(pos)
        self.dash_win.cv_submitted.connect(self.transition_to_hud)
        self.dash_win.logout_requested.connect(self.handle_dashboard_logout)
        self.dash_win.show()
        if self.login_win:
            self.login_win.close()
            self.login_win = None

    def handle_dashboard_logout(self):
        self.stop_heartbeat()
        pos = self.dash_win.pos() if self.dash_win else None
        self.show_login()
        if pos and self.login_win: self.login_win.move(pos)
        if self.dash_win:
            self.dash_win.close()
            self.dash_win = None
        if self.dash_win:
            self.dash_win.close()
            self.dash_win = None

    def transition_to_hud(self, cv_text, jd_text, link_text, linkedin_url, intelligence_mode="turbo"):
        from main import StealthHUD
        pos = self.dash_win.pos() if self.dash_win else None
        # Pass full context to HUD
        self.hud_win = StealthHUD(cv_text, jd_text, link_text, linkedin_url, intelligence_mode)
        if pos: self.hud_win.move(pos)
        self.hud_win.show()
        if self.dash_win:
            self.dash_win.close()
            self.dash_win = None

if __name__ == "__main__":
    try:
        print("[Launcher] Starting StealthHUD Engine...")
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        controller = StealthController()
        print("[Launcher] Controller initialized. Entering Event Loop.")
        sys.exit(app.exec())
    except Exception as e:
        print(f"[Launcher] CRITICAL STARTUP ERROR: {e}")
        import traceback
        with open("critical_boot_error.txt", "w") as f:
            f.write(traceback.format_exc())
        input("Press Enter to close...") # Keep console open
