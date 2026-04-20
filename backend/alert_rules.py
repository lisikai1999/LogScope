import re
import json
import time
import asyncio
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from logger import app_logger


class RuleType(Enum):
    CONSECUTIVE_ERROR = "consecutive_error"
    KEYWORD_FREQUENCY = "keyword_frequency"
    REGEX_MATCH = "regex_match"
    LEVEL_COUNT = "level_count"


class NotificationType(Enum):
    EMAIL = "email"
    WEBHOOK = "webhook"


class AlertStatus(Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    MUTED = "muted"


@dataclass
class RuleCondition:
    rule_type: str
    level: Optional[str] = None
    count: int = 5
    time_window_seconds: int = 60
    keyword: Optional[str] = None
    regex_pattern: Optional[str] = None
    case_sensitive: bool = False


@dataclass
class NotificationChannel:
    channel_type: str
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRule:
    id: str
    name: str
    description: str
    container_id: Optional[str] = None
    container_name: Optional[str] = None
    condition: RuleCondition = None
    notifications: List[NotificationChannel] = field(default_factory=list)
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_triggered_at: Optional[float] = None
    cooldown_seconds: int = 300
    mute_until: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.condition:
            result['condition'] = asdict(self.condition)
        result['notifications'] = [asdict(n) for n in self.notifications]
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AlertRule':
        condition_data = data.get('condition', {})
        condition = RuleCondition(
            rule_type=condition_data.get('rule_type', RuleType.KEYWORD_FREQUENCY.value),
            level=condition_data.get('level'),
            count=condition_data.get('count', 5),
            time_window_seconds=condition_data.get('time_window_seconds', 60),
            keyword=condition_data.get('keyword'),
            regex_pattern=condition_data.get('regex_pattern'),
            case_sensitive=condition_data.get('case_sensitive', False)
        )
        
        notifications_data = data.get('notifications', [])
        notifications = [
            NotificationChannel(
                channel_type=n.get('channel_type', NotificationType.EMAIL.value),
                enabled=n.get('enabled', True),
                config=n.get('config', {})
            ) for n in notifications_data
        ]
        
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            container_id=data.get('container_id'),
            container_name=data.get('container_name'),
            condition=condition,
            notifications=notifications,
            enabled=data.get('enabled', True),
            created_at=data.get('created_at', time.time()),
            updated_at=data.get('updated_at', time.time()),
            last_triggered_at=data.get('last_triggered_at'),
            cooldown_seconds=data.get('cooldown_seconds', 300),
            mute_until=data.get('mute_until')
        )


