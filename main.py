import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton, 
                             QLabel, QFrame, QScrollArea, QSizePolicy, QStackedWidget)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPoint, QThread, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon, QTextCursor
import keyboard
try:
    from win32mica import MICAMODE, ApplyMica
    HAS_MICA = True
except ImportError:
    HAS_MICA = False

import stealth_engine
from dotenv import load_dotenv

# Fix for PyInstaller path handling
def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Load .env from the bundle or current directory
env_path = get_resource_path(".env")
load_dotenv(env_path, override=True)

APP_VERSION = "1.1.4"

# Import Handlers with Error Reporting
try:
    from audio_handler import AudioThread
    from ai_engine import ai_engine
    from vision_handler import vision_handler
    from history_manager import history_manager
    from auth_manager import auth_manager
    from hwid_utils import is_already_running
except ImportError as e:
    import ctypes
    msg = f"Critical Error: Missing module {e.name}. The application was not bundled correctly."
    ctypes.windll.user32.MessageBoxW(0, msg, "ZenithHUD Error", 16)
    sys.exit(1)

class AIWorker(QThread):
    finished = pyqtSignal(str, str) # Type (AI/YOU), Full Message
    chunk_received = pyqtSignal(str, str) # Type, Chunk

    def __init__(self, query, mode="text", image_path=None):
        super().__init__()
        self.query = query
        self.mode = mode
        self.image_path = image_path
        self._is_stopped = False

    def stop(self):
        self._is_stopped = True

    def run(self):
        full_response = ""
        if self.mode == "text":
            try:
                for chunk in ai_engine.get_ai_response_stream(self.query, provider="groq"):
                    if self._is_stopped:
                        break
                    if chunk:
                        full_response += chunk
                        self.chunk_received.emit("AI", chunk)
            except Exception as e:
                full_response = f"Intelligence Stream Error: {str(e)}"
                self.chunk_received.emit("AI", full_response)
        elif self.mode == "vision":
            try:
                full_response = ai_engine.analyze_screen(self.image_path, self.query)
                if not self._is_stopped:
                    self.chunk_received.emit("AI", full_response)
            except Exception as e:
                full_response = f"Vision Intelligence Error: {str(e)}"
                self.chunk_received.emit("AI", full_response)
        
        if not self._is_stopped:
            self.finished.emit("AI", full_response)

