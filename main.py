import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton, 
                             QLabel, QFrame, QScrollArea)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPoint, QThread
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
    from history_manager import history_manager
    from auth_manager import auth_manager
except ImportError as e:
    import ctypes
    msg = f"Critical Error: Missing module {e.name}. The application was not bundled correctly."
    ctypes.windll.user32.MessageBoxW(0, msg, "StealthHUD Error", 16)
    sys.exit(1)

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

class KeyboardThread(QThread):
    hotkey_pressed = pyqtSignal(str)

    def run(self):
        keyboard.add_hotkey('ctrl+shift+r', lambda: self.hotkey_pressed.emit("read_screen"))
        keyboard.add_hotkey('ctrl+shift+h', lambda: self.hotkey_pressed.emit("toggle_hear"))
        keyboard.add_hotkey('ctrl+shift+s', lambda: self.hotkey_pressed.emit("toggle_stealth"))
        keyboard.add_hotkey('ctrl+shift+c', lambda: self.hotkey_pressed.emit("clear_chat"))
        
        # Window Movement
        keyboard.add_hotkey('alt+up', lambda: self.hotkey_pressed.emit("move_up"))
        keyboard.add_hotkey('alt+down', lambda: self.hotkey_pressed.emit("move_down"))
        keyboard.add_hotkey('alt+left', lambda: self.hotkey_pressed.emit("move_left"))
        keyboard.add_hotkey('alt+right', lambda: self.hotkey_pressed.emit("move_right"))
        
        keyboard.wait()

class StealthHUD(QMainWindow):
    def __init__(self, cv_text=""):
        super().__init__()
        self.cv_text = cv_text
        ai_engine.set_cv_context(cv_text)
        self.setWindowTitle("StealthHUD AI Assistant")
        # Added Tool flag to hide from taskbar
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFixedSize(550, 750)
        
        # Initialize Hotkeys
        self.kb_thread = KeyboardThread()
        self.kb_thread.hotkey_pressed.connect(self.handle_hotkey)
        self.kb_thread.start()
        
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
        
        self.title_label = QLabel("STEALTH ASSISTANT")
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

        # --- Chat Area ---
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                border: 2px solid rgba(0, 0, 0, 0.05);
                color: #1A2E2A;
                font-size: 14px;
                padding: 15px;
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

    def end_interview_flow(self):
        self.end_btn.setText("⏳ GENERATING AI INSIGHTS...")
        self.end_btn.setEnabled(False)
        self.log_message("<span style='color:#D32F2F;'>[SYSTEM] Closing session and analyzing intelligence...</span>")
        
        # We run report generation in a simple thread to avoid UI freeze
        def process_report():
            report_data = ai_engine.generate_interview_report()
            user = auth_manager.current_user
            if user:
                history_manager.save_interview(user, report_data)
            self.close()

        import threading
        threading.Thread(target=process_report).start()

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
        elif key == "move_up":
            self.move(self.x(), self.y() - 50)
        elif key == "move_down":
            self.move(self.x(), self.y() + 50)
        elif key == "move_left":
            self.move(self.x() - 50, self.y())
        elif key == "move_right":
            self.move(self.x() + 50, self.y())

    def toggle_stealth(self):
        self.is_stealth = not self.is_stealth
        hwnd = self.winId().__int__()
        stealth_engine.set_stealth_mode(hwnd, self.is_stealth)
        self.update_stealth_button_style()
        self.log_message(f"<span style='color:gray;'>[SYSTEM] Stealth Mode {'ENABLED' if self.is_stealth else 'DISABLED'}</span>")

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
        """Action trigger for rapid-fire MCQ testing."""
        self.screen_btn.setText("ANALYZING...")
        self.screen_btn.setStyleSheet("background: #6200EA; color: white; border-radius: 15px; padding: 12px; font-weight: 900;")
        self.log_message("<span style='color:#6200EA;'>[SYSTEM] Capture & Analyze in progress...</span>")
        
        # Start analysis in background
        path = vision_handler.capture_fullscreen()
        query = "Solve EVERY question on screen. Start each answer on a NEW LINE."
        self.ai_worker = AIWorker(query, mode="vision", image_path=path)
        self.ai_worker.finished.connect(self.handle_vision_finished)
        self.ai_worker.start()

    def handle_vision_finished(self, sender, message):
        """Resets the button after analysis is complete."""
        self.log_message(f"<span style='color:#7C4DFF;'><b>AI (Savant Eye):</b> {message}</span>")
        self.screen_btn.setText("READ SCREEN: OFF")
        self.screen_btn.setStyleSheet("background: rgba(255, 255, 255, 0.5); color: #007E44; border-radius: 15px; padding: 12px; font-weight: 900;")

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
        # Automatically get AI response for interviewer voice
        self.ai_worker = AIWorker(text, mode="text")
        self.ai_worker.finished.connect(self.handle_ai_voice_finished)
        self.ai_worker.start()

    def handle_ai_voice_finished(self, sender, message):
        self.log_message(f"<span style='color:#007E44;'><b>AI (Voice Response):</b> {message}</span>")

    def handle_user_input(self):
        text = self.input_field.text().strip()
        if text:
            self.log_message(f"<span style='color:#D4AF37;'><b>YOU:</b> {text}</span>")
            self.input_field.clear()
            self.ai_worker = AIWorker(text, mode="text")
            self.ai_worker.finished.connect(self.handle_ai_finished)
            self.ai_worker.start()
        else:
            # Empty ENTER key press: Manually flush the audio buffer and trigger AI!
            if self.is_listening:
                self.audio_thread.flush_now()

    def handle_ai_finished(self, sender, message):
        self.log_message(f"<span style='color:#007E44;'><b>AI (Manual Input):</b> {message}</span>")

    def log_message(self, message):
        formatted_message = message.replace("\n", "<br>")
        # Add extra vertical spacing between messages for readability
        spacer = "<br><br>" if self.chat_display.toPlainText().strip() else ""
        self.chat_display.append(f"{spacer}{formatted_message}")
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
