import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton, 
                             QLabel, QFrame, QScrollArea)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QFont, QIcon, QTextCursor
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

# Load .env from the executable's directory
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

import dotenv
# FORCE load from the current directory, ignoring all other .env files
env_path = os.path.join(application_path, ".env")
dotenv.load_dotenv(env_path, override=True)

# Import Handlers with Error Reporting
try:
    from audio_handler import AudioThread
    from ai_engine import ai_engine
    from vision_handler import vision_handler
except ImportError as e:
    import ctypes
    msg = f"Critical Error: Missing module {e.name}. The application was not bundled correctly."
    ctypes.windll.user32.MessageBoxW(0, msg, "StealthHUD Error", 16)
    sys.exit(1)

from PyQt6.QtCore import QThread, pyqtSignal

class AIWorker(QThread):
    finished = pyqtSignal(str, str) # Type (AI/YOU), Message

    def __init__(self, query, mode="text", image_path=None):
        super().__init__()
        self.query = query
        self.mode = mode
        self.image_path = image_path

    def run(self):
        if self.mode == "text":
            response = ai_engine.get_groq_response(self.query)
        elif self.mode == "vision":
            response = ai_engine.analyze_screen(self.image_path, self.query)
        
        self.finished.emit("AI", response)

class StealthHUD(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StealthHUD AI Assistant")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.resize(450, 650)
        self.setMinimumSize(350, 400)
        
        # UI State
        self.is_stealth = True
        self.is_listening = False
        self.is_reading_screen = False
        
        # Components
        self.audio_thread = AudioThread()
        self.audio_thread.transcript_received.connect(self.handle_transcript)
        self.audio_thread.partial_transcript_received.connect(self.handle_partial_transcript)
        self.audio_thread.error_occurred.connect(lambda e: self.log_message(f"<span style='color:red;'>[AUDIO ERROR] {e}</span>"))
        
        self.interim_active = False
        
        self.init_ui()
        self.apply_mica_effect()
        
        # Display Debug Info
        env_path = os.path.join(application_path, ".env")
        self.log_message(f"<span style='color:yellow;'>[DEBUG] Searching .env in: {application_path}</span>")
        if os.path.exists(env_path):
            self.log_message("<span style='color:lime;'>[DEBUG] .env file FOUND!</span>")
        else:
            self.log_message("<span style='color:orange;'>[DEBUG] .env file NOT FOUND at this path!</span>")
        
        from keys import key_manager
        for log in key_manager.status_log:
            color = "lime" if "Loaded" in log else "red"
            self.log_message(f"<span style='color:{color};'>[DEBUG] {log}</span>")

        # Window dragging
        self.old_pos = None

    def init_ui(self):
        # Central Widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main Layout
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)

        # --- Top Bar ---
        self.top_bar = QHBoxLayout()
        
        self.title_label = QLabel("STEALTH ASSISTANT PRO")
        self.title_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-weight: bold; font-size: 14px; letter-spacing: 1px;")
        
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
        
        button_style = "QPushButton { background: transparent; color: white; border: none; font-size: 16px; } QPushButton:hover { background: rgba(255, 255, 255, 0.1); }"
        self.min_btn.setStyleSheet(button_style)
        self.close_btn.setStyleSheet(button_style)

        self.top_bar.addWidget(self.title_label)
        self.top_bar.addStretch()
        self.top_bar.addWidget(self.stealth_toggle)
        self.top_bar.addWidget(self.min_btn)
        self.top_bar.addWidget(self.close_btn)
        
        self.layout.addLayout(self.top_bar)

        # --- Chat Area ---
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background: rgba(0, 0, 0, 0.4);
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: #EEE;
                font-size: 14px;
                padding: 10px;
            }
        """)
        self.layout.addWidget(self.chat_display)

        # --- Toggles Area ---
        self.toggle_layout = QHBoxLayout()
        
        self.listen_btn = QPushButton("AUTO-HEAR: OFF")
        self.listen_btn.clicked.connect(self.toggle_listening)
        
        self.screen_btn = QPushButton("READ SCREEN: OFF")
        self.screen_btn.clicked.connect(self.toggle_screen_reading)
        
        toggle_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                color: #BBB;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.1); }
        """
        self.listen_btn.setStyleSheet(toggle_style)
        self.screen_btn.setStyleSheet(toggle_style)
        
        self.toggle_layout.addWidget(self.listen_btn)
        self.toggle_layout.addWidget(self.screen_btn)
        
        self.layout.addLayout(self.toggle_layout)

        # --- Input Area ---
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type custom question...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 5px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                color: white;
                padding: 10px;
                font-size: 14px;
            }
        """)
        self.input_field.returnPressed.connect(self.handle_user_input)
        self.layout.addWidget(self.input_field)

    def apply_mica_effect(self):
        if HAS_MICA:
            try:
                hwnd = self.winId().__int__()
                ApplyMica(hwnd, MICAMODE.DARK)
            except Exception as e:
                print(f"Mica error: {e}")
        else:
            self.setStyleSheet("background-color: #1A1A1A;") # Fallback dark background

    def toggle_stealth(self):
        self.is_stealth = not self.is_stealth
        hwnd = self.winId().__int__()
        stealth_engine.set_stealth_mode(hwnd, self.is_stealth)
        self.update_stealth_button_style()
        self.log_message(f"<span style='color:gray;'>[SYSTEM] Stealth Mode {'ENABLED' if self.is_stealth else 'DISABLED'}</span>")

    def update_stealth_button_style(self):
        if self.is_stealth:
            self.stealth_toggle.setText("STEALTH: ON")
            self.stealth_toggle.setStyleSheet("background: #00C853; color: white; border-radius: 5px; padding: 5px; font-weight: bold;")
        else:
            self.stealth_toggle.setText("STEALTH: OFF")
            self.stealth_toggle.setStyleSheet("background: #D50000; color: white; border-radius: 5px; padding: 5px; font-weight: bold;")

    def toggle_listening(self):
        self.is_listening = not self.is_listening
        if self.is_listening:
            self.audio_thread.start()
            self.listen_btn.setText("AUTO-HEAR: ON")
            self.listen_btn.setStyleSheet("background: #2962FF; color: white; border-radius: 5px; padding: 8px; font-weight: bold;")
            self.log_message("<span style='color:#2962FF;'>[SYSTEM] Auto-Hear Started</span>")
        else:
            self.audio_thread.stop()
            self.listen_btn.setText("AUTO-HEAR: OFF")
            self.listen_btn.setStyleSheet("background: rgba(255, 255, 255, 0.05); color: #BBB; border-radius: 5px; padding: 8px; font-weight: bold;")
            self.log_message("<span style='color:gray;'>[SYSTEM] Auto-Hear Stopped</span>")

    def toggle_screen_reading(self):
        self.is_reading_screen = not self.is_reading_screen
        if self.is_reading_screen:
            self.screen_btn.setText("READ SCREEN: ON")
            self.screen_btn.setStyleSheet("background: #6200EA; color: white; border-radius: 5px; padding: 8px; font-weight: bold;")
            self.log_message("<span style='color:#6200EA;'>[SYSTEM] Screen Reading Active (Capturing...)</span>")
            self.perform_screen_analysis()
        else:
            self.screen_btn.setText("READ SCREEN: OFF")
            self.screen_btn.setStyleSheet("background: rgba(255, 255, 255, 0.05); color: #BBB; border-radius: 5px; padding: 8px; font-weight: bold;")

    def perform_screen_analysis(self):
        path = vision_handler.capture_fullscreen()
        self.ai_worker = AIWorker("Analyze this screen and provide the answer.", mode="vision", image_path=path)
        self.ai_worker.finished.connect(self.handle_ai_finished)
        self.ai_worker.start()

    def handle_partial_transcript(self, text):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        if not self.interim_active:
            self.chat_display.append("") # Create a new block
            self.interim_active = True
            
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertHtml(f"<span style='color:#AAA;'><b>INTERVIEWER (Listening):</b> {text}</span>")
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
        # Automatically get AI response for interviewer voice
        self.ai_worker = AIWorker(text, mode="text")
        self.ai_worker.finished.connect(self.handle_ai_finished)
        self.ai_worker.start()

    def handle_user_input(self):
        text = self.input_field.text().strip()
        if text:
            self.log_message(f"<b>YOU:</b> {text}")
            self.input_field.clear()
            self.ai_worker = AIWorker(text, mode="text")
            self.ai_worker.finished.connect(self.handle_ai_finished)
            self.ai_worker.start()
        else:
            # Empty ENTER key press: Manually flush the audio buffer and trigger AI!
            if self.is_listening:
                self.audio_thread.flush_now()

    def handle_ai_finished(self, sender, message):
        self.log_message(f"<span style='color:#00E676;'><b>AI:</b> {message}</span>")

    def log_message(self, message):
        self.chat_display.append(message)
        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)

    def showEvent(self, event):
        hwnd = self.winId().__int__()
        stealth_engine.set_stealth_mode(hwnd, self.is_stealth)
        super().showEvent(event)

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
    app = QApplication(sys.argv)
    window = StealthHUD()
    window.show()
    sys.exit(app.exec())
