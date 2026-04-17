"""
Alerting system for trading platform.
Sends alerts via Discord, Telegram, and Email for critical events.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import json
import aiohttp
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"


class AlertChannel(Enum):
    """Alert notification channels."""
    DISCORD = "discord"
    TELEGRAM = "telegram"
    EMAIL = "email"
    SLACK = "slack"


@dataclass
class Alert:
    """Alert event."""
    title: str
    message: str
    severity: AlertSeverity
    tags: Dict[str, str]
    timestamp: datetime
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'title': self.title,
            'message': self.message,
            'severity': self.severity.value,
            'tags': self.tags,
            'timestamp': self.timestamp.isoformat(),
            'metric_value': self.metric_value,
            'threshold': self.threshold,
        }


class AlertRule:
    """Alert rule definition."""
    
    def __init__(self, 
                 name: str,
                 condition_fn: callable,
                 severity: AlertSeverity,
                 channels: List[AlertChannel],
                 cooldown_seconds: int = 300):
        self.name = name
        self.condition_fn = condition_fn
        self.severity = severity
        self.channels = channels
        self.cooldown_seconds = cooldown_seconds
        self.last_triggered: Optional[datetime] = None
    
    def should_trigger(self, metrics: Dict[str, Any]) -> bool:
        """Check if alert should trigger."""
        if self.last_triggered:
            elapsed = (datetime.now() - self.last_triggered).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False
        
        return self.condition_fn(metrics)
    
    def triggered(self):
        """Mark alert as triggered."""
        self.last_triggered = datetime.now()


class DiscordNotifier:
    """Sends alerts to Discord."""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send(self, alert: Alert):
        """Send alert to Discord."""
        try:
            embed = {
                'title': alert.title,
                'description': alert.message,
                'color': self._severity_color(alert.severity),
                'fields': [
                    {'name': 'Severity', 'value': alert.severity.value},
                    {'name': 'Time', 'value': alert.timestamp.isoformat()},
                ]
            }
            
            if alert.tags:
                for key, value in alert.tags.items():
                    embed['fields'].append({'name': key, 'value': value})
            
            if alert.metric_value is not None:
                embed['fields'].append({
                    'name': 'Metric Value',
                    'value': f"{alert.metric_value:.2f}"
                })
            
            if alert.threshold is not None:
                embed['fields'].append({
                    'name': 'Threshold',
                    'value': f"{alert.threshold:.2f}"
                })
            
            payload = {'embeds': [embed]}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as resp:
                    if resp.status != 204:
                        logger.error(f"Discord notification failed: {resp.status}")
        except Exception as e:
            logger.error(f"Error sending Discord alert: {e}")
    
    @staticmethod
    def _severity_color(severity: AlertSeverity) -> int:
        """Get color code for severity."""
        colors = {
            AlertSeverity.INFO: 0x00FF00,
            AlertSeverity.WARNING: 0xFFFF00,
            AlertSeverity.ERROR: 0xFF6600,
            AlertSeverity.CRITICAL: 0xFF0000,
        }
        return colors.get(severity, 0x808080)


class TelegramNotifier:
    """Sends alerts to Telegram."""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def send(self, alert: Alert):
        """Send alert to Telegram."""
        try:
            message = self._format_message(alert)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        'chat_id': self.chat_id,
                        'text': message,
                        'parse_mode': 'HTML'
                    }
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Telegram notification failed: {resp.status}")
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
    
    @staticmethod
    def _format_message(alert: Alert) -> str:
        """Format alert as HTML message."""
        severity_emoji = {
            AlertSeverity.INFO: 'ℹ️',
            AlertSeverity.WARNING: '⚠️',
            AlertSeverity.ERROR: '❌',
            AlertSeverity.CRITICAL: '🚨',
        }
        
        emoji = severity_emoji.get(alert.severity, '•')
        message = f"{emoji} <b>{alert.title}</b>\n"
        message += f"<i>{alert.message}</i>\n"
        message += f"Severity: {alert.severity.value}\n"
        
        if alert.tags:
            for key, value in alert.tags.items():
                message += f"{key}: {value}\n"
        
        if alert.metric_value is not None:
            message += f"Value: {alert.metric_value:.2f}\n"
        
        if alert.threshold is not None:
            message += f"Threshold: {alert.threshold:.2f}\n"
        
        message += f"Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message


class EmailNotifier:
    """Sends alerts via email."""
    
    def __init__(self, 
                 smtp_server: str,
                 smtp_port: int,
                 sender_email: str,
                 sender_password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
    
    async def send(self, alert: Alert, recipient_emails: List[str]):
        """Send alert via email."""
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"
            message["From"] = self.sender_email
            message["To"] = ", ".join(recipient_emails)
            
            text = self._format_text(alert)
            html = self._format_html(alert)
            
            message.attach(MIMEText(text, "plain"))
            message.attach(MIMEText(html, "html"))
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_smtp,
                recipient_emails,
                message.as_string()
            )
        except Exception as e:
            logger.error(f"Error sending email alert: {e}")
    
    def _send_smtp(self, recipients: List[str], message: str):
        """Send via SMTP."""
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, recipients, message)
    
    @staticmethod
    def _format_text(alert: Alert) -> str:
        """Format alert as plain text."""
        text = f"{alert.title}\n"
        text += f"{'=' * 50}\n\n"
        text += f"{alert.message}\n\n"
        text += f"Severity: {alert.severity.value}\n"
        text += f"Time: {alert.timestamp.isoformat()}\n"
        
        if alert.tags:
            text += "\nTags:\n"
            for key, value in alert.tags.items():
                text += f"  {key}: {value}\n"
        
        if alert.metric_value is not None:
            text += f"\nMetric Value: {alert.metric_value:.2f}\n"
        
        if alert.threshold is not None:
            text += f"Threshold: {alert.threshold:.2f}\n"
        
        return text
    
    @staticmethod
    def _format_html(alert: Alert) -> str:
        """Format alert as HTML."""
        severity_color = {
            AlertSeverity.INFO: '#00AA00',
            AlertSeverity.WARNING: '#FFAA00',
            AlertSeverity.ERROR: '#FF6600',
            AlertSeverity.CRITICAL: '#FF0000',
        }.get(alert.severity, '#808080')
        
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <div style="border-left: 5px solid {severity_color}; padding: 10px;">
                    <h2 style="color: {severity_color};">{alert.title}</h2>
                    <p>{alert.message}</p>
                    <table style="margin-top: 20px;">
                        <tr>
                            <td><b>Severity:</b></td>
                            <td>{alert.severity.value}</td>
                        </tr>
                        <tr>
                            <td><b>Time:</b></td>
                            <td>{alert.timestamp.isoformat()}</td>
                        </tr>
        """
        
        if alert.tags:
            for key, value in alert.tags.items():
                html += f"<tr><td><b>{key}:</b></td><td>{value}</td></tr>\n"
        
        if alert.metric_value is not None:
            html += f"<tr><td><b>Metric Value:</b></td><td>{alert.metric_value:.2f}</td></tr>\n"
        
        if alert.threshold is not None:
            html += f"<tr><td><b>Threshold:</b></td><td>{alert.threshold:.2f}</td></tr>\n"
        
        html += """
                    </table>
                </div>
            </body>
        </html>
        """
        
        return html