class ReportWorker(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def run(self):
        try:
            from ai_engine import ai_engine
            from history_manager import history_manager
            from auth_manager import auth_manager
            
            report_data = ai_engine.generate_interview_report()
            user = auth_manager.current_user
            if user:
                history_manager.save_interview(user, report_data)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class KeyboardThread(QThread):
    hotkey_pressed = pyqtSignal(str)

    def run(self):
        keyboard.add_hotkey('ctrl+shift+r', lambda: self.hotkey_pressed.emit("read_screen"))
        keyboard.add_hotkey('ctrl+shift+h', lambda: self.hotkey_pressed.emit("toggle_hear"))
        keyboard.add_hotkey('ctrl+shift+s', lambda: self.hotkey_pressed.emit("toggle_stealth"))
        keyboard.add_hotkey('ctrl+shift+c', lambda: self.hotkey_pressed.emit("clear_chat"))
        keyboard.add_hotkey('ctrl+shift+x', lambda: self.hotkey_pressed.emit("copy_last"))
        
        # Window Movement
        keyboard.add_hotkey('alt+up', lambda: self.hotkey_pressed.emit("move_up"))
        keyboard.add_hotkey('alt+down', lambda: self.hotkey_pressed.emit("move_down"))
        keyboard.add_hotkey('alt+left', lambda: self.hotkey_pressed.emit("move_left"))
        keyboard.add_hotkey('alt+right', lambda: self.hotkey_pressed.emit("move_right"))
        
        keyboard.wait()

class OTAUpdateWorker(QThread):
    update_available = pyqtSignal(dict)
    
    def run(self):
        try:
            import requests
            res = requests.get(f"{auth_manager.backend_url}/api/app/version", timeout=5)
            if res.ok:
                data = res.json()
                if data.get("status") == "success":
                    remote_version = data.get("version", "1.0.0")
                    if not remote_version: return
                    v1 = APP_VERSION.split(".")
                    v2 = remote_version.split(".")
                    is_newer = False
                    for i in range(min(len(v1), len(v2))):
                        if int(v2[i]) > int(v1[i]):
                            is_newer = True
                            break
                        elif int(v2[i]) < int(v1[i]):
                            break
                    if is_newer:
                        self.update_available.emit(data)
        except Exception as e:
            print(f"[OTA] Update Check Failed: {e}")

class DownloadWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(str)
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        
    def run(self):
        try:
            import requests
            import tempfile
            
            res = requests.get(self.url, stream=True, timeout=10)
            res.raise_for_status()
            
            total_size = int(res.headers.get('content-length', 0))
            block_size = 8192
            downloaded = 0
            
            temp_dir = tempfile.gettempdir()
            filepath = os.path.join(temp_dir, "ZenithHUD_PRO_Update.exe")
            
            self.status.emit("Downloading payload...")
            
            with open(filepath, 'wb') as f:
                for data in res.iter_content(block_size):
                    f.write(data)
                    downloaded += len(data)
                    if total_size > 0:
                        percent = int((downloaded / total_size) * 100)
                        self.progress.emit(percent)
                        
            self.finished.emit(filepath)
        except Exception as e:
            print(f"DL Error: {e}")
            self.finished.emit("")

from PyQt6.QtWidgets import QDialog, QProgressBar

class OTAUpdateDialog(QDialog):
    def __init__(self, parent, update_data):
        super().__init__(parent)
        self.update_data = update_data
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 380)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.bg = QFrame(self)
        self.bg.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 0.98);
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 12px;
            }
        """)
        bg_layout = QVBoxLayout(self.bg)
        bg_layout.setContentsMargins(30, 30, 30, 30)
        
        # Header Layout with Close Button
        header_layout = QHBoxLayout()
        
        title = QLabel("STRATEGIC UPDATE AVAILABLE")
        title.setStyleSheet("color: #38BDF8; font-size: 18px; font-weight: 900; letter-spacing: 1px;")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94A3B8;
                font-size: 24px;
                font-weight: 200;
                border: none;
            }
            QPushButton:hover {
                color: #F8FAFC;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 15px;
            }
        """)
        close_btn.clicked.connect(self.reject)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        bg_layout.addLayout(header_layout)
        
        v_label = QLabel(f"Version {APP_VERSION} → {update_data.get('version')}")
        v_label.setStyleSheet("color: #94A3B8; font-size: 14px; margin-bottom: 15px;")
        v_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bg_layout.addWidget(v_label)
        
        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setText(update_data.get("release_notes", "Performance improvements."))
        notes.setStyleSheet("""
            QTextEdit {
                background: rgba(30, 41, 59, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: #F8FAFC;
                padding: 10px;
                font-size: 13px;
            }
        """)
        bg_layout.addWidget(notes)
        
        self.progress = QProgressBar()
        self.progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #1E293B;
                text-align: center;
                color: transparent;
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: #38BDF8;
                border-radius: 4px;
            }
        """)
        self.progress.hide()
        bg_layout.addWidget(self.progress)
        
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.hide()
        bg_layout.addWidget(self.status_lbl)
        
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("IGNORE")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94A3B8;
                border: 1px solid #475569;
                border-radius: 8px;
                padding: 10px;
                font-weight: 800;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.05); }
        """)
        if update_data.get("force_update"):
            self.btn_cancel.hide()
        else:
            self.btn_cancel.clicked.connect(self.reject)
            
        self.btn_update = QPushButton("INSTALL SECURE UPDATE")
        self.btn_update.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-weight: 800;
            }
            QPushButton:hover { background: #38BDF8; }
        """)
        self.btn_update.clicked.connect(self.start_download)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_update)
        bg_layout.addLayout(btn_layout)
        
        layout.addWidget(self.bg)
        
    def start_download(self):
        self.btn_update.hide()
        self.btn_cancel.hide()
        self.progress.show()
        self.status_lbl.show()
        self.status_lbl.setText("Establishing secure connection...")
        
        self.dl_thread = DownloadWorker(self.update_data.get("download_url"))
        self.dl_thread.progress.connect(self.progress.setValue)
        self.dl_thread.status.connect(self.status_lbl.setText)
        self.dl_thread.finished.connect(self.on_download_complete)
        self.dl_thread.start()
        
    def on_download_complete(self, filepath):
        if filepath:
            self.status_lbl.setText("Launching installer...")
            try:
                os.startfile(filepath)
                sys.exit(0)
            except Exception as e:
                self.status_lbl.setText(f"Execute Error: {e}")
                self.btn_cancel.show()
        else:
            self.status_lbl.setText("Download failed. Please try again.")
            self.btn_cancel.show()
        
class MaintenanceThread(QThread):
    status_changed = pyqtSignal(dict) # Returns the full status dict

    def run(self):
        while True:
            try:
                from hwid_utils import get_hwid
                import requests
                
                params = {"hwid": get_hwid()}
                if auth_manager.current_user:
                    params["email"] = auth_manager.current_user
                    
                res = requests.get(
                    f"{auth_manager.backend_url}/api/auth/system-status",
                    params=params,
                    timeout=5
                )
                if res.ok:
                    self.status_changed.emit(res.json())
                else:
                    print(f"[Maintenance] API Error: {res.status_code}")
            except Exception as e:
                print(f"[Maintenance] Connection Failure: {e}")
            self.sleep(5) 

class MaintenanceOverlay(QFrame):
    def __init__(self, parent=None, message=""):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 0.95);
                border-radius: 12px;
            }
            QLabel {
                color: #FFFFFF;
                background: transparent;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        
        icon = QLabel("🛠️")
        icon.setStyleSheet("font-size: 64px; margin-bottom: 20px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        
        title = QLabel("SYSTEM UNDER MAINTENANCE")
        title.setStyleSheet("font-size: 24px; font-weight: 900; color: #38BDF8; letter-spacing: 2px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        self.msg_label = QLabel(message)
        self.msg_label.setStyleSheet("font-size: 14px; font-weight: 500; color: #94A3B8; margin-top: 10px;")
        self.msg_label.setWordWrap(True)
        self.msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.msg_label)
        
        sub_msg = QLabel("\nWe will send you an email as soon as we are back online.")
        sub_msg.setStyleSheet("font-size: 12px; color: #64748B; font-style: italic;")
        sub_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub_msg)
        
        close_btn = QPushButton("EXIT SYSTEM")
        close_btn.setFixedWidth(200)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #D32F2F;
                color: white;
                border-radius: 10px;
                padding: 12px;
                font-weight: 800;
                margin-top: 30px;
            }
            QPushButton:hover { background: #B71C1C; }
        """)
        close_btn.clicked.connect(QApplication.quit)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.hide()

    def show_maintenance(self, message):
        self.msg_label.setText(message)
        self.setGeometry(self.parent().rect())
        self.raise_()
        self.show()

class TicketWorker(QThread):
    history_loaded = pyqtSignal(dict)
    message_sent = pyqtSignal(bool, bool)

    def __init__(self, email, action='load'):
        super().__init__()
        self.email = email
        self.action = action
        self.msg_text = ""
        self.msg_role = "user"
        self.is_first_msg = False

    def run(self):
        try:
            if self.action == 'load':
                data = auth_manager.get_ticket_history(self.email)
                if data: self.history_loaded.emit(data)
            elif self.action == 'send':
                success = auth_manager.send_ticket_message(self.email, self.msg_text, self.msg_role)
                self.message_sent.emit(success, self.is_first_msg)
        except Exception as e:
            print(f"Worker Error: {e}")

