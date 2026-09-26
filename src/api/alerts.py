"""
src/api/alerts.py

Email alerting for critical grid anomalies via Gmail SMTP.
Dedup is in-memory (per anomaly ID) - resets on server restart, which is
fine for a single-process student deployment. Swap for Mongo-backed dedup
only if this ever runs multi-worker or needs to survive restarts.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("powerpredict.alerts")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")
ALERT_FROM = os.getenv("ALERT_FROM", SMTP_USER)
ALERT_TO = os.getenv("ALERT_TO", SMTP_USER)  # comma-separated for multiple recipients

_alerted_ids = set()


def _send_email(subject: str, body: str) -> bool:
    if not SMTP_USER or not SMTP_APP_PASSWORD:
        logger.warning("SMTP not configured - skipping alert: %s", subject)
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = ALERT_FROM
        msg["To"] = ALERT_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_APP_PASSWORD)
            server.sendmail(ALERT_FROM, ALERT_TO.split(","), msg.as_string())
        logger.info("Sent alert email: %s", subject)
        return True
    except Exception as e:
        logger.error("Failed to send alert email: %s", e)
        return False


def check_and_send_anomaly_alerts(anomaly_queue: list) -> int:
    """Call with the list from get_anomaly_queue(). Emails once per
    newly-seen CRITICAL item (dedup by its 'id'). Returns count sent."""
    sent = 0
    for item in anomaly_queue:
        if item.get("severity") != "CRITICAL":
            continue
        aid = item.get("id")
        if not aid or aid in _alerted_ids:
            continue
        _alerted_ids.add(aid)

        subject = f"[PowerPredict] CRITICAL anomaly - {item.get('asset')} ({item.get('zone')})"
        body = (
            f"Critical anomaly detected.\n\n"
            f"ID: {aid}\n"
            f"Asset: {item.get('asset')}\n"
            f"Zone: {item.get('zone')}\n"
            f"Timestamp: {item.get('timestamp')}\n"
            f"Voltage: {item.get('voltage')} V\n"
            f"Active power: {item.get('active_power')} kW\n"
            f"Reconstruction error: {item.get('reconstruction_error')}\n\n"
            f"Automated alert from the PowerPredict anomaly pipeline."
        )
        if _send_email(subject, body):
            sent += 1
    return sent