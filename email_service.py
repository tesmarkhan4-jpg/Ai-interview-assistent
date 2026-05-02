import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

class EmailService:
    def __init__(self):
        self.sender_email = "faheemkhan101992@gmail.com"
        self.password = "pzdm jbaq hdxs ubzu"
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    def send_otp(self, receiver_email, otp, user_name="User"):
        subject = f"StealthHUD Verification Code: {otp}"
        
        html_content = f"""
        <html>
        <body style="font-family: 'Inter', sans-serif; background-color: #0F172A; color: #E2E8F0; padding: 40px; margin: 0;">
            <div style="max-width: 600px; margin: auto; background: rgba(30, 41, 59, 0.95); padding: 50px; border-radius: 30px; border: 1px solid rgba(0, 230, 118, 0.2); box-shadow: 0 20px 50px rgba(0,0,0,0.5);">
                <div style="text-align: center; margin-bottom: 40px;">
                    <h1 style="color: #00E676; letter-spacing: 5px; margin: 0; font-size: 32px; font-weight: 900;">STEALTH HUD</h1>
                    <p style="color: #D4AF37; font-size: 11px; letter-spacing: 2px; font-weight: bold; margin-top: 10px;">ELITE ACCESS PROTOCOL</p>
                </div>
                
                <h2 style="color: #FFFFFF; font-size: 20px; text-align: center;">Hello, {user_name}</h2>
                <p style="text-align: center; color: rgba(255,255,255,0.7); line-height: 1.6;">
                    To finalize your secure access to the Stealth Intelligence Network, please use the following verification code:
                </p>
                
                <div style="text-align: center; margin: 40px 0;">
                    <span style="display: inline-block; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007E44, stop:1 #009688); color: #FFFFFF; font-size: 48px; font-weight: 900; padding: 20px 40px; border-radius: 20px; letter-spacing: 15px; border: 2px solid rgba(0, 230, 118, 0.5); box-shadow: 0 10px 20px rgba(0,230,118,0.2);">
                        {otp}
                    </span>
                </div>
                
                <p style="text-align: center; color: rgba(255,255,255,0.4); font-size: 12px; margin-top: 40px;">
                    This code will expire in 10 minutes. If you did not request this code, please ignore this email.
                </p>
                
                <div style="border-top: 1px solid rgba(255,255,255,0.1); margin-top: 40px; padding-top: 20px; text-align: center;">
                    <p style="color: rgba(255,255,255,0.3); font-size: 10px;">&copy; 2026 StealthHUD Intelligence Systems. All Rights Reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = MIMEMultipart()
        msg['From'] = f"StealthHUD Access <{self.sender_email}>"
        msg['To'] = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))
        
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.password)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"[EmailService] Error: {e}")
            return False

email_service = EmailService()
