"""
app/services/live_integrations.py

Live Real-World Integrations Module (Sprint 10 / Option 2).
Provides real SMTP/Gmail email delivery, Slack Webhook notifications, and Inbound Webhook Ingestion.
"""
import os
import logging
import smtplib
import json
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RealEmailConnector:
    """Delivers real emails via SMTP/Gmail App Password if configured."""

    @classmethod
    def send_real_email(
        cls, to_email: str, subject: str, body: str, from_name: str = "HireAI Sales Executive"
    ) -> Dict[str, Any]:
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "").strip()
        smtp_password = os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip()

        if smtp_user and smtp_password:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"{from_name} <{smtp_user}>"
                msg["To"] = to_email
                msg.attach(MIMEText(body, "plain"))

                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                    server.sendmail(smtp_user, to_email, msg.as_string())

                logger.info(f"📧 [REAL EMAIL SENT] Successfully sent email to {to_email} via SMTP ({smtp_host})")
                return {
                    "delivery_status": "REAL_EMAIL_DELIVERED",
                    "to": to_email,
                    "smtp_host": smtp_host,
                    "delivered": True,
                }
            except Exception as exc:
                logger.error(f"❌ [SMTP ERROR] Failed to send real email to {to_email}: {exc}")
                return {
                    "delivery_status": "SMTP_ERROR",
                    "error": str(exc),
                    "delivered": False,
                }

        # Fallback simulation if credentials not set yet
        logger.info(f"📧 [SIMULATED EMAIL SENT] To: {to_email} | Subject: {subject}")
        return {
            "delivery_status": "SIMULATED_EMAIL_SENT",
            "to": to_email,
            "note": "Configure SMTP_USER & SMTP_PASSWORD in .env for live Gmail delivery",
            "delivered": True,
        }


class RealSlackConnector:
    """Posts real Slack notifications via Slack Webhook URL if configured."""

    @classmethod
    def post_slack_notification(
        cls, title: str, text: str, alert_type: str = "INFO"
    ) -> Dict[str, Any]:
        webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")

        icon = "⚡" if alert_type == "INFO" else ("🔔" if alert_type == "APPROVAL" else "✅")
        payload = {
            "text": f"{icon} *{title}*\n```{text}```\n_Powered by HireAI Autonomous Platform_",
        }

        if webhook_url:
            try:
                req = urllib.request.Request(
                    webhook_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req) as resp:
                    resp_text = resp.read().decode("utf-8")

                logger.info(f"📢 [REAL SLACK ALERT SENT] Posted alert to Slack: {title}")
                return {
                    "slack_status": "REAL_SLACK_POSTED",
                    "webhook_configured": True,
                    "posted": True,
                }
            except Exception as exc:
                logger.error(f"❌ [SLACK ERROR] Failed to post Slack message: {exc}")
                return {
                    "slack_status": "SLACK_ERROR",
                    "error": str(exc),
                    "posted": False,
                }

        logger.info(f"📢 [SIMULATED SLACK ALERT] {title} — {text}")
        return {
            "slack_status": "SIMULATED_SLACK_ALERT",
            "note": "Configure SLACK_WEBHOOK_URL in .env for live Slack channel alerts",
            "posted": True,
        }