class AlertManager:
    """Manages alerts and notifications."""
    
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.notifiers: Dict[AlertChannel, Any] = {}
        self.alert_history: List[Alert] = []
    
    def register_rule(self, rule: AlertRule):
        """Register an alert rule."""
        self.rules.append(rule)
    
    def register_notifier(self, channel: AlertChannel, notifier: Any):
        """Register a notification channel."""
        self.notifiers[channel] = notifier
    
    async def evaluate(self, metrics: Dict[str, Any]):
        """Evaluate all rules."""
        for rule in self.rules:
            if rule.should_trigger(metrics):
                alert = Alert(
                    title=rule.name,
                    message=f"Alert triggered: {rule.name}",
                    severity=rule.severity,
                    tags={},
                    timestamp=datetime.now(),
                )
                await self.send_alert(alert, rule.channels)
                rule.triggered()
    
    async def send_alert(self, alert: Alert, channels: List[AlertChannel]):
        """Send alert to specified channels."""
        self.alert_history.append(alert)
        
        tasks = []
        for channel in channels:
            if channel in self.notifiers:
                notifier = self.notifiers[channel]
                if channel == AlertChannel.DISCORD:
                    tasks.append(notifier.send(alert))
                elif channel == AlertChannel.TELEGRAM:
                    tasks.append(notifier.send(alert))
                elif channel == AlertChannel.EMAIL:
                    tasks.append(notifier.send(alert, ['admin@example.com']))
        
        if tasks:
            await asyncio.gather(*tasks)
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get recent alerts."""
        return self.alert_history[-limit:]


if __name__ == '__main__':
    # Example usage
    manager = AlertManager()
    
    # Define alert rules
    pnl_loss_rule = AlertRule(
        name="Daily P&L Loss Threshold",
        condition_fn=lambda m: m.get('pnl_daily', 0) < -500,
        severity=AlertSeverity.CRITICAL,
        channels=[AlertChannel.DISCORD, AlertChannel.TELEGRAM]
    )
    
    manager.register_rule(pnl_loss_rule)
    
    # Example metrics
    metrics = {'pnl_daily': -600}
    print(f"Rule would trigger: {pnl_loss_rule.should_trigger(metrics)}")
