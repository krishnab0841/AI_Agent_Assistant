"""
Agent system for the AI Agent Assistant.
This module contains the base agent class and agent registry.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import json
import asyncio
from datetime import datetime

class Agent(ABC):
    """Base class for all agents."""
    
    def __init__(self, agent_id: str, name: str, description: str):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.capabilities = []
        
    @abstractmethod
    async def process(self, message: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a message and return a response."""
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary representation."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities
        }

class AgentRegistry:
    """Manages registration and lookup of agents."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentRegistry, cls).__new__(cls)
            cls._instance._agents = {}
        return cls._instance
    
    def register(self, agent: Agent) -> None:
        """Register a new agent."""
        self._agents[agent.agent_id] = agent
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)
    
    def get_agents(self) -> List[Agent]:
        """Get all registered agents."""
        return list(self._agents.values())
    
    def find_agent_by_capability(self, capability: str) -> List[Agent]:
        """Find agents that have a specific capability."""
        return [
            agent for agent in self._agents.values() 
            if capability in agent.capabilities
        ]

# Global agent registry
agent_registry = AgentRegistry()