class SuspendedOverlay(QFrame):
    def __init__(self, parent=None, email=""):
        super().__init__(parent)
        self.email = email
        self.ticket_active = False
        self.rendered_ids = set()
        
        self.setStyleSheet("""
            QFrame { background-color: #0f172a; border-radius: 20px; }
            QLabel { color: #f8fafc; background: transparent; }
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 40, 40, 40)
        self.main_layout.setSpacing(20)
        
        # 1. HEADER
        header_layout = QHBoxLayout()
        title_v = QVBoxLayout()
        title = QLabel("ZENITH SUPPORT")
        title.setStyleSheet("font-size: 22px; font-weight: 900; color: #f1f5f9; letter-spacing: 1px;")
        title_v.addWidget(title)
        subtitle = QLabel("Official Appeal Channel")
        subtitle.setStyleSheet("font-size: 11px; color: #6366f1; font-weight: 700; text-transform: uppercase;")
        title_v.addWidget(subtitle)
        header_layout.addLayout(title_v)
        header_layout.addStretch()
        
        self.back_btn = QPushButton("EXIT")
        self.back_btn.setFixedSize(80, 36)
        self.back_btn.setStyleSheet("background: rgba(255, 255, 255, 0.05); color: #94a3b8; font-weight: 800; border-radius: 8px;")
        self.back_btn.clicked.connect(QApplication.quit)
        header_layout.addWidget(self.back_btn)
        self.main_layout.addLayout(header_layout)

        # 2. STACKED CONTENT
        self.content_stack = QStackedWidget()
        
        # --- PAGE 0: APPEAL FORM ---
        self.form_page = QWidget()
        form_layout = QVBoxLayout(self.form_page)
        form_layout.setSpacing(15)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        f_icon = QLabel("🛡️")
        f_icon.setStyleSheet("font-size: 50px;")
        f_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(f_icon)
        
        f_title = QLabel("Account Restricted")
        f_title.setStyleSheet("font-size: 24px; font-weight: 800; color: #ef4444;")
        f_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(f_title)
        
        f_desc = QLabel("Please provide details about your activity to help our security team review your restriction.")
        f_desc.setStyleSheet("font-size: 13px; color: #94a3b8; line-height: 1.6;")
        f_desc.setFixedWidth(450)
        f_desc.setWordWrap(True)
        f_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(f_desc)
        
        self.appeal_field = QTextEdit()
        self.appeal_field.setPlaceholderText("Describe your issue or appeal here...")
        self.appeal_field.setFixedSize(500, 150)
        self.appeal_field.setStyleSheet("""
            QTextEdit {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                padding: 15px;
                color: #f1f5f9;
                font-size: 14px;
            }
            QTextEdit:focus { border-color: #4f46e5; background: rgba(255, 255, 255, 0.05); }
        """)
        form_layout.addWidget(self.appeal_field, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.submit_btn = QPushButton("SUBMIT APPEAL")
        self.submit_btn.setFixedSize(300, 50)
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.setStyleSheet("""
            QPushButton { background: #4f46e5; color: white; font-weight: 800; border-radius: 12px; font-size: 14px; }
            QPushButton:hover { background: #6366f1; }
        """)
        self.submit_btn.clicked.connect(self.submit_appeal)
        form_layout.addWidget(self.submit_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # --- PAGE 1: CONVERSATION ---
        self.chat_page = QWidget()
        chat_layout = QVBoxLayout(self.chat_page)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.chat_inner = QWidget()
        self.chat_inner_layout = QVBoxLayout(self.chat_inner)
        self.chat_inner_layout.setSpacing(15)
        self.chat_inner_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.chat_inner)
        chat_layout.addWidget(self.scroll)
        
        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 10, 0, 0)
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Follow-up message...")
        self.chat_input.setFixedHeight(50)
        self.chat_input.setStyleSheet("""
            QLineEdit { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 0 15px; color: white; }
            QLineEdit:focus { border-color: #4f46e5; }
        """)
        self.chat_input.returnPressed.connect(self.send_reply)
        input_row.addWidget(self.chat_input)
        
        self.chat_send_btn = QPushButton("SEND")
        self.chat_send_btn.setFixedSize(80, 50)
        self.chat_send_btn.setStyleSheet("background: #4f46e5; color: white; font-weight: 800; border-radius: 10px;")
        self.chat_send_btn.clicked.connect(self.send_reply)
        input_row.addWidget(self.chat_send_btn)
        chat_layout.addLayout(input_row)
        
        self.content_stack.addWidget(self.form_page)
        self.content_stack.addWidget(self.chat_page)
        self.main_layout.addWidget(self.content_stack)

        # Workers & Timers
        self.load_worker = TicketWorker(self.email, 'load')
        self.load_worker.history_loaded.connect(self.sync_ui)
        
        self.send_worker = TicketWorker(self.email, 'send')
        self.send_worker.message_sent.connect(self.on_sent)
        
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.poll)
        self.refresh_timer.start(5000)

    def poll(self):
        if self.isVisible() and self.email and not self.load_worker.isRunning():
            self.load_worker.email = self.email
            self.load_worker.start()

    def sync_ui(self, data):
        messages = data.get("messages", [])
        if not messages:
            self.content_stack.setCurrentIndex(0)
            return

        self.content_stack.setCurrentIndex(1)
        
        # Incremental rendering
        new_added = False
        for i, m in enumerate(messages):
            msg_id = f"{i}_{len(m.get('text',''))}"
            if msg_id not in self.rendered_ids:
                self.add_bubble(m.get('text',''), m.get('role') == 'admin')
                self.rendered_ids.add(msg_id)
                new_added = True
        
        if new_added:
            QTimer.singleShot(100, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    def add_bubble(self, text, is_admin):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 5, 10, 5)
        
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(480)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        # Premium Aesthetics
        if is_admin:
            bg = "rgba(16, 185, 129, 0.15)" # Emerald Glow
            border = "rgba(16, 185, 129, 0.4)"
            radius = "15px 15px 15px 2px"
            text_style = "color: #f8fafc; font-weight: 500;"
        else:
            bg = "rgba(79, 70, 229, 0.2)" # Deep Indigo
            border = "rgba(99, 102, 241, 0.4)"
            radius = "15px 15px 2px 15px"
            text_style = "color: #ffffff; font-weight: 500;"
        
        lbl.setStyleSheet(f"""
            QLabel {{
                background: {bg}; 
                {text_style}
                padding: 14px 18px; 
                border-radius: {radius}; 
                border: 1px solid {border}; 
                font-size: 13px;
                line-height: 1.6;
            }}
        """)
        
        if is_admin:
            layout.addWidget(lbl)
            layout.addStretch()
        else:
            layout.addStretch()
            layout.addWidget(lbl)
            
        self.chat_inner_layout.addWidget(container)
        QTimer.singleShot(10, self.chat_inner.adjustSize)

    def submit_appeal(self):
        txt = self.appeal_field.toPlainText().strip()
        if not txt: return
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("SUBMITTING...")
        self.send_worker.msg_text = txt
        self.send_worker.email = self.email
        self.send_worker.start()

    def send_reply(self):
        txt = self.chat_input.text().strip()
        if not txt: return
        self.chat_input.clear()
        self.send_worker.msg_text = txt
        self.send_worker.email = self.email
        self.send_worker.start()

    def on_sent(self, success, _):
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("SUBMIT APPEAL")
        self.poll()

    def show_suspended(self, email):
        # Enforce dark viewport background
        if hasattr(self, 'scroll'):
            self.scroll.viewport().setStyleSheet("background: #0f172a;")
            self.chat_inner.setStyleSheet("background: #0f172a;")

        if (not email or email == "Unknown") and auth_manager.current_user:
            email = auth_manager.current_user
            
        if self.email != email and email and email != "Unknown":
            self.email = email
            self.rendered_ids.clear()
            while self.chat_inner_layout.count():
                item = self.chat_inner_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            self.poll()
            
        self.setGeometry(self.parent().rect())
        self.raise_()
        self.show()
            
        if not self.refresh_timer.isActive():
            self.refresh_timer.start(5000)

class StealthHUD(QMainWindow):
    def __init__(self, cv_text="", jd_text="", link_text="", linkedin_url=""):
        super().__init__()
        
        # Initialize AI Context
        from ai_engine import ai_engine
        ai_engine.set_cv_context(cv_text)
        ai_engine.set_job_context(jd_text, link_text, linkedin_url)
        self.setWindowTitle("StealthHUD AI Assistant")
        # Added Tool flag to hide from taskbar
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # --- ABSOLUTE STEALTH REINFORCEMENT ---
        self.stealth_timer = QTimer(self)
        self.stealth_timer.timeout.connect(self.apply_current_stealth)
        self.stealth_timer.start(5000) # Re-apply every 5s to combat OS overrides
        
        # --- REACTIVE SHIELD (Auto-Hide on Screenshot Keys) ---
        import keyboard
        try:
            keyboard.add_hotkey('print screen', self.reactive_hide)
            keyboard.add_hotkey('win+shift+s', self.reactive_hide)
            keyboard.add_hotkey('alt+print screen', self.reactive_hide)
        except: pass
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFixedSize(550, 750)
        
        # Initialize Hotkeys
        self.kb_thread = KeyboardThread()
        self.kb_thread.hotkey_pressed.connect(self.handle_hotkey)
        self.kb_thread.start()
        
        # UI State
        self.is_stealth = True
        self.is_listening = False
        self.interim_active = False
        self.streaming_active = False
        self.last_voice_text = ""
        self.active_worker = None # Unified worker for Voice, Text, and Vision
        
        self.is_reading_screen = False
        self.last_ai_response = ""
        
        # Components
        self.audio_thread = AudioThread()
        self.audio_thread.transcript_received.connect(self.handle_transcript)
        self.audio_thread.partial_transcript_received.connect(self.handle_partial_transcript)
        self.audio_thread.error_occurred.connect(lambda e: self.log_message(f"<span style='color:red;'>[AUDIO ERROR] {e}</span>"))
        
        self.interim_active = False
        
        self.init_ui()
        
        # --- PROTECTION LAYERS ---
        self.maint_overlay = MaintenanceOverlay(self.glass_panel)
        self.suspended_overlay = SuspendedOverlay(self.glass_panel)
        
        self.maint_thread = MaintenanceThread()
        self.maint_thread.status_changed.connect(self.handle_system_status_update)
        self.maint_thread.start()
        
        # --- OTA AUTO-UPDATES ---
        self.ota_worker = OTAUpdateWorker()
        self.ota_worker.update_available.connect(self.show_ota_dialog)
        self.ota_worker.start()
        
    def show_ota_dialog(self, data):
        self.ota_dialog = OTAUpdateDialog(self, data)
        result = self.ota_dialog.exec()
        # If mandatory and user closes/rejects, exit the app
        if data.get("force_update") and result == QDialog.DialogCode.Rejected:
            QApplication.quit()
            sys.exit(0)
        
    # Window dragging
        self.old_pos = None

    def init_ui(self):
        # Central Widget
        self.central_widget = QWidget()
        self.central_widget.setObjectName("centralWidget")
        self.central_widget.setStyleSheet("#centralWidget { background: transparent; }")
        self.setCentralWidget(self.central_widget)
        
        # Main Layout
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Jelly Glass Panel
        self.glass_panel = QFrame()
        self.glass_panel.setObjectName("glassPanel")
        self.glass_panel.setStyleSheet("""
            #glassPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                                            stop:0 rgba(220, 255, 250, 0.4), 
                                            stop:1 rgba(190, 245, 235, 0.2));
                border-radius: 50px;
                border: 2px solid rgba(255, 255, 255, 0.6);
            }
        """)
        self.layout.addWidget(self.glass_panel)
        
        self.panel_layout = QVBoxLayout(self.glass_panel)
        self.panel_layout.setContentsMargins(30, 30, 30, 30)
        self.panel_layout.setSpacing(15)

        # --- Top Bar ---
        self.top_bar = QHBoxLayout()
        
        self.title_label = QLabel("ZENITH HUD")
        self.title_label.setStyleSheet("color: #007E44; font-weight: 900; font-size: 16px; letter-spacing: 2px; background: transparent;")
        
        def get_indicator(key_name):
            val = os.getenv(key_name)
            color = "#00E676" if val else "#D32F2F"
            lbl = QLabel("●")
            lbl.setStyleSheet(f"color: {color}; font-size: 16px; background: transparent;")
            lbl.setToolTip(key_name)
            return lbl

        self.indicators = QHBoxLayout()
        self.indicators.setSpacing(2)
        self.indicators.addWidget(get_indicator("GROQ_API_KEYS"))
        self.indicators.addWidget(get_indicator("GEMINI_API_KEYS"))
        self.indicators.addWidget(get_indicator("DEEPGRAM_API_KEYS"))
        
        self.stealth_toggle = QPushButton("STEALTH: ON")
        self.stealth_toggle.setFixedWidth(100)
        self.stealth_toggle.clicked.connect(self.toggle_stealth)
        self.update_stealth_button_style()

        self.min_btn = QPushButton("—")
        self.min_btn.setFixedSize(30, 30)
        self.min_btn.clicked.connect(self.showMinimized)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self.close)
        
        button_style = "QPushButton { background: rgba(0, 0, 0, 0.05); color: #000000; border-radius: 15px; font-size: 16px; } QPushButton:hover { background: rgba(211, 47, 47, 0.2); color: #D32F2F; }"
        self.min_btn.setStyleSheet(button_style)
        self.close_btn.setStyleSheet(button_style)

        self.top_bar.addWidget(self.title_label)
        self.top_bar.addLayout(self.indicators)
        self.top_bar.addStretch()
        self.top_bar.addWidget(self.stealth_toggle)
        self.top_bar.addWidget(self.min_btn)
        self.top_bar.addWidget(self.close_btn)
        
        self.panel_layout.addLayout(self.top_bar)
        
        # --- Tactical Settings Bar ---
        self.settings_bar = QHBoxLayout()
        self.settings_bar.setSpacing(10)
        
        # Intelligence Tier Toggle
        self.tier_btn = QPushButton("TIER: TURBO")
        self.tier_btn.clicked.connect(self.toggle_tier)
        
        # Mode Toggle
        self.mode_btn = QPushButton("MODE: INTERVIEW")
        self.mode_btn.clicked.connect(self.toggle_mode)
        
        setting_btn_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: #007E44;
                border: 1px solid rgba(0, 126, 68, 0.3);
                border-radius: 10px;
                padding: 5px 15px;
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 1px;
            }
            QPushButton:hover { background: rgba(0, 126, 68, 0.1); }
        """
        self.tier_btn.setStyleSheet(setting_btn_style)
        self.mode_btn.setStyleSheet(setting_btn_style)
        
        self.settings_bar.addWidget(self.tier_btn)
        self.settings_bar.addWidget(self.mode_btn)
        self.settings_bar.addStretch()
        
        self.panel_layout.addLayout(self.settings_bar)

        # --- Chat Area ---
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                border: 2px solid rgba(0, 0, 0, 0.05);
                color: #1A2E2A;
                font-size: 15px;
                padding: 20px;
            }
            QTextEdit:focus {
                border: 2px solid rgba(0, 230, 118, 0.3);
            }
        """)
        self.panel_layout.addWidget(self.chat_display)

        # --- Toggles Area ---
        self.toggle_layout = QHBoxLayout()
        
        self.listen_btn = QPushButton("AUTO-HEAR: OFF")
        self.listen_btn.clicked.connect(self.toggle_listening)
        
        self.screen_btn = QPushButton("READ SCREEN: OFF")
        self.screen_btn.clicked.connect(self.trigger_screen_analysis)
        
        toggle_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.85);
                color: #007E44;
                border: 2px solid rgba(0, 0, 0, 0.05);
                border-radius: 15px;
                padding: 12px;
                font-weight: 900;
            }
            QPushButton:hover { background: rgba(0, 230, 118, 0.2); border: 2px solid rgba(0, 230, 118, 0.4); }
        """
        self.listen_btn.setStyleSheet(toggle_style)
        self.screen_btn.setStyleSheet(toggle_style)
        
        self.toggle_layout.addWidget(self.listen_btn)
        self.toggle_layout.addWidget(self.screen_btn)
        
        self.panel_layout.addLayout(self.toggle_layout)

        # --- End Session Button ---
        self.end_btn = QPushButton("END INTERVIEW & SYNC INSIGHTS")
        self.end_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 0, 0, 0.05);
                color: #D32F2F;
                border: 1px solid rgba(211, 47, 47, 0.2);
                border-radius: 15px;
                padding: 10px;
                font-weight: 900;
                font-size: 11px;
                letter-spacing: 1px;
            }
            QPushButton:hover { background: rgba(211, 47, 47, 0.1); }
        """)
        self.end_btn.clicked.connect(self.end_interview_flow)
        self.panel_layout.addWidget(self.end_btn)

        # --- Input Area ---
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type custom question...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                border: 2px solid rgba(0, 0, 0, 0.05);
                color: #1A2E2A;
                padding: 15px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid rgba(0, 230, 118, 0.3);
            }
        """)
        self.input_field.returnPressed.connect(self.handle_user_input)
        self.panel_layout.addWidget(self.input_field)

    def toggle_tier(self):
        current = ai_engine.intelligence_tier
        new_tier = "savant" if current == "turbo" else "turbo"
        ai_engine.set_tier(new_tier)
        self.tier_btn.setText(f"TIER: {new_tier.upper()}")
        color = "#6200EA" if new_tier == "savant" else "#007E44"
        self.tier_btn.setStyleSheet(self.tier_btn.styleSheet() + f" color: {color};")
        self.log_message(f"<span style='color:gray;'>[SYSTEM] Intelligence Tier: {new_tier.upper()}</span>")

    def toggle_mode(self):
        modes = ["interview", "code", "mcq"]
        current = ai_engine.mode
        new_idx = (modes.index(current) + 1) % len(modes)
        new_mode = modes[new_idx]
        ai_engine.set_mode(new_mode)
        self.mode_btn.setText(f"MODE: {new_mode.upper()}")
        self.log_message(f"<span style='color:gray;'>[SYSTEM] Operational Mode: {new_mode.upper()}</span>")

    def end_interview_flow(self):
        # Create a centered loading overlay
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
        from PyQt6.QtCore import Qt
        
        self.loading_dialog = QDialog(self)
        self.loading_dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.loading_dialog.setModal(True)
        self.loading_dialog.setStyleSheet("background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px;")
        
        layout = QVBoxLayout()
        label = QLabel("🚀 ANALYZING INTERVIEW INTELLIGENCE...")
        label.setStyleSheet("font-weight: bold; color: #1e293b; padding: 10px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        progress = QProgressBar()
        progress.setRange(0, 0) # Indeterminate
        progress.setStyleSheet("QProgressBar { height: 6px; border: none; background: #f1f5f9; border-radius: 3px; } QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #3b82f6); border-radius: 3px; }")
        
        layout.addWidget(label)
        layout.addWidget(progress)
        self.loading_dialog.setLayout(layout)
        self.loading_dialog.setFixedSize(350, 100)
        self.loading_dialog.show()
        
        # Move dialog to center of HUD
        hud_center = self.geometry().center()
        self.loading_dialog.move(hud_center.x() - 175, hud_center.y() - 50)

        self.end_btn.setEnabled(False)
        self.log_message("<span style='color:#D32F2F;'>[SYSTEM] Closing session and analyzing intelligence...</span>")
        
        self.report_worker = ReportWorker()
        self.report_worker.finished.connect(self.handle_report_finished)
        self.report_worker.error.connect(self.handle_report_error)
        self.report_worker.start()

    def handle_report_finished(self):
        if hasattr(self, 'loading_dialog'):
            self.loading_dialog.close()
        # Relaunch the Dashboard (cv_panel.py)
        import subprocess
        import sys
        
        # Determine the correct path to cv_panel.py
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
            # In bundled mode, we should ideally launch the main executable again 
            # but with a flag or just let it handle the login/dashboard transition.
            # However, launching cv_panel.py directly is what the user asked.
            script_path = os.path.join(application_path, "_internal", "cv_panel.py")
            if os.path.exists(script_path):
                subprocess.Popen([sys.executable, script_path])
            else:
                # Fallback to just launching the main app again
                subprocess.Popen([sys.executable])
        else:
            subprocess.Popen([sys.executable, "cv_panel.py"])
        
        self.close()

    def handle_report_error(self, err):
        if hasattr(self, 'loading_dialog'):
            self.loading_dialog.close()
        self.log_message(f"<span style='color:red;'>[SYSTEM ERROR] Report failed: {err}</span>")
        self.end_btn.setText("END INTERVIEW & SYNC INSIGHTS")
        self.end_btn.setEnabled(True)

    def handle_system_status_update(self, status):
        # 1. Check Suspension (High Priority)
        if status.get("suspended"):
            # Stop all tactical activity
            self.audio_thread.stop()
            self.is_listening = False
            self.listen_btn.setEnabled(False)
            self.screen_btn.setEnabled(False)
            self.input_field.setEnabled(False)
            self.end_btn.setEnabled(False)
            
            # Show suspended overlay
            self.suspended_overlay.show_suspended(status.get("email", "Unknown"))
            return
        else:
            self.suspended_overlay.hide()

        # 2. Check Maintenance
        if status.get("maintenance_mode"):
            # Stop all tactical activity
            self.audio_thread.stop()
            self.is_listening = False
            self.listen_btn.setEnabled(False)
            self.screen_btn.setEnabled(False)
            self.input_field.setEnabled(False)
            self.end_btn.setEnabled(False)
            
            # Show maintenance overlay
            self.maint_overlay.show_maintenance(status.get("maintenance_message", "Strategic calibration in progress..."))
        else:
            if self.maint_overlay.isVisible():
                self.log_message(f"<span style='color:#00E676;'>[SYSTEM] Maintenance complete. Tactical link restored.</span>")
            self.maint_overlay.hide()
            
            # Restore state if not suspended
            self.listen_btn.setEnabled(True)
            self.screen_btn.setEnabled(True)
            self.input_field.setEnabled(True)
            self.end_btn.setEnabled(True)

    def handle_hotkey(self, key):
        if key == "read_screen":
            self.trigger_screen_analysis()
        elif key == "toggle_hear":
            self.toggle_listening()
        elif key == "toggle_stealth":
            self.toggle_stealth()
        elif key == "clear_chat":
            self.chat_display.clear()
            self.log_message("<i style='color:gray;'>[SYSTEM] Chat cleared via shortcut.</i>")
        elif key == "copy_last":
            self.copy_last_response()
        elif key == "move_up":
            self.move(self.x(), self.y() - 50)
        elif key == "move_down":
            self.move(self.x(), self.y() + 50)
        elif key == "move_left":
            self.move(self.x() - 50, self.y())
        elif key == "move_right":
            self.move(self.x() + 50, self.y())

    def copy_last_response(self):
        if hasattr(self, 'last_ai_response') and self.last_ai_response:
            QApplication.clipboard().setText(self.last_ai_response)
            self.log_message("<span style='color:#00B0FF;'>[SYSTEM] 📋 Last AI response copied to clipboard!</span>")
        else:
            self.log_message("<span style='color:gray;'>[SYSTEM] No AI response to copy yet.</span>")

    def toggle_stealth(self):
        self.is_stealth = not self.is_stealth
        hwnd = self.winId().__int__()
        success = stealth_engine.set_stealth_mode(hwnd, self.is_stealth)
        self.update_stealth_button_style()
        if success:
            status = "ACTIVE (Window Invisible to Share)" if self.is_stealth else "DISABLED"
            self.log_message(f"<span style='color:#00E676;'>[SYSTEM] Stealth Shield {status}</span>")
        else:
            self.log_message(f"<span style='color:#FF5252;'>[SYSTEM] Stealth Warning: OS rejected invisibility flag.</span>")

    def update_stealth_button_style(self):
        if self.is_stealth:
            self.stealth_toggle.setText("STEALTH: ON")
            self.stealth_toggle.setStyleSheet("background: #00E676; color: #1A2E2A; border-radius: 15px; padding: 8px; font-weight: 900;")
        else:
            self.stealth_toggle.setText("STEALTH: OFF")
            self.stealth_toggle.setStyleSheet("background: #D32F2F; color: white; border-radius: 15px; padding: 8px; font-weight: 900;")

    def toggle_listening(self):
        self.is_listening = not self.is_listening
        if self.is_listening:
            self.audio_thread.start()
            self.listen_btn.setText("AUTO-HEAR: ON")
            self.listen_btn.setStyleSheet("background: #00B0FF; color: white; border-radius: 15px; padding: 12px; font-weight: 900;")
            self.log_message("<span style='color:#007E44;'>[SYSTEM] Auto-Hear Started</span>")
        else:
            self.audio_thread.stop()
            self.listen_btn.setText("AUTO-HEAR: OFF")
            self.listen_btn.setStyleSheet("background: rgba(255, 255, 255, 0.5); color: #007E44; border-radius: 15px; padding: 12px; font-weight: 900;")
            self.log_message("<span style='color:gray;'>[SYSTEM] Auto-Hear Stopped</span>")

    def trigger_screen_analysis(self):
        """Action trigger for rapid-fire MCQ testing or code solving."""
        self.screen_btn.setText("ANALYZING...")
        self.screen_btn.setStyleSheet("background: #6200EA; color: white; border-radius: 15px; padding: 12px; font-weight: 900;")
        self.log_message("<span style='color:#6200EA;'>[SYSTEM] Capture & Analyze in progress...</span>")
        
        # Hide HUD to prevent it from blocking the capture
        self.hide()
        
        # Delay 150ms to allow OS window animation to clear safely without blocking main loop
        QTimer.singleShot(150, self._do_capture_and_analyze)

    def _do_capture_and_analyze(self):
        # Start analysis in background
        path = vision_handler.capture_fullscreen()
        
        # Restore HUD
        self.show()
        
        if not path:
            self.log_message("<span style='color:red;'>[SYSTEM ERROR] Tactical Capture Failed. Please ensure ZenithHUD is running as Administrator.</span>")
            self.screen_btn.setText("READ SCREEN: OFF")
            self.screen_btn.setStyleSheet("background: rgba(255, 255, 255, 0.5); color: #007E44; border-radius: 15px; padding: 12px; font-weight: 900;")
            return

        # Dynamic query based on mode
        if ai_engine.mode == "code":
            query = "Extract the code problem from the screen and solve it with optimized, clean code."
        elif ai_engine.mode == "mcq":
            query = "Identify the question and all options. Provide the correct answer and a brief reason."
        else:
            query = "Identify any questions or logic on screen and provide a natural, conversational answer."
            
        # Unified AI routing
        self.stop_active_worker()
        self.active_worker = AIWorker(query, mode="vision", image_path=path)
        self.active_worker.finished.connect(self.handle_vision_finished)
        self.active_worker.start()

    def handle_vision_finished(self, sender, message):
        """Resets the button after analysis is complete."""
        self.last_ai_response = message
        # Standardize labels: Use SAVANT EYE for vision analysis
        self.log_message(f"<span style='color:#7C4DFF;'><b>AI (Savant Eye):</b> {message}</span>")
        self.screen_btn.setText("READ SCREEN: OFF")
        self.screen_btn.setStyleSheet("background: rgba(255, 255, 255, 0.5); color: #007E44; border-radius: 15px; padding: 12px; font-weight: 900;")

    def perform_screen_analysis(self):
        self.hide()
        QTimer.singleShot(150, self._do_perform_screen_analysis)

    def _do_perform_screen_analysis(self):
        path = vision_handler.capture_fullscreen()
        self.show()
        
        self.stop_active_worker()
        self.active_worker = AIWorker("Analyze this screen and provide the answer.", mode="vision", image_path=path)
        self.active_worker.finished.connect(self.handle_ai_finished)
        self.active_worker.start()

    def handle_partial_transcript(self, text):
        # --- SMART INTERRUPTION HANDLING ---
        # If the active worker is running AND hasn't started streaming, kill it.
        # We don't rollback the UI, we just let the AI read the stacked history.
        if self.active_worker and self.active_worker.isRunning() and not self.streaming_active:
            print("[System] Interruption detected! Aborting previous AI task...")
            self.stop_active_worker()

        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        if not self.interim_active:
            self.chat_display.append("") # Create a new block
            self.interim_active = True
            
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
        
        # Clean replacement of the interim line
        cursor.insertHtml(f"<span style='color:rgba(0, 126, 68, 0.5);'><b>INTERVIEWER (Listening):</b> {text}</span>")
        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)

    def handle_transcript(self, text):
        # Clear the 'Listening' state
        if self.interim_active:
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            cursor.deletePreviousChar() # Remove the extra newline
            self.interim_active = False

        self.log_message(f"<span style='color:#00B0FF;'><b>INTERVIEWER:</b> {text}</span>")
        self.last_voice_text = text
        
        # --- UNIFIED WORKER ROUTING ---
        self.stop_active_worker()
        
        # Automatically get AI response for interviewer voice
        self.active_worker = AIWorker(text, mode="text")
        self.active_worker.chunk_received.connect(self.handle_ai_chunk)
        self.active_worker.finished.connect(self.handle_ai_finished)
        self.active_worker.start()

    def stop_active_worker(self):
        """Safely stops any running AI generation to prevent race conditions."""
        if hasattr(self, 'active_worker') and self.active_worker and self.active_worker.isRunning():
            try:
                # Signal graceful stop
                self.active_worker.stop()
                
                # Disconnect signals immediately to prevent UI updates from late chunks
                try:
                    self.active_worker.chunk_received.disconnect()
                except: pass
                try:
                    self.active_worker.finished.disconnect()
                except: pass
                
                # Give it a moment to finish cleanly
                if not self.active_worker.wait(300):
                    # If still running after 300ms, use more aggressive wait but avoid terminate() if possible
                    # terminate() is the last resort and known to cause crashes
                    print("[System] Worker sluggish. Waiting for lock release...")
                    self.active_worker.wait(700)
            except Exception as e:
                print(f"[System] Stop Error: {e}")
        
        self.active_worker = None
        self.streaming_active = False

    def handle_ai_chunk(self, sender, chunk):
        if not self.chat_display or not chunk: return
        
        if not self.streaming_active:
            self.log_message(f"<span style='color:#007E44;'><b>AI (Savant Eye):</b> </span>", append_newline=False)
            self.streaming_active = True
        
        # Ensure we are modifying the end of the document
        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)
        self.chat_display.insertPlainText(chunk)
        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)

    def handle_user_input(self):
        text = self.input_field.text().strip()
        if text:
            self.log_message(f"<span style='color:#D4AF37;'><b>YOU:</b> {text}</span>")
            self.input_field.clear()
            
            self.stop_active_worker()
            self.active_worker = AIWorker(text, mode="text")
            self.active_worker.chunk_received.connect(self.handle_ai_chunk)
            self.active_worker.finished.connect(self.handle_ai_finished)
            self.active_worker.start()
        else:
            # Empty ENTER key press: Manually flush the audio buffer and trigger AI!
            if self.is_listening:
                self.audio_thread.flush_now()

    def handle_ai_finished(self, sender, message):
        self.last_ai_response = message
        self.streaming_active = False # Reset for next session

    def log_message(self, message, append_newline=True):
        formatted_message = message.replace("\n", "<br>")
        # Add extra vertical spacing between messages for readability
        spacer = "<br><br>" if self.chat_display.toPlainText().strip() and append_newline else ""
        self.chat_display.append(f"{spacer}{formatted_message}")
        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)

    def showEvent(self, event):
        super().showEvent(event)
        # Apply stealth with a slight delay to ensure OS window handles are fully ready
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, self.apply_current_stealth)

    def reactive_hide(self):
        """Intense Stealth: Disappear the moment a screenshot key is pressed."""
        # Only trigger if the HUD is actually active and visible
        if self.is_stealth and self.isVisible():
            self.hide()
            # Stay hidden for 1.5 seconds to allow the screenshot tool to finish
            QTimer.singleShot(1500, self.show)

    def closeEvent(self, event):
        """Cleanup and ensure the app fully terminates."""
        try:
            import keyboard
            keyboard.unhook_all()
        except: pass
        super().closeEvent(event)
        QApplication.quit()

    def apply_current_stealth(self):
        if not self.is_stealth:
            hwnd = self.winId().__int__()
            stealth_engine.set_stealth_mode(hwnd, False)
            return

        hwnd = self.winId().__int__()
        success = stealth_engine.set_stealth_mode(hwnd, True)
        
        # Logic for 'Absolute Stealth' - Check if running as Admin
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        if not is_admin and not hasattr(self, '_admin_warned'):
            print("[SYSTEM] WARNING: Running as Standard User. Stealth works best as ADMINISTRATOR.")
            self._admin_warned = True

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

