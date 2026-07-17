import uuid
import asyncio
from typing import Optional, Any
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_agent_task import AIAgentTask
from app.models.enums import AgentTaskStatus, BackoffPolicy


class ExecutionScheduler:
    @classmethod
    async def schedule_task(
        cls,
        db: AsyncSession,
        task: AIAgentTask
    ) -> None:
        """Sets status to READY so execution loop can process it."""
        task.status = AgentTaskStatus.READY
        await db.flush()

    @classmethod
    async def execute_task_with_retry(
        cls,
        db: AsyncSession,
        task: AIAgentTask,
        run_func: Any,
        backoff_policy: BackoffPolicy = BackoffPolicy.NONE,
        max_retries: int = 3
    ) -> dict[str, Any]:
        """Runs the task function, executing backoffs and increments attempts on failure."""
        task.status = AgentTaskStatus.RUNNING
        await db.flush()

        attempts = 0
        while attempts < max_retries:
            try:
                # Run the actual work function
                result = await run_func(db, task)
                task.status = AgentTaskStatus.COMPLETED
                task.result_json = result
                await db.flush()
                return {"status": "success", "result": result}
            except Exception as e:
                attempts += 1
                if attempts >= max_retries:
                    task.status = AgentTaskStatus.FAILED
                    task.result_json = {"error": str(e), "attempts": attempts}
                    await db.flush()
                    return {"status": "failed", "error": str(e)}

                # Calculate backoff delay
                delay = 0
                if backoff_policy == BackoffPolicy.FIXED:
                    delay = 2
                elif backoff_policy == BackoffPolicy.EXPONENTIAL:
                    delay = 2 ** attempts

                if delay > 0:
                    await asyncio.sleep(delay)
        
        return {"status": "failed", "error": "Max retries exceeded."}

    @classmethod
    async def run_parallel_tasks(
        cls,
        db: AsyncSession,
        tasks: list[AIAgentTask],
        run_func: Any
    ) -> list[dict[str, Any]]:
        """Runs a list of tasks in parallel using asyncio.gather."""
        # Update statuses to RUNNING
        for t in tasks:
            t.status = AgentTaskStatus.RUNNING
        await db.flush()

        async def run_one(t: AIAgentTask):
            try:
                res = await run_func(db, t)
                t.status = AgentTaskStatus.COMPLETED
                t.result_json = res
                return {"task_id": t.id, "status": "success", "result": res}
            except Exception as e:
                t.status = AgentTaskStatus.FAILED
                t.result_json = {"error": str(e)}
                return {"task_id": t.id, "status": "failed", "error": str(e)}

        coros = [run_one(t) for t in tasks]
        results = await asyncio.gather(*coros)
        await db.flush()
        return results
