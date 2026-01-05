import os
import smtplib
import pymysql
import logging
import csv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Logging configuration
log_dir = os.path.join(BASE_DIR, 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'app.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Notification schedule (days before expiration)
NOTIFY_DAYS = [14, 7, 3, 1]

def get_db_connection() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        db=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306)),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def save_sent_history(to_email: str, cert_subject: str, days_left: int):
    """
    Records email history to a CSV file.
    Creates the file and header automatically if it doesn't exist.
    """
    history_file = os.path.join(log_dir, 'email_history.csv')
    file_exists = os.path.isfile(history_file)
    
    try:
        with open(history_file, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['Timestamp', 'Recipient', 'Cert Subject', 'Days Left', 'Status'])
            
            writer.writerow([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                to_email,
                cert_subject,
                days_left,
                'Success'
            ])
    except Exception as e:
        logger.error(f"Failed to write history log: {e}")

def send_email(to_email: str, subject: str, cert_info: Dict[str, Any], days_left: int) -> None:
    sender_email = "kisti-grid-ca@kisti.re.kr"
    smtp_server = "localhost"
    smtp_port = 25

    html_content = f"""
    <html>
    <head>
        <style>
            table {{ border-collapse: collapse; width: 100%; max-width: 600px; font-family: Arial, sans-serif; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #f2f2f2; font-weight: bold; color: #333; }}
            .warning {{ color: #d9534f; font-weight: bold; }}
            .footer {{ margin-top: 20px; font-size: 12px; color: #777; line-height: 1.5; }}
            .content {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        </style>
    </head>
    <body>
        <div class="content">
            <h2>KISTI Grid Certificate Expiration Warning</h2>
            <p>Greetings,</p>
            <p>This is an automated notification to inform you that the Grid Certificate you manage is scheduled to expire in <b>{days_left} days</b>.</p>
            <p>To prevent any service interruption, please renew your certificate before the expiration date.</p>
            <br>
            <table>
                <tr>
                    <th>Distinguished Name (DN)</th>
                    <td>{cert_info['subject']}</td>
                </tr>
                <tr>
                    <th>Expiration Date (KST)</th>
                    <td class="warning">{cert_info['vuntil']}</td>
                </tr>
                <tr>
                    <th>Days Remaining</th>
                    <td class="warning">{days_left} Days</td>
                </tr>
            </table>
            <div class="footer">
                <hr style="border: 0; border-top: 1px solid #eee;">
                <p>This is an automated message; please do not reply to this email.<br>
                For inquiries, please contact the <b>KISTI Grid CA Center</b>.</p>
            </div>
        </div>
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
            save_sent_history(to_email, cert_info['subject'], days_left)
    except Exception as e:
        logger.error(f"[Email Failed] To: {to_email}, Error: {e}")

def check_and_notify() -> None:
    today = datetime.now().date()
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            logger.info("--- Starting Certificate Expiration Check ---")
            for days in NOTIFY_DAYS:
                target_date = today + timedelta(days=days)
                
                sql = """
                    SELECT c.certid, c.subject, c.vuntil, r.email 
                    FROM cert c
                    INNER JOIN csr r ON c.csrid = r.csrid
                    WHERE DATE(c.vuntil) = %s
                    AND r.email IS NOT NULL AND r.email != ''
                """
                cursor.execute(sql, (target_date,))
                rows = cursor.fetchall()
                
                if rows:
                    logger.info(f"Target Date: {target_date} ({days} days left), Found: {len(rows)} certs")
                    for row in rows:
                        subject_title = f"[KISTI CA] (Urgent) Certificate Expiration Notice ({days} days left) - {row['subject'][:30]}..."
                        send_email(row['email'], subject_title, row, days)
                else:
                    logger.debug(f"Target Date: {target_date} ({days} days left), Found: 0")

    except Exception as e:
        logger.error(f"[DB Error] {e}")
    finally:
        if conn and conn.open:
            conn.close()
            logger.info("--- Check Completed ---")

if __name__ == "__main__":
    check_and_notify()
