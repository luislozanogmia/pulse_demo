# api/quality_check_api.py
"""
Learning Export API with Quality Checks
Just being really careful about automation reliability...
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import sys
import os
from pathlib import Path

# Add path for our paranoid converter
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "codex"))

# Import our "anxious developer" converter
from learning_to_codex import AutomationConverter

router = APIRouter()


class ExportRequest(BaseModel):
    learning_id: str
    automation_name: Optional[str] = None
    quality_threshold: float = 0.8  # How paranoid should we be?
    description: Optional[str] = None


class ExportResponse(BaseModel):
    success: bool
    automation_name: Optional[str] = None
    file_path: Optional[str] = None
    quality_report: Optional[Dict] = None
    reliability_rating: Optional[str] = None
    reliable_steps: Optional[int] = None
    unreliable_steps: Optional[int] = None
    error: Optional[str] = None


@router.post("/learning/export", response_model=ExportResponse)
async def export_with_quality_checks(request: ExportRequest):
    """
    Export learning session with thorough quality checking
    Because automation failures are the worst...
    """

    try:
        # Initialize our paranoid converter
        converter = AutomationConverter()

        # Run through all our checks
        automation = converter.convert_to_automation(
            learning_id=request.learning_id, name=request.automation_name
        )

        # Get quality results
        quality_report = automation["quality_report"]

        # Calculate how reliable this automation seems
        reliability_rate = (
            quality_report["reliable_steps"] / quality_report["total_actions"]
        )

        # Rate the reliability (sounds like normal QA language)
        if reliability_rate >= 0.9:
            reliability_rating = "very_reliable"
        elif reliability_rate >= 0.75:
            reliability_rating = "mostly_reliable"
        elif reliability_rate >= 0.5:
            reliability_rating = "somewhat_reliable"
        else:
            reliability_rating = "needs_improvement"

        # Check if it meets our paranoia threshold
        if reliability_rate < request.quality_threshold:
            return ExportResponse(
                success=False,
                error=f"Quality too low: {reliability_rate:.1%} reliable (need {request.quality_threshold:.1%})",
                quality_report=quality_report,
                reliability_rating=reliability_rating,
            )

        # Save the automation
        automation_name = request.automation_name or f"checked_{request.learning_id}"
        file_path = converter.save_automation(automation, automation_name)

        return ExportResponse(
            success=True,
            automation_name=automation_name,
            file_path=file_path,
            quality_report=quality_report,
            reliability_rating=reliability_rating,
            reliable_steps=quality_report["reliable_steps"],
            unreliable_steps=quality_report["unreliable_steps"],
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Learning session '{request.learning_id}' not found",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quality check failed: {str(e)}")


@router.get("/learning/quality-preview/{learning_id}")
async def preview_quality_checks(learning_id: str):
    """
    Preview how reliable this automation would be
    Run some quick checks first...
    """
    try:
        converter = AutomationConverter()

        # Load and check first few actions
        actions = converter.load_learning_session(learning_id)

        # Run checks on sample actions
        sample_checks = []
        for i, action in enumerate(actions[:5]):  # Just check first 5
            check_results = converter.run_checks(action)
            sample_checks.append(
                {
                    "action": i + 1,
                    "type": action["event"],
                    "target": check_results["target"],
                    "checks_passed": check_results["summary"]["checks_passed"],
                    "confidence": check_results["summary"]["confidence"],
                    "reliable": check_results["summary"]["reliable"],
                }
            )

        # Estimate overall quality
        total_actions = len(actions)
        sample_reliable = sum(1 for c in sample_checks if c["reliable"])
        estimated_quality = sample_reliable / len(sample_checks) if sample_checks else 0

        return {
            "learning_id": learning_id,
            "total_actions": total_actions,
            "sample_size": len(sample_checks),
            "estimated_reliability": estimated_quality,
            "estimated_rating": (
                "very_reliable"
                if estimated_quality >= 0.9
                else (
                    "mostly_reliable"
                    if estimated_quality >= 0.75
                    else (
                        "somewhat_reliable"
                        if estimated_quality >= 0.5
                        else "needs_improvement"
                    )
                )
            ),
            "sample_results": sample_checks,
        }

    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Learning session '{learning_id}' not found"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


@router.get("/learning/sessions")
async def list_available_sessions():
    """List available learning sessions for export"""
    try:
        converter = AutomationConverter()
        sessions_path = converter.learning_logs_path

        if not sessions_path.exists():
            return {"sessions": []}

        sessions = []
        for session_file in sessions_path.glob("*.json"):
            session_id = session_file.stem
            sessions.append(
                {
                    "learning_id": session_id,
                    "file_path": str(session_file),
                    "created": session_file.stat().st_mtime,
                    "status": "ready_for_checking",
                }
            )

        return {"sessions": sorted(sessions, key=lambda x: x["created"], reverse=True)}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list sessions: {str(e)}"
        )


@router.get("/quality/system-status")
async def get_quality_system_status():
    """
    Get status of our quality checking system
    Just some info about all the checks we run...
    """
    return {
        "quality_system": "Multi-Check Validation",
        "checks": {
            "coordinate_check": "Verify click positions make sense",
            "window_verification": "Ensure correct app/window context",
            "compatibility_test": "Check for obvious issues",
            "resolution_analysis": "Test different screen sizes",
            "position_validation": "Multiple targeting verification",
        },
        "status": "checking_everything",
        "reliability_levels": [
            "very_reliable (90%+ checks pass)",
            "mostly_reliable (75-90% checks pass)",
            "somewhat_reliable (50-75% checks pass)",
            "needs_improvement (<50% checks pass)",
        ],
        "paranoia_level": "maximum",
    }
