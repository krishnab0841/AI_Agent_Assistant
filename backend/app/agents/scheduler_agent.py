"""
Scheduler Agent for managing calendar events and scheduling.
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import pytz
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from . import Agent, agent_registry
from ..config import config

# Set up logging
logger = logging.getLogger(__name__)

# If modifying these scopes, delete the token.json file
SCOPES = ['https://www.googleapis.com/auth/calendar']

class SchedulerAgent(Agent):
    """Agent responsible for scheduling and managing calendar events."""
    
    def __init__(self):
        super().__init__(
            agent_id="scheduler_agent",
            name="Scheduler Agent",
            description="Manages calendar events and scheduling"
        )
        self.capabilities = [
            "schedule_meeting",
            "list_events",
            "update_event",
            "cancel_event"
        ]
        self.service = self._get_calendar_service()
    
    def _get_calendar_service(self):
        """Get Google Calendar service with proper authentication."""
        creds = None
        token_path = os.path.join(os.path.dirname(__file__), '..', '..', 'token.json')
        credentials_path = os.path.join(os.path.dirname(__file__), '..', '..', 'credentials.json')
        
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError("credentials.json not found. Please set up Google OAuth credentials.")
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
        
        return build('calendar', 'v3', credentials=creds)
    
    async def process(self, message: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process scheduling-related messages."""
        action = message.get('action')
        
        try:
            if action == 'schedule_meeting':
                return await self._schedule_meeting(message)
            elif action == 'list_events':
                return await self._list_events(message)
            elif action == 'update_event':
                return await self._update_event(message)
            elif action == 'cancel_event':
                return await self._cancel_event(message)
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown action: {action}'
                }
        except Exception as e:
            logger.error(f"Error in SchedulerAgent: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def _schedule_meeting(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a new meeting."""
        required_fields = ['summary', 'start_time', 'end_time', 'attendees']
        for field in required_fields:
            if field not in data:
                return {'status': 'error', 'message': f'Missing required field: {field}'}
        
        # Convert times to RFC3339 format
        timezone = data.get('timezone', 'UTC')
        start_time = self._parse_datetime(data['start_time'], timezone)
        end_time = self._parse_datetime(data['end_time'], timezone)
        
        event = {
            'summary': data['summary'],
            'location': data.get('location', ''),
            'description': data.get('description', ''),
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': timezone,
            },
            'attendees': [{'email': email} for email in data['attendees']],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }
        
        # Add recurrence rule if specified
        if 'recurrence' in data:
            event['recurrence'] = [data['recurrence']]
        
        try:
            event = self.service.events().insert(calendarId='primary', body=event).execute()
            return {
                'status': 'success',
                'event_id': event['id'],
                'html_link': event.get('htmlLink'),
                'message': f"Event created: {event['summary']}"
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def _list_events(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """List upcoming events."""
        time_min = data.get('time_min', datetime.utcnow().isoformat() + 'Z')
        max_results = data.get('max_results', 10)
        
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return {
                'status': 'success',
                'events': [{
                    'id': event['id'],
                    'summary': event.get('summary', 'No title'),
                    'start': event['start'].get('dateTime', event['start'].get('date')),
                    'end': event['end'].get('dateTime', event['end'].get('date')),
                    'status': event.get('status'),
                    'htmlLink': event.get('htmlLink')
                } for event in events]
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def _update_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing event."""
        if 'event_id' not in data:
            return {'status': 'error', 'message': 'Missing event_id'}
        
        try:
            # First get the existing event
            event = self.service.events().get(
                calendarId='primary',
                eventId=data['event_id']
            ).execute()
            
            # Update fields if provided
            if 'summary' in data:
                event['summary'] = data['summary']
            if 'description' in data:
                event['description'] = data['description']
            if 'location' in data:
                event['location'] = data['location']
            if 'start_time' in data:
                event['start'] = {
                    'dateTime': self._parse_datetime(data['start_time'], data.get('timezone', 'UTC')).isoformat(),
                    'timeZone': data.get('timezone', 'UTC')
                }
            if 'end_time' in data:
                event['end'] = {
                    'dateTime': self._parse_datetime(data['end_time'], data.get('timezone', 'UTC')).isoformat(),
                    'timeZone': data.get('timezone', 'UTC')
                }
            if 'attendees' in data:
                event['attendees'] = [{'email': email} for email in data['attendees']]
            
            # Update the event
            updated_event = self.service.events().update(
                calendarId='primary',
                eventId=event['id'],
                body=event
            ).execute()
            
            return {
                'status': 'success',
                'event_id': updated_event['id'],
                'message': f"Event updated: {updated_event['summary']}"
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def _cancel_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel an existing event."""
        if 'event_id' not in data:
            return {'status': 'error', 'message': 'Missing event_id'}
        
        try:
            self.service.events().delete(
                calendarId='primary',
                eventId=data['event_id']
            ).execute()
            
            return {
                'status': 'success',
                'message': f"Event {data['event_id']} has been cancelled."
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _parse_datetime(self, dt_str: str, timezone_str: str = 'UTC') -> datetime:
        """Parse a datetime string with timezone support."""
        timezone = pytz.timezone(timezone_str)
        
        # Try parsing with timezone first
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = timezone.localize(dt)
            return dt
        except ValueError:
            pass
        
        # Try parsing as a relative time (e.g., "in 2 hours")
        if dt_str.startswith('in '):
            try:
                parts = dt_str[3:].split()
                if len(parts) >= 2 and parts[0].isdigit():
                    value = int(parts[0])
                    unit = parts[1].lower()
                    
                    now = datetime.now(timezone)
                    if 'minute' in unit:
                        return now + timedelta(minutes=value)
                    elif 'hour' in unit:
                        return now + timedelta(hours=value)
                    elif 'day' in unit:
                        return now + timedelta(days=value)
                    elif 'week' in unit:
                        return now + timedelta(weeks=value)
            except (ValueError, IndexError):
                pass
        
        # If we get here, we couldn't parse the datetime
        raise ValueError(f"Could not parse datetime: {dt_str}")

# Register the agent
scheduler_agent = SchedulerAgent()
agent_registry.register(scheduler_agent)
