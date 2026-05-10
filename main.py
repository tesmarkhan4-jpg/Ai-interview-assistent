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
    from keys import is_already_running
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

    def run(self):
        full_response = ""
        if self.mode == "text":
            try:
                for chunk in ai_engine.get_ai_response_stream(self.query, provider="groq"):
                    if chunk:
                        full_response += chunk
                        self.chunk_received.emit("AI", chunk)
            except Exception as e:
                full_response = f"Intelligence Stream Error: {str(e)}"
                self.chunk_received.emit("AI", full_response)
        elif self.mode == "vision":
            full_response = ai_engine.analyze_screen(self.image_path, self.query)
            self.chunk_received.emit("AI", full_response)
        
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
        """Action trigger for rapid-fire MCQ testing or code solving."""
        self.screen_btn.setText("ANALYZING...")
        self.screen_btn.setStyleSheet("background: #6200EA; color: white; border-radius: 15px; padding: 12px; font-weight: 900;")
        self.log_message("<span style='color:#6200EA;'>[SYSTEM] Capture & Analyze in progress...</span>")
        
        # Start analysis in background
        path = vision_handler.capture_fullscreen()
        
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
        self.log_message(f"<span style='color:#7C4DFF;'><b>AI (Savant Eye):</b> {message}</span>")
        self.screen_btn.setText("READ SCREEN: OFF")
        self.screen_btn.setStyleSheet("background: rgba(255, 255, 255, 0.5); color: #007E44; border-radius: 15px; padding: 12px; font-weight: 900;")

    def perform_screen_analysis(self):
        path = vision_handler.capture_fullscreen()
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
                self.active_worker.chunk_received.disconnect()
            except: pass
            try:
                self.active_worker.finished.disconnect()
            except: pass
            
            try:
                self.active_worker.terminate()
                self.active_worker.wait(500)
            except: pass
        
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
    if is_already_running():
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "ZenithHUD is already operational on this system.", "Instance Conflict", 16)
        sys.exit(0)
        
    app = QApplication(sys.argv)
    
    # Auth Check
    from auth_manager import auth_manager
    from login_window import LoginWindow
    
    if not auth_manager.current_user:
        # Show Login Screen if no session
        login = LoginWindow()
        login.show()
    else:
        # Show Main App if session exists
        window = StealthHUD()
        window.show()
        
    sys.exit(app.exec())
