import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QPushButton, QLabel, QFrame, QApplication, QStackedWidget)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPalette, QBrush
from auth_manager import auth_manager

class LoginWindow(QWidget):
    login_success = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFixedSize(550, 750)
        
        self.init_ui()
        self.old_pos = None
        
        # Temp storage for multi-step flows
        self.pending_name = ""
        self.pending_email = ""
        self.pending_pass = ""

    def init_ui(self):
        # Main Layout
        self.root_layout = QVBoxLayout()
        self.root_layout.setContentsMargins(25, 25, 25, 25)
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
        
        self.panel_layout = QVBoxLayout(self.glass_panel)
        self.panel_layout.setContentsMargins(50, 50, 50, 50)
        self.panel_layout.setSpacing(20)

        # Top Bar (Close)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(45, 45)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(45, 74, 69, 0.1);
                color: #2D4A45;
                border-radius: 22px;
                font-size: 20px;
            }
            QPushButton:hover { background: rgba(211, 47, 47, 0.2); color: #D32F2F; }
        """)
        close_btn.clicked.connect(self.close)
        close_btn.move(430, 25)
        close_btn.setParent(self.glass_panel)

        # Header Section
        self.title_label = QLabel("STEALTH ACCESS")
        self.title_label.setStyleSheet("color: #D4AF37; font-size: 28px; font-weight: 900; letter-spacing: 10px; background: transparent;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.panel_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("SECURE LUXURY AUTHENTICATION")
        self.subtitle_label.setStyleSheet("color: rgba(0, 0, 0, 0.4); font-size: 10px; font-weight: 900; letter-spacing: 3px;")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.panel_layout.addWidget(self.subtitle_label)

        self.panel_layout.addStretch()

        # Dynamic View Container
        self.view_container = QStackedWidget()
        self.panel_layout.addWidget(self.view_container)

        self.setup_login_view()
        self.setup_signup_view()
        self.setup_otp_view()
        self.setup_forgot_view()
        self.setup_reset_view()

        self.panel_layout.addStretch()
        
        # Status Label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #D32F2F; font-size: 13px; font-weight: bold;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.panel_layout.addWidget(self.status_label)

        self.view_container.setCurrentIndex(0)

    def get_input_style(self):
        return """
            QLineEdit {
                background: rgba(255, 255, 255, 0.4);
                border: 1px solid rgba(45, 74, 69, 0.1);
                border-radius: 20px;
                padding: 15px;
                color: #1A2E2A;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(0, 230, 118, 0.3);
                background: rgba(255, 255, 255, 0.6);
            }
        """

    def get_btn_style(self, primary=True):
        if primary:
            return """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007E44, stop:1 #009688);
                    color: white;
                    border-radius: 25px;
                    padding: 15px;
                    font-weight: 900;
                    letter-spacing: 2px;
                    font-size: 13px;
                }
                QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #009688, stop:1 #26A69A); }
            """
        else:
            return """
                QPushButton {
                    background: transparent;
                    color: #007E44;
                    font-weight: 900;
                    font-size: 11px;
                }
                QPushButton:hover { color: #00B0FF; }
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

        login_btn = QPushButton("SIGN IN")
        login_btn.setStyleSheet(self.get_btn_style())
        login_btn.clicked.connect(self.handle_login)
        layout.addWidget(login_btn)

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
        
        success, msg = auth_manager.login(email, pw)
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