@dataclass
class AlertEvent:
    id: str
    rule_id: str
    rule_name: str
    container_id: Optional[str]
    container_name: Optional[str]
    triggered_at: float
    status: str
    matched_logs: List[Dict[str, Any]] = field(default_factory=list)
    message: str = ""
    resolved_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RuleMatcher:
    def __init__(self):
        self.rule_states: Dict[str, Dict[str, Any]] = {}

    def _get_or_create_state(self, rule_id: str) -> Dict[str, Any]:
        if rule_id not in self.rule_states:
            self.rule_states[rule_id] = {
                'matched_logs': [],
                'last_check': time.time(),
                'consecutive_count': 0
            }
        return self.rule_states[rule_id]

    def match_log(self, log_entry: Dict[str, Any], rule: AlertRule) -> bool:
        condition = rule.condition
        state = self._get_or_create_state(rule.id)
        now = time.time()
        
        if condition.rule_type == RuleType.CONSECUTIVE_ERROR.value:
            return self._check_consecutive_error(log_entry, condition, state, rule)
        elif condition.rule_type == RuleType.KEYWORD_FREQUENCY.value:
            return self._check_keyword_frequency(log_entry, condition, state, rule, now)
        elif condition.rule_type == RuleType.REGEX_MATCH.value:
            return self._check_regex_match(log_entry, condition, state)
        elif condition.rule_type == RuleType.LEVEL_COUNT.value:
            return self._check_level_count(log_entry, condition, state, rule, now)
        
        return False

    def _check_consecutive_error(
        self, 
        log_entry: Dict[str, Any], 
        condition: RuleCondition,
        state: Dict[str, Any],
        rule: AlertRule
    ) -> bool:
        message = log_entry.get('message', '').upper()
        is_error = False
        
        if condition.level:
            level_upper = condition.level.upper()
            if level_upper in message:
                is_error = True
        else:
            error_keywords = ['ERROR', 'EXCEPTION', 'FATAL', 'CRITICAL']
            for keyword in error_keywords:
                if keyword in message:
                    is_error = True
                    break
        
        if is_error:
            state['consecutive_count'] += 1
            state['matched_logs'].append(log_entry)
            state['matched_logs'] = state['matched_logs'][-condition.count:]
            
            if state['consecutive_count'] >= condition.count:
                return True
        else:
            state['consecutive_count'] = 0
            state['matched_logs'] = []
        
        return False

    def _check_keyword_frequency(
        self,
        log_entry: Dict[str, Any],
        condition: RuleCondition,
        state: Dict[str, Any],
        rule: AlertRule,
        now: float
    ) -> bool:
        if not condition.keyword:
            return False
        
        message = log_entry.get('message', '')
        keyword = condition.keyword
        
        if condition.case_sensitive:
            matches = keyword in message
        else:
            matches = keyword.lower() in message.lower()
        
        if matches:
            state['matched_logs'].append({
                'log': log_entry,
                'timestamp': now
            })
            
            window_start = now - condition.time_window_seconds
            state['matched_logs'] = [
                entry for entry in state['matched_logs']
                if entry['timestamp'] >= window_start
            ]
            
            if len(state['matched_logs']) >= condition.count:
                return True
        
        return False

    def _check_regex_match(
        self,
        log_entry: Dict[str, Any],
        condition: RuleCondition,
        state: Dict[str, Any]
    ) -> bool:
        if not condition.regex_pattern:
            return False
        
        message = log_entry.get('message', '')
        
        try:
            flags = 0 if condition.case_sensitive else re.IGNORECASE
            pattern = re.compile(condition.regex_pattern, flags)
            
            if pattern.search(message):
                state['matched_logs'].append(log_entry)
                state['matched_logs'] = state['matched_logs'][-100:]
                return True
        except re.error as e:
            app_logger.error(f"Invalid regex pattern: {condition.regex_pattern}, error: {e}")
        
        return False

    def _check_level_count(
        self,
        log_entry: Dict[str, Any],
        condition: RuleCondition,
        state: Dict[str, Any],
        rule: AlertRule,
        now: float
    ) -> bool:
        if not condition.level:
            return False
        
        message = log_entry.get('message', '').upper()
        level_upper = condition.level.upper()
        
        if level_upper in message:
            state['matched_logs'].append({
                'log': log_entry,
                'timestamp': now
            })
            
            window_start = now - condition.time_window_seconds
            state['matched_logs'] = [
                entry for entry in state['matched_logs']
                if entry['timestamp'] >= window_start
            ]
            
            if len(state['matched_logs']) >= condition.count:
                return True
        
        return False

    def get_matched_logs(self, rule_id: str) -> List[Dict[str, Any]]:
        state = self.rule_states.get(rule_id, {})
        matched = state.get('matched_logs', [])
        
        result = []
        for item in matched:
            if isinstance(item, dict) and 'log' in item:
                result.append(item['log'])
            else:
                result.append(item)
        
        return result

    def reset_rule_state(self, rule_id: str):
        if rule_id in self.rule_states:
            self.rule_states[rule_id]['matched_logs'] = []
            self.rule_states[rule_id]['consecutive_count'] = 0


