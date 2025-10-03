"""
Enhanced Email Agent for sending and managing emails with Gmail integration.
"""
import os
import smtplib
import logging
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr, parseaddr, formatdate, make_msgid
from typing import Dict, Any, List, Optional, Union
import mimetypes
import json
from pathlib import Path

from . import Agent, agent_registry
from ..config import config

# Set up logging
logger = logging.getLogger(__name__)

class EmailAgent(Agent):
    """Agent responsible for sending and managing emails with Gmail integration."""
    
    # OAuth2 scopes required for Gmail
    _SCOPES = [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.compose',
        'https://www.googleapis.com/auth/gmail.modify'
    ]
    
    def __init__(self):
        super().__init__(
            agent_id="email_agent",
            name="Email Agent",
            description="Handles sending and managing emails with Gmail integration"
        )
        self.capabilities = [
            "send_email",
            "verify_email_setup",
            "list_templates",
            "get_template"
        ]
        
        # Load SMTP configuration
        self.smtp_config = {
            'host': os.getenv('SMTP_HOST', 'smtp.gmail.com'),
            'port': int(os.getenv('SMTP_PORT', 587)),
            'username': os.getenv('SMTP_USERNAME', ''),
            'password': os.getenv('SMTP_PASSWORD', ''),
            'from_email': os.getenv('SMTP_FROM_EMAIL', os.getenv('SMTP_USERNAME', '')),
            'from_name': os.getenv('SMTP_FROM_NAME', 'AI Assistant'),
            'use_tls': os.getenv('SMTP_USE_TLS', 'true').lower() == 'true',
            'timeout': int(os.getenv('SMTP_TIMEOUT', 10))
        }
        
        # Templates directory
        self.templates_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'templates',
            'emails'
        )
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # Initialize SMTP connection
        self.smtp_connection = None
    
    async def process(self, message: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process email-related messages."""
        action = message.get('action')
        
        try:
            if action == 'send_email':
                return await self.send_email(
                    to_emails=message.get('to'),
                    subject=message.get('subject', 'No Subject'),
                    body=message.get('body', ''),
                    body_type=message.get('body_type', 'plain'),
                    cc_emails=message.get('cc', []),
                    bcc_emails=message.get('bcc', []),
                    reply_to=message.get('reply_to'),
                    attachments=message.get('attachments', [])
                )
            elif action == 'verify_setup':
                return await self.verify_smtp_connection()
            elif action == 'list_templates':
                return await self.list_email_templates()
            elif action == 'get_template':
                return await self.get_email_template(message.get('template_name'))
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown action: {action}'
                }
        except Exception as e:
            logger.error(f"Error in EmailAgent: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    async def verify_smtp_connection(self) -> Dict[str, Any]:
        """Verify SMTP connection and authentication."""
        try:
            # Check if required settings are present
            if not self.smtp_config['username'] or not self.smtp_config['password']:
                return {
                    'status': 'error',
                    'message': 'SMTP username and password are required',
                    'configured': False
                }
            
            # Test SMTP connection
            with self._get_smtp_connection() as server:
                # If we get here, connection was successful
                return {
                    'status': 'success',
                    'message': 'SMTP connection successful',
                    'configured': True,
                    'server': self.smtp_config['host'],
                    'port': self.smtp_config['port'],
                    'username': self.smtp_config['username'],
                    'from_email': self.smtp_config['from_email']
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'SMTP connection failed: {str(e)}',
                'configured': False
            }
    
    def _get_smtp_connection(self):
        """
        Create and return a new SMTP connection.
        
        Returns:
            SMTP: An authenticated SMTP connection
            
        Raises:
            smtplib.SMTPException: If connection or authentication fails
        """
        context = ssl.create_default_context()
        
        # Create SMTP connection
        server = smtplib.SMTP(
            host=self.smtp_config['host'],
            port=self.smtp_config['port'],
            timeout=self.smtp_config['timeout']
        )
        
        # Start TLS if needed
        if self.smtp_config['use_tls']:
            server.starttls(context=context)
        
        # Authenticate using OAuth2 or password
        if self.smtp_config['use_oauth2']:
            creds = self._get_oauth2_credentials()
            if not creds or not creds.valid:
                raise smtplib.SMTPAuthenticationError(
                    534, 
                    'OAuth2 credentials not valid or expired. Please re-authenticate.'
                )
            
            # Get the access token
            access_token = creds.token
            
            # Authenticate with XOAUTH2
            auth_string = 'user=%s\1auth=Bearer %s\1\1' % (
                self.smtp_config['username'], 
                access_token
            )
            auth_string = base64.b64encode(auth_string.encode()).decode()
            
            # Send the authentication command
            code, response = server.docmd('AUTH', 'XOAUTH2 ' + auth_string)
            if code != 235:
                raise smtplib.SMTPAuthenticationError(
                    code, 
                    response.decode() if hasattr(response, 'decode') else str(response)
                )
        else:
            # Standard username/password authentication
            if self.smtp_config['username'] and self.smtp_config['password']:
                try:
                    server.login(
                        self.smtp_config['username'],
                        self.smtp_config['password']
                    )
                except smtplib.SMTPAuthenticationError as e:
                    if 'Application-specific password required' in str(e):
                        raise smtplib.SMTPAuthenticationError(
                            e.smtp_code,
                            'Application-specific password required. Enable 2-Step Verification and generate an App Password at: https://myaccount.google.com/apppasswords'
                        ) from e
                    raise
        
        return server
    
    async def send_email(
        self,
        to_emails: Union[str, List[str]],
        subject: str,
        body: str,
        body_type: str = 'plain',
        cc_emails: Optional[Union[str, List[str]]] = None,
        bcc_emails: Optional[Union[str, List[str]]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        use_gmail_api: bool = False
    ) -> Dict[str, Any]:
        """
        Send an email with the given parameters.
        
        Args:
            to_emails: Single email or list of recipient emails
            subject: Email subject
            body: Email body content
            body_type: 'plain' or 'html'
            cc_emails: CC recipients
            bcc_emails: BCC recipients
            reply_to: Reply-to email address
            attachments: List of attachment dicts with 'filename' and 'content'
            
        Returns:
            Dict with status and message
        """
        # Normalize email addresses
        to_emails = self._normalize_emails(to_emails)
        cc_emails = self._normalize_emails(cc_emails or [])
        bcc_emails = self._normalize_emails(bcc_emails or [])
        
        if not to_emails and not cc_emails and not bcc_emails:
            return {'status': 'error', 'message': 'No recipients specified'}
        
        # Create message container
        msg = MIMEMultipart()
        msg['From'] = formataddr((self.smtp_config['from_name'], self.smtp_config['from_email']))
        msg['To'] = ', '.join(to_emails)
        if cc_emails:
            msg['Cc'] = ', '.join(cc_emails)
        if reply_to:
            msg['Reply-To'] = reply_to
        
        msg['Subject'] = subject
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid()
        
        # Attach body
        msg.attach(MIMEText(body, body_type))
        
        # Add attachments if any
        if attachments:
            for attachment in attachments:
                self._add_attachment(msg, attachment)
        
        # All recipients (to + cc + bcc)
        all_recipients = to_emails + cc_emails + bcc_emails
        
        try:
            # Use Gmail API if requested and OAuth2 is configured
            if use_gmail_api and self.smtp_config['use_oauth2']:
                return await self._send_via_gmail_api(msg, all_recipients)
            
            # Otherwise use SMTP
            with self._get_smtp_connection() as server:
                server.send_message(msg)
            
            logger.info(f"Email sent to {', '.join(all_recipients)}")
            return self._create_success_response(
                to_emails, 
                cc_emails, 
                bcc_emails, 
                subject, 
                msg['Message-ID']
            )
            
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP authentication failed: {str(e)}"
            if 'Application-specific password required' in str(e):
                error_msg += "\nYou need to use an App Password instead of your regular Gmail password. "
                error_msg += "Enable 2-Step Verification and generate an App Password at: https://myaccount.google.com/apppasswords"
            logger.error(error_msg)
            return {
                'status': 'error',
                'message': error_msg
            }
            
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {str(e)}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'message': error_msg
            }
            
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'message': error_msg
            }
    
    async def list_email_templates(self) -> Dict[str, Any]:
        """List all available email templates."""
        try:
            if not os.path.exists(self.templates_dir):
                return {
                    'status': 'success',
                    'templates': [],
                    'templates_dir': self.templates_dir
                }
            
            templates = []
            for file in os.listdir(self.templates_dir):
                if file.endswith('.html'):
                    templates.append({
                        'name': os.path.splitext(file)[0],
                        'filename': file,
                        'path': os.path.join(self.templates_dir, file)
                    })
            
            return {
                'status': 'success',
                'templates': templates,
                'templates_dir': self.templates_dir
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to list templates: {str(e)}'
            }
    
    async def get_email_template(self, template_name: str) -> Dict[str, Any]:
        """Get the content of an email template."""
        try:
            if not template_name:
                return {
                    'status': 'error',
                    'message': 'Template name is required'
                }
            
            # Ensure template has .html extension
            if not template_name.endswith('.html'):
                template_name += '.html'
            
            template_path = os.path.join(self.templates_dir, template_name)
            
            if not os.path.exists(template_path):
                return {
                    'status': 'error',
                    'message': f'Template not found: {template_name}'
                }
            
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                'status': 'success',
                'template': {
                    'name': os.path.splitext(template_name)[0],
                    'filename': template_name,
                    'path': template_path,
                    'content': content
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get template: {str(e)}'
            }
    
    def _get_oauth2_credentials(self):
        """
        Get OAuth2 credentials, refreshing if necessary.
        
        Returns:
            google.oauth2.credentials.Credentials or None: The OAuth2 credentials
        """
        creds = None
        token_path = self.smtp_config['token_path']
        
        # Try to load existing credentials
        if os.path.exists(token_path):
            try:
                creds = Credentials.from_authorized_user_file(token_path, self._SCOPES)
            except Exception as e:
                logger.warning(f"Error loading credentials: {e}")
        
        # If no valid credentials, try to refresh
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Save the refreshed credentials
                    with open(token_path, 'w') as token:
                        token.write(creds.to_json())
                except Exception as e:
                    logger.error(f"Error refreshing token: {e}")
                    return None
            else:
                return None
                
        return creds
    
    def get_oauth2_auth_url(self) -> str:
        """
        Get the authorization URL for OAuth2 authentication.
        
        Returns:
            str: The authorization URL
        """
        if not os.path.exists(self.smtp_config['credentials_path']):
            raise FileNotFoundError(
                f"OAuth2 credentials file not found at {self.smtp_config['credentials_path']}"
            )
            
        flow = InstalledAppFlow.from_client_secrets_file(
            self.smtp_config['credentials_path'],
            self._SCOPES
        )
        
        # Generate the authorization URL
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            prompt='consent',
            include_granted_scopes='true'
        )
        
        return auth_url
    
    def exchange_oauth2_code(self, authorization_response: str) -> bool:
        """
        Exchange the authorization code for OAuth2 tokens.
        
        Args:
            authorization_response: The full redirect URL after user authorization
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.smtp_config['credentials_path'],
                self._SCOPES
            )
            
            # Exchange the code for a token
            flow.fetch_token(authorization_response=authorization_response)
            
            # Save the credentials
            creds = flow.credentials
            with open(self.smtp_config['token_path'], 'w') as token:
                token.write(creds.to_json())
                
            return True
            
        except Exception as e:
            logger.error(f"Error exchanging authorization code: {e}")
            return False
    
    def _normalize_emails(self, emails: Union[str, List[str]]) -> List[str]:
        """Normalize email addresses to a list of valid email strings."""
        if not emails:
            return []
            
        if isinstance(emails, str):
            if ',' in emails:
                emails = [e.strip() for e in emails.split(',') if e.strip()]
            else:
                emails = [emails.strip()]
        
        # Validate email format
        valid_emails = []
        for email in emails:
            _, email_addr = parseaddr(email)
            if '@' in email_addr and '.' in email_addr.split('@')[1]:
                valid_emails.append(email_addr)
        
        return valid_emails
    
    def _create_success_response(
        self, 
        to_emails: List[str], 
        cc_emails: List[str], 
        bcc_emails: List[str], 
        subject: str, 
        message_id: str
    ) -> Dict[str, Any]:
        """Create a standardized success response for sent emails."""
        return {
            'status': 'success',
            'message': 'Email sent successfully',
            'to': to_emails,
            'cc': cc_emails,
            'bcc': bcc_emails,
            'subject': subject,
            'message_id': message_id,
            'timestamp': formatdate(localtime=True)
        }
    
    async def _send_via_gmail_api(
        self, 
        message: MIMEMultipart, 
        recipients: List[str]
    ) -> Dict[str, Any]:
        """
        Send an email using the Gmail API.
        
        Args:
            message: The email message to send
            recipients: List of recipient email addresses
            
        Returns:
            Dict with status and message
        """
        try:
            creds = self._get_oauth2_credentials()
            if not creds or not creds.valid:
                return {
                    'status': 'error',
                    'message': 'Valid OAuth2 credentials are required to use the Gmail API',
                    'auth_required': True
                }
            
            # Create the Gmail API client
            service = build('gmail', 'v1', credentials=creds)
            
            # Convert message to string and then to base64url
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode()
            
            # Send the message
            send_request = service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            )
            result = send_request.execute()
            
            logger.info(f"Email sent via Gmail API to {', '.join(recipients)}")
            
            return {
                'status': 'success',
                'message': 'Email sent successfully via Gmail API',
                'gmail_message_id': result.get('id'),
                'thread_id': result.get('threadId'),
                'label_ids': result.get('labelIds', []),
                'timestamp': formatdate(localtime=True)
            }
            
        except Exception as e:
            error_msg = f"Failed to send email via Gmail API: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'message': error_msg
            }
    
    def _add_attachment(self, msg: MIMEMultipart, attachment: Dict[str, Any]) -> bool:
        """Add an attachment to the email."""
        try:
            filename = attachment.get('filename', 'attachment.bin')
            content = attachment.get('content')
            content_type = attachment.get('content_type')
            
            if not content:
                logger.warning("Skipping empty attachment")
                return False
            
            # If content is a file path, read the file
            if isinstance(content, str) and os.path.isfile(content):
                with open(content, 'rb') as f:
                    content = f.read()
                if not filename or filename == 'attachment.bin':
                    filename = os.path.basename(content)
            elif isinstance(content, str):
                content = content.encode('utf-8')
            
            # Guess content type if not provided
            if not content_type:
                content_type, _ = mimetypes.guess_type(filename)
                if not content_type:
                    content_type = 'application/octet-stream'
            
            # Create the attachment
            maintype, subtype = content_type.split('/', 1) if '/' in content_type else (content_type, '')
            
            attachment_part = MIMEApplication(content, _subtype=subtype)
            attachment_part.add_header('Content-Disposition', 'attachment', filename=filename)
            
            # Add to message
            msg.attach(attachment_part)
            return True
            
        except Exception as e:
            logger.error(f"Failed to add attachment: {str(e)}")
            return False

# Register the agent
email_agent = EmailAgent()
agent_registry.register(email_agent)
