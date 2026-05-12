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

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QObject
import traceback
log_time("Qt Core Loaded")

def exception_hook(exctype, value, tb):
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(error_msg)
    
    # Log to file for debugging
    try:
        data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), "StealthHUD")
        os.makedirs(data_dir, exist_ok=True)
        log_path = os.path.join(data_dir, "crash_log.txt")
        with open(log_path, "w") as f:
            f.write(error_msg)
    except:
        pass

    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setText("StealthHUD - Application Error")
    msg.setDetailedText(error_msg)
    msg.exec()
    sys.exit(1)

sys.excepthook = exception_hook

# Heavy GUI imports moved inside methods for speed

class StealthController(QObject):
    def __init__(self):
        super().__init__()
        log_time("Controller Start")
        self.login_win = None
        self.dash_win = None
        self.hud_win = None
        
        # Check if already signed in
        log_time("Importing Auth")
        from auth_manager import auth_manager
        log_time("Auth Manager Imported")
        if auth_manager.current_user:
            print(f"[Launcher] Session detected: {auth_manager.current_user}. Skipping Login.")
            auth_manager.validate_session_async() # Verify in background
            self.transition_to_cv()
        else:
            self.show_login()

    def show_login(self):
        from login_window import LoginWindow
        self.login_win = LoginWindow()
        self.login_win.login_success.connect(self.transition_to_cv)
        self.login_win.show()

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
        pos = self.dash_win.pos() if self.dash_win else None
        self.show_login()
        if pos and self.login_win: self.login_win.move(pos)
        if self.dash_win:
            self.dash_win.close()
            self.dash_win = None

    def transition_to_hud(self, cv_text, jd_text, link_text, linkedin_url):
        from main import StealthHUD
        pos = self.dash_win.pos() if self.dash_win else None
        # Pass full context to HUD
        self.hud_win = StealthHUD(cv_text, jd_text, link_text, linkedin_url)
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
