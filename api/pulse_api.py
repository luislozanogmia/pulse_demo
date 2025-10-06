from fastapi import APIRouter
from core.pulse import run_pulse

router = APIRouter()


@router.post("/pulse/run")
def trigger_pulse():
    run_pulse()
    return {"status": "pulse triggered"}
