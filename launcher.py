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

# Load .env early
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

import dotenv
env_path = os.path.join(application_path, ".env")
dotenv.load_dotenv(env_path, override=True)

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QObject
import traceback

def exception_hook(exctype, value, tb):
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    print(error_msg)
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setText("StealthHUD - Application Error")
    msg.setDetailedText(error_msg)
    msg.exec()
    sys.exit(1)

sys.excepthook = exception_hook

from login_window import LoginWindow
from cv_panel import UserDashboard
from main import StealthHUD

class StealthController(QObject):
    def __init__(self):
        super().__init__()
        self.login_win = None
        self.dash_win = None
        self.hud_win = None
        self.show_login()

    def show_login(self):
        self.login_win = LoginWindow()
        self.login_win.login_success.connect(self.transition_to_cv)
        self.login_win.show()

    def transition_to_cv(self):
        pos = self.login_win.pos() if self.login_win else None
        self.dash_win = UserDashboard()
        if pos: self.dash_win.move(pos)
        self.dash_win.cv_submitted.connect(self.transition_to_hud)
        self.dash_win.show()
        if self.login_win:
            self.login_win.close()
            self.login_win = None

    def transition_to_hud(self, cv_text):
        pos = self.dash_win.pos() if self.dash_win else None
        # We pass cv_text to the HUD which now synchronizes it with the AI Engine.
        self.hud_win = StealthHUD(cv_text)
        if pos: self.hud_win.move(pos)
        self.hud_win.show()
        if self.dash_win:
            self.dash_win.close()
            self.dash_win = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    controller = StealthController()
    sys.exit(app.exec())