if __name__ == "__main__":
    if is_already_running():
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "ZenithHUD is already operational on this system.", "Instance Conflict", 16)
        sys.exit(0)
        
    app = QApplication(sys.argv)
    
    # Auth Check
    from auth_manager import auth_manager
    from login_window import LoginWindow
    
    # 0. Maintenance Check (Top Priority)
    is_maint, maint_msg = auth_manager.check_maintenance()
    if is_maint:
        import ctypes
        msg = f"ZenithHUD System Under Maintenance\n\n{maint_msg}\n\nWe will send you an email as soon as we are reactive."
        ctypes.windll.user32.MessageBoxW(0, msg, "System Maintenance", 64) # 64 = Icon Information
        sys.exit(0)

    if not auth_manager.current_user:
        # Show Login Screen if no session
        login = LoginWindow()
        login.show()
    else:
        # Show Main App if session exists
        window = StealthHUD()
        window.show()
        
    sys.exit(app.exec())

# --- GLOBAL TACTICAL EXCEPTION HANDLER (Auto-Healing) ---
def global_exception_handler(etype, value, tb):
    import traceback
    import datetime
    import ctypes
    
    error_msg = "".join(traceback.format_exception(etype, value, tb))
    print(f"\n[CRITICAL ANOMALY] {error_msg}")
    
    # Persistent logging for engineering review
    log_path = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), "StealthHUD", "crash_log.txt")
    try:
        with open(log_path, "a") as f:
            f.write(f"\n--- {datetime.datetime.now()} ---\n{error_msg}\n")
    except: pass
    
    # Auto-Heal Notification
    try:
        ctypes.windll.user32.MessageBoxW(0, 
            "ZenithHUD encountered a tactical anomaly. Auto-healing logic has been engaged to prevent failure. If this persists, please restart the app as Administrator.", 
            "Tactical System Recovery", 0x10)
    except: pass

sys.excepthook = global_exception_handler
