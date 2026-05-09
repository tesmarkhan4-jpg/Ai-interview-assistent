import sys
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QPushButton, QLabel, QFrame, QApplication, QStackedWidget)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint, QThread, QTimer
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPalette, QBrush, QPixmap
from auth_manager import auth_manager

class LoginWorker(QThread):
    finished = pyqtSignal(bool, str)
    def __init__(self, email, pw):
        super().__init__()
        self.email = email
        self.pw = pw
        
    def run(self):
        success, msg = auth_manager.login(self.email, self.pw)
        self.finished.emit(success, msg)

class LoginWindow(QWidget):
    login_success = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedSize(900, 600)
        
        self.init_ui()
        self.old_pos = None
        
        # Temp storage for multi-step flows
        self.pending_name = ""
        self.pending_email = ""
        self.pending_pass = ""
        
        # Login Animation setup
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_loading_text)
        self.anim_dots = 0

    def init_ui(self):
        # Main Layout (Horizontal Split)
        self.root_layout = QHBoxLayout()
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)
        self.setLayout(self.root_layout)

        # LEFT PANEL (BRAND ZONE)
        self.left_panel = QFrame()
        self.left_panel.setFixedWidth(400)
        self.left_panel.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F0FDF4, stop:1 #D1FAE5);
                border-top-left-radius: 12px;
                border-bottom-left-radius: 12px;
                border-right: 1px solid #E2E8F0;
            }
        """)
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(40, 60, 40, 60)
        
        # 3D Transparent Logo
        self.logo_label = QLabel()
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        logo_path = os.path.join(base_path, "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)
        else:
            self.logo_label.setText("🧠")
            self.logo_label.setStyleSheet("color: #059669; font-size: 120px;")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_layout.addWidget(self.logo_label)

        self.left_layout.addStretch()
        
        brand_title = QLabel("STEALTH ASSIST")
        brand_title.setStyleSheet("color: #064E3B; font-size: 28px; font-weight: 900; letter-spacing: 2px;")
        self.left_layout.addWidget(brand_title)
        
        brand_desc = QLabel("Autonomous Intelligence for\nHigh-Stakes Career Strategy.")
        brand_desc.setStyleSheet("color: #047857; font-size: 14px; font-weight: 600; line-height: 1.5;")
        self.left_layout.addWidget(brand_desc)
        
        self.root_layout.addWidget(self.left_panel)

        # RIGHT PANEL (FORM ZONE)
        self.right_panel = QFrame()
        self.right_panel.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(60, 40, 60, 40)
        
        # Close Button (Top Right)
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #94A3B8; border-radius: 16px; font-size: 16px; font-weight: bold; }
            QPushButton:hover { background: #F1F5F9; color: #0F172A; }
        """)
        self.close_btn.clicked.connect(self.close)
        self.close_btn.move(450, 15)
        self.close_btn.setParent(self.right_panel)

        self.right_layout.addStretch()
        
        form_title = QLabel("Welcome Back")
        form_title.setStyleSheet("color: #0F172A; font-size: 24px; font-weight: 700;")
        self.right_layout.addWidget(form_title)
        
        form_sub = QLabel("Please sign in to your command center")
        form_sub.setStyleSheet("color: #64748B; font-size: 14px; margin-bottom: 20px;")
        self.right_layout.addWidget(form_sub)

        # Dynamic View Container
        self.view_container = QStackedWidget()
        self.right_layout.addWidget(self.view_container)

        self.setup_login_view()
        self.setup_signup_view()
        self.setup_otp_view()
        self.setup_forgot_view()
        self.setup_reset_view()

        self.right_layout.addStretch()
        
        # Status Label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #EF4444; font-size: 13px; font-weight: 600;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_layout.addWidget(self.status_label)

        self.root_layout.addWidget(self.right_panel)
        self.view_container.setCurrentIndex(0)

    def get_input_style(self):
        return """
            QLineEdit {
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 14px;
                color: #1E293B;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #10B981;
                background: #FFFFFF;
            }
        """

    def get_btn_style(self, primary=True):
        if primary:
            return """
                QPushButton {
                    background-color: #059669;
                    color: #FFFFFF;
                    border-radius: 8px;
                    padding: 16px;
                    font-weight: 700;
                    font-size: 14px;
                }
                QPushButton:hover { background-color: #047857; }
                QPushButton:pressed { background-color: #065F46; }
            """
        else:
            return """
                QPushButton {
                    background: transparent;
                    color: #059669;
                    font-weight: 600;
                    font-size: 13px;
                }
                QPushButton:hover { color: #047857; text-decoration: underline; }
            """

    def setup_login_view(self):
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setSpacing(15)

        self.login_email = QLineEdit()
        self.login_email.setPlaceholderText("Email Address")
        self.login_email.setStyleSheet(self.get_input_style())
        layout.addWidget(self.login_email)

        self.login_pass = QLineEdit()
        self.login_pass.setPlaceholderText("Password")
        self.login_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_pass.setStyleSheet(self.get_input_style())
        layout.addWidget(self.login_pass)

        forgot_btn = QPushButton("Forgot Password?")
        forgot_btn.setStyleSheet(self.get_btn_style(False))
        forgot_btn.clicked.connect(lambda: self.view_container.setCurrentIndex(3))
        layout.addWidget(forgot_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.login_btn = QPushButton("SIGN IN")
        self.login_btn.setStyleSheet(self.get_btn_style())
        self.login_btn.clicked.connect(self.handle_login)
        layout.addWidget(self.login_btn)

        switch_btn = QPushButton("Need an account? Create one")
        switch_btn.setStyleSheet(self.get_btn_style(False))
        switch_btn.clicked.connect(lambda: self.view_container.setCurrentIndex(1))
        layout.addWidget(switch_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.view_container.addWidget(view)

    def setup_signup_view(self):
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setSpacing(15)

        self.reg_name = QLineEdit()
        self.reg_name.setPlaceholderText("Full Name")
        self.reg_name.setStyleSheet(self.get_input_style())
        layout.addWidget(self.reg_name)

        self.reg_email = QLineEdit()
        self.reg_email.setPlaceholderText("Email Address")
        self.reg_email.setStyleSheet(self.get_input_style())
        layout.addWidget(self.reg_email)

        self.reg_pass = QLineEdit()
        self.reg_pass.setPlaceholderText("Password")
        self.reg_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.reg_pass.setStyleSheet(self.get_input_style())
        layout.addWidget(self.reg_pass)

        reg_btn = QPushButton("GET VERIFICATION CODE")
        reg_btn.setStyleSheet(self.get_btn_style())
        reg_btn.clicked.connect(self.handle_start_register)
        layout.addWidget(reg_btn)

        switch_btn = QPushButton("Already have an account? Sign in")
        switch_btn.setStyleSheet(self.get_btn_style(False))
        switch_btn.clicked.connect(lambda: self.view_container.setCurrentIndex(0))
        layout.addWidget(switch_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.view_container.addWidget(view)

    def setup_otp_view(self):
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setSpacing(15)

        instr = QLabel("Enter the 6-digit code sent to your email")
        instr.setStyleSheet("color: rgba(0,0,0,0.6); font-size: 11px; font-weight: bold;")
        instr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instr)

        self.otp_input = QLineEdit()
        self.otp_input.setPlaceholderText("OTP CODE")
        self.otp_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.otp_input.setStyleSheet(self.get_input_style() + "QLineEdit { font-size: 24px; letter-spacing: 10px; font-weight: 900; }")
        layout.addWidget(self.otp_input)

        verify_btn = QPushButton("VERIFY & REGISTER")
        verify_btn.setStyleSheet(self.get_btn_style())
        verify_btn.clicked.connect(self.handle_verify_register)
        layout.addWidget(verify_btn)

        back_btn = QPushButton("Back to Sign Up")
        back_btn.setStyleSheet(self.get_btn_style(False))
        back_btn.clicked.connect(lambda: self.view_container.setCurrentIndex(1))
        layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.view_container.addWidget(view)

    def setup_forgot_view(self):
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setSpacing(15)

        self.forgot_email = QLineEdit()
        self.forgot_email.setPlaceholderText("Registered Email")
        self.forgot_email.setStyleSheet(self.get_input_style())
        layout.addWidget(self.forgot_email)

        send_btn = QPushButton("SEND RESET CODE")
        send_btn.setStyleSheet(self.get_btn_style())
        send_btn.clicked.connect(self.handle_send_reset)
        layout.addWidget(send_btn)

        back_btn = QPushButton("Back to Sign In")
        back_btn.setStyleSheet(self.get_btn_style(False))
        back_btn.clicked.connect(lambda: self.view_container.setCurrentIndex(0))
        layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.view_container.addWidget(view)

    def setup_reset_view(self):
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setSpacing(15)

        self.reset_otp = QLineEdit()
        self.reset_otp.setPlaceholderText("OTP CODE")
        self.reset_otp.setStyleSheet(self.get_input_style())
        layout.addWidget(self.reset_otp)

        self.reset_pass = QLineEdit()
        self.reset_pass.setPlaceholderText("New Password")
        self.reset_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.reset_pass.setStyleSheet(self.get_input_style())
        layout.addWidget(self.reset_pass)

        reset_btn = QPushButton("RESET PASSWORD")
        reset_btn.setStyleSheet(self.get_btn_style())
        reset_btn.clicked.connect(self.handle_finish_reset)
        layout.addWidget(reset_btn)

        self.view_container.addWidget(view)

    def show_msg(self, text, error=True):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {'#D32F2F' if error else '#00E676'}; font-size: 13px; font-weight: bold;")

    def handle_login(self):
        email = self.login_email.text()
        pw = self.login_pass.text()
        if not email or not pw:
            self.show_msg("Email and Password required.")
            return
        
        # Disable button and start animation
        self.login_btn.setEnabled(False)
        self.login_btn.setText("LOGGING IN")
        self.anim_dots = 0
        self.anim_timer.start(400)
        
        self.login_worker = LoginWorker(email, pw)
        self.login_worker.finished.connect(self.on_login_finished)
        self.login_worker.start()

    def update_loading_text(self):
        self.anim_dots = (self.anim_dots + 1) % 4
        self.login_btn.setText("LOGGING IN" + "." * self.anim_dots)

    def on_login_finished(self, success, msg):
        self.anim_timer.stop()
        self.login_btn.setEnabled(True)
        self.login_btn.setText("SIGN IN")
        
        if success:
            self.login_success.emit()
            self.close()
        else:
            self.show_msg(msg)

    def handle_start_register(self):
        name = self.reg_name.text()
        email = self.reg_email.text()
        pw = self.reg_pass.text()
        
        if not name or not email or not pw:
            self.show_msg("All fields are required.")
            return

        self.pending_name = name
        self.pending_email = email
        self.pending_pass = pw

        success, msg = auth_manager.send_verification_otp(email, name)
        if success:
            self.show_msg("Verification code sent!", False)
            self.view_container.setCurrentIndex(2) # OTP View
        else:
            self.show_msg(msg)

    def handle_verify_register(self):
        otp = self.otp_input.text()
        if not otp:
            self.show_msg("Enter OTP code.")
            return
            
        success, msg = auth_manager.register(self.pending_email, self.pending_pass, self.pending_name, otp)
        if success:
            self.show_msg("Account Created! Please Sign In.", False)
            self.view_container.setCurrentIndex(0)
        else:
            self.show_msg(msg)

    def handle_send_reset(self):
        email = self.forgot_email.text()
        if not email:
            self.show_msg("Email required.")
            return
        
        self.pending_email = email
        success, msg = auth_manager.send_verification_otp(email)
        if success:
            self.show_msg("Reset code sent!", False)
            self.view_container.setCurrentIndex(4) # Reset View
        else:
            self.show_msg(msg)

    def handle_finish_reset(self):
        otp = self.reset_otp.text()
        pw = self.reset_pass.text()
        if not otp or not pw:
            self.show_msg("All fields required.")
            return
            
        success = auth_manager.reset_password(self.pending_email, pw, otp)
        if success:
            self.show_msg("Password Reset! Please Sign In.", False)
            self.view_container.setCurrentIndex(0)
        else:
            self.show_msg("Failed to reset password. Check OTP.")

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())
