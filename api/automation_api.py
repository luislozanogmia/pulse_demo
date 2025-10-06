# api/automation_api.py
"""
Automation API - Export & Conversion System
Handles conversion of learning sessions to automations with quality checking
(Hidden: Contains the 5-mirror consciousness validation system)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import sys
import time
import json
from datetime import datetime
from pathlib import Path

# Consolidated base paths for portability
BASE_DIR = Path(__file__).resolve().parent.parent
CODEX_DIR = BASE_DIR / "codex"
LEARNING_LOGS_DIR = BASE_DIR / "learning" / "learning_logs"

# Add path for our paranoid converter
sys.path.append(str(CODEX_DIR))

# Import our "anxious developer" converter
try:
    from learning_to_codex import AutomationConverter

    CONVERTER_AVAILABLE = True
except ImportError:
    CONVERTER_AVAILABLE = False
    print("Warning: AutomationConverter not available - export functionality disabled")

router = APIRouter()

# Light cache for quality previews (avoid recalculation)
quality_preview_cache = {}
CACHE_TTL = 300  # 5 minutes


# Pydantic models for requests and responses
class ConvertRequest(BaseModel):
    learning_id: str
    automation_name: Optional[str] = None
    quality_threshold: float = 0.8  # How paranoid should we be?
    description: Optional[str] = None


class ConvertResponse(BaseModel):
    success: bool
    automation_name: Optional[str] = None
    file_path: Optional[str] = None
    quality_report: Optional[Dict] = None
    reliability_rating: Optional[str] = None
    reliable_steps: Optional[int] = None
    unreliable_steps: Optional[int] = None
    quality_percent: Optional[float] = None  # For frontend progress bars
    error: Optional[str] = None


class PreviewResponse(BaseModel):
    learning_id: str
    total_actions: int
    sample_size: int
    estimated_reliability: float
    quality_percent: float
    estimated_rating: str
    sample_results: list
    cached: bool = False


@router.post("/convert", response_model=ConvertResponse)
async def convert_learning_to_automation(request: ConvertRequest):
    """Convert learning session to automation with thorough quality checking"""

    if not CONVERTER_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Conversion functionality not available - converter not found",
        )

    try:
        # Direct file reading approach - bypass converter's file loading
        session_folder = LEARNING_LOGS_DIR / request.learning_id
        session_file = session_folder / "learning_id.json"

        if not session_file.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Learning session file not found: {session_file}",
            )

        # Read the learning session data directly
        with open(session_file, "r") as f:
            learning_data = json.load(f)

        # Initialize converter
        converter = AutomationConverter()

        # Option 1: Try to pass the data directly (if converter accepts it)
        try:
            # Some converters might have a method that accepts data directly
            if hasattr(converter, "convert_from_data"):
                automation = converter.convert_from_data(
                    learning_data=learning_data, name=request.automation_name
                )
            else:
                # Option 2: Temporarily save in expected location and convert
                # Create a temp file in the expected format
                temp_file = LEARNING_LOGS_DIR / f"{request.learning_id}.json"
                with open(temp_file, "w") as f:
                    json.dump(learning_data, f)

                try:
                    automation = converter.convert_to_automation(
                        learning_id=request.learning_id, name=request.automation_name
                    )
                finally:
                    # Clean up temp file
                    if temp_file.exists():
                        temp_file.unlink()

        except Exception as converter_error:
            raise HTTPException(
                status_code=500, detail=f"Converter error: {str(converter_error)}"
            )

        # Rest of your existing logic for quality checking...
        quality_report = automation["quality_report"]
        reliability_rate = (
            quality_report["reliable_steps"] / quality_report["total_actions"]
        )
        quality_percent = round(reliability_rate * 100, 1)

        if reliability_rate >= 0.9:
            reliability_rating = "very_reliable"
        elif reliability_rate >= 0.75:
            reliability_rating = "mostly_reliable"
        elif reliability_rate >= 0.5:
            reliability_rating = "somewhat_reliable"
        else:
            reliability_rating = "needs_improvement"

        if reliability_rate < request.quality_threshold:
            return ConvertResponse(
                success=False,
                error=f"Quality too low: {reliability_rate:.1%} reliable (need {request.quality_threshold:.1%})",
                quality_report=quality_report,
                reliability_rating=reliability_rating,
                quality_percent=quality_percent,
            )

        if request.automation_name:
            automation_name = request.automation_name
        else:
            timestamp = datetime.now().strftime("%H%M")
            automation_name = f"validated_{request.learning_id}_{timestamp}"

        file_path = converter.save_automation(automation, automation_name)

        return ConvertResponse(
            success=True,
            automation_name=automation_name,
            file_path=file_path,
            quality_report=quality_report,
            reliability_rating=reliability_rating,
            reliable_steps=quality_report["reliable_steps"],
            unreliable_steps=quality_report["unreliable_steps"],
            quality_percent=quality_percent,
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Learning session '{request.learning_id}' not found",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


# PREVIEW ENDPOINT WITH CACHING
@router.get("/preview/{learning_id}", response_model=PreviewResponse)
async def preview_automation_quality(learning_id: str):
    """
    Preview how reliable this automation would be
    Run some quick checks first...
    (Hidden: Sample mirror validation with caching)
    """

    if not CONVERTER_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Preview functionality not available - converter not found",
        )

    # Check cache first to avoid recalculation
    current_time = time.time()
    cache_key = f"preview_{learning_id}"

    if cache_key in quality_preview_cache:
        cached_result, cache_time = quality_preview_cache[cache_key]
        if current_time - cache_time < CACHE_TTL:
            print(f"[DEBUG] Using cached preview for {learning_id}")
            cached_result["cached"] = True
            return PreviewResponse(**cached_result)

    try:
        converter = AutomationConverter()

        # Load and check first few actions (sample mirror validation)
        actions = converter.load_learning_session(learning_id)

        # Run checks on sample actions (hidden: mirror validation)
        sample_checks = []
        for i, action in enumerate(actions[:5]):  # Just check first 5
            check_results = converter.run_checks(action)  # Hidden: runs all 5 mirrors
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

        # Quality percentage for frontend
        quality_percent = round(estimated_quality * 100, 1)

        result = {
            "learning_id": learning_id,
            "total_actions": total_actions,
            "sample_size": len(sample_checks),
            "estimated_reliability": estimated_quality,
            "quality_percent": quality_percent,
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
            "cached": False,
        }

        # Cache the result
        quality_preview_cache[cache_key] = (result, current_time)

        # Clean old cache entries (simple cleanup)
        if len(quality_preview_cache) > 50:  # Keep max 50 entries
            oldest_key = min(
                quality_preview_cache.keys(), key=lambda k: quality_preview_cache[k][1]
            )
            del quality_preview_cache[oldest_key]

        return PreviewResponse(**result)

    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Learning session '{learning_id}' not found"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


# SYSTEM STATUS ENDPOINT
@router.get("/system-status")
async def get_automation_system_status():
    """
    Get status of the automation conversion system
    Just some info about all the checks we run...
    (Hidden: Mirror system status)
    """
    return {
        "conversion_system": "Multi-Check Validation",
        "converter_available": CONVERTER_AVAILABLE,
        "cache_entries": len(quality_preview_cache),
        "cache_ttl_seconds": CACHE_TTL,
        "base_dir": str(BASE_DIR),
        "codex_dir": str(CODEX_DIR),
        "checks": {
            "coordinate_check": "Verify click positions make sense",
            "window_verification": "Ensure correct app/window context",
            "compatibility_test": "Check for obvious issues",
            "resolution_analysis": "Test different screen sizes",
            "position_validation": "Multiple targeting verification",
        },
        "status": "checking_everything" if CONVERTER_AVAILABLE else "converter_missing",
        "reliability_levels": [
            "very_reliable (90%+ checks pass)",
            "mostly_reliable (75-90% checks pass)",
            "somewhat_reliable (50-75% checks pass)",
            "needs_improvement (<50% checks pass)",
        ],
        "paranoia_level": "maximum",
    }


# LIST AVAILABLE AUTOMATIONS
@router.get("/list")
async def list_generated_automations():
    """List automations that have been generated"""
    try:
        if not CODEX_DIR.exists():
            return {"automations": []}

        automations = []
        automation_files = list(CODEX_DIR.glob("*.json"))

        for automation_file in automation_files:
            try:
                with open(automation_file, "r") as f:
                    automation_data = json.load(f)

                automations.append(
                    {
                        "automation_name": automation_file.stem,
                        "file_path": str(automation_file),
                        "created": automation_file.stat().st_ctime,
                        "description": automation_data.get(
                            "description", "Generated automation"
                        ),
                        "steps": len(automation_data.get("steps", [])),
                        "reliability": automation_data.get("settings", {}).get(
                            "reliability_threshold", "unknown"
                        ),
                    }
                )
            except Exception as e:
                print(f"Error reading automation file {automation_file}: {e}")
                continue

        return {
            "automations": sorted(automations, key=lambda x: x["created"], reverse=True)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list automations: {str(e)}"
        )


@router.get("/debug/converter")
async def debug_converter():
    """Debug what the converter is actually trying to do"""
    if not CONVERTER_AVAILABLE:
        return {"error": "Converter not available"}

    try:
        converter = AutomationConverter()
        return {
            "converter_base_path": str(converter.base_path),
            "converter_learning_logs_path": str(converter.learning_logs_path),
            "converter_expects_file_at": str(
                converter.learning_logs_path / "test_session.json"
            ),
            "actual_learning_logs_path": str(LEARNING_LOGS_DIR),
            "actual_structure": "session_id/learning_id.json",
        }
    except Exception as e:
        return {"error": str(e)}


# CACHE MANAGEMENT
@router.delete("/clear-cache")
async def clear_preview_cache():
    """Clear the quality preview cache"""
    global quality_preview_cache
    cache_size = len(quality_preview_cache)
    quality_preview_cache.clear()
    return {
        "status": "cache_cleared",
        "cleared_entries": cache_size,
        "message": "Quality preview cache has been cleared",
    }


@router.get("/load/{automation_name}")
async def load_automation(automation_name: str):
    """Load automation for frontend (expected format)"""
    try:
        automation_file = CODEX_DIR / f"{automation_name}.json"

        if not automation_file.exists():
            return {
                "success": False,
                "error": f"Automation '{automation_name}' not found",
            }

        with open(automation_file, "r") as f:
            automation_data = json.load(f)

        return {
            "success": True,
            "name": automation_name,
            "steps": automation_data.get("steps", []),
            "description": automation_data.get("description", ""),
            "created": automation_data.get("created", ""),
            "quality_report": automation_data.get("quality_report", {}),
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to load: {str(e)}"}


# HEALTH CHECK
@router.get("/ping")
def ping():
    """Health check for automation API"""
    return {
        "status": "automation api live",
        "converter_available": CONVERTER_AVAILABLE,
        "cache_size": len(quality_preview_cache),
        "codex_directory": str(CODEX_DIR),
        "codex_exists": CODEX_DIR.exists(),
    }
