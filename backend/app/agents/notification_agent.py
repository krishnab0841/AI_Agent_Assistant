"""
Notification Agent for managing and sending various types of notifications.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import json

from . import Agent, agent_registry
from .message_bus import message_bus

# Set up logging
logger = logging.getLogger(__name__)

class NotificationType:
    """Notification type constants."""
    INFO = 'info'
    SUCCESS = 'success'
    WARNING = 'warning'
    ERROR = 'error'
    TASK_REMINDER = 'task_reminder'
    MEETING_REMINDER = 'meeting_reminder'
    EMAIL_NOTIFICATION = 'email_notification'
    SYSTEM_ALERT = 'system_alert'

class NotificationChannel:
    """Notification channel constants."""
    IN_APP = 'in_app'
    EMAIL = 'email'
    SMS = 'sms'
    PUSH = 'push'
    SLACK = 'slack'
    WEBHOOK = 'webhook'

class NotificationAgent(Agent):
    """Agent responsible for managing and sending notifications."""
    
    def __init__(self):
        super().__init__(
            agent_id="notification_agent",
            name="Notification Agent",
            description="Manages and sends various types of notifications"
        )
        self.capabilities = [
            "send_notification",
            "list_notifications",
            "mark_as_read",
            "get_notification_preferences",
            "update_notification_preferences"
        ]
        
        # In-memory storage for notifications (in a real app, use a database)
        self._notifications = {}
        self._preferences = {}
        
        # Default notification preferences
        self._default_preferences = {
            NotificationType.INFO: [NotificationChannel.IN_APP],
            NotificationType.SUCCESS: [NotificationChannel.IN_APP],
            NotificationType.WARNING: [NotificationChannel.IN_APP, NotificationChannel.EMAIL],
            NotificationType.ERROR: [NotificationChannel.IN_APP, NotificationChannel.EMAIL, NotificationChannel.PUSH],
            NotificationType.TASK_REMINDER: [NotificationChannel.IN_APP, NotificationChannel.EMAIL],
            NotificationType.MEETING_REMINDER: [NotificationChannel.IN_APP, NotificationChannel.EMAIL, NotificationChannel.PUSH],
            NotificationType.EMAIL_NOTIFICATION: [NotificationChannel.EMAIL],
            NotificationType.SYSTEM_ALERT: [NotificationChannel.IN_APP, NotificationChannel.EMAIL, NotificationChannel.SLACK]
        }
        
        # Set up message bus subscriptions
        self._subscriptions = [
            message_bus.subscribe("notification.*", self._handle_notification_message),
            message_bus.subscribe("task.*", self._handle_task_event),
            message_bus.subscribe("meeting.*", self._handle_meeting_event)
        ]
    
    async def _handle_notification_message(self, message: Dict[str, Any]) -> None:
        """Handle notification-related messages from the message bus."""
        action = message.get('action')
        
        try:
            if action == 'send':
                await self.send_notification(
                    notification_type=message.get('type', NotificationType.INFO),
                    title=message.get('title'),
                    message=message.get('message'),
                    recipient=message.get('recipient'),
                    channels=message.get('channels'),
                    priority=message.get('priority', 'normal'),
                    metadata=message.get('metadata', {})
                )
            elif action == 'mark_as_read' and 'notification_id' in message:
                await self.mark_as_read(
                    notification_id=message['notification_id'],
                    user_id=message.get('user_id')
                )
        except Exception as e:
            logger.error(f"Error handling notification message: {str(e)}")
    
    async def _handle_task_event(self, message: Dict[str, Any]) -> None:
        """Handle task-related events and generate appropriate notifications."""
        event_type = message.get('type')
        task = message.get('task')
        
        if not task or not isinstance(task, dict):
            return
        
        try:
            if event_type == 'created':
                await self.send_notification(
                    notification_type=NotificationType.INFO,
                    title=f"New Task: {task.get('title', 'Untitled Task')}",
                    message=task.get('description', 'No description provided.'),
                    recipient=task.get('assignee'),
                    metadata={
                        'task_id': task.get('task_id'),
                        'event': 'task_created',
                        'priority': task.get('priority', 'medium')
                    }
                )
            elif event_type == 'completed':
                await self.send_notification(
                    notification_type=NotificationType.SUCCESS,
                    title=f"Task Completed: {task.get('title', 'Untitled Task')}",
                    message=f"The task was completed by {task.get('assignee', 'someone')}.",
                    recipient=task.get('creator'),
                    metadata={
                        'task_id': task.get('task_id'),
                        'event': 'task_completed',
                        'completed_by': task.get('assignee')
                    }
                )
            elif event_type == 'due_soon':
                await self.send_notification(
                    notification_type=NotificationType.TASK_REMINDER,
                    title=f"Task Due Soon: {task.get('title', 'Untitled Task')}",
                    message=f"This task is due on {task.get('due_date')}.",
                    recipient=task.get('assignee'),
                    metadata={
                        'task_id': task.get('task_id'),
                        'event': 'task_due_soon',
                        'due_date': task.get('due_date')
                    }
                )
        except Exception as e:
            logger.error(f"Error handling task event: {str(e)}")
    
    async def _handle_meeting_event(self, message: Dict[str, Any]) -> None:
        """Handle meeting-related events and generate appropriate notifications."""
        event_type = message.get('type')
        meeting = message.get('meeting', {})
        
        try:
            if event_type == 'scheduled':
                await self.send_notification(
                    notification_type=NotificationType.MEETING_REMINDER,
                    title=f"Meeting Scheduled: {meeting.get('title', 'Untitled Meeting')}",
                    message=f"A meeting has been scheduled for {meeting.get('start_time')}.",
                    recipient=meeting.get('attendees', []),
                    metadata={
                        'meeting_id': meeting.get('meeting_id'),
                        'event': 'meeting_scheduled',
                        'start_time': meeting.get('start_time'),
                        'end_time': meeting.get('end_time')
                    }
                )
            elif event_type == 'starting_soon':
                await self.send_notification(
                    notification_type=NotificationType.MEETING_REMINDER,
                    title=f"Meeting Starting Soon: {meeting.get('title', 'Untitled Meeting')}",
                    message=f"Your meeting starts in 15 minutes.",
                    recipient=meeting.get('attendees', []),
                    metadata={
                        'meeting_id': meeting.get('meeting_id'),
                        'event': 'meeting_starting_soon',
                        'start_time': meeting.get('start_time')
                    }
                )
        except Exception as e:
            logger.error(f"Error handling meeting event: {str(e)}")
    
    async def send_notification(
        self,
        notification_type: str,
        title: str,
        message: str,
        recipient: Union[str, List[str], None] = None,
        channels: Optional[List[str]] = None,
        priority: str = 'normal',
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a notification to the specified recipient(s) through the specified channels.
        
        Args:
            notification_type: Type of notification (e.g., 'info', 'error', 'task_reminder')
            title: Notification title
            message: Notification message
            recipient: Recipient user ID(s) or email address(es)
            channels: List of channels to send the notification through
                     (if None, uses default preferences for the notification type)
            priority: Notification priority ('low', 'normal', 'high')
            metadata: Additional metadata to include with the notification
            
        Returns:
            Dictionary with status and notification ID(s)
        """
        if not recipient:
            logger.warning("No recipient specified for notification")
            return {"status": "error", "message": "No recipient specified"}
        
        # Normalize recipients to a list
        if isinstance(recipient, str):
            recipients = [recipient]
        else:
            recipients = list(recipient)
        
        # Get default channels if none specified
        if not channels:
            channels = self._get_default_channels(notification_type)
        
        notification_id = f"notif_{len(self._notifications) + 1}"
        timestamp = datetime.utcnow().isoformat()
        
        notification = {
            "id": notification_id,
            "type": notification_type,
            "title": title,
            "message": message,
            "recipients": recipients,
            "channels": channels,
            "priority": priority,
            "status": "sent",
            "created_at": timestamp,
            "updated_at": timestamp,
            "metadata": metadata or {}
        }
        
        # Store the notification
        self._notifications[notification_id] = notification
        
        # Send the notification through each channel
        send_tasks = []
        
        for channel in channels:
            if channel == NotificationChannel.IN_APP:
                send_tasks.append(self._send_in_app_notification(notification))
            elif channel == NotificationChannel.EMAIL:
                send_tasks.append(self._send_email_notification(notification))
            elif channel == NotificationChannel.SMS:
                send_tasks.append(self._send_sms_notification(notification))
            elif channel == NotificationChannel.PUSH:
                send_tasks.append(self._send_push_notification(notification))
            elif channel == NotificationChannel.SLACK:
                send_tasks.append(self._send_slack_notification(notification))
            elif channel == NotificationChannel.WEBHOOK:
                send_tasks.append(self._send_webhook_notification(notification))
        
        # Wait for all notifications to be sent
        results = await asyncio.gather(*send_tasks, return_exceptions=True)
        
        # Check for any failures
        failures = [r for r in results if isinstance(r, Exception)]
        
        if failures:
            notification["status"] = "partially_failed"
            notification["metadata"]["failures"] = [str(f) for f in failures]
            logger.warning(f"Failed to send some notifications: {failures}")
        
        # Update the stored notification
        notification["updated_at"] = datetime.utcnow().isoformat()
        self._notifications[notification_id] = notification
        
        # Publish an event about the sent notification
        await message_bus.publish("notification.sent", notification)
        
        return {
            "status": "success",
            "notification_id": notification_id,
            "channels": channels,
            "failures": len(failures)
        }
    
    async def list_notifications(
        self,
        user_id: Optional[str] = None,
        notification_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List notifications matching the given filters.
        
        Args:
            user_id: Filter by recipient user ID
            notification_type: Filter by notification type
            status: Filter by status (e.g., 'sent', 'read', 'failed')
            limit: Maximum number of notifications to return
            offset: Offset for pagination
            
        Returns:
            Dictionary containing the list of notifications and pagination info
        """
        filtered = []
        
        for notif in self._notifications.values():
            # Apply filters
            if user_id and user_id not in notif["recipients"]:
                continue
                
            if notification_type and notif["type"] != notification_type:
                continue
                
            if status and notif["status"] != status:
                continue
                
            filtered.append(notif)
        
        # Sort by creation time (newest first)
        filtered.sort(key=lambda x: x["created_at"], reverse=True)
        
        # Apply pagination
        total = len(filtered)
        paginated = filtered[offset:offset + limit]
        
        return {
            "status": "success",
            "notifications": paginated,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + len(paginated)) < total
            }
        }
    
    async def mark_as_read(
        self,
        notification_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark a notification as read for a specific user.
        
        Args:
            notification_id: ID of the notification
            user_id: ID of the user who read the notification
            
        Returns:
            Dictionary with status and updated notification
        """
        if notification_id not in self._notifications:
            return {"status": "error", "message": "Notification not found"}
        
        notification = self._notifications[notification_id]
        
        # Update read status
        if "read_by" not in notification:
            notification["read_by"] = []
        
        if user_id and user_id not in notification["read_by"]:
            notification["read_by"].append(user_id)
        
        notification["status"] = "read"
        notification["updated_at"] = datetime.utcnow().isoformat()
        
        # Store the updated notification
        self._notifications[notification_id] = notification
        
        # Publish an event about the read notification
        await message_bus.publish("notification.read", {
            "notification_id": notification_id,
            "user_id": user_id,
            "read_at": notification["updated_at"]
        })
        
        return {
            "status": "success",
            "notification": notification
        }
    
    async def get_notification_preferences(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get notification preferences for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dictionary with the user's notification preferences
        """
        # In a real implementation, this would fetch from a database
        preferences = self._preferences.get(user_id, self._default_preferences)
        
        return {
            "status": "success",
            "user_id": user_id,
            "preferences": preferences
        }
    
    async def update_notification_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update notification preferences for a user.
        
        Args:
            user_id: ID of the user
            preferences: Dictionary of notification preferences
            
        Returns:
            Dictionary with status and updated preferences
        """
        # In a real implementation, this would save to a database
        if user_id not in self._preferences:
            self._preferences[user_id] = {}
        
        # Update only the provided preferences
        for key, value in preferences.items():
            if key in self._default_preferences:
                self._preferences[user_id][key] = value
        
        # Publish an event about the updated preferences
        await message_bus.publish("notification.preferences_updated", {
            "user_id": user_id,
            "preferences": self._preferences[user_id]
        })
        
        return {
            "status": "success",
            "user_id": user_id,
            "preferences": self._preferences[user_id]
        }
    
    def _get_default_channels(self, notification_type: str) -> List[str]:
        """Get default channels for a notification type."""
        return self._default_preferences.get(notification_type, [NotificationChannel.IN_APP])
    
    async def _send_in_app_notification(self, notification: Dict[str, Any]) -> bool:
        """Send an in-app notification."""
        try:
            # In a real implementation, this would use WebSockets or a similar mechanism
            # to push the notification to the user's active sessions
            logger.info(f"Sending in-app notification to {notification['recipients']}: {notification['title']}")
            return True
        except Exception as e:
            logger.error(f"Failed to send in-app notification: {str(e)}")
            return False
    
    async def _send_email_notification(self, notification: Dict[str, Any]) -> bool:
        """Send an email notification."""
        try:
            # Use the email agent to send the notification
            email_result = await message_bus.request("email_agent", {
                "action": "send_email",
                "to": notification["recipients"],
                "subject": notification["title"],
                "body": notification["message"],
                "body_type": "plain"
            })
            
            return email_result.get("status") == "success"
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
            return False
    
    async def _send_sms_notification(self, notification: Dict[str, Any]) -> bool:
        """Send an SMS notification."""
        try:
            # In a real implementation, this would use an SMS gateway API
            logger.info(f"Sending SMS to {notification['recipients']}: {notification['message']}")
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS notification: {str(e)}")
            return False
    
    async def _send_push_notification(self, notification: Dict[str, Any]) -> bool:
        """Send a push notification."""
        try:
            # In a real implementation, this would use Firebase Cloud Messaging (FCM) or similar
            logger.info(f"Sending push notification to {notification['recipients']}: {notification['title']}")
            return True
        except Exception as e:
            logger.error(f"Failed to send push notification: {str(e)}")
            return False
    
    async def _send_slack_notification(self, notification: Dict[str, Any]) -> bool:
        """Send a Slack notification."""
        try:
            # In a real implementation, this would use the Slack API
            logger.info(f"Sending Slack notification: {notification['title']} - {notification['message']}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {str(e)}")
            return False
    
    async def _send_webhook_notification(self, notification: Dict[str, Any]) -> bool:
        """Send a webhook notification."""
        try:
            # In a real implementation, this would make an HTTP POST request to the webhook URL
            logger.info(f"Sending webhook notification: {notification['title']}")
            return True
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {str(e)}")
            return False
    
    async def process(self, message: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process notification-related messages."""
        action = message.get('action')
        
        try:
            if action == 'send':
                return await self.send_notification(
                    notification_type=message.get('type', NotificationType.INFO),
                    title=message.get('title'),
                    message=message.get('message'),
                    recipient=message.get('recipient'),
                    channels=message.get('channels'),
                    priority=message.get('priority', 'normal'),
                    metadata=message.get('metadata', {})
                )
            elif action == 'list':
                return await self.list_notifications(
                    user_id=message.get('user_id'),
                    notification_type=message.get('type'),
                    status=message.get('status'),
                    limit=message.get('limit', 50),
                    offset=message.get('offset', 0)
                )
            elif action == 'mark_as_read' and 'notification_id' in message:
                return await self.mark_as_read(
                    notification_id=message['notification_id'],
                    user_id=message.get('user_id')
                )
            elif action == 'get_preferences' and 'user_id' in message:
                return await self.get_notification_preferences(message['user_id'])
            elif action == 'update_preferences' and 'user_id' in message and 'preferences' in message:
                return await self.update_notification_preferences(
                    user_id=message['user_id'],
                    preferences=message['preferences']
                )
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown action or missing parameters: {action}'
                }
        except Exception as e:
            logger.error(f"Error in NotificationAgent: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

# Register the agent
notification_agent = NotificationAgent()
agent_registry.register(notification_agent)
