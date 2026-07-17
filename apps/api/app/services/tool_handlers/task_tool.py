import uuid
from datetime import datetime
from app.services.task_service import TaskService
from app.schemas.task import TaskCreateRequest
from app.models.enums import TaskPriority, TaskType


class TaskTool:
    """Tool handler managing CRM Task operations."""

    async def execute(self, db, ctx, arguments: dict) -> dict:
        action = arguments.get("action", "create_task")
        service = TaskService(db)

        if action == "create_task":
            task_data = arguments.get("task_data", {})
            
            # Map lead_id
            lead_id_str = task_data.get("lead_id")
            if not lead_id_str:
                raise ValueError("lead_id is required for create_task action.")
            
            due_at_str = task_data.get("due_at")
            due_at = None
            if due_at_str:
                try:
                    due_at = datetime.fromisoformat(due_at_str.replace("Z", "+00:00"))
                except ValueError:
                    due_at = None

            # Map priority
            priority_val = task_data.get("priority", "MEDIUM")
            try:
                priority = TaskPriority[priority_val]
            except KeyError:
                priority = TaskPriority.MEDIUM

            # Map type
            type_val = task_data.get("type", "CUSTOM")
            try:
                task_type = TaskType[type_val]
            except KeyError:
                task_type = TaskType.CUSTOM

            # Determine assignee (default to current user or a generated uuid)
            assigned_to = None
            if ctx.user:
                assigned_to = ctx.user.id
            else:
                assigned_to_str = task_data.get("assigned_to")
                assigned_to = uuid.UUID(assigned_to_str) if assigned_to_str else uuid.uuid4()

            payload = TaskCreateRequest(
                lead_id=uuid.UUID(str(lead_id_str)),
                assigned_to=assigned_to,
                title=task_data.get("title", "Follow-up Task"),
                description=task_data.get("description", ""),
                priority=priority,
                type=task_type,
                due_at=due_at
            )

            task = await service.create_task(ctx, payload)
            return {
                "id": str(task.id),
                "title": task.title,
                "status": task.status.value if hasattr(task.status, 'value') else task.status,
                "due_at": task.due_at.isoformat() if task.due_at else None
            }
        else:
            raise ValueError(f"Unsupported task action: {action}")
