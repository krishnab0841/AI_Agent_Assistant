"""
Entry point for the AI Agent Assistant backend.
"""
import uvicorn
from .main import app

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
