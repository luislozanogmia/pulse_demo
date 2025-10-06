from fastapi import APIRouter
import json
import os

router = APIRouter()

MEMORY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "core", "core_memory.json"
)


@router.get("/memory/get")
def get_memory():
    if not os.path.exists(MEMORY_PATH):
        return {"memory": []}
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            memory = json.load(f)
        return {"memory": memory}
    except Exception:
        return {"memory": []}
