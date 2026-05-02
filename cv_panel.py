import os
import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                             QPushButton, QLabel, QFrame, QFileDialog, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QFont, QLinearGradient

try:
    import fitz  # PyMuPDF
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

from auth_manager import auth_manager
from history_manager import history_manager
import datetime
import webbrowser
import tempfile
from PyQt6.QtWidgets import QScrollArea

class PDFWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            doc = fitz.open(self.file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            self.finished.emit(True, text)
        except Exception as e:
            self.finished.emit(False, str(e))

class InterviewCard(QFrame):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.setFixedSize(200, 160)
        self.setObjectName("interviewCard")
        self.setStyleSheet("""
            #interviewCard {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
            }
            #interviewCard:hover {
                background: rgba(0, 230, 118, 0.1);
                border: 1px solid rgba(0, 230, 118, 0.3);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        date_lbl = QLabel(data['date'])
        date_lbl.setStyleSheet("color: #D4AF37; font-weight: bold; font-size: 11px; background: transparent;")
        date_lbl.setWordWrap(True)
        layout.addWidget(date_lbl)
        
        sum_lbl = QLabel(data['summary'][:60] + "...")
        sum_lbl.setStyleSheet("color: rgba(0, 0, 0, 0.6); font-size: 10px; background: transparent;")
        sum_lbl.setWordWrap(True)
        layout.addWidget(sum_lbl)
        
        layout.addStretch()
        
        view_btn = QPushButton("VIEW INSIGHTS")
        view_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 126, 68, 0.1);
                color: #007E44;
                border-radius: 10px;
                padding: 5px;
                font-size: 9px;
                font-weight: 900;
            }
            QPushButton:hover { background: #007E44; color: white; }
        """)
        view_btn.clicked.connect(self.open_insights)
        layout.addWidget(view_btn)

    def open_insights(self):
        html = history_manager.generate_summary_html(self.data['id'])
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html') as f:
            f.write(html)
            path = f.name
        webbrowser.open('file://' + path)

class UserDashboard(QWidget):
    cv_submitted = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFixedSize(550, 750)
        
        self.cv_text = ""
        self.init_ui()
        self.old_pos = None

    def get_greeting(self):
        hour = datetime.datetime.now().hour
        user = auth_manager.current_user_name or "Candidate"
        if hour < 12: greeting = "Good Morning"
        elif hour < 18: greeting = "Good Afternoon"
        else: greeting = "Good Evening"
        return f"{greeting}, {user}"

    def init_ui(self):
        # Main Layout
        self.root_layout = QVBoxLayout()
        self.root_layout.setContentsMargins(30, 30, 30, 30)
        self.setLayout(self.root_layout)

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
        self.root_layout.addWidget(self.glass_panel)
        
        panel_layout = QVBoxLayout(self.glass_panel)
        panel_layout.setContentsMargins(50, 50, 50, 50)
        panel_layout.setSpacing(25)

        # --- Dashboard Greeting ---
        self.greet_label = QLabel(self.get_greeting())
        self.greet_label.setStyleSheet("color: #007E44; font-size: 24px; font-weight: 900; background: transparent;")
        panel_layout.addWidget(self.greet_label)

        # --- Recent Interviews Section ---
        hist_label = QLabel("RECENT INTERVIEWS")
        hist_label.setStyleSheet("color: rgba(0, 0, 0, 0.4); font-size: 11px; font-weight: 900; letter-spacing: 2px;")
        panel_layout.addWidget(hist_label)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.scroll.setFixedHeight(180)
        
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.scroll_layout = QHBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(15)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        
        self.refresh_history()
        
        self.scroll.setWidget(self.scroll_content)
        panel_layout.addWidget(self.scroll)

        # --- CV Management Section ---
        cv_label = QLabel("CV MANAGEMENT")
        cv_label.setStyleSheet("color: rgba(0, 0, 0, 0.4); font-size: 11px; font-weight: 900; letter-spacing: 2px;")
        panel_layout.addWidget(cv_label)

        # PDF Upload Section
        self.upload_btn = QPushButton("📄 UPLOAD CV (PDF)")
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 0, 0, 0.05);
                color: #000000;
                border: 2px dashed rgba(0, 0, 0, 0.1);
                border-radius: 25px;
                padding: 15px;
                font-weight: 900;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(0, 230, 118, 0.1);
                border: 2px dashed rgba(0, 230, 118, 0.4);
            }
        """)
        self.upload_btn.clicked.connect(self.handle_upload)
        panel_layout.addWidget(self.upload_btn)

        # Text Area
        self.text_area = QTextEdit()
        self.text_area.setPlaceholderText("Paste your CV text here to sync AI brain...")
        self.text_area.setStyleSheet("""
            QTextEdit {
                background: rgba(255, 255, 255, 0.5);
                border: 2px solid rgba(0, 0, 0, 0.05);
                border-radius: 30px;
                padding: 15px;
                color: #000000;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 2px solid rgba(0, 230, 118, 0.3);
            }
        """)
        self.text_area.textChanged.connect(self.validate_input)
        panel_layout.addWidget(self.text_area)

        # Launch Button
        self.launch_btn = QPushButton("LAUNCH STEALTH HUD")
        self.launch_btn.setEnabled(False)
        self.launch_btn.setStyleSheet("""
            QPushButton:enabled {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007E44, stop:1 #00B0FF);
                color: white;
                border-radius: 25px;
                padding: 15px;
                font-weight: 900;
                letter-spacing: 2px;
            }
            QPushButton:disabled {
                background: rgba(0, 0, 0, 0.1);
                color: rgba(0, 0, 0, 0.3);
                border-radius: 25px;
                padding: 15px;
                font-weight: 900;
            }
        """)
        self.launch_btn.clicked.connect(self.handle_launch)
        panel_layout.addWidget(self.launch_btn)
        # Close Button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(45, 45)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 0, 0, 0.05);
                color: #000000;
                border-radius: 22px;
                font-size: 20px;
            }
            QPushButton:hover {
                background: rgba(211, 47, 47, 0.2);
                color: #D32F2F;
            }
        """)
        close_btn.clicked.connect(self.close)
        close_btn.move(430, 25)
        close_btn.setParent(self.glass_panel)

    def refresh_history(self):
        # Clear existing
        for i in reversed(range(self.scroll_layout.count())): 
            item = self.scroll_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        
        user = auth_manager.current_user
        if user:
            history = history_manager.get_user_history(user)
            if history:
                for entry in history:
                    card = InterviewCard(entry)
                    self.scroll_layout.addWidget(card)
            else:
                placeholder = QLabel("No interviews yet. Launch HUD to begin!")
                placeholder.setStyleSheet("color: rgba(0,0,0,0.3); font-size: 12px; font-weight: bold;")
                self.scroll_layout.addWidget(placeholder)
        self.scroll_layout.addStretch()

    def handle_upload(self):
        # Use Non-Native dialog for better stability on transparent frameless windows
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CV PDF", "", "PDF Files (*.pdf)", 
            options=QFileDialog.Option.DontUseNativeDialog
        )
        
        if file_path:
            if not HAS_PDF:
                self.upload_btn.setText("❌ PDF Library Missing")
                return

            self.upload_btn.setText("⏳ SYNCING CV...")
            self.upload_btn.setEnabled(False)
            
            self.pdf_worker = PDFWorker(file_path)
            self.pdf_worker.finished.connect(lambda success, text: self.on_pdf_finished(success, text, file_path))
            self.pdf_worker.start()

    def on_pdf_finished(self, success, text, file_path):
        self.upload_btn.setEnabled(True)
        if success:
            self.cv_text = text
            self.upload_btn.setText(f"✅ {os.path.basename(file_path)} SYNCED")
            self.upload_btn.setStyleSheet(self.upload_btn.styleSheet().replace("dashed rgba(0, 0, 0, 0.1)", "solid #00E676"))
            self.validate_input()
        else:
            self.upload_btn.setText(f"❌ Error: {text[:20]}...")

    def validate_input(self):
        has_content = len(self.text_area.toPlainText().strip()) > 1 or len(self.cv_text.strip()) > 1
        self.launch_btn.setEnabled(has_content)

    def handle_launch(self):
        final_text = self.text_area.toPlainText().strip() or self.cv_text
        self.cv_submitted.emit(final_text)
        self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None
