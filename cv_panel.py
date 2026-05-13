import os
import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, 
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

class HistoryWorker(QThread):
    finished = pyqtSignal(list)
    def __init__(self, user):
        super().__init__()
        self.user = user
    def run(self):
        history = history_manager.get_user_history(self.user)
        self.finished.emit(history or [])

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
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 16px;
            }
            #interviewCard:hover {
                border: 1px solid #10B981;
                background: #F0FDF4;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        
        date_lbl = QLabel(data['date'])
        date_lbl.setStyleSheet("color: #64748B; font-weight: 700; font-size: 11px; background: transparent;")
        date_lbl.setWordWrap(True)
        layout.addWidget(date_lbl)
        
        # Truncate summary to just a few key words for a "Status" feel
        summary_text = data.get('summary', 'Session Complete')
        short_status = " ".join(summary_text.split()[:8]) + ("..." if len(summary_text.split()) > 8 else "")
        
        sum_lbl = QLabel(short_status)
        sum_lbl.setStyleSheet("color: #1E293B; font-size: 13px; font-weight: 600; background: transparent;")
        sum_lbl.setWordWrap(True)
        layout.addWidget(sum_lbl)
        
        layout.addStretch()
        
        view_btn = QPushButton("View Report")
        view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_btn.setStyleSheet("""
            QPushButton {
                background: #F1F5F9;
                color: #475569;
                border-radius: 8px;
                padding: 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover { background: #10B981; color: white; }
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
    cv_submitted = pyqtSignal(str, str, str, str) # CV, JD, Link, LinkedIn
    logout_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedSize(1000, 700)
        
        self.cv_text = ""
        self.init_ui()
        self.old_pos = None
        
        # Protection Layers
        from main import MaintenanceThread, MaintenanceOverlay, SuspendedOverlay
        self.maint_overlay = MaintenanceOverlay(self.main_container)
        self.suspended_overlay = SuspendedOverlay(self.main_container)
        
        self.maint_thread = MaintenanceThread()
        self.maint_thread.status_changed.connect(self.handle_system_status_update)
        self.maint_thread.start()

    def handle_system_status_update(self, status):
        print(f"[Status] Suspended: {status.get('suspended')} | Email: {status.get('email')}")
        # 1. Check Suspension
        if status.get("suspended"):
            self.launch_btn.setEnabled(False)
            self.upload_btn.setEnabled(False)
            self.suspended_overlay.show_suspended(status.get("email", "Unknown"))
            return
        else:
            self.suspended_overlay.hide()

        # 2. Check Maintenance
        if status.get("maintenance_mode"):
            self.maint_overlay.show_maintenance(status.get("maintenance_message", "Strategic calibration in progress..."))
            self.launch_btn.setEnabled(False)
            self.upload_btn.setEnabled(False)
        else:
            self.maint_overlay.hide()
            self.validate_input()
            self.upload_btn.setEnabled(True)

    def handle_maintenance_update(self, active, message):
        # Deprecated: replaced by handle_system_status_update
        pass

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
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.root_layout)

        # Main Container
        self.main_container = QFrame()
        self.main_container.setObjectName("mainContainer")
        self.main_container.setStyleSheet("""
            #mainContainer {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 12px;
            }
        """)
        self.root_layout.addWidget(self.main_container)
        
        self.container_layout = QVBoxLayout(self.main_container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)

        # TOP NAVIGATION
        self.nav_bar = QFrame()
        self.nav_bar.setFixedHeight(80)
        self.nav_bar.setStyleSheet("background-color: #FFFFFF; border-bottom: 1px solid #F1F5F9; border-top-left-radius: 12px; border-top-right-radius: 12px;")
        self.nav_layout = QHBoxLayout(self.nav_bar)
        self.nav_layout.setContentsMargins(40, 0, 40, 0)

        self.greet_label = QLabel(self.get_greeting())
        self.greet_label.setStyleSheet("color: #0F172A; font-size: 22px; font-weight: 800;")
        self.nav_layout.addWidget(self.greet_label)

        # Trial / Premium Indicator
        self.trial_label = QLabel()
        self.update_trial_status()
        self.nav_layout.addWidget(self.trial_label)

        self.nav_layout.addStretch()

        # Logout Button
        self.logout_btn = QPushButton("Log Out")
        self.logout_btn.setFixedSize(100, 36)
        self.logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logout_btn.setStyleSheet("""
            QPushButton { background: #F1F5F9; color: #475569; border-radius: 10px; font-weight: 700; font-size: 13px; }
            QPushButton:hover { background: #E2E8F0; color: #1E293B; }
        """)
        self.logout_btn.clicked.connect(self.handle_logout)
        self.nav_layout.addWidget(self.logout_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(36, 36)
        self.close_btn.setStyleSheet("""
            QPushButton { background: #F8FAFC; color: #94A3B8; border-radius: 18px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background: #FEE2E2; color: #DC2626; }
        """)
        self.close_btn.clicked.connect(self.close)
        self.nav_layout.addWidget(self.close_btn)
        
        self.container_layout.addWidget(self.nav_bar)

        # DASHBOARD CONTENT (GRID SPLIT)
        self.dashboard_frame = QFrame()
        self.dashboard_layout = QHBoxLayout(self.dashboard_frame)
        self.dashboard_layout.setContentsMargins(30, 30, 30, 30)
        self.dashboard_layout.setSpacing(30)

        # --- LEFT COLUMN: THE LABORATORY (INPUTS) ---
        self.left_col = QFrame()
        self.left_col.setFixedWidth(450)
        self.left_layout = QVBoxLayout(self.left_col)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(20)

        # CV Card
        self.cv_card = QFrame()
        self.cv_card.setStyleSheet("background-color: #FFFFFF; border: 1px solid #F1F5F9; border-radius: 12px;")
        self.cv_layout = QVBoxLayout(self.cv_card)
        self.cv_layout.setContentsMargins(25, 25, 25, 25)
        
        cv_label = QLabel("YOUR EXPERIENCE")
        cv_label.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 800; letter-spacing: 1.5px;")
        self.cv_layout.addWidget(cv_label)

        self.upload_btn = QPushButton("📄 Upload Resume (PDF)")
        self.upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.upload_btn.setStyleSheet("""
            QPushButton { background: #F8FAFC; color: #475569; border: 2px dashed #E2E8F0; border-radius: 10px; padding: 18px; font-weight: 700; font-size: 13px; }
            QPushButton:hover { border-color: #10B981; color: #059669; background: #F0FDF4; }
        """)
        self.upload_btn.clicked.connect(self.handle_upload)
        self.cv_layout.addWidget(self.upload_btn)

        self.text_area = QTextEdit()
        self.text_area.setPlaceholderText("Or paste your resume text here...")
        self.text_area.setMaximumHeight(100)
        self.text_area.setStyleSheet("QTextEdit { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 12px; font-size: 13px; color: #1E293B; } QTextEdit:focus { border: 2px solid #10B981; background: #FFFFFF; }")
        self.cv_layout.addWidget(self.text_area)
        self.left_layout.addWidget(self.cv_card)

        # JD Card
        self.jd_card = QFrame()
        self.jd_card.setStyleSheet("background-color: #FFFFFF; border: 1px solid #F1F5F9; border-radius: 12px;")
        self.jd_layout = QVBoxLayout(self.jd_card)
        self.jd_layout.setContentsMargins(25, 25, 25, 25)
        
        jd_label = QLabel("JOB DETAILS")
        jd_label.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 800; letter-spacing: 1.5px;")
        self.jd_layout.addWidget(jd_label)

        self.jd_area = QTextEdit()
        self.jd_area.setPlaceholderText("Paste the Job Description...")
        self.jd_area.setStyleSheet("QTextEdit { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 12px; font-size: 13px; color: #1E293B; } QTextEdit:focus { border: 2px solid #10B981; background: #FFFFFF; }")
        self.jd_layout.addWidget(self.jd_area)
        
        self.link_field = QLineEdit()
        self.link_field.setPlaceholderText("Company Website Link")
        self.link_field.setStyleSheet("QLineEdit { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 14px; font-size: 13px; color: #1E293B; } QLineEdit:focus { border: 2px solid #10B981; background: #FFFFFF; }")
        self.jd_layout.addWidget(self.link_field)

        self.linkedin_field = QLineEdit()
        self.linkedin_field.setPlaceholderText("Your LinkedIn Profile (Optional)")
        self.linkedin_field.setStyleSheet("QLineEdit { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 14px; font-size: 13px; color: #1E293B; } QLineEdit:focus { border: 2px solid #10B981; background: #FFFFFF; }")
        self.jd_layout.addWidget(self.linkedin_field)
        self.left_layout.addWidget(self.jd_card)

        self.dashboard_layout.addWidget(self.left_col)

        # --- RIGHT COLUMN: THE HUB (ACTIVITY & LAUNCH) ---
        self.right_col = QFrame()
        self.right_layout = QVBoxLayout(self.right_col)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(20)

        # Recent Activity
        self.activity_card = QFrame()
        self.activity_card.setStyleSheet("background-color: #FFFFFF; border: 1px solid #F1F5F9; border-radius: 12px;")
        self.activity_layout = QVBoxLayout(self.activity_card)
        self.activity_layout.setContentsMargins(25, 25, 25, 25)
        
        act_label = QLabel("RECENT INTERVIEWS")
        act_label.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 800; letter-spacing: 1.5px;")
        self.activity_layout.addWidget(act_label)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(10)
        self.refresh_history()
        self.scroll.setWidget(self.scroll_content)
        self.activity_layout.addWidget(self.scroll)
        self.right_layout.addWidget(self.activity_card)

        # Launch Card
        self.launch_card = QFrame()
        self.launch_card.setFixedHeight(120)
        self.launch_card.setStyleSheet("background-color: #FFFFFF; border: 1px solid #F1F5F9; border-radius: 12px;")
        self.launch_layout = QVBoxLayout(self.launch_card)
        self.launch_layout.setContentsMargins(25, 25, 25, 25)
        
        self.launch_btn = QPushButton("Start Interview Assistant")
        self.launch_btn.setEnabled(False)
        self.launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launch_btn.setStyleSheet("""
            QPushButton:enabled { background-color: #059669; color: #FFFFFF; border-radius: 10px; font-weight: 800; font-size: 16px; padding: 18px; }
            QPushButton:enabled:hover { background-color: #047857; }
            QPushButton:disabled { background-color: #F1F5F9; color: #94A3B8; border-radius: 10px; font-weight: 800; padding: 18px; }
        """)
        self.text_area.textChanged.connect(self.validate_input)
        self.launch_btn.clicked.connect(self.handle_launch_or_upgrade)
        self.launch_layout.addWidget(self.launch_btn)
        
        self.right_layout.addWidget(self.launch_card)
        self.dashboard_layout.addWidget(self.right_col)
        
        self.container_layout.addWidget(self.dashboard_frame)
        
        # Live Timer for Trial
        from PyQt6.QtCore import QTimer
        self.trial_timer = QTimer(self)
        self.trial_timer.timeout.connect(self.update_trial_status)
        self.trial_timer.start(60000) # Update every minute

    def refresh_history(self):
        # Clear existing
        for i in reversed(range(self.scroll_layout.count())): 
            item = self.scroll_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        
        self.history_placeholder = QLabel("Loading history...")
        self.history_placeholder.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: bold; padding: 20px;")
        self.scroll_layout.addWidget(self.history_placeholder)
        
        user = auth_manager.current_user
        if user:
            self.history_worker = HistoryWorker(user)
            self.history_worker.finished.connect(self.on_history_loaded)
            self.history_worker.start()
        else:
            self.on_history_loaded([])

    def on_history_loaded(self, history):
        if hasattr(self, 'history_placeholder') and self.history_placeholder:
            self.history_placeholder.setParent(None)
            self.history_placeholder = None
            
        if history:
            for entry in history:
                card = InterviewCard(entry)
                self.scroll_layout.addWidget(card)
        else:
            placeholder = QLabel("No interviews yet. Launch HUD to begin!")
            placeholder.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: bold; padding: 20px;")
            self.scroll_layout.addWidget(placeholder)
        self.scroll_layout.addStretch()

    def update_trial_status(self):
        if auth_manager.tier == "PRO":
            self.trial_label.setText("✨ PREMIUM ACCOUNT")
            self.trial_label.setStyleSheet("color: #6200EA; font-size: 11px; font-weight: 800; background: #EDE7F6; padding: 5px 12px; border-radius: 10px;")
            return

        # Calculate days left
        try:
            if auth_manager.trial_expiry:
                expiry = datetime.datetime.fromisoformat(auth_manager.trial_expiry)
                now = datetime.datetime.utcnow()
                diff = expiry - now
                days = diff.days
                hours = diff.seconds // 3600
                
                if diff.total_seconds() <= 0:
                    self.trial_label.setText("⚠️ TRIAL EXPIRED")
                    self.trial_label.setStyleSheet("color: #D32F2F; font-size: 11px; font-weight: 800; background: #FFEBEE; padding: 5px 12px; border-radius: 10px;")
                else:
                    self.trial_label.setText(f"⏳ {days}d {hours}h LEFT")
                    self.trial_label.setStyleSheet("color: #059669; font-size: 11px; font-weight: 800; background: #F0FDF4; padding: 5px 12px; border-radius: 10px;")
            else:
                self.trial_label.setText("TRIAL MODE")
                self.trial_label.setStyleSheet("color: #475569; font-size: 11px; font-weight: 800; background: #F1F5F9; padding: 5px 12px; border-radius: 10px;")
        except:
            self.trial_label.setText("TRIAL MODE")

    def is_expired(self):
        if auth_manager.tier == "PRO": return False
        try:
            if auth_manager.trial_expiry:
                expiry = datetime.datetime.fromisoformat(auth_manager.trial_expiry)
                return datetime.datetime.utcnow() > expiry
        except:
            pass
        return False

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
            self.upload_btn.setStyleSheet(self.upload_btn.styleSheet().replace("dashed #CBD5E1", "solid #10B981"))
            self.validate_input()
        else:
            self.upload_btn.setText(f"❌ Error: {text[:20]}...")

    def validate_input(self):
        has_content = len(self.text_area.toPlainText().strip()) > 1 or len(self.cv_text.strip()) > 1
        
        if self.is_expired():
            self.launch_btn.setEnabled(True)
            self.launch_btn.setText("💎 UPGRADE TO PREMIUM")
            self.launch_btn.setStyleSheet("""
                QPushButton { background-color: #6200EA; color: #FFFFFF; border-radius: 10px; font-weight: 800; font-size: 16px; padding: 18px; }
                QPushButton:hover { background-color: #4527A0; }
            """)
        else:
            self.launch_btn.setEnabled(has_content)
            self.launch_btn.setText("Start Interview Assistant")
            self.launch_btn.setStyleSheet("""
                QPushButton:enabled { background-color: #059669; color: #FFFFFF; border-radius: 10px; font-weight: 800; font-size: 16px; padding: 18px; }
                QPushButton:enabled:hover { background-color: #047857; }
                QPushButton:disabled { background-color: #F1F5F9; color: #94A3B8; border-radius: 10px; font-weight: 800; padding: 18px; }
            """)

    def handle_launch_or_upgrade(self):
        if self.is_expired():
            # Dynamically fetch checkout URL from config
            try:
                res = requests.get(f"{auth_manager.backend_url}/api/admin/config", timeout=5)
                config = res.json()
                checkout_url = config.get("CHECKOUT_URL", "https://stealthhud.com/upgrade")
                webbrowser.open(checkout_url)
            except:
                webbrowser.open("https://stealthhud.com/upgrade")
            return
        
        self.handle_launch()

    def handle_launch(self):
        final_cv = self.text_area.toPlainText().strip() or self.cv_text
        final_jd = self.jd_area.toPlainText().strip()
        final_link = self.link_field.text().strip()
        final_linkedin = self.linkedin_field.text().strip()
        self.cv_submitted.emit(final_cv, final_jd, final_link, final_linkedin)
        self.close()

    def handle_logout(self):
        auth_manager.logout()
        # Emit signal to let the launcher return to the login window
        self.logout_requested.emit()

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
