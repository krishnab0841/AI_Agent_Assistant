"""
Configuration settings for the AI Agent Assistant.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class."""
    # API Configuration
    API_TITLE = "AI Agent Assistant API"
    API_VERSION = "0.1.0"
    
    # Google Gemini API
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    # WebSocket Configuration
    WEBSOCKET_PATH = "/ws"
    
    # CORS Configuration
    CORS_ORIGINS = ["*"]  # In production, replace with your frontend URL
    
    # Application Settings
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    @classmethod
    def check_required_vars(cls):
        """Check that all required environment variables are set."""
        required_vars = [
            ("GOOGLE_API_KEY", cls.GOOGLE_API_KEY),
        ]
        
        missing = [name for name, value in required_vars if not value]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

# Initialize configuration
config = Config()

# Check required environment variables on import
config.check_required_vars()
