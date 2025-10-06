from fastapi import APIRouter
import json
import os

router = APIRouter()

TREASURE_MAP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "treasure_map_combined.json",
)


@router.get("/vision/treasure")
def get_treasure_map():
    if not os.path.exists(TREASURE_MAP_PATH):
        return {"error": "treasure map not found"}
    try:
        with open(TREASURE_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return {"error": "treasure map not found"}
