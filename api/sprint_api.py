from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import threading

from action.task_now import get_task_for_now
from action.sprint_agent import ping_pong_loop

router = APIRouter()


class RunSprintRequest(BaseModel):
    pass  # No task name needed — uses current calendar task


@router.get("/sprint/status")
def sprint_status():
    try:
        task = get_task_for_now()
        if not task:
            raise HTTPException(status_code=404, detail="No calendar task matched")
        return {
            "status": "task loaded",
            "task": task.get("task", "unknown"),
            "context": task.get("context", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sprint/run")
def run_sprint(_: RunSprintRequest):
    try:
        task = get_task_for_now()
        if not task:
            raise HTTPException(status_code=404, detail="No calendar task matched")
        thread = threading.Thread(target=ping_pong_loop, args=(task,))
        thread.start()
        return {"status": "sprint started", "task": task.get("task", "unknown")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