class NotificationService:
    def __init__(self):
        self.email_config: Dict[str, Any] = {}
        self.webhook_timeout = 10

    def configure_email(
        self,
        smtp_host: str,
        smtp_port: int,
        sender_email: str,
        sender_password: str,
        use_tls: bool = True
    ):
        self.email_config = {
            'smtp_host': smtp_host,
            'smtp_port': smtp_port,
            'sender_email': sender_email,
            'sender_password': sender_password,
            'use_tls': use_tls
        }

    async def send_notification(
        self,
        channel: NotificationChannel,
        alert_event: AlertEvent,
        rule: AlertRule
    ) -> bool:
        if not channel.enabled:
            return False
        
        try:
            if channel.channel_type == NotificationType.EMAIL.value:
                return await self._send_email(channel, alert_event, rule)
            elif channel.channel_type == NotificationType.WEBHOOK.value:
                return await self._send_webhook(channel, alert_event, rule)
        except Exception as e:
            app_logger.error(f"Failed to send notification via {channel.channel_type}: {e}")
        
        return False

    async def _send_email(
        self,
        channel: NotificationChannel,
        alert_event: AlertEvent,
        rule: AlertRule
    ) -> bool:
        config = channel.config
        
        smtp_host = config.get('smtp_host', self.email_config.get('smtp_host'))
        smtp_port = config.get('smtp_port', self.email_config.get('smtp_port', 587))
        sender_email = config.get('sender_email', self.email_config.get('sender_email'))
        sender_password = config.get('sender_password', self.email_config.get('sender_password'))
        use_tls = config.get('use_tls', self.email_config.get('use_tls', True))
        recipient_email = config.get('recipient_email')
        
        if not all([smtp_host, smtp_port, sender_email, sender_password, recipient_email]):
            app_logger.error("Incomplete email configuration")
            return False
        
        subject = f"[ALERT] {alert_event.rule_name}"
        body = self._generate_email_body(alert_event, rule)
        
        try:
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            loop = asyncio.get_event_loop()
            
            def send_sync():
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    if use_tls:
                        server.starttls()
                    server.login(sender_email, sender_password)
                    server.send_message(msg)
            
            await loop.run_in_executor(None, send_sync)
            app_logger.info(f"Email notification sent to {recipient_email}")
            return True
            
        except Exception as e:
            app_logger.error(f"Failed to send email: {e}")
            return False

    def _generate_email_body(self, alert_event: AlertEvent, rule: AlertRule) -> str:
        lines = [
            "=" * 60,
            "日志告警通知",
            "=" * 60,
            "",
            f"告警规则: {alert_event.rule_name}",
            f"告警状态: {alert_event.status}",
            f"触发时间: {datetime.fromtimestamp(alert_event.triggered_at).strftime('%Y-%m-%d %H:%M:%S')}",
            f"容器: {alert_event.container_name or alert_event.container_id or '所有容器'}",
            "",
            "=" * 60,
            "告警详情",
            "=" * 60,
            "",
            alert_event.message,
            "",
        ]
        
        if alert_event.matched_logs:
            lines.extend([
                "=" * 60,
                "匹配的日志（最近10条）",
                "=" * 60,
                "",
            ])
            
            for i, log in enumerate(alert_event.matched_logs[-10:], 1):
                timestamp = datetime.fromtimestamp(log.get('timestamp', time.time()))
                stream = log.get('stream', 'stdout')
                message = log.get('message', '')
                lines.append(f"[{i}] {timestamp.strftime('%Y-%m-%d %H:%M:%S')} [{stream.upper()}]")
                lines.append(f"    {message[:200]}" + ("..." if len(message) > 200 else ""))
                lines.append("")
        
        lines.extend([
            "=" * 60,
            "告警规则配置",
            "=" * 60,
            "",
            f"规则类型: {rule.condition.rule_type}",
            f"描述: {rule.description}",
            f"冷却时间: {rule.cooldown_seconds} 秒",
            "",
            "=" * 60,
        ])
        
        return "\n".join(lines)

    async def _send_webhook(
        self,
        channel: NotificationChannel,
        alert_event: AlertEvent,
        rule: AlertRule
    ) -> bool:
        config = channel.config
        webhook_url = config.get('url')
        
        if not webhook_url:
            app_logger.error("Webhook URL not configured")
            return False
        
        payload = self._generate_webhook_payload(alert_event, rule, config)
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.webhook_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = config.get('headers', {'Content-Type': 'application/json'})
                method = config.get('method', 'POST').upper()
                
                if method == 'POST':
                    async with session.post(webhook_url, json=payload, headers=headers) as response:
                        if response.status in [200, 201, 202, 204]:
                            app_logger.info(f"Webhook notification sent to {webhook_url}")
                            return True
                        else:
                            response_text = await response.text()
                            app_logger.error(f"Webhook request failed with status {response.status}: {response_text}")
                            return False
                elif method == 'GET':
                    async with session.get(webhook_url, headers=headers) as response:
                        if response.status in [200, 201, 202, 204]:
                            app_logger.info(f"Webhook notification sent to {webhook_url}")
                            return True
                        return False
        except Exception as e:
            app_logger.error(f"Failed to send webhook: {e}")
            return False
        
        return False

    def _generate_webhook_payload(
        self,
        alert_event: AlertEvent,
        rule: AlertRule,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        payload_type = config.get('payload_type', 'generic')
        
        if payload_type == 'dingtalk':
            return self._generate_dingtalk_payload(alert_event, rule)
        elif payload_type == 'wechat':
            return self._generate_wechat_payload(alert_event, rule)
        elif payload_type == 'slack':
            return self._generate_slack_payload(alert_event, rule)
        else:
            return self._generate_generic_payload(alert_event, rule)

    def _generate_generic_payload(self, alert_event: AlertEvent, rule: AlertRule) -> Dict[str, Any]:
        return {
            'event_id': alert_event.id,
            'rule_id': alert_event.rule_id,
            'rule_name': alert_event.rule_name,
            'status': alert_event.status,
            'triggered_at': alert_event.triggered_at,
            'triggered_at_formatted': datetime.fromtimestamp(alert_event.triggered_at).isoformat(),
            'container_id': alert_event.container_id,
            'container_name': alert_event.container_name,
            'message': alert_event.message,
            'matched_logs': alert_event.matched_logs[:20],
            'rule_config': {
                'rule_type': rule.condition.rule_type,
                'description': rule.description,
                'cooldown_seconds': rule.cooldown_seconds
            }
        }

    def _generate_dingtalk_payload(self, alert_event: AlertEvent, rule: AlertRule) -> Dict[str, Any]:
        container_info = alert_event.container_name or alert_event.container_id or '所有容器'
        status_text = "🔴 触发告警" if alert_event.status == AlertStatus.ACTIVE.value else "🟢 告警恢复"
        
        text_parts = [
            f"### {status_text}",
            f"**告警规则**: {alert_event.rule_name}",
            f"**容器**: {container_info}",
            f"**触发时间**: {datetime.fromtimestamp(alert_event.triggered_at).strftime('%Y-%m-%d %H:%M:%S')}",
            f"**详情**: {alert_event.message}",
        ]
        
        if alert_event.matched_logs:
            text_parts.append("\n**匹配日志**:")
            for log in alert_event.matched_logs[:5]:
                msg = log.get('message', '')[:100]
                text_parts.append(f"> {msg}")
        
        return {
            'msgtype': 'markdown',
            'markdown': {
                'title': f"日志告警: {alert_event.rule_name}",
                'text': '\n\n'.join(text_parts)
            }
        }

    def _generate_wechat_payload(self, alert_event: AlertEvent, rule: AlertRule) -> Dict[str, Any]:
        container_info = alert_event.container_name or alert_event.container_id or '所有容器'
        status_text = "🔴 触发告警" if alert_event.status == AlertStatus.ACTIVE.value else "🟢 告警恢复"
        
        content_parts = [
            f"{status_text}",
            f"告警规则: {alert_event.rule_name}",
            f"容器: {container_info}",
            f"触发时间: {datetime.fromtimestamp(alert_event.triggered_at).strftime('%Y-%m-%d %H:%M:%S')}",
            f"详情: {alert_event.message}",
        ]
        
        if alert_event.matched_logs:
            content_parts.append("\n匹配日志:")
            for log in alert_event.matched_logs[:3]:
                msg = log.get('message', '')[:80]
                content_parts.append(f"- {msg}")
        
        return {
            'msgtype': 'text',
            'text': {
                'content': '\n'.join(content_parts)
            }
        }

    def _generate_slack_payload(self, alert_event: AlertEvent, rule: AlertRule) -> Dict[str, Any]:
        container_info = alert_event.container_name or alert_event.container_id or '所有容器'
        color = "danger" if alert_event.status == AlertStatus.ACTIVE.value else "good"
        
        fields = [
            {
                "title": "告警规则",
                "value": alert_event.rule_name,
                "short": False
            },
            {
                "title": "容器",
                "value": container_info,
                "short": True
            },
            {
                "title": "触发时间",
                "value": datetime.fromtimestamp(alert_event.triggered_at).strftime('%Y-%m-%d %H:%M:%S'),
                "short": True
            }
        ]
        
        return {
            'attachments': [
                {
                    'color': color,
                    'pretext': '日志告警通知',
                    'title': alert_event.message[:100] if len(alert_event.message) > 100 else alert_event.message,
                    'fields': fields,
                    'ts': int(alert_event.triggered_at)
                }
            ]
        }


class AlertRuleEngine:
    def __init__(self, storage_path: str = "alert_rules.json"):
        self.storage_path = storage_path
        self.rules: Dict[str, AlertRule] = {}
        self.alerts: Dict[str, AlertEvent] = {}
        self.matcher = RuleMatcher()
        self.notification_service = NotificationService()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        self._load_rules()

    def _load_rules(self):
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for rule_data in data.get('rules', []):
                    rule = AlertRule.from_dict(rule_data)
                    self.rules[rule.id] = rule
                app_logger.info(f"Loaded {len(self.rules)} alert rules from {self.storage_path}")
        except FileNotFoundError:
            app_logger.info(f"No existing alert rules file found at {self.storage_path}")
        except Exception as e:
            app_logger.error(f"Failed to load alert rules: {e}")

    def _save_rules(self):
        try:
            data = {
                'rules': [rule.to_dict() for rule in self.rules.values()]
            }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            app_logger.error(f"Failed to save alert rules: {e}")

    def create_rule(self, rule_data: Dict[str, Any]) -> AlertRule:
        import uuid
        rule_id = str(uuid.uuid4())
        rule_data['id'] = rule_id
        rule = AlertRule.from_dict(rule_data)
        self.rules[rule.id] = rule
        self._save_rules()
        app_logger.info(f"Created alert rule: {rule.name} (ID: {rule.id})")
        return rule

    def update_rule(self, rule_id: str, rule_data: Dict[str, Any]) -> Optional[AlertRule]:
        if rule_id not in self.rules:
            return None
        
        existing = self.rules[rule_id]
        rule_data['id'] = rule_id
        rule_data['created_at'] = existing.created_at
        rule_data['updated_at'] = time.time()
        rule_data['last_triggered_at'] = existing.last_triggered_at
        
        rule = AlertRule.from_dict(rule_data)
        self.rules[rule.id] = rule
        self._save_rules()
        app_logger.info(f"Updated alert rule: {rule.name} (ID: {rule.id})")
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        if rule_id not in self.rules:
            return False
        
        rule = self.rules.pop(rule_id)
        self._save_rules()
        app_logger.info(f"Deleted alert rule: {rule.name} (ID: {rule.id})")
        return True

    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        return self.rules.get(rule_id)

    def list_rules(self, container_id: Optional[str] = None) -> List[AlertRule]:
        if container_id:
            return [
                rule for rule in self.rules.values()
                if rule.container_id == container_id or rule.container_id is None
            ]
        return list(self.rules.values())

    def mute_rule(self, rule_id: str, duration_seconds: int) -> bool:
        rule = self.get_rule(rule_id)
        if not rule:
            return False
        
        rule.mute_until = time.time() + duration_seconds
        rule.updated_at = time.time()
        self._save_rules()
        app_logger.info(f"Muted rule {rule_id} for {duration_seconds} seconds")
        return True

    def unmute_rule(self, rule_id: str) -> bool:
        rule = self.get_rule(rule_id)
        if not rule:
            return False
        
        rule.mute_until = None
        rule.updated_at = time.time()
        self._save_rules()
        app_logger.info(f"Unmuted rule {rule_id}")
        return True

    def process_log(self, log_entry: Dict[str, Any], container_id: str, container_name: Optional[str] = None):
        if not self._running:
            return
        
        now = time.time()
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            if rule.container_id and rule.container_id != container_id:
                continue
            
            if rule.mute_until and rule.mute_until > now:
                continue
            
            if rule.last_triggered_at and (now - rule.last_triggered_at) < rule.cooldown_seconds:
                continue
            
            if self.matcher.match_log(log_entry, rule):
                self._trigger_alert(rule, container_id, container_name, now)

    def _trigger_alert(
        self,
        rule: AlertRule,
        container_id: str,
        container_name: Optional[str],
        triggered_at: float
    ):
        import uuid
        
        matched_logs = self.matcher.get_matched_logs(rule.id)
        
        message = self._generate_alert_message(rule, matched_logs)
        
        event_id = str(uuid.uuid4())
        alert_event = AlertEvent(
            id=event_id,
            rule_id=rule.id,
            rule_name=rule.name,
            container_id=container_id,
            container_name=container_name,
            triggered_at=triggered_at,
            status=AlertStatus.ACTIVE.value,
            matched_logs=matched_logs[-20:],
            message=message
        )
        
        self.alerts[event_id] = alert_event
        rule.last_triggered_at = triggered_at
        rule.updated_at = time.time()
        self._save_rules()
        
        app_logger.warning(f"ALERT TRIGGERED: {rule.name} (Rule ID: {rule.id})")
        
        asyncio.create_task(self._send_notifications(alert_event, rule))
        
        self.matcher.reset_rule_state(rule.id)

    def _generate_alert_message(self, rule: AlertRule, matched_logs: List[Dict[str, Any]]) -> str:
        condition = rule.condition
        
        if condition.rule_type == RuleType.CONSECUTIVE_ERROR.value:
            level = condition.level or "ERROR"
            return f"{level} 日志连续出现 {len(matched_logs)} 次，超过阈值 {condition.count} 次"
        
        elif condition.rule_type == RuleType.KEYWORD_FREQUENCY.value:
            keyword = condition.keyword or "(未设置)"
            return f"关键词 '{keyword}' 在 {condition.time_window_seconds} 秒内出现 {len(matched_logs)} 次，超过阈值 {condition.count} 次"
        
        elif condition.rule_type == RuleType.REGEX_MATCH.value:
            pattern = condition.regex_pattern or "(未设置)"
            return f"正则表达式 '{pattern}' 匹配到日志内容"
        
        elif condition.rule_type == RuleType.LEVEL_COUNT.value:
            level = condition.level or "(未设置)"
            return f"{level} 级别日志在 {condition.time_window_seconds} 秒内出现 {len(matched_logs)} 次，超过阈值 {condition.count} 次"
        
        return "告警规则触发"

    async def _send_notifications(self, alert_event: AlertEvent, rule: AlertRule):
        for channel in rule.notifications:
            await self.notification_service.send_notification(channel, alert_event, rule)

    def list_alerts(
        self,
        status: Optional[str] = None,
        rule_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AlertEvent]:
        alerts = list(self.alerts.values())
        
        if status:
            alerts = [a for a in alerts if a.status == status]
        
        if rule_id:
            alerts = [a for a in alerts if a.rule_id == rule_id]
        
        alerts.sort(key=lambda a: a.triggered_at, reverse=True)
        
        return alerts[:limit]

    def get_alert(self, alert_id: str) -> Optional[AlertEvent]:
        return self.alerts.get(alert_id)

    async def start(self):
        self._running = True
        app_logger.info("Alert rule engine started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        app_logger.info("Alert rule engine stopped")


alert_engine = AlertRuleEngine()
