import os
import json
import random
import logging
import smtplib
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def generate_verification_code() -> str:
        """6자리 난수 이메일 인증코드 생성"""
        return f"{random.randint(100000, 999999)}"

    @staticmethod
    def send_verification_email(to_email: str, code: str) -> bool:
        """
        이메일 및 알림으로 6자리 인증코드 전송
        지원되는 발송 전송 방식:
        1. Resend API (RESEND_API_KEY) : 개인 비밀번호 없이 실제 수신 이메일함으로 즉시 전송
        2. Discord Webhook (DISCORD_WEBHOOK_URL) : 디스코드 채널로 실시간 인증코드 알림 카드 전송
        3. Standard SMTP (SMTP_USER & SMTP_PASSWORD) : Gmail/Naver SMTP 통해 이메일 전송
        4. 콘솔 시뮬레이션 로그
        """
        resend_api_key = os.getenv("RESEND_API_KEY")
        discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")

        print(f"==================================================")
        print(f" [Email Verification Code Generation]")
        print(f" To: {to_email}")
        print(f" Verification Code: {code}")
        print(f"==================================================")

        # 1. Resend API 발송 (비밀번호 입력 불필요, 실제 이메일함 수신)
        if resend_api_key:
            try:
                url = "https://api.resend.com/emails"
                headers = {
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                }
                payload = {
                    "from": "Smart Contract Hub <onboarding@resend.dev>",
                    "to": [to_email],
                    "subject": "[Smart Contract Evidence Hub] 이메일 인증번호 안내",
                    "html": f"""
                    <div style="max-width:480px;margin:0 auto;padding:24px;border:1px solid #e2e8f0;border-radius:16px;font-family:sans-serif;">
                        <h2 style="color:#4f46e5;margin-bottom:8px;">Smart Contract Evidence Hub</h2>
                        <p style="color:#64748b;font-size:14px;">비밀번호 변경을 위한 인증번호입니다.</p>
                        <div style="background:#f8fafc;padding:20px;text-align:center;border-radius:12px;margin:16px 0;">
                            <span style="font-size:32px;font-weight:900;color:#4f46e5;letter-spacing:4px;">{code}</span>
                        </div>
                        <p style="font-size:12px;color:#ef4444;">* 5분 이내에 인증을 완료해주세요.</p>
                    </div>
                    """,
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req) as resp:
                    resp_data = resp.read().decode('utf-8')
                    print(f" [SUCCESS] Resend API: Real email delivered to {to_email} ({resp_data})")
                    return True
            except urllib.error.HTTPError as he:
                err_msg = he.read().decode('utf-8')
                logger.error(f"[EmailService] Resend API HTTP error {he.code}: {err_msg}")
                print(f" [ERROR] Resend API HTTP error {he.code}: {err_msg}")
            except Exception as e:
                logger.error(f"[EmailService] Resend API delivery failed: {e}")
                print(f" [ERROR] Resend API exception: {e}")

        # 2. Discord Webhook 전송 (디스코드 알림)
        if discord_webhook_url:
            try:
                discord_payload = {
                    "username": "Evidence Hub Security Bot",
                    "embeds": [
                        {
                            "title": "🔒 비밀번호 변경 이메일 인증코드",
                            "description": f"수신 이메일: `{to_email}`\n인증코드: **{code}**\n유효시간: **5분**",
                            "color": 5267175,
                        }
                    ],
                }
                req = urllib.request.Request(
                    discord_webhook_url,
                    data=json.dumps(discord_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req) as resp:
                    print(f" [SUCCESS] Discord Webhook: Notification sent for {to_email}")
            except Exception as e:
                logger.error(f"[EmailService] Discord Webhook failed: {e}")

        # 3. Standard SMTP 전송
        if smtp_user and smtp_password:
            try:
                smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
                smtp_port = int(os.getenv("SMTP_PORT", "587"))

                msg = MIMEMultipart("alternative")
                msg["Subject"] = "[Smart Contract Evidence Hub] 이메일 인증번호 안내"
                msg["From"] = smtp_user
                msg["To"] = to_email

                html_content = f"""
                <div style="max-width:520px;margin:0 auto;padding:24px;background:#ffffff;border-radius:12px;font-family:sans-serif;border:1px solid #e2e8f0;">
                    <h2 style="color:#4f46e5;">Smart Contract Evidence Hub</h2>
                    <p>비밀번호 변경을 위한 인증번호입니다.</p>
                    <div style="background:#f8fafc;padding:16px;text-align:center;border-radius:8px;">
                        <span style="font-size:28px;font-weight:bold;color:#4f46e5;">{code}</span>
                    </div>
                </div>
                """
                msg.attach(MIMEText(html_content, "html", "utf-8"))

                if smtp_port == 465:
                    with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as server:
                        server.login(smtp_user, smtp_password)
                        server.sendmail(smtp_user, [to_email], msg.as_string())
                else:
                    with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                        server.starttls()
                        server.login(smtp_user, smtp_password)
                        server.sendmail(smtp_user, [to_email], msg.as_string())

                print(f" [SUCCESS] SMTP delivered email to {to_email}")
                return True
            except Exception as e:
                logger.error(f"[EmailService] SMTP error: {e}")

        return True
