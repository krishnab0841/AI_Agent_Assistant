"""
Message Bus for inter-agent communication.
"""
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable, Set
from uuid import uuid4
import time

# Set up logging
logger = logging.getLogger(__name__)

MessageHandler = Callable[[Dict[str, Any]], Awaitable[None]]

class MessageBus:
    """
    A simple message bus for inter-agent communication.
    Supports pub/sub and request/response patterns.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MessageBus, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the message bus."""
        self._subscriptions: Dict[str, Set[MessageHandler]] = {}
        self._response_handlers: Dict[str, asyncio.Future] = {}
        self._response_timeout = 30  # seconds
    
    async def publish(self, channel: str, message: Dict[str, Any]) -> None:
        """
        Publish a message to a channel.
        
        Args:
            channel: The channel to publish to
            message: The message to publish (must be JSON-serializable)
        """
        if not channel:
            raise ValueError("Channel cannot be empty")
        
        logger.debug(f"Publishing to {channel}: {json.dumps(message, indent=2)}")
        
        # Call all handlers subscribed to this channel
        handlers = self._subscriptions.get(channel, set())
        
        # Also check for wildcard subscriptions (e.g., 'agent.*' matches 'agent.scheduler')
        for sub_channel in self._subscriptions:
            if sub_channel.endswith('*') and channel.startswith(sub_channel[:-1]):
                handlers.update(self._subscriptions[sub_channel])
        
        # Execute handlers in parallel
        await asyncio.gather(
            *[handler(message) for handler in handlers],
            return_exceptions=True
        )
    
    async def request(
        self,
        channel: str,
        message: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Send a request and wait for a response.
        
        Args:
            channel: The channel to send the request to
            message: The request message (must be JSON-serializable)
            timeout: Timeout in seconds (default: self._response_timeout)
            
        Returns:
            The response message
            
        Raises:
            asyncio.TimeoutError: If no response is received within the timeout
            Exception: If an error occurs in the handler
        """
        if not channel:
            raise ValueError("Channel cannot be empty")
        
        # Generate a unique ID for this request
        request_id = f"req_{uuid4().hex}"
        
        # Create a future to hold the response
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._response_handlers[request_id] = future
        
        # Add request ID to the message
        message = message.copy()
        message['_request_id'] = request_id
        
        # Set up timeout
        timeout = timeout or self._response_timeout
        
        try:
            # Publish the request
            await self.publish(channel, message)
            
            # Wait for the response with timeout
            return await asyncio.wait_for(future, timeout)
        finally:
            # Clean up the future
            if request_id in self._response_handlers:
                del self._response_handlers[request_id]
    
    async def respond(
        self,
        request_message: Dict[str, Any],
        response: Dict[str, Any]
    ) -> None:
        """
        Send a response to a request.
        
        Args:
            request_message: The original request message
            response: The response message (must be JSON-serializable)
        """
        request_id = request_message.get('_request_id')
        if not request_id:
            logger.warning("Cannot respond: no request_id in message")
            return
        
        # Add response time and request ID to the response
        response = response.copy()
        response['_request_id'] = request_id
        response['_response_time'] = time.time()
        
        # Complete the future if it exists
        if request_id in self._response_handlers:
            future = self._response_handlers[request_id]
            if not future.done():
                future.set_result(response)
            del self._response_handlers[request_id]
    
    def subscribe(self, channel: str, handler: MessageHandler) -> Callable:
        """
        Subscribe to messages on a channel.
        
        Args:
            channel: The channel to subscribe to (supports * wildcard)
            handler: The handler function to call when a message is received
            
        Returns:
            A function that can be called to unsubscribe
        """
        if not channel:
            raise ValueError("Channel cannot be empty")
        
        if channel not in self._subscriptions:
            self._subscriptions[channel] = set()
        
        self._subscriptions[channel].add(handler)
        
        # Return an unsubscribe function
        def unsubscribe():
            if channel in self._subscriptions:
                self._subscriptions[channel].discard(handler)
                if not self._subscriptions[channel]:
                    del self._subscriptions[channel]
        
        return unsubscribe
    
    def unsubscribe(self, channel: str, handler: MessageHandler) -> None:
        """
        Unsubscribe a handler from a channel.
        
        Args:
            channel: The channel to unsubscribe from
            handler: The handler to remove
        """
        if channel in self._subscriptions:
            self._subscriptions[channel].discard(handler)
            if not self._subscriptions[channel]:
                del self._subscriptions[channel]
    
    def clear(self) -> None:
        """Clear all subscriptions and pending requests."""
        self._subscriptions.clear()
        
        # Cancel all pending requests
        for request_id, future in list(self._response_handlers.items()):
            if not future.done():
                future.cancel()
            del self._response_handlers[request_id]

# Global message bus instance
message_bus = MessageBus()
