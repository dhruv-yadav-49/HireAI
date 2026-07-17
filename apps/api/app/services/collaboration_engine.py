import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai_agent_session import AIAgentSession
from app.models.ai_agent_task import AIAgentTask
from app.models.enums import AgentTaskStatus
from app.services.execution_scheduler import ExecutionScheduler


class CollaborationEngine:
    @classmethod
    async def execute_sequential_graph(
        cls,
        db: AsyncSession,
        session_id: uuid.UUID,
        tasks: list[AIAgentTask],
        run_func: Any
    ) -> list[dict[str, Any]]:
        """Executes tasks in sequential order."""
        results = []
        for task in tasks:
            res = await ExecutionScheduler.execute_task_with_retry(
                db, task, run_func
            )
            results.append(res)
        return results

    @classmethod
    async def execute_parallel_graph(
        cls,
        db: AsyncSession,
        session_id: uuid.UUID,
        tasks: list[AIAgentTask],
        run_func: Any
    ) -> list[dict[str, Any]]:
        """Executes tasks in parallel and aggregates the results."""
        return await ExecutionScheduler.run_parallel_tasks(
            db, tasks, run_func
        )
