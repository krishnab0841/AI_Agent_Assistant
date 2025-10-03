"""
Task Agent for managing and tracking tasks.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
import uuid

from . import Agent, agent_registry
from .message_bus import message_bus

# Set up logging
logger = logging.getLogger(__name__)

class TaskStatus:
    """Task status constants."""
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'

class TaskPriority:
    """Task priority constants."""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'

class Task:
    """Represents a task in the system."""
    
    def __init__(
        self,
        task_id: str,
        title: str,
        description: str = '',
        priority: str = TaskPriority.MEDIUM,
        due_date: Optional[datetime] = None,
        assignee: Optional[str] = None,
        creator: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.task_id = task_id
        self.title = title
        self.description = description
        self.priority = priority
        self.status = TaskStatus.PENDING
        self.due_date = due_date
        self.assignee = assignee
        self.creator = creator
        self.tags = set(tags) if tags else set()
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
        self.updated_at = self.created_at
        self.completed_at: Optional[datetime] = None
        self.dependencies: Set[str] = set()
        self.dependents: Set[str] = set()
        self.progress = 0.0  # 0.0 to 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            'task_id': self.task_id,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'assignee': self.assignee,
            'creator': self.creator,
            'tags': list(self.tags),
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'dependencies': list(self.dependencies),
            'dependents': list(self.dependents),
            'progress': self.progress
        }
    
    def update(self, updates: Dict[str, Any]) -> None:
        """Update task attributes."""
        for key, value in updates.items():
            if hasattr(self, key):
                if key in ('tags', 'dependencies', 'dependents'):
                    # Convert lists to sets for these attributes
                    setattr(self, key, set(value) if value else set())
                else:
                    setattr(self, key, value)
        self.updated_at = datetime.utcnow()
    
    def add_dependency(self, task_id: str) -> bool:
        """Add a task dependency."""
        if task_id != self.task_id and task_id not in self.dependencies:
            self.dependencies.add(task_id)
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def remove_dependency(self, task_id: str) -> bool:
        """Remove a task dependency."""
        if task_id in self.dependencies:
            self.dependencies.remove(task_id)
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def add_dependent(self, task_id: str) -> bool:
        """Add a dependent task."""
        if task_id != self.task_id and task_id not in self.dependents:
            self.dependents.add(task_id)
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def remove_dependent(self, task_id: str) -> bool:
        """Remove a dependent task."""
        if task_id in self.dependents:
            self.dependents.remove(task_id)
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def update_progress(self, progress: float) -> None:
        """Update task progress (0.0 to 1.0)."""
        self.progress = max(0.0, min(1.0, progress))
        self.updated_at = datetime.utcnow()
    
    def start(self) -> bool:
        """Mark task as in progress."""
        if self.status == TaskStatus.PENDING:
            self.status = TaskStatus.IN_PROGRESS
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def complete(self) -> bool:
        """Mark task as completed."""
        if self.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED):
            self.status = TaskStatus.COMPLETED
            self.progress = 1.0
            self.completed_at = datetime.utcnow()
            self.updated_at = self.completed_at
            return True
        return False
    
    def cancel(self) -> bool:
        """Mark task as cancelled."""
        if self.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED):
            self.status = TaskStatus.CANCELLED
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def fail(self) -> bool:
        """Mark task as failed."""
        if self.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED):
            self.status = TaskStatus.FAILED
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def is_overdue(self) -> bool:
        """Check if the task is overdue."""
        if self.due_date and self.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            return datetime.utcnow() > self.due_date.replace(tzinfo=None)
        return False

class TaskAgent(Agent):
    """Agent responsible for managing and tracking tasks."""
    
    def __init__(self):
        super().__init__(
            agent_id="task_agent",
            name="Task Agent",
            description="Manages and tracks tasks"
        )
        self.capabilities = [
            "create_task",
            "get_task",
            "update_task",
            "delete_task",
            "list_tasks",
            "start_task",
            "complete_task",
            "cancel_task",
            "fail_task",
            "add_dependency",
            "remove_dependency",
            "add_comment",
            "get_comments"
        ]
        
        # In-memory storage (in a real app, use a database)
        self._tasks: Dict[str, Task] = {}
        self._comments: Dict[str, List[Dict[str, Any]]] = {}
        
        # Set up message bus subscriptions
        self._subscriptions = [
            message_bus.subscribe("task.*", self._handle_task_message),
            message_bus.subscribe("schedule.task_reminder", self._handle_task_reminder)
        ]
        
        # Start background task for checking due tasks
        self._background_task = asyncio.create_task(self._check_due_tasks())
    
    async def _handle_task_message(self, message: Dict[str, Any]) -> None:
        """Handle task-related messages from the message bus."""
        action = message.get('action')
        task_id = message.get('task_id')
        
        try:
            if action == 'create':
                await self.create_task(
                    title=message['title'],
                    description=message.get('description', ''),
                    priority=message.get('priority', TaskPriority.MEDIUM),
                    due_date=message.get('due_date'),
                    assignee=message.get('assignee'),
                    creator=message.get('creator'),
                    tags=message.get('tags'),
                    metadata=message.get('metadata')
                )
            elif action == 'update' and task_id:
                updates = {k: v for k, v in message.items() 
                         if k not in ('action', 'task_id')}
                await self.update_task(task_id, updates)
            elif action == 'start' and task_id:
                await self.start_task(task_id)
            elif action == 'complete' and task_id:
                await self.complete_task(task_id)
            elif action == 'cancel' and task_id:
                await self.cancel_task(task_id)
            elif action == 'fail' and task_id:
                await self.fail_task(task_id)
            elif action == 'add_dependency' and task_id and 'depends_on' in message:
                await self.add_dependency(task_id, message['depends_on'])
            elif action == 'remove_dependency' and task_id and 'depends_on' in message:
                await self.remove_dependency(task_id, message['depends_on'])
            elif action == 'add_comment' and task_id and 'comment' in message:
                await self.add_comment(
                    task_id=task_id,
                    author=message.get('author', 'system'),
                    comment=message['comment']
                )
        except Exception as e:
            logger.error(f"Error handling task message: {str(e)}")
    
    async def _handle_task_reminder(self, message: Dict[str, Any]) -> None:
        """Handle task reminder messages."""
        task_id = message.get('task_id')
        if not task_id:
            return
            
        task = self._tasks.get(task_id)
        if not task:
            return
            
        # Send a notification about the due task
        await message_bus.publish("notification.send", {
            "type": "task_reminder",
            "title": f"Task Due: {task.title}",
            "message": task.description or "No description provided.",
            "priority": task.priority,
            "task_id": task_id,
            "due_date": task.due_date.isoformat() if task.due_date else None
        })
    
    async def _check_due_tasks(self) -> None:
        """Background task to check for due tasks and send reminders."""
        while True:
            try:
                now = datetime.utcnow()
                for task in self._tasks.values():
                    if task.due_date and not task.completed_at and not task.is_overdue():
                        time_until_due = (task.due_date - now).total_seconds()
                        
                        # Send reminder if due in the next hour
                        if 0 < time_until_due <= 3600:  # 1 hour in seconds
                            await message_bus.publish("schedule.task_reminder", {
                                "task_id": task.task_id
                            })
                
                # Check every 5 minutes
                await asyncio.sleep(300)
            except asyncio.CancelledError:
                # Clean up on cancellation
                break
            except Exception as e:
                logger.error(f"Error in task reminder loop: {str(e)}")
                await asyncio.sleep(60)  # Wait a minute before retrying
    
    async def create_task(
        self,
        title: str,
        description: str = '',
        priority: str = TaskPriority.MEDIUM,
        due_date: Optional[datetime] = None,
        assignee: Optional[str] = None,
        creator: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new task."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = Task(
            task_id=task_id,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            assignee=assignee,
            creator=creator,
            tags=tags,
            metadata=metadata or {}
        )
        
        self._tasks[task_id] = task
        self._comments[task_id] = []
        
        # Notify about the new task
        await message_bus.publish("task.created", task.to_dict())
        
        return {"status": "success", "task_id": task_id, "task": task.to_dict()}
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID."""
        task = self._tasks.get(task_id)
        return task.to_dict() if task else None
    
    async def update_task(
        self, 
        task_id: str, 
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a task."""
        task = self._tasks.get(task_id)
        if not task:
            return {"status": "error", "message": f"Task not found: {task_id}"}
        
        # Handle special fields
        if 'progress' in updates:
            task.update_progress(updates.pop('progress'))
        
        # Update other fields
        task.update(updates)
        
        # Notify about the update
        await message_bus.publish("task.updated", task.to_dict())
        
        return {"status": "success", "task": task.to_dict()}
    
    async def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Delete a task."""
        if task_id not in self._tasks:
            return {"status": "error", "message": f"Task not found: {task_id}"}
        
        task = self._tasks[task_id]
        
        # Clean up dependencies
        for dep_id in task.dependencies:
            if dep_id in self._tasks:
                self._tasks[dep_id].remove_dependent(task_id)
        
        for dep_id in task.dependents:
            if dep_id in self._tasks:
                self._tasks[dep_id].remove_dependency(task_id)
        
        # Remove the task
        del self._tasks[task_id]
        if task_id in self._comments:
            del self._comments[task_id]
        
        # Notify about the deletion
        await message_bus.publish("task.deleted", {"task_id": task_id})
        
        return {"status": "success"}
    
    async def list_tasks(
        self,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        creator: Optional[str] = None,
        priority: Optional[str] = None,
        tag: Optional[str] = None,
        include_completed: bool = False
    ) -> List[Dict[str, Any]]:
        """List tasks matching the given filters."""
        tasks = []
        
        for task in self._tasks.values():
            if not include_completed and task.status == TaskStatus.COMPLETED:
                continue
                
            if status and task.status != status:
                continue
                
            if assignee and task.assignee != assignee:
                continue
                
            if creator and task.creator != creator:
                continue
                
            if priority and task.priority != priority:
                continue
                
            if tag and tag not in task.tags:
                continue
                
            tasks.append(task.to_dict())
        
        return tasks
    
    async def start_task(self, task_id: str) -> Dict[str, Any]:
        """Mark a task as in progress."""
        task = self._tasks.get(task_id)
        if not task:
            return {"status": "error", "message": f"Task not found: {task_id}"}
        
        if task.start():
            await message_bus.publish("task.started", task.to_dict())
            return {"status": "success", "task": task.to_dict()}
        else:
            return {"status": "error", "message": f"Cannot start task in {task.status} state"}
    
    async def complete_task(self, task_id: str) -> Dict[str, Any]:
        """Mark a task as completed."""
        task = self._tasks.get(task_id)
        if not task:
            return {"status": "error", "message": f"Task not found: {task_id}"}
        
        if task.complete():
            await message_bus.publish("task.completed", task.to_dict())
            return {"status": "success", "task": task.to_dict()}
        else:
            return {"status": "error", "message": f"Cannot complete task in {task.status} state"}
    
    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a task."""
        task = self._tasks.get(task_id)
        if not task:
            return {"status": "error", "message": f"Task not found: {task_id}"}
        
        if task.cancel():
            await message_bus.publish("task.cancelled", task.to_dict())
            return {"status": "success", "task": task.to_dict()}
        else:
            return {"status": "error", "message": f"Cannot cancel task in {task.status} state"}
    
    async def fail_task(self, task_id: str, reason: str = "") -> Dict[str, Any]:
        """Mark a task as failed."""
        task = self._tasks.get(task_id)
        if not task:
            return {"status": "error", "message": f"Task not found: {task_id}"}
        
        if task.fail():
            if reason:
                task.metadata['failure_reason'] = reason
                
            await message_bus.publish("task.failed", {
                **task.to_dict(),
                "reason": reason
            })
            return {"status": "success", "task": task.to_dict()}
        else:
            return {"status": "error", "message": f"Cannot fail task in {task.status} state"}
    
    async def add_dependency(self, task_id: str, depends_on: str) -> Dict[str, Any]:
        """Add a dependency between tasks."""
        task = self._tasks.get(task_id)
        dependency = self._tasks.get(depends_on)
        
        if not task or not dependency:
            return {"status": "error", "message": "Task or dependency not found"}
        
        if task_id == depends_on:
            return {"status": "error", "message": "A task cannot depend on itself"}
        
        if task.add_dependency(depends_on) and dependency.add_dependent(task_id):
            await message_bus.publish("task.dependency_added", {
                "task_id": task_id,
                "depends_on": depends_on
            })
            return {"status": "success"}
        else:
            return {"status": "error", "message": "Dependency already exists"}
    
    async def remove_dependency(self, task_id: str, depends_on: str) -> Dict[str, Any]:
        """Remove a dependency between tasks."""
        task = self._tasks.get(task_id)
        dependency = self._tasks.get(depends_on)
        
        if not task or not dependency:
            return {"status": "error", "message": "Task or dependency not found"}
        
        if task.remove_dependency(depends_on) and dependency.remove_dependent(task_id):
            await message_bus.publish("task.dependency_removed", {
                "task_id": task_id,
                "depends_on": depends_on
            })
            return {"status": "success"}
        else:
            return {"status": "error", "message": "Dependency does not exist"}
    
    async def add_comment(
        self, 
        task_id: str, 
        author: str, 
        comment: str
    ) -> Dict[str, Any]:
        """Add a comment to a task."""
        if task_id not in self._tasks:
            return {"status": "error", "message": f"Task not found: {task_id}"}
        
        comment_id = f"comment_{uuid.uuid4().hex[:8]}"
        comment_data = {
            "id": comment_id,
            "task_id": task_id,
            "author": author,
            "comment": comment,
            "created_at": datetime.utcnow().isoformat()
        }
        
        if task_id not in self._comments:
            self._comments[task_id] = []
        
        self._comments[task_id].append(comment_data)
        
        # Notify about the new comment
        await message_bus.publish("task.comment_added", comment_data)
        
        return {"status": "success", "comment_id": comment_id}
    
    async def get_comments(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all comments for a task."""
        return self._comments.get(task_id, []).copy()
    
    async def process(self, message: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process task-related messages."""
        action = message.get('action')
        task_id = message.get('task_id')
        
        try:
            if action == 'create':
                return await self.create_task(
                    title=message['title'],
                    description=message.get('description', ''),
                    priority=message.get('priority', TaskPriority.MEDIUM),
                    due_date=message.get('due_date'),
                    assignee=message.get('assignee'),
                    creator=message.get('creator'),
                    tags=message.get('tags'),
                    metadata=message.get('metadata')
                )
            elif action == 'get' and task_id:
                task = await self.get_task(task_id)
                return {"status": "success" if task else "error", "task": task}
            elif action == 'update' and task_id:
                updates = {k: v for k, v in message.items() 
                         if k not in ('action', 'task_id')}
                return await self.update_task(task_id, updates)
            elif action == 'delete' and task_id:
                return await self.delete_task(task_id)
            elif action == 'list':
                return {
                    "status": "success",
                    "tasks": await self.list_tasks(
                        status=message.get('status'),
                        assignee=message.get('assignee'),
                        creator=message.get('creator'),
                        priority=message.get('priority'),
                        tag=message.get('tag'),
                        include_completed=message.get('include_completed', False)
                    )
                }
            elif action == 'start' and task_id:
                return await self.start_task(task_id)
            elif action == 'complete' and task_id:
                return await self.complete_task(task_id)
            elif action == 'cancel' and task_id:
                return await self.cancel_task(task_id)
            elif action == 'fail' and task_id:
                return await self.fail_task(task_id, message.get('reason', ''))
            elif action == 'add_dependency' and task_id and 'depends_on' in message:
                return await self.add_dependency(task_id, message['depends_on'])
            elif action == 'remove_dependency' and task_id and 'depends_on' in message:
                return await self.remove_dependency(task_id, message['depends_on'])
            elif action == 'add_comment' and task_id and 'comment' in message:
                return await self.add_comment(
                    task_id=task_id,
                    author=message.get('author', 'system'),
                    comment=message['comment']
                )
            elif action == 'get_comments' and task_id:
                return {
                    "status": "success",
                    "comments": await self.get_comments(task_id)
                }
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown action or missing parameters: {action}'
                }
        except Exception as e:
            logger.error(f"Error in TaskAgent: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

# Register the agent
task_agent = TaskAgent()
agent_registry.register(task_agent)
