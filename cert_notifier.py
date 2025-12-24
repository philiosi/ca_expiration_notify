import os
import smtplib
import pymysql
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Dict, Any

# 환경 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# 로깅 설정
log_dir = os.path.join(BASE_DIR, 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(os.path.join(log_dir, 'app.log'), encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 알림 주기 설정 (D-Day)
NOTIFY_DAYS = [14, 7, 3, 1]

def get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        db=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306)),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def send_email(to_email: str, subject: str, cert_info: Dict[str, Any], days_left: int):
    sender_email = "kisti-grid-ca@kisti.re.kr"
    smtp_server, smtp_port = "localhost", 25

    html_content = f"""
    <html>
    <head>
        <style>
            table {{ border-collapse: collapse; width: 100%; max-width: 600px; font-family: Arial, sans-serif; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #f2f2f2; font-weight: bold; }}
            .warning {{ color: #d9534f; font-weight: bold; }}
            .footer {{ margin-top: 20px; font-size: 12px; color: #777; }}
        </style>
    </head>
    <body>
        <h2>[Notice] Certificate Expiration Warning</h2>
        <p>This is an automated notification. The Grid Certificate you manage will expire in <b>{days_left} days</b>.</p>
        <p>Please renew your certificate before the expiration date.</p>
        <br>
        <table>
            <tr><th>Distinguished Name (DN)</th><td>{cert_info['subject']}</td></tr>
            <tr><th>Expiration Date (KST)</th><td class="warning">{cert_info['vuntil']}</td></tr>
            <tr><th>Days Remaining</th><td class="warning">{days_left} Days</td></tr>
        </table>
        <div class="footer"><p>Do not reply to this email.<br>Contact: KISTI Grid CA Center</p></div>
    </body>
    </html>
    """
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"KISTI Grid CA <{sender_email}>"
    msg['To'] = to_email
    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.sendmail(sender_email, to_email, msg.as_string())
            logger.info(f"[Email Sent] To: {to_email} (Days Left: {days_left})")
    except Exception as e:
        logger.error(f"[Email Failed] To: {to_email}, Error: {e}")

def check_and_notify():
    today = datetime.now().date()
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            logger.info("--- Starting Check ---")
            for days in NOTIFY_DAYS:
                target_date = today + timedelta(days=days)
                sql = """
                    SELECT c.certid, c.subject, c.vuntil, r.email 
                    FROM cert c INNER JOIN csr r ON c.csrid = r.csrid
                    WHERE DATE(c.vuntil) = %s AND r.email IS NOT NULL AND r.email != ''
                """
                cursor.execute(sql, (target_date,))
                rows = cursor.fetchall()
                if rows:
                    logger.info(f"Target Date: {target_date} ({days} days left), Found: {len(rows)}")
                    for row in rows:
                        subject_title = f"[Urgent] Certificate Expiration Notice ({days} days left) - {row['subject'][:30]}..."
                        send_email(row['email'], subject_title, row, days)
                else:
                    logger.debug(f"Target Date: {target_date} ({days} days left), Found: 0")
    except Exception as e:
        logger.error(f"[DB Error] {e}")
    finally:
        if conn: conn.close()
        logger.info("--- Check Completed ---")

if __name__ == "__main__":
    check_and_notify()
